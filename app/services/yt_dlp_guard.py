"""yt-dlp 호출에 대한 동시성/single-flight/circuit breaker 가드.

세 가지 책임을 단일 진입점 `run_guarded()` 로 묶는다:
1. **Circuit breaker** — YOUTUBE_BOT_CHECK 발생 시 일정 시간 모든 신규 호출 차단.
2. **Single-flight** — 동일 video_id 동시 호출 시 fn 은 1회만 실행되고 두 호출 모두 같은 결과/예외를 받는다.
3. **Concurrency limit** — 프로세스 단위 세마포어로 yt-dlp 동시 호출을 제한.

상태는 모두 인메모리(프로세스 로컬). multi-instance 공유는 후속 PR로 분리.
"""
import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.core.config import settings
from app.core.logging import get_logger
from app.services.yt_dlp_errors import YtDlpClassifiedError, YtDlpErrorClass

T = TypeVar("T")
logger = get_logger(__name__)


class CircuitOpenError(Exception):
    """서킷 브레이커가 open 상태일 때 raise — 503 매핑 대상."""


# ── 전역 상태 — 프로세스 단위 ──────────────────────────────
_semaphore: asyncio.Semaphore | None = None
_inflight: dict[str, asyncio.Future] = {}
_circuit_opened_at: float | None = None
_circuit_lock = asyncio.Lock()


def _get_semaphore() -> asyncio.Semaphore:
    """세마포어 lazy 초기화 — 임포트 시점이 아닌 첫 사용 시점에 생성."""
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(settings.yt_dlp_concurrency)
    return _semaphore


def is_circuit_open() -> bool:
    """현재 서킷이 open 상태인지 반환. 만료 시 자동 reset."""
    global _circuit_opened_at
    if _circuit_opened_at is None:
        return False
    elapsed = time.monotonic() - _circuit_opened_at
    if elapsed >= settings.youtube_circuit_open_seconds:
        # 명시적 close — 가독성/디버깅을 위해 None으로 reset.
        _circuit_opened_at = None
        return False
    return True


async def trip_circuit() -> None:
    """서킷 브레이커를 open 한다 — YOUTUBE_BOT_CHECK 시 호출."""
    global _circuit_opened_at
    async with _circuit_lock:
        _circuit_opened_at = time.monotonic()
        logger.warning("stage=circuit_trip opened_at=%s", _circuit_opened_at)


async def reset_circuit() -> None:
    """테스트/운영용 명시적 close. 외부에서 호출할 일이 거의 없음."""
    global _circuit_opened_at
    async with _circuit_lock:
        _circuit_opened_at = None


async def run_guarded(video_id: str, fn: Callable[[], Awaitable[T]]) -> T:
    """가드된 yt-dlp 호출.

    동작:
    1. circuit open 이면 즉시 `CircuitOpenError`.
    2. 동일 video_id 가 이미 inflight 면 그 future 를 대기 (single-flight).
    3. 새 요청이면 future 등록 후 세마포어 획득 → fn() 실행.
    4. fn 이 `YtDlpClassifiedError(YOUTUBE_BOT_CHECK)` 를 raise 하면 자동으로 `trip_circuit()` 후 예외 전파.

    실패 시에도 future 는 항상 정리되며, 동시 호출자도 같은 예외를 받는다.
    """
    if is_circuit_open():
        raise CircuitOpenError("YouTube circuit breaker is open")

    # ── single-flight: 이미 inflight 라면 기존 future 대기 ──
    existing = _inflight.get(video_id)
    if existing is not None:
        logger.info("stage=guard_join video_id=%s", video_id)
        return await asyncio.wait_for(
            asyncio.shield(existing),
            timeout=settings.inflight_wait_timeout_seconds,
        )

    loop = asyncio.get_event_loop()
    future: asyncio.Future = loop.create_future()
    _inflight[video_id] = future

    try:
        async with _get_semaphore():
            try:
                result = await fn()
            except YtDlpClassifiedError as e:
                # BOT_CHECK 은 서킷을 trip — 동시 호출자도 같은 예외 수신.
                if e.error_class == YtDlpErrorClass.YOUTUBE_BOT_CHECK:
                    await trip_circuit()
                if not future.done():
                    future.set_exception(e)
                raise
            except Exception as e:
                if not future.done():
                    future.set_exception(e)
                raise
            else:
                if not future.done():
                    future.set_result(result)
                return result
    finally:
        # 동시 호출자가 future 를 await 중일 수 있으므로
        # set_result/set_exception 이후 안전하게 pop 한다.
        _inflight.pop(video_id, None)
        # 조인자가 없을 때 "Future exception was never retrieved" 경고를 막기 위해
        # 예외를 명시적으로 한 번 조회한다 (호출자는 이미 raise 로 받았다).
        if future.done() and not future.cancelled():
            try:
                future.exception()
            except asyncio.CancelledError:
                pass


# ── 테스트 헬퍼 ─────────────────────────────────────────
def _reset_state_for_tests() -> None:
    """단위 테스트 격리용 — 모듈 전역 상태 초기화."""
    global _semaphore, _circuit_opened_at
    _semaphore = None
    _circuit_opened_at = None
    _inflight.clear()
