"""OpenAI text-to-speech adapter with safe input chunking."""

from pathlib import Path

from openai import OpenAI


class OpenAITTSProvider:
    name = "openai-tts"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini-tts", voice: str = "alloy") -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.voice = voice

    def synthesize(self, text: str, output_path: str) -> str:
        if not text.strip():
            raise ValueError("TTS input cannot be empty")
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        chunks = self._chunks(text)
        if len(chunks) == 1:
            self._write_chunk(chunks[0], path)
            return str(path)
        paths = []
        for index, chunk in enumerate(chunks, start=1):
            chunk_path = path.with_name(f"{path.stem}_{index}{path.suffix}")
            self._write_chunk(chunk, chunk_path)
            paths.append(chunk_path)
        self._concat_mp3(paths, path)
        for chunk_path in paths:
            chunk_path.unlink(missing_ok=True)
        return str(path)

    def _write_chunk(self, text: str, path: Path) -> None:
        with self.client.audio.speech.with_streaming_response.create(
            model=self.model,
            voice=self.voice,
            input=text,
            response_format="mp3",
        ) as response:
            response.stream_to_file(path)

    @staticmethod
    def _chunks(text: str, max_chars: int = 4000) -> list[str]:
        words = text.split()
        chunks: list[str] = []
        current: list[str] = []
        size = 0
        for word in words:
            extra = len(word) + (1 if current else 0)
            if current and size + extra > max_chars:
                chunks.append(" ".join(current))
                current, size = [], 0
            current.append(word)
            size += extra
        if current:
            chunks.append(" ".join(current))
        return chunks

    @staticmethod
    def _concat_mp3(paths: list[Path], output: Path) -> None:
        import shutil
        import subprocess
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("FFmpeg is required to concatenate TTS chunks")
        manifest = output.with_suffix(".tts.txt")
        manifest.write_text("\n".join(f"file '{p.resolve().as_posix()}'" for p in paths), encoding="utf-8")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(manifest), "-c", "copy", str(output)],
            check=True,
            capture_output=True,
            text=True,
        )
        manifest.unlink(missing_ok=True)
