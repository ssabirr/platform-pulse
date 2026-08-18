"""
Platform Pulse - web server.

Serves the frontend and one JSON endpoint that wraps the MTA data engine.

    python server.py            # live MTA data
    python server.py --demo     # synthetic data, no network needed

The browser can't read MTA feeds directly: they're protobuf, and they're served
without CORS headers. This server is the shim that makes them browser-readable.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import mta

WEB_DIR = Path(__file__).parent / "web"

app = FastAPI(title="Platform Pulse", docs_url=None, redoc_url=None)


def demo_mode() -> bool:
    """Read at request time, so `--demo` works no matter how the app is started."""
    return os.environ.get("PLATFORM_PULSE_DEMO", "").lower() in {"1", "true", "yes"}


@app.get("/api/arrivals")
def arrivals():
    """Live arrivals for every configured station."""
    if demo_mode():
        return mta.demo_snapshot()
    try:
        return mta.snapshot()
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={
                "error": f"Couldn't reach the MTA feeds ({type(exc).__name__}).",
                "stations": [],
                "server_now": None,
            },
        )


@app.get("/api/health")
def health():
    return {"ok": True, "demo": demo_mode()}


app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")


if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser(description="Platform Pulse web server")
    parser.add_argument("--demo", action="store_true", help="serve synthetic data, no network")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    args = parser.parse_args()

    if args.demo:
        os.environ["PLATFORM_PULSE_DEMO"] = "1"

    print(f"Platform Pulse  ->  http://{args.host}:{args.port}" + ("   [demo data]" if args.demo else ""))
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
