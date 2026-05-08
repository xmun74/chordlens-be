"""tests/services/test_yt_dlp_guard.py — guard 모듈 동작 검증."""
import asyncio
from unittest.mock import patch

import pytest

from app.services import yt_dlp_guard
from app.services.yt_dlp_errors import YtDlpClassifiedError, YtDlpErrorClass
from app.services.yt_dlp_guard import (
    CircuitOpenError,
    is_circuit_open,
    run_guarded,
    trip_circuit,
)


@pytest.fixture(autouse=True)
def _reset_guard_state():
    """각 테스트 전후로 guard 모듈 전역 상태를 격리한다."""
    yt_dlp_guard._reset_state_for_tests()
    yield
    yt_dlp_guard._reset_state_for_tests()


# ── circuit breaker ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_circuit_initially_closed():
    assert is_circuit_open() is False


@pytest.mark.asyncio
async def test_trip_circuit_makes_open():
    await trip_circuit()
    assert is_circuit_open() is True


@pytest.mark.asyncio
async def test_circuit_open_blocks_run_guarded():
    await trip_circuit()

    async def fn():
        return "should not run"

    with pytest.raises(CircuitOpenError):
        await run_guarded("vid", fn)


@pytest.mark.asyncio
async def test_circuit_auto_closes_after_window():
    """monotonic 을 mock 해서 만료 시간을 흉내낸다."""
    await trip_circuit()
    assert is_circuit_open() is True

    # 31분 경과 — 30분 기본 윈도우(youtube_circuit_open_seconds=1800) 초과.
    fake_now = yt_dlp_guard._circuit_opened_at + 1801
    with patch.object(yt_dlp_guard.time, "monotonic", return_value=fake_now):
        assert is_circuit_open() is False
    # 명시적 reset 도 됐는지 확인
    assert yt_dlp_guard._circuit_opened_at is None


# ── single-flight ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_guarded_returns_fn_result():
    async def fn():
        return 42

    result = await run_guarded("vid", fn)
    assert result == 42


@pytest.mark.asyncio
async def test_single_flight_dedups_concurrent_calls():
    """동일 video_id 에 대한 두 동시 호출 → fn 은 1회만 실행."""
    call_count = 0
    started = asyncio.Event()
    release = asyncio.Event()

    async def fn():
        nonlocal call_count
        call_count += 1
        started.set()
        await release.wait()
        return "result"

    task1 = asyncio.create_task(run_guarded("same_vid", fn))
    await started.wait()
    # task1 이 fn 안에서 대기 중 — 같은 video_id 로 두 번째 호출.
    task2 = asyncio.create_task(run_guarded("same_vid", fn))
    await asyncio.sleep(0.05)
    release.set()

    r1, r2 = await asyncio.gather(task1, task2)
    assert r1 == r2 == "result"
    assert call_count == 1


@pytest.mark.asyncio
async def test_single_flight_propagates_exception_to_joiner():
    """첫 호출이 예외 raise 시 두 번째 호출도 같은 예외 수신."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def fn():
        started.set()
        await release.wait()
        raise YtDlpClassifiedError(YtDlpErrorClass.YOUTUBE_BOT_CHECK, "bot")

    task1 = asyncio.create_task(run_guarded("vid_x", fn))
    await started.wait()
    task2 = asyncio.create_task(run_guarded("vid_x", fn))
    await asyncio.sleep(0.05)
    release.set()

    with pytest.raises(YtDlpClassifiedError) as ei1:
        await task1
    with pytest.raises(YtDlpClassifiedError) as ei2:
        await task2
    assert ei1.value.error_class == YtDlpErrorClass.YOUTUBE_BOT_CHECK
    assert ei2.value.error_class == YtDlpErrorClass.YOUTUBE_BOT_CHECK


@pytest.mark.asyncio
async def test_inflight_cleared_after_success():
    async def fn():
        return 1

    await run_guarded("clear_vid", fn)
    assert "clear_vid" not in yt_dlp_guard._inflight


@pytest.mark.asyncio
async def test_inflight_cleared_after_exception():
    async def fn():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await run_guarded("clear_vid_err", fn)
    assert "clear_vid_err" not in yt_dlp_guard._inflight


# ── circuit auto-trip ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_youtube_bot_check_trips_circuit():
    async def fn():
        raise YtDlpClassifiedError(YtDlpErrorClass.YOUTUBE_BOT_CHECK, "bot")

    with pytest.raises(YtDlpClassifiedError):
        await run_guarded("trip_vid", fn)
    assert is_circuit_open() is True


@pytest.mark.asyncio
async def test_other_errors_do_not_trip_circuit():
    async def fn():
        raise YtDlpClassifiedError(YtDlpErrorClass.RATE_LIMIT, "429")

    with pytest.raises(YtDlpClassifiedError):
        await run_guarded("vid_429", fn)
    assert is_circuit_open() is False

    async def fn2():
        raise RuntimeError("network")

    with pytest.raises(RuntimeError):
        await run_guarded("vid_net", fn2)
    assert is_circuit_open() is False


# ── 세마포어 ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_semaphore_serializes_distinct_video_ids():
    """concurrency=1 일 때 서로 다른 video_id 두 호출이 직렬 실행됨을 검증."""
    in_flight_count = 0
    max_concurrent = 0
    barrier = asyncio.Event()

    async def fn():
        nonlocal in_flight_count, max_concurrent
        in_flight_count += 1
        max_concurrent = max(max_concurrent, in_flight_count)
        await asyncio.sleep(0.05)
        in_flight_count -= 1
        return "ok"

    task1 = asyncio.create_task(run_guarded("vid_a", fn))
    task2 = asyncio.create_task(run_guarded("vid_b", fn))
    await asyncio.gather(task1, task2)

    assert max_concurrent == 1
