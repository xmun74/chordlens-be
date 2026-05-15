from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    supabase_url: str
    supabase_key: str
    allowed_origin: str = "http://localhost:3000"
    youtube_cookies_path: str = ""

    # ── yt-dlp Webshare proxy 설정 ───────────────────────────
    # Webshare country/sticky-session 포맷은 env 값이 책임지고,
    # 백엔드는 이 URL을 yt-dlp proxy 옵션으로 그대로 전달한다.
    ytdlp_proxy_url: str = ""
    ytdlp_proxy_country: str = ""
    ytdlp_use_cookies: bool = False

    # ── yt-dlp 봇 감지 방어 설정 ──────────────────────────────
    # 동시에 yt-dlp를 호출할 수 있는 워커 수. 기본 1로 직렬화한다.
    yt_dlp_concurrency: int = 1
    # 봇 감지 발생 시 서킷이 열려있는 시간 (초). 기본 30분.
    youtube_circuit_open_seconds: float = 1800.0
    # yt-dlp 한 호출의 소켓 타임아웃 (초).
    yt_dlp_timeout_seconds: float = 60.0
    # single-flight inflight future await 시 최대 대기 시간 (초).
    inflight_wait_timeout_seconds: float = 120.0
    # retryable yt-dlp 에러의 추가 재시도 횟수.
    ytdlp_retry_count: int = 1
    # retryable yt-dlp 에러 재시도 전 대기 시간 (초).
    ytdlp_backoff_seconds: float = 1.0


settings = Settings()
