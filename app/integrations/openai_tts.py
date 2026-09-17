"""OpenAI text-to-speech adapter."""

from pathlib import Path

from openai import OpenAI


class OpenAITTSProvider:
    name = "openai-tts"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini-tts", voice: str = "alloy") -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.voice = voice

    def synthesize(self, text: str, output_path: str) -> str:
        if len(text) > 4096:
            raise ValueError("OpenAI TTS input must be chunked to 4096 characters or less")
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.client.audio.speech.with_streaming_response.create(
            model=self.model,
            voice=self.voice,
            input=text,
            response_format="mp3",
        ) as response:
            response.stream_to_file(path)
        return str(path)
