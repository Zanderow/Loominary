"""CLI entry points for RAG chat and reindexing."""
from __future__ import annotations

import questionary
from rich.markup import escape
from rich.table import Table
from rich.text import Text

from loominary.utils.progress import console


def chat_repl(db_conn) -> None:
    """Interactive Q&A REPL over the Loominary transcript library."""
    from loominary.rag.chat import ask, format_sources
    from loominary.rag.qdrant import ensure_collection, get_client
    from loominary import config

    ensure_collection()
    client = get_client()
    info = client.get_collection(config.QDRANT_COLLECTION)

    if info.points_count == 0:
        console.print(
            "[yellow]The vector index is empty.[/yellow]  "
            "Run [bold]Reindex all transcripts[/bold] first."
        )
        return

    console.print(
        f"[cyan]Library loaded:[/cyan] {info.points_count:,} chunks across your transcripts.\n"
        "[dim]Type your question, or 'quit' to exit.[/dim]\n"
    )

    while True:
        question = questionary.text("You:").ask()
        if question is None or question.strip().lower() in ("quit", "exit", "q"):
            break
        if not question.strip():
            continue

        console.print()
        try:
            stream = ask(question)
            current_phase = None
            showed_thinking = False

            for phase, token in stream:
                if phase == "thinking" and current_phase != "thinking":
                    current_phase = "thinking"
                    showed_thinking = True
                    console.print(Text("Thinking... ", style="dim"), end="")
                elif phase == "answering" and current_phase != "answering":
                    if showed_thinking:
                        console.print()
                        console.print()
                    current_phase = "answering"

                if phase == "thinking":
                    console.print(Text(token, style="dim"), end="")
                else:
                    console.print(Text(token), end="")

            console.print()

            if stream.hits:
                console.print()
                console.print(Text(format_sources(stream.hits), style="dim"))
        except Exception as e:
            console.print(f"\n[red]Error: {escape(str(e))}[/red]")
        console.print()


def run_reindex(db_conn, *, force: bool = False) -> None:
    """Reindex all transcript files into Qdrant."""
    from loominary.rag.indexer import reindex_all

    console.print("[cyan]Reindexing all transcripts...[/cyan]")
    stats = reindex_all(db_conn, force=force)

    table = Table(title="Reindex Summary", border_style="cyan")
    table.add_column("Metric", style="bold")
    table.add_column("Value")
    table.add_row("Total files", str(stats["files"]))
    table.add_row("Indexed", str(stats["indexed"]))
    table.add_row("Skipped (unchanged)", str(stats["skipped"]))
    table.add_row("Missing files", str(stats["missing"]))
    table.add_row("Total chunks", str(stats["chunks"]))
    console.print(table)
