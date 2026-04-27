from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from app.models.chord import ChordItem, LyricLine


class ResultListItem(BaseModel):
    id: str
    video_url: str
    title: str | None
    channel_name: str | None
    thumbnail_url: str | None
    created_at: datetime


class ResultListResponse(BaseModel):
    items: list[ResultListItem]
    total: int


class ResultDetail(BaseModel):
    id: str
    video_id: str
    title: str
    channel_name: str
    thumbnail_url: str
    chords: list[ChordItem]
    lyrics: Optional[list[LyricLine]] = None
    cached: bool
