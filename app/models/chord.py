from pydantic import BaseModel
from typing import List, Literal, Optional
import uuid


class ExtractRequest(BaseModel):
    youtube_url: str


class ChordItem(BaseModel):
    time: str
    chord: str
    fret: int = 0                  # 구 캐시 데이터 호환 — 기본값 open position
    voicing: Literal["open", "barre"] = "open"  # 구 캐시 데이터 호환


class LyricLine(BaseModel):
    time: str
    text: str


class ExtractResponse(BaseModel):
    id: uuid.UUID
    video_id: str
    title: str
    channel_name: str
    thumbnail_url: str
    chords: List[ChordItem]
    lyrics: Optional[List[LyricLine]] = None
    cached: bool
