"""OpenAI Whisper backend with chunked processing for long audio files."""
import subprocess
import tempfile
import os
from pathlib import Path

from loominary.transcription.base import TranscriptionEngine, TranscriptResult
from loominary.utils.progress import console

# Whisper processes 30-second windows internally, but the STFT for the full
# audio is computed up-front, blowing up RAM for long files.
# We pre-split anything over this threshold into chunks before transcribing.
CHUNK_THRESHOLD_S = 1200   # 20 minutes
CHUNK_SIZE_S = 600          # 10-minute chunks


class WhisperEngine(TranscriptionEngine):
    def __init__(self, model_size: str = "small"):
        self._model_size = model_size
        self._model = None

    def _load_model(self):
        if self._model is None:
            console.print(f"[cyan]Loading OpenAI Whisper model '{self._model_size}'...[/cyan]")
            import whisper
            self._model = whisper.load_model(self._model_size)
            console.print("[green]Model loaded.[/green]")

    def transcribe(self, audio_path: str) -> TranscriptResult:
        self._load_model()

        duration = _get_duration_s(audio_path)
        if duration and duration > CHUNK_THRESHOLD_S:
            console.print(
                f"[yellow]Audio is {duration/60:.0f} min — splitting into "
                f"{CHUNK_SIZE_S//60}-min chunks to avoid OOM.[/yellow]"
            )
            return self._transcribe_chunked(audio_path, duration)

        return self._transcribe_single(audio_path)

    def _transcribe_single(self, audio_path: str) -> TranscriptResult:
        console.print(f"[cyan]Transcribing with OpenAI Whisper ({self._model_size})...[/cyan]")
        try:
            result = self._model.transcribe(audio_path, fp16=False, word_timestamps=True)
        except MemoryError as e:
            raise MemoryError(
                "Ran out of RAM during transcription. "
                "Set WHISPER_BACKEND=faster-whisper in .env (uses ~4x less memory) "
                "or use a smaller model (WHISPER_MODEL=tiny)."
            ) from e

        segments = [
            {"start": s["start"], "end": s["end"], "text": s["text"]}
            for s in result.get("segments", [])
        ]
        return TranscriptResult(
            text=result["text"].strip(),
            language=result.get("language", ""),
            segments=segments,
        )

    def _transcribe_chunked(self, audio_path: str, duration: float) -> TranscriptResult:
        """Split audio into chunks via ffmpeg, transcribe each, concatenate."""
        all_text: list[str] = []
        all_segments: list[dict] = []
        detected_language = ""

        starts = list(range(0, int(duration), CHUNK_SIZE_S))
        with tempfile.TemporaryDirectory() as tmp_dir:
            for i, start in enumerate(starts):
                chunk_path = os.path.join(tmp_dir, f"chunk_{i:04d}.mp3")
                _ffmpeg_slice(audio_path, chunk_path, start, CHUNK_SIZE_S)

                console.print(
                    f"[cyan]Transcribing chunk {i+1}/{len(starts)} "
                    f"({start//60}–{min(start+CHUNK_SIZE_S, int(duration))//60} min)...[/cyan]"
                )
                try:
                    result = self._model.transcribe(chunk_path, fp16=False, word_timestamps=True)
                except MemoryError as e:
                    raise MemoryError(
                        f"Ran out of RAM on chunk {i+1}. "
                        "Set WHISPER_BACKEND=faster-whisper in .env or use WHISPER_MODEL=tiny."
                    ) from e

                if not detected_language:
                    detected_language = result.get("language", "")

                chunk_text = result["text"].strip()
                if chunk_text:
                    all_text.append(chunk_text)

                for seg in result.get("segments", []):
                    all_segments.append({
                        "start": seg["start"] + start,
                        "end": seg["end"] + start,
                        "text": seg["text"],
                    })

        return TranscriptResult(
            text=" ".join(all_text),
            language=detected_language,
            segments=all_segments,
        )


def _get_duration_s(audio_path: str) -> float | None:
    """Use ffprobe to get audio duration in seconds."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                audio_path,
            ],
            capture_output=True, text=True, timeout=15,
        )
        return float(result.stdout.strip())
    except Exception:
        return None


def _ffmpeg_slice(src: str, dst: str, start_s: int, duration_s: int) -> None:
    """Extract a time slice from an audio file using ffmpeg."""
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-ss", str(start_s),
            "-t", str(duration_s),
            "-i", src,
            "-acodec", "copy",
            dst,
        ],
        capture_output=True, check=True, timeout=120,
    )
