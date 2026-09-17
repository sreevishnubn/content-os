from app.integrations.openai_tts import OpenAITTSProvider
from app.integrations.renderer import FFmpegRenderer
from app.integrations.youtube_oauth import SCOPES


def test_tts_chunks_long_text():
    chunks = OpenAITTSProvider._chunks("word " * 2000)
    assert len(chunks) > 1
    assert all(len(chunk) <= 4000 for chunk in chunks)


def test_renderer_contract():
    assert FFmpegRenderer.name == "ffmpeg"


def test_youtube_scopes_include_upload_and_analytics():
    assert any(scope.endswith("youtube.upload") for scope in SCOPES)
    assert any(scope.endswith("yt-analytics.readonly") for scope in SCOPES)
