"""
VersionCheckBot — Bot worker heartbeat + restart signalling

SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (c) 2024 VersionCheckBot Contributors

The bot worker writes a small JSON file with its current status every 15 s.
The web panel reads this file to show a real status indicator (alive vs.
running vs. idle vs. error) instead of just trusting the container's existence.

The web panel can also signal a clean restart by writing a sentinel file —
the heartbeat thread sees it and calls os._exit(0) so Docker's restart policy
picks up a fresh process (and crucially a freshly-loaded .env via load_dotenv).
"""
import json
import os
import sys
import time
import threading
import logging
from pathlib import Path
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# /app/data is always writeable by the bot container's webuser/botuser (UID 1000)
# and is mounted on a shared volume that the web container also reads.
_DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
HEARTBEAT_FILE = _DATA_DIR / ".bot_heartbeat"
RESTART_FILE = _DATA_DIR / ".restart_requested"

PLACEHOLDER_MARKERS = ("placeholder", "your_bot_token", "changeme")


def is_placeholder_token(token: str) -> bool:
    """True if the token looks like an unconfigured placeholder."""
    if not token:
        return True
    low = token.lower()
    if any(m in low for m in PLACEHOLDER_MARKERS):
        return True
    if token.startswith("000000:"):
        return True
    return False


_state: dict = {
    "status": "starting",     # starting | running | idle | error
    "message": "",
    "started_at": None,
    "pid": os.getpid(),
}
_thread: threading.Thread | None = None
_stop = threading.Event()


def _write() -> None:
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            **_state,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        HEARTBEAT_FILE.write_text(json.dumps(payload))
    except Exception as exc:
        log.warning("Heartbeat write failed: %s", exc)


def _check_restart() -> bool:
    if RESTART_FILE.exists():
        try:
            RESTART_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        return True
    return False


def set_status(status: str, message: str = "") -> None:
    """Update the worker's status (called from the main flow)."""
    _state["status"] = status
    _state["message"] = message
    if not _state["started_at"]:
        _state["started_at"] = datetime.now(timezone.utc).isoformat()
    _write()


def _bg_loop() -> None:
    while not _stop.wait(15):
        _write()
        if _check_restart():
            log.info("Restart signal received — exiting cleanly for Docker to respawn")
            # use os._exit to skip Python finalizers (the bot is async + threaded,
            # and a clean asyncio shutdown from here is fragile)
            os._exit(0)


def start() -> None:
    """Start the background heartbeat thread (idempotent)."""
    global _thread
    if _thread is None or not _thread.is_alive():
        _thread = threading.Thread(target=_bg_loop, daemon=True, name="heartbeat")
        _thread.start()
        log.debug("Heartbeat thread started")


def stop() -> None:
    _stop.set()


def idle_wait(reason: str) -> None:
    """Stay alive without doing anything. Used when bot can't start (bad token).

    The web panel sees status=idle, the user fixes config, presses "Restart bot",
    which writes RESTART_FILE; the heartbeat thread exits the process and Docker
    respawns it with a freshly-loaded .env.
    """
    log.warning("Bot entering IDLE mode: %s", reason)
    set_status("idle", reason)
    start()
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        stop()
