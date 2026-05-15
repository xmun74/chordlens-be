"""YouTube 오디오/자막 추출 서비스.

yt-dlp 호출은 1회만 수행하며(자막은 인라인으로 함께 받음), DownloadError 는 모두
`YtDlpClassifiedError` 로 래핑해 라우터로 전파한다.
"""
import os
import glob
import yt_dlp

from app.core.config import settings
from app.core.logging import get_logger
from app.services.yt_dlp_errors import (
    YtDlpClassifiedError,
    YtDlpErrorClass,
    classify,
)

logger = get_logger(__name__)

TEMP_DIR = "/tmp/chordlens"

# 자막 화이트리스트 — yt-dlp 는 존재하지 않는 언어를 무시하므로 안전.
# 화이트리스트 외 언어 영상은 자막 없이 진행된다 (트레이드오프, TRD §11 참조).
_SUBTITLE_LANGS = ["en", "ko", "ja", "es"]


class _YtDlpLogCapture:
    """yt-dlp가 ignoreerrors=True로 삼킨 에러 메시지를 분류용으로 보관한다."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def debug(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        self.messages.append(str(msg))

    def error(self, msg: str) -> None:
        self.messages.append(str(msg))

    def text(self) -> str:
        return "\n".join(self.messages)


# ── 하위 호환 alias ─────────────────────────────────────
# 기존 코드(라우터/테스트)가 import 하던 `VideoUnavailableError` 를 유지한다.
# 새 코드는 `YtDlpClassifiedError` 를 직접 catch 하는 것을 권장.
class VideoUnavailableError(Exception):
    """비공개·연령제한·삭제된 영상에 대한 예외 (deprecated alias).

    내부적으로 `YtDlpClassifiedError(VIDEO_UNAVAILABLE)` 로 통일되었으며,
    하위 호환을 위해 클래스 자체는 유지한다. 라우터에서는 `YtDlpClassifiedError` 를
    `error_class == VIDEO_UNAVAILABLE` 로 분기하라.
    """


def _ensure_temp_dir() -> None:
    os.makedirs(TEMP_DIR, exist_ok=True)


def extract_audio(youtube_url: str) -> tuple[str, dict]:
    """YouTube URL에서 MP3와 자막(VTT)을 함께 추출하고 메타데이터를 반환한다.

    yt-dlp 는 단 한 번만 호출된다 — 자막 화이트리스트(`_SUBTITLE_LANGS`)에 해당하는
    자막이 있으면 함께 다운로드되며, lyrics.py 가 그 vtt 파일을 파싱한다.

    Returns:
        (mp3_path, metadata) 튜플.

    Raises:
        YtDlpClassifiedError: yt-dlp 가 분류 가능한 에러로 실패한 경우.
        RuntimeError: MP3 후처리 실패 등 그 외 오류.
    """
    _ensure_temp_dir()
    ytdlp_log_capture = _YtDlpLogCapture()

    ydl_opts: dict = {
        "format": "bestaudio/best",
        "outtmpl": f"{TEMP_DIR}/%(id)s.%(ext)s",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "quiet": True,
        "no_warnings": True,
        # 자막 인라인 다운로드 — 별도 yt-dlp 호출을 제거.
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": _SUBTITLE_LANGS,
        "subtitlesformat": "vtt",
        # 자막 429 등 비치명적 에러 시 오디오 추출 계속 진행.
        # 오디오 자체 실패 시 info=None 반환 → 아래 체크에서 처리.
        "ignoreerrors": True,
        # 소켓 타임아웃 — yt-dlp 가 hang 되는 것을 방지.
        "socket_timeout": settings.yt_dlp_timeout_seconds,
        "logger": ytdlp_log_capture,
    }
    if settings.ytdlp_proxy_url:
        ydl_opts["proxy"] = settings.ytdlp_proxy_url

    if settings.ytdlp_use_cookies and settings.youtube_cookies_path and os.path.exists(
        settings.youtube_cookies_path
    ):
        ydl_opts["cookiefile"] = settings.youtube_cookies_path
    else:
        ydl_opts["nocookies"] = True

    info = None
    try:
        logger.info(
            "stage=audio_extract result=start proxy_enabled=%s proxy_country=%s cookies_enabled=%s",
            bool(settings.ytdlp_proxy_url),
            settings.ytdlp_proxy_country or "",
            bool(ydl_opts.get("cookiefile")),
        )
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        error_class = classify(msg)
        logger.warning(
            "stage=audio_extract result=download_error error_class=%s msg=%s",
            error_class.value,
            msg,
        )
        raise YtDlpClassifiedError(error_class, msg) from e

    if not info:
        # ignoreerrors=True 일 때 yt-dlp 가 None 을 반환하는 경로 — 영상 접근 불가로 간주.
        logged_error = ytdlp_log_capture.text()
        error_class = classify(logged_error)
        logger.warning(
            "stage=audio_extract result=no_info error_class=%s url=%s",
            error_class.value,
            youtube_url,
        )
        if error_class != YtDlpErrorClass.UNKNOWN:
            raise YtDlpClassifiedError(error_class, logged_error)
        raise YtDlpClassifiedError(
            YtDlpErrorClass.VIDEO_UNAVAILABLE,
            "비공개 또는 접근할 수 없는 영상입니다.",
        )

    video_id = info["id"]
    all_files = glob.glob(f"{TEMP_DIR}/{video_id}*")
    logger.info(
        "stage=audio_extract result=ok video_id=%s files=%d",
        video_id,
        len(all_files),
    )

    mp3_path = f"{TEMP_DIR}/{video_id}.mp3"
    if not os.path.exists(mp3_path):
        raise RuntimeError(f"MP3 파일 생성 실패: {mp3_path}")

    metadata = {
        "title": info.get("title", ""),
        "channel_name": info.get("uploader", ""),
        "thumbnail_url": info.get("thumbnail", ""),
        "duration": info.get("duration"),
    }

    return mp3_path, metadata


def cleanup_files(*paths: str) -> None:
    """임시 파일을 삭제한다. 성공·실패 무관하게 항상 호출한다."""
    for path in paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except OSError:
            pass
