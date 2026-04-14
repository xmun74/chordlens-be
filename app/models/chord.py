from pydantic import BaseModel, HttpUrl
from typing import List
import uuid


class ExtractRequest(BaseModel):
    youtube_url: str


class ChordItem(BaseModel):
    time: str
    chord: str


class ExtractResponse(BaseModel):
    id: uuid.UUID
    title: str
    channel_name: str
    thumbnail_url: str
    chords: List[ChordItem]
    cached: bool
