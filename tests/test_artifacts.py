from pathlib import Path

from app.integrations.artifacts import materialize_artifact


def test_materialize_local_artifact(tmp_path):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"test")
    path, temporary = materialize_artifact(str(source))
    assert path == str(source)
    assert temporary is False


def test_materialize_http_artifact(monkeypatch, tmp_path):
    class FakeResponse:
        def __init__(self):
            self._read_once = False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size):
            if self._read_once:
                return b""
            self._read_once = True
            return b"test"

    monkeypatch.setattr("app.integrations.artifacts.urlopen", lambda *args, **kwargs: FakeResponse())
    path, temporary = materialize_artifact("https://example.com/video.mp4")
    try:
        assert Path(path).read_bytes() == b"test"
        assert temporary is True
    finally:
        Path(path).unlink(missing_ok=True)
