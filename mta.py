"""
Platform Pulse - data engine.

Ported from train_board.py. Same stop IDs, same MTA feeds, same idea:
read live arrivals straight from the MTA's public GTFS-realtime feeds.

Changes from the CLI version:
  - Feeds are deduped by URL, not by object identity. B and D both live on
    gtfs-bdfm, so the old code fetched that feed twice and double-counted
    every B/D train.
  - Results come back as plain dicts with absolute arrival timestamps, so a
    browser can tick countdowns down on its own between fetches.
  - Feed responses are cached for REFRESH_SECONDS, so ten open browser tabs
    still only cost the MTA one request per feed.
"""

from __future__ import annotations

import random
import threading
import time
from datetime import datetime, timezone

from nyct_gtfs import NYCTFeed

REFRESH_SECONDS = 30

# Stop IDs from the MTA's official GTFS static stops.txt (bundled with nyct-gtfs).
# Add a station by appending here - the API and the frontend both read this list.
STATIONS = [
    {
        "name": "Cathedral Pkwy (110 St)",
        "stop_id": "A17",
        "lines": ["B", "C", "D"],
    },
    {
        "name": "103 St",
        "stop_id": "119",
        "lines": ["1"],
    },
]

# Official MTA route colors. `dark` marks bullets that need black text.
ROUTE_COLORS = {
    "1": "#EE352E", "2": "#EE352E", "3": "#EE352E",
    "4": "#00933C", "5": "#00933C", "6": "#00933C",
    "7": "#B933AD",
    "A": "#0039A6", "C": "#0039A6", "E": "#0039A6",
    "B": "#FF6319", "D": "#FF6319", "F": "#FF6319", "M": "#FF6319",
    "G": "#6CBE45",
    "J": "#996633", "Z": "#996633",
    "L": "#A7A9AC",
    "N": "#FCCC0A", "Q": "#FCCC0A", "R": "#FCCC0A", "W": "#FCCC0A",
    "S": "#808183", "GS": "#808183",
    "SIR": "#1F4F8F",
}
DARK_TEXT_ROUTES = {"N", "Q", "R", "W", "L"}

DIRECTION_LABELS = {"N": "Uptown", "S": "Downtown"}


def route_color(route_id: str) -> str:
    return ROUTE_COLORS.get(route_id, "#6E7480")


# --------------------------------------------------------------------------
# Feed management
# --------------------------------------------------------------------------

class FeedPool:
    """Holds one NYCTFeed per distinct feed URL, refreshed at most every 30s."""

    def __init__(self, refresh_seconds: int = REFRESH_SECONDS):
        self._refresh_seconds = refresh_seconds
        self._feeds: dict[str, NYCTFeed] = {}
        self._last_refresh: dict[str, float] = {}
        self._lock = threading.Lock()
        self.last_error: str | None = None

    def _feed_url(self, line: str) -> str | None:
        return NYCTFeed._train_to_url.get(line)

    def required_urls(self) -> list[str]:
        """The distinct feed URLs needed to cover every configured station."""
        urls = []
        for station in STATIONS:
            for line in station["lines"]:
                url = self._feed_url(line)
                if url and url not in urls:
                    urls.append(url)
        return urls

    def get(self, line: str) -> NYCTFeed | None:
        """Return a refreshed feed for `line`, sharing objects across lines."""
        url = self._feed_url(line)
        if url is None:
            return None

        with self._lock:
            feed = self._feeds.get(url)
            age = time.time() - self._last_refresh.get(url, 0)

            try:
                if feed is None:
                    feed = NYCTFeed(url)
                    self._feeds[url] = feed
                    self._last_refresh[url] = time.time()
                elif age >= self._refresh_seconds:
                    feed.refresh()
                    self._last_refresh[url] = time.time()
                self.last_error = None
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
                return self._feeds.get(url)

            return feed


_pool = FeedPool()


# --------------------------------------------------------------------------
# Arrivals
# --------------------------------------------------------------------------

def get_arrivals(station: dict, pool: FeedPool = _pool, limit: int = 6) -> list[dict]:
    """Live arrivals for one station, soonest first."""
    now = datetime.now()
    target_stops = {station["stop_id"] + "N", station["stop_id"] + "S"}
    arrivals: list[dict] = []
    seen_urls: set[str] = set()

    for line in station["lines"]:
        url = pool._feed_url(line)
        if url is None or url in seen_urls:
            continue
        seen_urls.add(url)

        feed = pool.get(line)
        if feed is None:
            continue

        try:
            trips = feed.filter_trips(
                line_id=station["lines"],
                headed_for_stop_id=list(target_stops),
            )
        except Exception:
            continue

        for trip in trips:
            for stu in trip.stop_time_updates:
                if stu.stop_id not in target_stops:
                    continue
                arrival_time = stu.arrival or stu.departure
                if arrival_time is None:
                    continue
                seconds = (arrival_time - now).total_seconds()
                if seconds < -60:
                    continue

                direction = stu.stop_id[-1]
                arrivals.append({
                    "route": trip.route_id,
                    "color": route_color(trip.route_id),
                    "dark_text": trip.route_id in DARK_TEXT_ROUTES,
                    "direction": direction,
                    "direction_label": DIRECTION_LABELS.get(direction, direction),
                    "headsign": trip.headsign_text or "",
                    "arrival_epoch": arrival_time.timestamp(),
                    "seconds_away": seconds,
                    "train_id": trip.nyc_train_id,
                })

    arrivals.sort(key=lambda a: a["seconds_away"])
    return arrivals[:limit]


def snapshot(pool: FeedPool = _pool) -> dict:
    """Everything the frontend needs in one payload."""
    stations = []
    for station in STATIONS:
        stations.append({
            "name": station["name"],
            "stop_id": station["stop_id"],
            "lines": station["lines"],
            "arrivals": get_arrivals(station, pool),
        })

    return {
        "server_now": datetime.now(timezone.utc).timestamp(),
        "refresh_seconds": REFRESH_SECONDS,
        "stations": stations,
        "error": pool.last_error,
    }


# --------------------------------------------------------------------------
# Demo mode - synthetic data, no network. For UI work and offline dev.
# --------------------------------------------------------------------------

_DEMO_TRIPS = [
    ("Cathedral Pkwy (110 St)", "C", "N", "168 St"),
    ("Cathedral Pkwy (110 St)", "C", "S", "Euclid Av"),
    ("Cathedral Pkwy (110 St)", "B", "N", "145 St"),
    ("Cathedral Pkwy (110 St)", "C", "N", "168 St"),
    ("103 St", "1", "S", "South Ferry"),
    ("103 St", "1", "N", "Van Cortlandt Park-242 St"),
    ("103 St", "1", "S", "South Ferry"),
]

_demo_offsets: dict[int, float] = {}
_demo_started = time.time()


def demo_snapshot() -> dict:
    """Fake arrivals that count down realistically and recycle when they hit zero."""
    now = time.time()
    if not _demo_offsets:
        for i, _ in enumerate(_DEMO_TRIPS):
            _demo_offsets[i] = now + 45 + i * 190 + random.randint(0, 60)

    by_station: dict[str, list] = {s["name"]: [] for s in STATIONS}
    for i, (station_name, route, direction, headsign) in enumerate(_DEMO_TRIPS):
        if _demo_offsets[i] < now - 30:
            _demo_offsets[i] = now + 600 + random.randint(0, 400)
        eta = _demo_offsets[i]
        by_station[station_name].append({
            "route": route,
            "color": route_color(route),
            "dark_text": route in DARK_TEXT_ROUTES,
            "direction": direction,
            "direction_label": DIRECTION_LABELS[direction],
            "headsign": headsign,
            "arrival_epoch": eta,
            "seconds_away": eta - now,
            "train_id": f"demo-{i}",
        })

    stations = []
    for station in STATIONS:
        arrivals = sorted(by_station[station["name"]], key=lambda a: a["seconds_away"])
        stations.append({
            "name": station["name"],
            "stop_id": station["stop_id"],
            "lines": station["lines"],
            "arrivals": arrivals,
        })

    return {
        "server_now": now,
        "refresh_seconds": REFRESH_SECONDS,
        "stations": stations,
        "error": None,
        "demo": True,
    }
