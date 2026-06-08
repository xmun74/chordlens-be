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
    # 실제 운지 데이터 (chords-db position). FE가 다이어그램을 그대로 렌더한다.
    # frets/fingers: 6현(저음 E현→고음 e현 순), -1=뮤트, 0=개방. base_fret: 다이어그램 시작 프렛.
    # barres: 바레가 걸리는 (base_fret 기준 상대) 프렛 목록. 구 캐시 데이터는 빈 배열/기본값.
    frets: List[int] = []
    fingers: List[int] = []
    base_fret: int = 1
    barres: List[int] = []


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
