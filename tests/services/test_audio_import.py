# tests/services/test_audio_import.py
"""yt-dlp[default] 의존성 정상 설치 및 audio 모듈 import 검증."""


def test_audio_module_imports():
    """app.services.audio 모듈에서 핵심 심볼이 ImportError 없이 import 되어야 한다."""
    from app.services.audio import (
        extract_audio,
        VideoUnavailableError,
        cleanup_files,
    )

    assert callable(extract_audio)
    assert callable(cleanup_files)
    assert issubclass(VideoUnavailableError, Exception)


def test_yt_dlp_version_truthy():
    """yt-dlp 패키지 버전이 truthy 한 문자열로 노출되어야 한다."""
    import yt_dlp.version

    assert yt_dlp.version.__version__
    assert isinstance(yt_dlp.version.__version__, str)
