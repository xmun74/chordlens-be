import re
from fastapi import HTTPException
from app.db import get_supabase
from app.models.chord import ChordItem, LyricLine
from app.models.result import ResultListItem, ResultListResponse, ResultDetail


def _parse_video_id(video_url: str) -> str:
    m = re.search(r"(?:v=|youtu\.be/)([\w\-]{11})", video_url)
    return m.group(1) if m else "unknown"


async def list_results(limit: int = 20, offset: int = 0) -> ResultListResponse:
    supabase = get_supabase()
    try:
        response = await (
            supabase.table("chord_results")
            .select("id, video_url, title, channel_name, thumbnail_url, created_at", count="exact")
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=500, detail="failed to fetch results")

    items = [
        ResultListItem(
            id=str(row["id"]),
            video_url=row["video_url"],
            title=row.get("title"),
            channel_name=row.get("channel_name"),
            thumbnail_url=row.get("thumbnail_url"),
            created_at=row["created_at"],
        )
        for row in (response.data or [])
    ]
    total = response.count if response.count is not None else len(items)
    return ResultListResponse(items=items, total=total)


async def get_result(id: str) -> ResultDetail:
    supabase = get_supabase()
    try:
        response = await (
            supabase.table("chord_results")
            .select("id, video_url, title, channel_name, thumbnail_url, chords, lyrics")
            .eq("id", id)
            .limit(1)
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=500, detail="failed to fetch result")

    if not response.data:
        raise HTTPException(status_code=404, detail="result not found")

    row = response.data[0]
    return ResultDetail(
        id=str(row["id"]),
        video_id=_parse_video_id(row["video_url"]),
        title=row["title"],
        channel_name=row["channel_name"],
        thumbnail_url=row["thumbnail_url"],
        chords=[ChordItem(**c) for c in (row["chords"] or [])],
        lyrics=[LyricLine(**l) for l in row["lyrics"]] if row.get("lyrics") else None,
        cached=True,
    )
