# Platform Pulse

![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Platform: Windows](https://img.shields.io/badge/platform-Windows-lightgrey)

Live NYC subway tracking for one small corner of the Upper West Side — the **B**, **C**, and **D** trains at **Cathedral Pkwy (110 St)**, and the **1** train at **103 St**. Straight from the MTA's real-time feeds, no API key required.

Two ways to view it:

- **`train_board.py`** — a colorful, auto-refreshing dashboard in your terminal
- **`train_widget.py`** — a frameless, always-on-top animated desktop widget

## Features

- Live countdowns pulled directly from MTA GTFS-realtime feeds
- Color-coded by official MTA line colors
- Countdown urgency coloring (green → yellow → red as a train approaches)
- Desktop widget adds: a glowing pulse when a train is under 2 minutes out, an animated fill bar per train, drag-to-move, and smooth per-second updates between data refreshes

## Requirements

- **Python 3.12** (Python 3.14 is *not* currently supported — `protobuf`'s compiled extension breaks on it)
- Windows (tested), should work cross-platform with minor tweaks

## Setup

```bash
py -3.12 -m venv venv
venv\Scripts\pip install -r requirements.txt
```

## Usage

Terminal dashboard:

```bash
venv\Scripts\python.exe train_board.py
```

```
Upper West Side Train Board - updated 10:43:46 PM
+-------------------------- Cathedral Pkwy (110 St) --------------------------+
|  C   Uptown - 168 St   6 min                                                |
|  C   Uptown - 168 St  19 min                                                |
+-----------------------------------------------------------------------------+
+---------------------------------- 103 St -----------------------------------+
|  1   Downtown - South Ferry               5 min                             |
|  1   Uptown - Van Cortlandt Park-242 St   6 min                             |
+-----------------------------------------------------------------------------+
```

Press `Ctrl+C` to stop.

Desktop widget:

```bash
venv\Scripts\python.exe train_widget.py
```

A small card appears in the top-right of your screen and stays on top of other windows. Drag it anywhere by clicking and holding; close it with the **✕** in the corner.

## How it works

- Station stop IDs come from the official MTA GTFS static `stops.txt` (bundled with the [`nyct-gtfs`](https://pypi.org/project/nyct-gtfs/) library)
- Live arrivals are read straight from MTA's public real-time feeds — the B/D and C trains come from separate feeds (`gtfs-bdfm` and `gtfs-ace`), the 1 train from the numbered-lines feed (`gtfs`)
- The desktop widget fetches on a background thread every 30 seconds and ticks the displayed countdowns every second in between, so numbers count down smoothly rather than jumping

## Notes

- B and D trains rarely serve Cathedral Pkwy in normal service (it's a B/C local stop; D usually runs express past it) — they'll show up during service changes or late nights when they do run local.
- `.env.example` is included for future use of the Anthropic API (`anthropic` + `python-dotenv` are installed); copy it to `.env` and add your key from [console.anthropic.com](https://console.anthropic.com) if you build on that later.

## Project structure

```
train_board.py    # terminal dashboard (rich)
train_widget.py   # desktop widget (PySide6), reuses train_board's data engine
requirements.txt
.env.example       # template for an Anthropic API key, if needed later
```

## License

[MIT](LICENSE)
