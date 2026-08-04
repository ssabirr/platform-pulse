"""
Upper West Side Train Board
Live countdown board for the B/C/D at Cathedral Pkwy (110 St)
and the 1 at 103 St, straight from the MTA's real-time feeds.
"""

import time
from datetime import datetime

from nyct_gtfs import NYCTFeed
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

REFRESH_SECONDS = 30

# Stop IDs pulled from the MTA's official GTFS static stops.txt (bundled with nyct-gtfs).
STATIONS = [
    {
        "name": "Cathedral Pkwy (110 St)",
        "stop_id": "A17",
        "lines": ["B", "C", "D"],
        "feed_line": "B",  # B/C/D all live on the ACE/BDFM feeds; "B" resolves to gtfs-bdfm
    },
    {
        "name": "103 St",
        "stop_id": "119",
        "lines": ["1"],
        "feed_line": "1",
    },
]

ROUTE_COLORS = {
    "1": "#EE352E",
    "B": "#FF6319",
    "C": "#0039A6",
    "D": "#FF6319",
}

DIRECTION_LABELS = {"N": "Uptown", "S": "Downtown"}

console = Console()


def load_feeds():
    """One NYCTFeed per distinct MTA data feed needed (dedup shared feeds like B/D)."""
    feeds = {}
    for station in STATIONS:
        for line in station["lines"]:
            if line not in feeds:
                try:
                    feeds[line] = NYCTFeed(line)
                except Exception:
                    feeds[line] = None
    return feeds


def refresh_feeds(feeds):
    for line, feed in feeds.items():
        if feed is None:
            continue
        try:
            feed.refresh()
        except Exception:
            pass


def urgency_style(minutes):
    if minutes <= 1:
        return "bold white on red"
    if minutes <= 2:
        return "bold red"
    if minutes <= 5:
        return "bold yellow"
    return "bold green"


def format_minutes(minutes):
    if minutes <= 0:
        return "now"
    if minutes < 1:
        return "<1 min"
    return f"{int(minutes)} min"


def get_arrivals(feeds, station, alerted, alert_bell):
    """Return sorted (line, direction, minutes, headsign) tuples for one station."""
    now = datetime.now()
    arrivals = []
    target_stops = {station["stop_id"] + "N", station["stop_id"] + "S"}

    seen_feeds = set()
    for line in station["lines"]:
        feed = feeds.get(line)
        if feed is None or id(feed) in seen_feeds:
            continue
        seen_feeds.add(id(feed))

        try:
            trips = feed.filter_trips(line_id=station["lines"], headed_for_stop_id=list(target_stops))
        except Exception:
            continue

        for trip in trips:
            for stu in trip.stop_time_updates:
                if stu.stop_id not in target_stops:
                    continue
                arrival_time = stu.arrival or stu.departure
                if arrival_time is None:
                    continue
                minutes = (arrival_time - now).total_seconds() / 60
                if minutes < -1:
                    continue
                direction = stu.stop_id[-1]
                arrivals.append((trip.route_id, direction, minutes, trip.headsign_text or ""))

                if minutes <= 2 and trip.nyc_train_id not in alerted:
                    alerted.add(trip.nyc_train_id)
                    alert_bell[0] = True

    arrivals.sort(key=lambda a: a[2])
    return arrivals


def build_station_panel(station, arrivals):
    table = Table.grid(padding=(0, 2))
    table.add_column(justify="left")
    table.add_column(justify="left")
    table.add_column(justify="right")

    if not arrivals:
        table.add_row("", Text("No live trains reported right now.", style="dim"), "")
    else:
        for route_id, direction, minutes, headsign in arrivals[:6]:
            bullet = Text(f" {route_id} ", style=f"bold white on {ROUTE_COLORS.get(route_id, 'grey50')}")
            dest = Text(f"{DIRECTION_LABELS.get(direction, direction)} - {headsign}", style="white")
            countdown = Text(format_minutes(minutes), style=urgency_style(minutes))
            table.add_row(bullet, dest, countdown)

    return Panel(table, title=f"[bold]{station['name']}[/bold]", border_style="grey50", expand=True)


def build_display(feeds):
    alerted = getattr(build_display, "_alerted", None)
    if alerted is None:
        alerted = set()
        build_display._alerted = alerted
    alert_bell = [False]

    panels = [build_station_panel(s, get_arrivals(feeds, s, alerted, alert_bell)) for s in STATIONS]

    header = Text(
        f"Upper West Side Train Board - updated {datetime.now().strftime('%I:%M:%S %p')}",
        style="bold cyan",
    )

    if alert_bell[0]:
        console.bell()

    return Group(header, *panels)


def main():
    feeds = load_feeds()
    console.print("[bold cyan]Starting Upper West Side Train Board...[/bold cyan]")

    with Live(build_display(feeds), console=console, refresh_per_second=1, screen=False) as live:
        try:
            while True:
                time.sleep(REFRESH_SECONDS)
                refresh_feeds(feeds)
                live.update(build_display(feeds))
        except KeyboardInterrupt:
            console.print("\n[bold cyan]Goodbye![/bold cyan]")


if __name__ == "__main__":
    main()
