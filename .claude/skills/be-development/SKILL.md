---
name: be-development
description: "ChordLens BE 개발 가이드. FastAPI 라우터/서비스/모델 구현, Supabase 비동기 연동, 오디오 파이프라인(yt-dlp + basic-pitch) 작업, 에러 처리 패턴 참조 시 사용."
---

# BE Development Guide

## 프로젝트 구조

```
app/
├── routers/       # HTTP 엔드포인트 — 라우터만, 비즈니스 로직 금지
├── services/      # 비즈니스 로직 — Supabase, 외부 API, 오디오 처리
├── models/        # Pydantic 스키마 — request/response 정의
├── core/          # 설정 (pydantic-settings)
└── db.py          # Supabase AsyncClient 초기화
```

## 레이어 규칙

### Router (`app/routers/`)

```python
# ✅ 올바른 패턴
@router.post("/extract", response_model=ExtractResponse)
async def extract_chords(request: ExtractRequest):
    if not is_valid_youtube_url(request.youtube_url):
        raise HTTPException(status_code=400, detail="유효하지 않은 YouTube URL입니다.")
    metadata, chords, lyrics = await some_service.process(request.youtube_url)
    return ExtractResponse(...)

# ❌ 금지 패턴 — Router에서 DB 직접 접근
@router.get("/results")
async def get_results():
    db = get_supabase()
    res = await db.table("chord_results").select("*").execute()  # 금지
```

### Service (`app/services/`)

```python
# ✅ 올바른 패턴 — 비즈니스 로직
async def cache_get(video_url: str) -> dict | None:
    db = get_supabase()
    res = await db.table("chord_results").select("*").eq("video_url", video_url) \
        .order("created_at", desc=True).limit(1).execute()
    return res.data[0] if res.data else None

# ❌ 금지 패턴 — Service에서 HTTP 예외
def process():
    raise HTTPException(status_code=500)  # 금지 — Router에서 catch해서 raise
```

## Supabase 비동기 패턴

Supabase 클라이언트는 `AsyncClient`다. 모든 DB 호출에 `await` 필수.

```python
from app.db import get_supabase

async def some_query():
    db = get_supabase()
    # 단건 조회
    res = await db.table("chord_results").select("*").eq("id", record_id).single().execute()
    # 다건 조회
    res = await db.table("chord_results").select("*").order("created_at", desc=True).execute()
    # 삽입
    res = await db.table("chord_results").insert({...}).execute()
    return res.data
```

## 오디오 파이프라인

```
yt-dlp (extract_audio) → MP3 → basic-pitch (recognize_chords) → ChordItem[]
```

임시 파일은 성공/실패 무관하게 `finally` 블록에서 정리:

```python
mp3_path = None
try:
    mp3_path, metadata = extract_audio(youtube_url)
    chords = recognize_chords(mp3_path)
    return metadata, chords
finally:
    cleanup_files(mp3_path)
```

블로킹 파이프라인은 스레드 풀에서 실행:

```python
metadata, chords = await asyncio.wait_for(
    asyncio.to_thread(_run_pipeline, youtube_url),
    timeout=60,
)
```

## 에러 처리 패턴

| 에러 | 상태코드 | Router에서 처리 |
|------|----------|----------------|
| 유효하지 않은 URL | 400 | `is_valid_youtube_url()` 후 raise |
| 비공개/접근 불가 영상 | 400 | `VideoUnavailableError` catch |
| 타임아웃 | 504 | `asyncio.TimeoutError` catch |
| 파이프라인 실패 | 500 | 일반 `Exception` catch |

## Pydantic 모델 패턴

```python
from pydantic import BaseModel
from typing import Optional, List
import uuid

class NewRequest(BaseModel):
    field: str

class NewResponse(BaseModel):
    id: uuid.UUID
    result: str
    optional_field: Optional[str] = None  # Optional은 None 기본값 필수
    items: List[SomeItem] = []            # List는 빈 리스트 기본값
```

## 테스트 패턴

```python
# tests/services/test_xxx.py
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_정상_케이스():
    with patch("app.services.cache.get_supabase") as mock_db:
        mock_db.return_value.table.return_value.select.return_value...execute = AsyncMock(
            return_value=MagicMock(data=[{...}])
        )
        result = await cache_get("https://youtube.com/...")
        assert result is not None
```

실행: `python -m pytest tests/ -v`
