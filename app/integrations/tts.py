"""Text-to-speech boundary for faceless narration."""

from abc import ABC, abstractmethod


class TTSProvider(ABC):
    name: str

    @abstractmethod
    def synthesize(self, text: str, output_path: str) -> str:
        raise NotImplementedError


class FileTTSProvider(TTSProvider):
    """Testing/local provider that expects a pre-generated audio file path."""

    name = "file"

    def synthesize(self, text: str, output_path: str) -> str:
        raise RuntimeError(
            "FileTTSProvider is a contract-only adapter. Configure a real TTS provider before production rendering."
        )
