from supabase import AsyncClient, acreate_client

_client: AsyncClient | None = None


async def init_supabase(url: str, key: str) -> None:
    global _client
    _client = await acreate_client(url, key)


def get_supabase() -> AsyncClient:
    if _client is None:
        raise RuntimeError("Supabase 클라이언트가 초기화되지 않았습니다.")
    return _client
