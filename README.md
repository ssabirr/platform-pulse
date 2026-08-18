# Platform Pulse

![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

Live NYC subway tracking for one small corner of the Upper West Side — the **B**, **C**, and **D** trains at **Cathedral Pkwy (110 St)**, and the **1** train at **103 St**. Straight from the MTA's real-time feeds, no API key required.

Three ways to view it:

- **`train_board.py`** — a colorful, auto-refreshing dashboard in your terminal
- **`train_widget.py`** — a frameless, always-on-top animated desktop widget (Windows)
- **`server.py`** + **`web/`** — a browser version you can open on your phone

All three share the same data engine and the same MTA feeds; the web version's copy of that engine lives in `mta.py`.

## Requirements

- **Python 3.12** (Python 3.14 is *not* currently supported — `protobuf`'s compiled extension breaks on it)
- The terminal dashboard and desktop widget are tested on Windows; the web version runs on any OS

## Setup

```bash
python -m venv venv
venv\Scripts\activate          # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
```

One `requirements.txt` covers all three entry points.

## Usage

### Terminal dashboard

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

### Desktop widget

```bash
venv\Scripts\python.exe train_widget.py
```

A small card appears in the top-right of your screen and stays on top of other windows. Drag it anywhere by clicking and holding; close it with the **✕** in the corner.

### Web version

```bash
python server.py
```

Open http://127.0.0.1:8000. No build step, no framework — the frontend in `web/` is static HTML/CSS/JS served by a small FastAPI backend.

Want to work on the UI without hitting the network?

```bash
python server.py --demo
```

Demo mode serves synthetic trains that count down and recycle, so the whole interface is exercisable offline. The page says so when it's active.

## How it works

- Station stop IDs come from the official MTA GTFS static `stops.txt` (bundled with the [`nyct-gtfs`](https://pypi.org/project/nyct-gtfs/) library)
- Live arrivals are read straight from MTA's public real-time feeds — the B/D and C trains come from separate feeds (`gtfs-bdfm` and `gtfs-ace`), the 1 train from the numbered-lines feed (`gtfs`)
- The terminal dashboard and web server share this arrival-matching logic; the desktop widget reuses `train_board.py` directly, the web server uses the `mta.py` port of it
- `train_widget.py` fetches on a background thread every 30 seconds and ticks the displayed countdowns every second in between, so numbers count down smoothly rather than jumping. The web page does the same thing with `setInterval`, and corrects for clock skew between the server and the browser using an absolute timestamp

### Why the web version needs a server

Browsers can't read MTA's feeds directly: they're GTFS-realtime protobuf, not JSON, and they're served without CORS headers, so a page's own `fetch()` is blocked before it starts. `server.py` is the shim — it fetches and decodes the feeds server-side and hands the browser plain JSON at `/api/arrivals`. See `mta.py`'s and `server.py`'s docstrings for the details, or the API section below.

### Web API

`GET /api/arrivals`

```json
{
  "server_now": 1755404400.12,
  "refresh_seconds": 30,
  "stations": [
    {
      "name": "Cathedral Pkwy (110 St)",
      "stop_id": "A17",
      "lines": ["B", "C", "D"],
      "arrivals": [
        {
          "route": "C",
          "color": "#0039A6",
          "dark_text": false,
          "direction": "N",
          "direction_label": "Uptown",
          "headsign": "168 St",
          "arrival_epoch": 1755404760.0,
          "seconds_away": 359.88,
          "train_id": "06 1201+ 168/EUC"
        }
      ]
    }
  ],
  "error": null
}
```

`GET /api/health` → `{"ok": true, "demo": false}`

## Adding a station

Append to `STATIONS` — in `train_board.py` for the CLI/widget, or `mta.py` for the web version (keep them in sync if you want all three views to match). Stop IDs come from the MTA's GTFS static `stops.txt`, bundled with `nyct-gtfs`.

```python
{"name": "96 St", "stop_id": "120", "lines": ["1", "2", "3"]},
```

## Notes

- B and D trains rarely serve Cathedral Pkwy in normal service (it's a B/C local stop; D usually runs express past it) — they'll show up during service changes or late nights when they do run local.
- `.env.example` is included for future use of the Anthropic API (`anthropic` + `python-dotenv` are installed); copy it to `.env` and add your key from [console.anthropic.com](https://console.anthropic.com) if you build on that later.

## Deploying the web version

Anything that runs a Python process works — Render, Railway, Fly.io. It binds `$PORT` if set:

```bash
uvicorn server:app --host 0.0.0.0 --port $PORT
```

Static hosts like GitHub Pages or Netlify won't work on their own, for the CORS/protobuf reasons above. If you want a static host, put `/api/arrivals` in a serverless function on the same domain instead.

## Project structure

```
train_board.py    # terminal dashboard (rich)
train_widget.py   # desktop widget (PySide6), reuses train_board's data engine
mta.py            # web data engine — stations, feed pool, arrivals, demo data
server.py         # FastAPI: /api/arrivals + serves web/
requirements.txt  # shared by all three entry points
.env.example      # template for an Anthropic API key, if needed later
web/
  index.html
  styles.css
  app.js          # fetch every 30s, tick every 1s, render
```

## License

[MIT](LICENSE)
