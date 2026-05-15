"""POST /extract — YouTube URL → 코드 추출 파이프라인.

서비스 레이어가 raise 하는 정형 예외를 HTTP 응답으로 매핑한다.
새 에러 코드는 `X-Error-Code` 응답 헤더로도 노출된다 (FE 호환성을 위해 detail 은 문자열 유지).
"""
import asyncio
import re

from fastapi import APIRouter, HTTPException

from app.core.logging import get_logger
from app.models.chord import ExtractRequest, ExtractResponse, LyricLine
from app.services.audio import cleanup_files, extract_audio
from app.services.cache import cache_get, cache_set
from app.services.chord import recognize_chords
from app.services.lyrics import extract_lyrics
from app.services.yt_dlp_errors import (
    NON_RETRYABLE,
    YtDlpClassifiedError,
    YtDlpErrorClass,
)
from app.services.yt_dlp_guard import (
    CircuitOpenError,
    is_circuit_open,
    run_guarded,
)

router = APIRouter()
logger = get_logger(__name__)

PIPELINE_TIMEOUT = 60  # 초 — TRD §4-1 기준
_RETRY_BACKOFF_SEC = 1.0

YOUTUBE_URL_PATTERN = re.compile(
    r"^(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[\w\-]{11}"
)


def is_valid_youtube_url(url: str) -> bool:
    return bool(YOUTUBE_URL_PATTERN.match(url))


def _parse_video_id(url: str) -> str:
    m = re.search(r"(?:v=|youtu\.be/)([\w\-]{11})", url)
    return m.group(1) if m else "unknown"


def _run_pipeline(youtube_url: str) -> tuple:
    """블로킹 파이프라인을 동기 함수로 묶어 스레드 풀에서 실행한다."""
    mp3_path = None
    video_id = _parse_video_id(youtube_url)
    clean_url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        mp3_path, metadata = extract_audio(clean_url)
        chords = recognize_chords(mp3_path)

        raw_lyrics = extract_lyrics(video_id)
        lyrics = [LyricLine(**l) for l in raw_lyrics] if raw_lyrics else None

        return metadata, chords, lyrics
    finally:
        cleanup_files(mp3_path)


def _http_error(status_code: int, error_code: str, message: str) -> HTTPException:
    """detail 은 문자열로 유지(FE 호환), error_code 는 헤더로 노출."""
    return HTTPException(
        status_code=status_code,
        detail=message,
        headers={"X-Error-Code": error_code},
    )


# ── YtDlpErrorClass → (status, error_code, default message) ──────
_ERROR_CLASS_MAP: dict[YtDlpErrorClass, tuple[int, str, str]] = {
    YtDlpErrorClass.YOUTUBE_BOT_CHECK: (
        503,
        "YOUTUBE_BOT_CHECK",
        "YouTube 봇 감지로 일시적으로 처리할 수 없습니다.",
    ),
    YtDlpErrorClass.RATE_LIMIT: (
        429,
        "RATE_LIMIT",
        "YouTube 요청이 일시적으로 제한되었습니다.",
    ),
    YtDlpErrorClass.VIDEO_UNAVAILABLE: (
        400,
        "VIDEO_UNAVAILABLE",
        "비공개 또는 접근할 수 없는 영상입니다.",
    ),
    YtDlpErrorClass.AUTH_REQUIRED: (
        401,
        "AUTH_REQUIRED",
        "쿠키 또는 로그인이 필요한 영상입니다.",
    ),
}


def _map_classified(e: YtDlpClassifiedError) -> HTTPException:
    if e.error_class in _ERROR_CLASS_MAP:
        status, code, default_msg = _ERROR_CLASS_MAP[e.error_class]
        return _http_error(status, code, e.original or default_msg)
    # NETWORK_TIMEOUT/UNKNOWN 이 retry 후에도 실패하면 500.
    return _http_error(500, "INTERNAL_ERROR", e.original or "처리 중 오류가 발생했습니다.")


async def _run_pipeline_with_timeout(youtube_url: str):
    return await asyncio.wait_for(
        asyncio.to_thread(_run_pipeline, youtube_url),
        timeout=PIPELINE_TIMEOUT,
    )


@router.post("/extract", response_model=ExtractResponse)
async def extract_chords(request: ExtractRequest):
    if not is_valid_youtube_url(request.youtube_url):
        raise _http_error(400, "INVALID_URL", "유효하지 않은 YouTube URL입니다.")

    video_id = _parse_video_id(request.youtube_url)

    # ── 캐시 우선 ──
    cached = await cache_get(request.youtube_url)
    if cached:
        return ExtractResponse(
            id=cached["id"],
            video_id=video_id,
            title=cached["title"],
            channel_name=cached["channel_name"],
            thumbnail_url=cached["thumbnail_url"],
            chords=cached["chords"],
            lyrics=cached["lyrics"],
            cached=True,
        )

    # ── 캐시 미스 ── 서킷 브레이커 우선 차단
    if is_circuit_open():
        raise _http_error(
            503,
            "CIRCUIT_OPEN",
            "서버 단 보호가 활성화되어 있습니다. 잠시 후 다시 시도해주세요.",
        )

    async def _do_pipeline():
        return await _run_pipeline_with_timeout(request.youtube_url)

    metadata = chords = lyrics = None
    try:
        metadata, chords, lyrics = await run_guarded(video_id, _do_pipeline)
    except YtDlpClassifiedError as e:
        if e.error_class in NON_RETRYABLE:
            raise _map_classified(e)
        # retryable — 1회만 in-process 재시도 (지수 백오프 1s).
        logger.info(
            "stage=extract_retry video_id=%s error_class=%s",
            video_id,
            e.error_class.value,
        )
        await asyncio.sleep(_RETRY_BACKOFF_SEC)
        try:
            metadata, chords, lyrics = await run_guarded(video_id, _do_pipeline)
        except YtDlpClassifiedError as e2:
            if e2.error_class in NON_RETRYABLE:
                raise _map_classified(e2)
            raise _http_error(500, "INTERNAL_ERROR", e2.original)
        except CircuitOpenError:
            raise _http_error(
                503,
                "CIRCUIT_OPEN",
                "서버 단 보호가 활성화되어 있습니다. 잠시 후 다시 시도해주세요.",
            )
        except asyncio.TimeoutError:
            raise _http_error(504, "PIPELINE_TIMEOUT", "처리 시간이 초과되었습니다.")
        except Exception as e2:
            raise _http_error(500, "INTERNAL_ERROR", f"처리 중 오류가 발생했습니다: {e2}")
    except CircuitOpenError:
        raise _http_error(
            503,
            "CIRCUIT_OPEN",
            "서버 단 보호가 활성화되어 있습니다. 잠시 후 다시 시도해주세요.",
        )
    except asyncio.TimeoutError:
        raise _http_error(504, "PIPELINE_TIMEOUT", "처리 시간이 초과되었습니다.")
    except HTTPException:
        raise
    except Exception as e:
        raise _http_error(500, "INTERNAL_ERROR", f"처리 중 오류가 발생했습니다: {e}")

    # ── 결과 저장 ──
    result_id = await cache_set(
        video_url=request.youtube_url,
        title=metadata["title"],
        channel_name=metadata["channel_name"],
        thumbnail_url=metadata["thumbnail_url"],
        chords=chords,
        lyrics=lyrics,
        duration=metadata.get("duration"),
    )

    return ExtractResponse(
        id=result_id,
        video_id=video_id,
        title=metadata["title"],
        channel_name=metadata["channel_name"],
        thumbnail_url=metadata["thumbnail_url"],
        chords=chords,
        lyrics=lyrics,
        cached=False,
    )
