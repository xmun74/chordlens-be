from typing import Optional
from app.db import get_supabase
from app.models.chord import ChordItem, LyricLine

TABLE = "chord_results"


async def cache_get(video_url: str) -> Optional[dict]:
    """video_url 기준으로 캐시를 조회한다. 최신 1건 반환, 없으면 None."""
    client = get_supabase()
    result = (
        await client.table(TABLE)
        .select("id, title, channel_name, thumbnail_url, chords, lyrics")
        .eq("video_url", video_url)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if not result.data:
        return None

    row = result.data[0]
    return {
        "id": row["id"],
        "title": row["title"],
        "channel_name": row["channel_name"],
        "thumbnail_url": row["thumbnail_url"],
        "chords": [ChordItem(**c) for c in row["chords"]],
        "lyrics": [LyricLine(**l) for l in row["lyrics"]] if row.get("lyrics") else None,
    }


async def cache_set(
    video_url: str,
    title: str,
    channel_name: str,
    thumbnail_url: str,
    chords: list[ChordItem],
    lyrics: list[LyricLine] | None,
) -> str:
    """분석 결과를 Supabase에 저장하고 생성된 UUID를 반환한다."""
    client = get_supabase()
    result = (
        await client.table(TABLE)
        .insert(
            {
                "video_url": video_url,
                "title": title,
                "channel_name": channel_name,
                "thumbnail_url": thumbnail_url,
                "chords": [c.model_dump() for c in chords],
                "lyrics": [l.model_dump() for l in lyrics] if lyrics else None,
            }
        )
        .execute()
    )

    return result.data[0]["id"]
