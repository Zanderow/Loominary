from __future__ import annotations

import logging
import time
import webbrowser
from datetime import datetime

logger = logging.getLogger(__name__)


def wait_until_premeet(start_time: datetime, pre_seconds: int = 30) -> None:
    """Sleep until `pre_seconds` before start_time, printing a countdown."""
    target = start_time.timestamp() - pre_seconds
    now = time.time()
    remaining = target - now

    if remaining <= 0:
        return

    logger.info(
        "Waiting until %s seconds before meeting start (%s)...",
        pre_seconds,
        start_time.strftime("%Y-%m-%d %H:%M:%S"),
    )

    while True:
        now = time.time()
        remaining = target - now
        if remaining <= 0:
            break
        if remaining > 60:
            mins = int(remaining // 60)
            print(f"  Meeting opens in ~{mins} minute(s)...", flush=True)
            sleep_for = min(60.0, remaining - 5)
        else:
            sleep_for = min(5.0, remaining)
        time.sleep(sleep_for)


def open_meeting_url(url: str, platform: str) -> None:
    """Open the meeting URL in the default browser."""
    logger.info("Opening %s meeting URL: %s", platform, url)
    print(f"Opening browser: {url}", flush=True)
    success = webbrowser.open(url)
    if not success:
        logger.warning("webbrowser.open returned False — browser may not have opened.")


def wait_until_start(start_time: datetime) -> None:
    """Sleep until start_time (or return immediately if already past)."""
    remaining = start_time.timestamp() - time.time()
    if remaining <= 0:
        return
    logger.info("Waiting %.0f seconds until meeting start...", remaining)
    deadline = start_time.timestamp()
    while time.time() < deadline:
        time.sleep(min(5.0, deadline - time.time()))
