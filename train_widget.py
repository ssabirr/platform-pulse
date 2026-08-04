"""
Upper West Side Train Widget
A frameless, always-on-top desktop widget with live-animated countdowns
for the B/C/D at Cathedral Pkwy (110 St) and the 1 at 103 St.

Reuses the data engine from train_board.py (same stop IDs, same MTA feeds).
"""

import sys
from datetime import datetime

import train_board as tb
from PySide6.QtCore import Qt, QTimer, QThread, Signal, Property, QPropertyAnimation, QEasingCurve, QPointF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QRegion
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
)

DATA_REFRESH_MS = 30_000
TICK_MS = 1_000
PROGRESS_WINDOW_MINUTES = 20
GLOW_THRESHOLD_MINUTES = 2


class FeedWorker(QThread):
    """Fetches live MTA data on its own thread so the UI never blocks/stutters."""
    dataReady = Signal(dict)

    def __init__(self):
        super().__init__()
        self._feeds = None
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        self._feeds = tb.load_feeds()
        alerted = set()
        while self._running:
            snapshot = {}
            for station in tb.STATIONS:
                arrivals = tb.get_arrivals(self._feeds, station, alerted, [False])
                snapshot[station["name"]] = [
                    (route_id, direction, datetime.now(), minutes, headsign)
                    for route_id, direction, minutes, headsign in arrivals[:4]
                ]
            self.dataReady.emit(snapshot)
            for _ in range(DATA_REFRESH_MS // 200):
                if not self._running:
                    return
                self.msleep(200)
            tb.refresh_feeds(self._feeds)


class ProgressBar(QWidget):
    """Thin animated bar that fills as a train's arrival approaches."""

    def __init__(self, color):
        super().__init__()
        self._fraction = 0.0
        self._color = QColor(color)
        self.setFixedHeight(4)
        self._anim = QPropertyAnimation(self, b"fraction")
        self._anim.setDuration(900)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

    def get_fraction(self):
        return self._fraction

    def set_fraction(self, value):
        self._fraction = max(0.0, min(1.0, value))
        self.update()

    fraction = Property(float, get_fraction, set_fraction)

    def animate_to(self, target):
        self._anim.stop()
        self._anim.setStartValue(self._fraction)
        self._anim.setEndValue(max(0.0, min(1.0, target)))
        self._anim.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 30))
        painter.drawRoundedRect(self.rect(), 2, 2)
        w = int(self.width() * self._fraction)
        if w > 0:
            painter.setBrush(self._color)
            painter.drawRoundedRect(0, 0, w, self.height(), 2, 2)


class TrainRow(QWidget):
    def __init__(self, route_id, direction, headsign):
        super().__init__()
        self.route_id = route_id
        self._glowing = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 4, 0, 4)
        outer.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(8)

        color = tb.ROUTE_COLORS.get(route_id, "#888888")
        self.bullet = QLabel(route_id)
        self.bullet.setFixedSize(26, 26)
        self.bullet.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bullet.setStyleSheet(
            f"background-color: {color}; color: white; border-radius: 13px; font-weight: bold;"
        )
        self.glow = QGraphicsDropShadowEffect()
        self.glow.setColor(QColor(color))
        self.glow.setOffset(0, 0)
        self.glow.setBlurRadius(4)
        self.bullet.setGraphicsEffect(self.glow)
        self.glow_anim = QPropertyAnimation(self.glow, b"blurRadius")
        self.glow_anim.setDuration(700)
        self.glow_anim.setStartValue(4)
        self.glow_anim.setEndValue(28)
        self.glow_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.glow_anim.setLoopCount(-1)

        direction_label = tb.DIRECTION_LABELS.get(direction, direction)
        self.dest_label = QLabel(f"{direction_label} - {headsign}")
        self.dest_label.setStyleSheet("color: #e8e8e8; font-size: 12px;")
        self.dest_label.setWordWrap(False)

        self.countdown_label = QLabel("...")
        self.countdown_label.setStyleSheet("color: #7CFC98; font-weight: bold; font-size: 13px;")
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.countdown_label.setFixedWidth(52)

        top.addWidget(self.bullet)
        top.addWidget(self.dest_label, 1)
        top.addWidget(self.countdown_label)
        outer.addLayout(top)

        self.bar = ProgressBar(color)
        outer.addWidget(self.bar)

        self.opacity = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.opacity)
        self.fade_in = QPropertyAnimation(self.opacity, b"opacity")
        self.fade_in.setDuration(400)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.start()

    def update_countdown(self, arrival_minutes_at_fetch, fetched_at):
        elapsed = (datetime.now() - fetched_at).total_seconds() / 60
        minutes = arrival_minutes_at_fetch - elapsed

        if minutes <= 0:
            text, style = "now", "color: #FF5C5C; font-weight: bold; font-size: 13px;"
        elif minutes < 1:
            text, style = "<1 min", "color: #FF5C5C; font-weight: bold; font-size: 13px;"
        elif minutes <= GLOW_THRESHOLD_MINUTES:
            text, style = f"{int(minutes)} min", "color: #FF8A65; font-weight: bold; font-size: 13px;"
        elif minutes <= 5:
            text, style = f"{int(minutes)} min", "color: #FFD54F; font-weight: bold; font-size: 13px;"
        else:
            text, style = f"{int(minutes)} min", "color: #7CFC98; font-weight: bold; font-size: 13px;"

        self.countdown_label.setText(text)
        self.countdown_label.setStyleSheet(style)
        self.bar.animate_to(1 - (minutes / PROGRESS_WINDOW_MINUTES))

        should_glow = minutes <= GLOW_THRESHOLD_MINUTES
        if should_glow and not self._glowing:
            self._glowing = True
            self.glow_anim.start()
        elif not should_glow and self._glowing:
            self._glowing = False
            self.glow_anim.stop()
            self.glow.setBlurRadius(4)

        return minutes


class StationCard(QWidget):
    def __init__(self, name):
        super().__init__()
        self.name = name
        self.rows = []
        self._data = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)

        title = QLabel(name)
        title.setStyleSheet("color: white; font-size: 13px; font-weight: bold;")
        layout.addWidget(title)

        self.rows_container = QVBoxLayout()
        self.rows_container.setSpacing(0)
        layout.addLayout(self.rows_container)

    def set_data(self, entries):
        self._data = entries
        for row in self.rows:
            row.setParent(None)
            row.deleteLater()
        self.rows = []
        if not entries:
            empty = QLabel("No live trains reported right now.")
            empty.setStyleSheet("color: #999; font-size: 11px; font-style: italic; padding: 6px 0;")
            self.rows_container.addWidget(empty)
            self.rows.append(empty)
            return
        for route_id, direction, fetched_at, minutes, headsign in entries:
            row = TrainRow(route_id, direction, headsign)
            row.update_countdown(minutes, fetched_at)
            self.rows_container.addWidget(row)
            self.rows.append(row)

    def tick(self):
        for row, (route_id, direction, fetched_at, minutes, headsign) in zip(self.rows, self._data):
            if isinstance(row, TrainRow):
                row.update_countdown(minutes, fetched_at)


class RoundedCard(QWidget):
    def __init__(self):
        super().__init__()
        self.setAutoFillBackground(True)
        self.setStyleSheet("background-color: rgb(24, 26, 32); border-radius: 16px;")


class TrainWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedWidth(320)
        self._drag_offset = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.card_frame = RoundedCard()
        self.card_frame.setObjectName("card")
        outer.addWidget(self.card_frame)

        card_layout = QVBoxLayout(self.card_frame)
        card_layout.setContentsMargins(0, 0, 0, 12)
        card_layout.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(14, 10, 8, 6)
        header_label = QLabel("UWS TRAINS")
        header_label.setStyleSheet("color: #888; font-size: 10px; letter-spacing: 2px; font-weight: bold;")
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(22, 22)
        close_btn.setStyleSheet(
            "QPushButton { color: #999; background: transparent; border: none; font-size: 12px; }"
            "QPushButton:hover { color: white; }"
        )
        close_btn.clicked.connect(self.close)
        header.addWidget(header_label)
        header.addStretch()
        header.addWidget(close_btn)
        card_layout.addLayout(header)

        self.stations = {}
        for station in tb.STATIONS:
            card = StationCard(station["name"])
            card_layout.addWidget(card)
            self.stations[station["name"]] = card

        self._position_top_right()

        self.tick_timer = QTimer(self)
        self.tick_timer.timeout.connect(self._tick)
        self.tick_timer.start(TICK_MS)

        self.worker = FeedWorker()
        self.worker.dataReady.connect(self._on_data)
        self.worker.start()

    def _position_top_right(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.adjustSize()
        self.move(screen.right() - self.width() - 24, screen.top() + 24)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._apply_mask)

    def _apply_mask(self):
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 16, 16)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def _on_data(self, snapshot):
        for name, entries in snapshot.items():
            self.stations[name].set_data(entries)
        self.adjustSize()
        self._apply_mask()

    def _tick(self):
        for card in self.stations.values():
            card.tick()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None

    def closeEvent(self, event):
        self.worker.stop()
        self.worker.wait(2000)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    widget = TrainWidget()
    widget.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
