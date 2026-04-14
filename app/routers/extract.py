import re
import uuid
import asyncio
from fastapi import APIRouter, HTTPException
from app.models.chord import ExtractRequest, ExtractResponse
from app.services.audio import extract_audio, convert_to_wav, cleanup_files, VideoUnavailableError
from app.services.chord import recognize_chords
from app.services.cache import cache_get, cache_set

router = APIRouter()

PIPELINE_TIMEOUT = 60  # 초 — TRD §4-1 기준

YOUTUBE_URL_PATTERN = re.compile(
    r"^(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[\w\-]{11}"
)


def is_valid_youtube_url(url: str) -> bool:
    return bool(YOUTUBE_URL_PATTERN.match(url))


def _run_pipeline(youtube_url: str) -> tuple:
    """블로킹 파이프라인을 동기 함수로 묶어 스레드 풀에서 실행한다."""
    mp3_path = None
    wav_path = None
    try:
        mp3_path, metadata = extract_audio(youtube_url)
        wav_path = convert_to_wav(mp3_path)
        chords = recognize_chords(wav_path)
        return metadata, chords
    finally:
        cleanup_files(mp3_path, wav_path)


@router.post("/extract", response_model=ExtractResponse)
async def extract_chords(request: ExtractRequest):
    if not is_valid_youtube_url(request.youtube_url):
        raise HTTPException(status_code=400, detail="유효하지 않은 YouTube URL입니다.")

    # 캐시 조회
    cached = await cache_get(request.youtube_url)
    if cached:
        return ExtractResponse(
            id=cached["id"],
            title=cached["title"],
            channel_name=cached["channel_name"],
            thumbnail_url=cached["thumbnail_url"],
            chords=cached["chords"],
            cached=True,
        )

    # 캐시 미스 — 파이프라인 실행
    try:
        metadata, chords = await asyncio.wait_for(
            asyncio.to_thread(_run_pipeline, request.youtube_url),
            timeout=PIPELINE_TIMEOUT,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="처리 시간이 초과되었습니다.")
    except VideoUnavailableError:
        raise HTTPException(status_code=400, detail="비공개 또는 접근할 수 없는 영상입니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"처리 중 오류가 발생했습니다: {str(e)}")

    # 결과 저장
    result_id = await cache_set(
        video_url=request.youtube_url,
        title=metadata["title"],
        channel_name=metadata["channel_name"],
        thumbnail_url=metadata["thumbnail_url"],
        chords=chords,
    )

    return ExtractResponse(
        id=result_id,
        title=metadata["title"],
        channel_name=metadata["channel_name"],
        thumbnail_url=metadata["thumbnail_url"],
        chords=chords,
        cached=False,
    )
