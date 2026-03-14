"""Entry point: bootstrap dirs, init DB, run CLI."""
import sys
from pathlib import Path

from loominary import config
from loominary.utils.progress import console


def main() -> None:
    # Create required directories
    config.LOOMINARY_TMP_DIR.mkdir(parents=True, exist_ok=True)
    (config.LOOMINARY_TMP_DIR / "audio").mkdir(parents=True, exist_ok=True)
    config.LOOMINARY_TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

    # Validate Spotify credentials early
    try:
        config.validate_spotify()
    except EnvironmentError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    # Initialize DB connection
    from loominary.database.repository import get_connection
    db_conn = get_connection(config.LOOMINARY_DB_PATH)

    # Authenticate with Spotify
    try:
        from loominary.auth.spotify_auth import get_spotify_client
        console.print("[cyan]Authenticating with Spotify...[/cyan]")
        sp = get_spotify_client()
        console.print("[green]Spotify authenticated.[/green]")
    except Exception as e:
        console.print(f"[red]Spotify authentication failed: {e}[/red]")
        sys.exit(1)

    # Run interactive CLI
    try:
        from loominary.cli import run
        run(db_conn, sp)
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")
        sys.exit(0)


if __name__ == "__main__":
    main()
