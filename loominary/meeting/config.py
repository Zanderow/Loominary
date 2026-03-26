from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

from loominary.meeting.errors import ConfigError

SUPPORTED_PLATFORMS = {"goldcast", "teams", "zoom", "generic"}
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


@dataclass
class MeetingConfig:
    name: str
    url: str
    platform: str
    start_time: datetime | None = field(default=None)
    duration_minutes: int | None = field(default=None)


def _validate_base_fields(raw: dict) -> tuple[str, str, str]:
    """Validate and return (name, url, platform). Raises ConfigError on failure."""
    for f in ("name", "url", "platform"):
        if f not in raw:
            raise ConfigError(f"Missing required field: '{f}'")

    name = str(raw["name"]).strip()
    url = str(raw["url"]).strip()
    platform = str(raw["platform"]).strip().lower()

    if not name:
        raise ConfigError("'name' must not be empty.")
    if not url:
        raise ConfigError("'url' must not be empty.")
    if platform not in SUPPORTED_PLATFORMS:
        raise ConfigError(
            f"'platform' must be one of: {', '.join(sorted(SUPPORTED_PLATFORMS))}. Got: '{platform}'"
        )

    return name, url, platform


def load_config(path: Path) -> MeetingConfig:
    """Load config for automatic mode — requires start_time and duration_minutes."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ConfigError(f"Failed to parse YAML config: {e}") from e

    if not isinstance(raw, dict):
        raise ConfigError("Config file must be a YAML mapping.")

    for f in ("start_time", "duration_minutes"):
        if f not in raw:
            raise ConfigError(f"Missing required field: '{f}'")

    name, url, platform = _validate_base_fields(raw)

    try:
        duration_minutes = int(raw["duration_minutes"])
    except (TypeError, ValueError):
        raise ConfigError("'duration_minutes' must be an integer.")
    if duration_minutes <= 0:
        raise ConfigError("'duration_minutes' must be positive.")

    start_time_raw = raw["start_time"]
    if isinstance(start_time_raw, datetime):
        start_time = start_time_raw
    else:
        try:
            start_time = datetime.strptime(str(start_time_raw).strip(), DATETIME_FORMAT)
        except ValueError:
            raise ConfigError(
                f"'start_time' must be in format '{DATETIME_FORMAT}'. Got: '{start_time_raw}'"
            )

    return MeetingConfig(
        name=name,
        url=url,
        platform=platform,
        start_time=start_time,
        duration_minutes=duration_minutes,
    )


def load_config_manual(path: Path) -> MeetingConfig:
    """Load config for manual recording — only name, url, platform are required."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ConfigError(f"Failed to parse YAML config: {e}") from e

    if not isinstance(raw, dict):
        raise ConfigError("Config file must be a YAML mapping.")

    name, url, platform = _validate_base_fields(raw)
    return MeetingConfig(name=name, url=url, platform=platform)
