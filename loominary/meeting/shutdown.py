from __future__ import annotations

import logging
import subprocess
import time

from loominary.meeting.errors import ShutdownError

logger = logging.getLogger(__name__)


def post_meeting_wait(minutes: int = 10) -> None:
    """Wait for `minutes` after the meeting ends before shutting down."""
    total_seconds = minutes * 60
    logger.info("Waiting %d minutes before shutdown...", minutes)
    print(f"\nWaiting {minutes} minutes before shutdown. Press Ctrl+C to cancel.", flush=True)

    deadline = time.time() + total_seconds
    try:
        while time.time() < deadline:
            remaining = deadline - time.time()
            mins_left = int(remaining // 60) + 1
            print(f"  Shutting down in ~{mins_left} minute(s)...", flush=True)
            time.sleep(min(60.0, remaining))
    except KeyboardInterrupt:
        logger.info("Post-meeting wait interrupted by user — proceeding to shutdown.")
        print("\nWait interrupted — proceeding to shutdown.", flush=True)


def shutdown_computer() -> None:
    """Initiate a Windows system shutdown."""
    logger.info("Initiating system shutdown.")
    print("Shutting down the computer now...", flush=True)
    result = subprocess.run(
        ["shutdown", "/s", "/t", "0"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ShutdownError(
            f"Shutdown command failed (exit {result.returncode}):\n"
            + result.stderr.strip()
            + "\nYou may need to run this script as Administrator."
        )
