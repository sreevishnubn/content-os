"""FFmpeg-based video renderer for deterministic faceless videos."""

import shutil
import subprocess
from pathlib import Path


class FFmpegRenderer:
    name = "ffmpeg"

    def render(self, image_paths: list[str], narration_path: str, output_path: str, *, seconds_per_image: int = 6) -> str:
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("FFmpeg is not installed or not available on PATH")
        if not image_paths:
            raise ValueError("At least one image is required")

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        manifest = output.with_suffix(".txt")
        lines = []
        for image in image_paths:
            lines.append(f"file '{Path(image).resolve().as_posix()}'")
            lines.append(f"duration {seconds_per_image}")
        lines.append(f"file '{Path(image_paths[-1]).resolve().as_posix()}'")
        manifest.write_text("\n".join(lines), encoding="utf-8")
        command = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(manifest),
            "-i", narration_path, "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(output),
        ]
        subprocess.run(command, check=True, capture_output=True, text=True)
        manifest.unlink(missing_ok=True)
        return str(output)
