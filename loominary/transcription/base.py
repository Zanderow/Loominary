"""Abstract TranscriptionEngine base class."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class TranscriptResult:
    text: str
    language: str
    segments: list = field(default_factory=list)


class TranscriptionEngine(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str) -> TranscriptResult:
        """Transcribe audio file at audio_path and return a TranscriptResult."""
        ...
