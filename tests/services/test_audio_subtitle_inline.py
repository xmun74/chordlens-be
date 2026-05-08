"""tests/services/test_audio_subtitle_inline.py

extract_audio() 가 yt-dlp 를 1회만 호출하고, DownloadError 를 ErrorClass 로 분류해
YtDlpClassifiedError 로 raise 하는지 검증한다.
"""
import os
from unittest.mock import MagicMock, patch

import pytest

from app.services import audio
from app.services.audio import extract_audio
from app.services.yt_dlp_errors import YtDlpClassifiedError, YtDlpErrorClass


class _FakeYDL:
    """yt_dlp.YoutubeDL 컨텍스트 매니저 페이크. extract_info 호출을 카운트한다."""

    def __init__(self, *, info=None, raise_exc=None):
        self._info = info
        self._raise_exc = raise_exc
        self.extract_info_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def extract_info(self, url, download=True):
        self.extract_info_calls += 1
        if self._raise_exc is not None:
            raise self._raise_exc
        return self._info


@pytest.fixture
def fake_mp3(tmp_path):
    """extract_audio 후 존재 확인을 만족시키기 위해 더미 mp3 파일을 만든다."""
    audio.TEMP_DIR = str(tmp_path)
    video_id = "abcdEFGH123"
    mp3_path = tmp_path / f"{video_id}.mp3"
    mp3_path.write_bytes(b"dummy")
    return video_id, str(mp3_path)


def test_extract_audio_calls_yt_dlp_once(fake_mp3):
    video_id, _ = fake_mp3
    fake = _FakeYDL(
        info={
            "id": video_id,
            "title": "Sample Title",
            "uploader": "Sample Channel",
            "thumbnail": "http://thumb",
        }
    )

    factory_calls = 0

    def factory(opts):
        nonlocal factory_calls
        factory_calls += 1
        # 자막 화이트리스트가 옵션에 포함됨을 검증.
        assert opts.get("writesubtitles") is True
        assert opts.get("writeautomaticsub") is True
        assert "en" in opts.get("subtitleslangs", [])
        assert opts.get("subtitlesformat") == "vtt"
        return fake

    with patch("app.services.audio.yt_dlp.YoutubeDL", side_effect=factory):
        mp3_path, metadata = extract_audio("https://www.youtube.com/watch?v=" + video_id)

    assert factory_calls == 1
    assert fake.extract_info_calls == 1
    assert metadata == {
        "title": "Sample Title",
        "channel_name": "Sample Channel",
        "thumbnail_url": "http://thumb",
    }
    assert os.path.exists(mp3_path)


def test_extract_audio_bot_check_raises_classified():
    import yt_dlp

    err = yt_dlp.utils.DownloadError(
        "ERROR: [youtube] xxx: Sign in to confirm you're not a bot."
    )
    fake = _FakeYDL(raise_exc=err)

    with patch("app.services.audio.yt_dlp.YoutubeDL", return_value=fake):
        with pytest.raises(YtDlpClassifiedError) as ei:
            extract_audio("https://www.youtube.com/watch?v=abcdEFGH123")

    assert ei.value.error_class == YtDlpErrorClass.YOUTUBE_BOT_CHECK


def test_extract_audio_private_video_raises_classified():
    import yt_dlp

    err = yt_dlp.utils.DownloadError("ERROR: Private video. Sign in if you've been granted access.")
    fake = _FakeYDL(raise_exc=err)

    with patch("app.services.audio.yt_dlp.YoutubeDL", return_value=fake):
        with pytest.raises(YtDlpClassifiedError) as ei:
            extract_audio("https://www.youtube.com/watch?v=abcdEFGH123")

    assert ei.value.error_class == YtDlpErrorClass.VIDEO_UNAVAILABLE


def test_extract_audio_rate_limit_raises_classified():
    import yt_dlp

    err = yt_dlp.utils.DownloadError("ERROR: HTTP Error 429: Too Many Requests")
    fake = _FakeYDL(raise_exc=err)

    with patch("app.services.audio.yt_dlp.YoutubeDL", return_value=fake):
        with pytest.raises(YtDlpClassifiedError) as ei:
            extract_audio("https://www.youtube.com/watch?v=abcdEFGH123")

    assert ei.value.error_class == YtDlpErrorClass.RATE_LIMIT


def test_extract_audio_unknown_error_classified_as_unknown():
    import yt_dlp

    err = yt_dlp.utils.DownloadError("ERROR: 알 수 없는 오류 abc")
    fake = _FakeYDL(raise_exc=err)

    with patch("app.services.audio.yt_dlp.YoutubeDL", return_value=fake):
        with pytest.raises(YtDlpClassifiedError) as ei:
            extract_audio("https://www.youtube.com/watch?v=abcdEFGH123")

    assert ei.value.error_class == YtDlpErrorClass.UNKNOWN


def test_extract_audio_none_info_classified_as_unavailable(tmp_path):
    audio.TEMP_DIR = str(tmp_path)
    fake = _FakeYDL(info=None)

    with patch("app.services.audio.yt_dlp.YoutubeDL", return_value=fake):
        with pytest.raises(YtDlpClassifiedError) as ei:
            extract_audio("https://www.youtube.com/watch?v=abcdEFGH123")

    assert ei.value.error_class == YtDlpErrorClass.VIDEO_UNAVAILABLE
