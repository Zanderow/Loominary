"""faster-whisper backend (CTranslate2-based, 4x faster on CPU)."""
from typing import Optional

from loominary.transcription.base import TranscriptionEngine, TranscriptResult
from loominary.utils.progress import console


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
        console.print(f"[cyan]Transcribing with faster-whisper ({self._model_size})...[/cyan]")

        segments_gen, info = self._model.transcribe(audio_path, beam_size=5)

        segments = []
        text_parts = []
        for seg in segments_gen:
            segments.append({
                "start": seg.start,
                "end": seg.end,
                "text": seg.text,
            })
            text_parts.append(seg.text)

        full_text = " ".join(text_parts).strip()
        return TranscriptResult(
            text=full_text,
            language=info.language,
            segments=segments,
        )
