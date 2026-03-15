"""faster-whisper backend (CTranslate2-based, 4x faster on CPU)."""
from typing import Optional

from rich.progress import Progress, BarColumn, TaskProgressColumn, TextColumn, TimeElapsedColumn

from loominary.transcription.base import TranscriptionEngine, TranscriptResult
from loominary.utils.progress import console


def _fmt_audio_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


class FasterWhisperEngine(TranscriptionEngine):
    def __init__(self, model_size: str = "small", device: str = "cpu", compute_type: str = "int8"):
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._model = None

    def _load_model(self):
        if self._model is None:
            console.print(f"[cyan]Loading faster-whisper model '{self._model_size}'...[/cyan]")
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                self._model_size,
                device=self._device,
                compute_type=self._compute_type,
            )
            console.print("[green]Model loaded.[/green]")

    def transcribe(self, audio_path: str) -> TranscriptResult:
        self._load_model()

        segments_gen, info = self._model.transcribe(audio_path, beam_size=5)
        total_duration = info.duration
        total_fmt = _fmt_audio_time(total_duration)

        segments = []
        text_parts = []

        with Progress(
            TextColumn(f"[cyan]Transcribing ({self._model_size})[/cyan]"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("[dim]{task.fields[audio_pos]}[/dim]"),
            TimeElapsedColumn(),
            console=console,
            transient=False,
        ) as progress:
            task = progress.add_task(
                "transcribing",
                total=total_duration,
                audio_pos=f"0:00 / {total_fmt}",
            )
            for seg in segments_gen:
                segments.append({
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text,
                })
                text_parts.append(seg.text)
                progress.update(
                    task,
                    completed=seg.end,
                    audio_pos=f"{_fmt_audio_time(seg.end)} / {total_fmt}",
                )

        full_text = " ".join(text_parts).strip()
        return TranscriptResult(
            text=full_text,
            language=info.language,
            segments=segments,
        )
