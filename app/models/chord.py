from pydantic import BaseModel
from typing import List, Optional
import uuid


class ExtractRequest(BaseModel):
    youtube_url: str


class ChordItem(BaseModel):
    time: str
    chord: str


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
