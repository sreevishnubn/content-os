"""Turn a ContentScript JSON file plus image assets into a narrated MP4."""

import argparse
import json
import os

from app.integrations.openai_tts import OpenAITTSProvider
from app.integrations.renderer import FFmpegRenderer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("script_json")
    parser.add_argument("--images", nargs="+", required=True)
    parser.add_argument("--output", default="data/output/video.mp4")
    parser.add_argument("--voice", default=os.getenv("CONTENTOS_TTS_VOICE", "alloy"))
    args = parser.parse_args()

    with open(args.script_json, encoding="utf-8") as handle:
        script = json.load(handle)

    narration = " ".join(
        [script["hook"]]
        + [section["narration"] for section in script.get("sections", [])]
        + [script.get("closing", "")]
    ).strip()
    if not narration:
        raise ValueError("Script contains no narration")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for narration")

    audio_path = os.path.splitext(args.output)[0] + ".mp3"
    OpenAITTSProvider(api_key=api_key, voice=args.voice).synthesize(narration, audio_path)
    output = FFmpegRenderer().render(args.images, audio_path, args.output)
    print(output)


if __name__ == "__main__":
    main()
