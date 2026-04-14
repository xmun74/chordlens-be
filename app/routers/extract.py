import re
from fastapi import APIRouter, HTTPException
from app.models.chord import ExtractRequest, ExtractResponse
from app.services.audio import extract_audio, convert_to_wav, cleanup_files
from app.services.chord import recognize_chords

router = APIRouter()

YOUTUBE_URL_PATTERN = re.compile(
    r"^(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[\w\-]{11}"
)


def is_valid_youtube_url(url: str) -> bool:
    return bool(YOUTUBE_URL_PATTERN.match(url))


@router.post("/extract", response_model=ExtractResponse)
async def extract_chords(request: ExtractRequest):
    if not is_valid_youtube_url(request.youtube_url):
        raise HTTPException(status_code=400, detail="유효하지 않은 YouTube URL입니다.")

    mp3_path = None
    wav_path = None

    try:
        mp3_path, metadata = extract_audio(request.youtube_url)
        wav_path = convert_to_wav(mp3_path)
        chords = recognize_chords(wav_path)

        # Phase 2에서 Supabase 캐시 저장/조회 추가 예정
        import uuid
        result_id = uuid.uuid4()

        return ExtractResponse(
            id=result_id,
            title=metadata["title"],
            channel_name=metadata["channel_name"],
            thumbnail_url=metadata["thumbnail_url"],
            chords=chords,
            cached=False,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"처리 중 오류가 발생했습니다: {str(e)}")
    finally:
        cleanup_files(mp3_path, wav_path)
