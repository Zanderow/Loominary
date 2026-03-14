"""Shared rich.Console + progress bar helpers."""
from rich.console import Console
from rich.progress import (
    Progress,
    BarColumn,
    DownloadColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

console = Console()


def make_download_progress() -> Progress:
    """Return a rich Progress configured for file downloads."""
    return Progress(
        TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.1f}%",
        "•",
        DownloadColumn(),
        "•",
        TransferSpeedColumn(),
        "•",
        TimeRemainingColumn(),
        console=console,
    )


def make_spinner_progress(description: str = "Working...") -> Progress:
    """Return a simple spinner progress for indeterminate tasks."""
    return Progress(
        TextColumn("[bold green]{task.description}"),
        console=console,
        transient=True,
    )
