"""tests/routers/test_extract_errors.py — POST /extract 에러 매핑 검증.

서비스 레이어를 mocking 하여 Router 가 (1) 새 예외 → HTTPException 매핑,
(2) X-Error-Code 헤더 노출, (3) retryable 1회 재시도, (4) 캐시 히트 시 guard 우회를 한다.
"""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import yt_dlp_guard
from app.services.yt_dlp_errors import YtDlpClassifiedError, YtDlpErrorClass
from app.services.yt_dlp_guard import CircuitOpenError


VALID_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
VIDEO_ID = "dQw4w9WgXcQ"


@pytest.fixture(autouse=True)
def _reset_guard():
    yt_dlp_guard._reset_state_for_tests()
    yield
    yt_dlp_guard._reset_state_for_tests()


@pytest.fixture
def client(monkeypatch):
    """cache_get 은 None, cache_set 은 더미 UUID 를 반환하도록 기본 설정."""
    async def _cache_get(_url):
        return None

    async def _cache_set(**kwargs):
        return "00000000-0000-0000-0000-000000000001"

    monkeypatch.setattr("app.routers.extract.cache_get", _cache_get)
    monkeypatch.setattr("app.routers.extract.cache_set", _cache_set)
    return TestClient(app, raise_server_exceptions=False)


# ── URL 유효성 ───────────────────────────────────────────────────


def test_invalid_url_returns_400(client):
    res = client.post("/extract", json={"youtube_url": "https://example.com/foo"})
    assert res.status_code == 400
    assert res.headers.get("X-Error-Code") == "INVALID_URL"


# ── ErrorClass → HTTPException 매핑 ──────────────────────────────


def _patch_pipeline_to_raise(exc):
    """run_guarded 이 호출하는 fn 이 항상 exc 를 raise 하도록 만든다."""
    async def fake_run_guarded(video_id, fn):
        raise exc

    return patch("app.routers.extract.run_guarded", side_effect=fake_run_guarded)


def test_youtube_bot_check_returns_503(client):
    exc = YtDlpClassifiedError(YtDlpErrorClass.YOUTUBE_BOT_CHECK, "bot check")
    with _patch_pipeline_to_raise(exc):
        res = client.post("/extract", json={"youtube_url": VALID_URL})
    assert res.status_code == 503
    assert res.headers.get("X-Error-Code") == "YOUTUBE_BOT_CHECK"


def test_rate_limit_returns_429(client):
    exc = YtDlpClassifiedError(YtDlpErrorClass.RATE_LIMIT, "429")
    with _patch_pipeline_to_raise(exc):
        res = client.post("/extract", json={"youtube_url": VALID_URL})
    assert res.status_code == 429
    assert res.headers.get("X-Error-Code") == "RATE_LIMIT"


def test_video_unavailable_returns_400(client):
    exc = YtDlpClassifiedError(YtDlpErrorClass.VIDEO_UNAVAILABLE, "private")
    with _patch_pipeline_to_raise(exc):
        res = client.post("/extract", json={"youtube_url": VALID_URL})
    assert res.status_code == 400
    assert res.headers.get("X-Error-Code") == "VIDEO_UNAVAILABLE"


def test_auth_required_returns_401(client):
    exc = YtDlpClassifiedError(YtDlpErrorClass.AUTH_REQUIRED, "cookies-from-browser")
    with _patch_pipeline_to_raise(exc):
        res = client.post("/extract", json={"youtube_url": VALID_URL})
    assert res.status_code == 401
    assert res.headers.get("X-Error-Code") == "AUTH_REQUIRED"


def test_circuit_open_error_returns_503_with_circuit_open_code(client):
    with _patch_pipeline_to_raise(CircuitOpenError("open")):
        res = client.post("/extract", json={"youtube_url": VALID_URL})
    assert res.status_code == 503
    assert res.headers.get("X-Error-Code") == "CIRCUIT_OPEN"


def test_pipeline_timeout_returns_504(client):
    with _patch_pipeline_to_raise(asyncio.TimeoutError()):
        res = client.post("/extract", json={"youtube_url": VALID_URL})
    assert res.status_code == 504
    assert res.headers.get("X-Error-Code") == "PIPELINE_TIMEOUT"


# ── Circuit pre-check ───────────────────────────────────────────


def test_circuit_open_blocks_before_pipeline(client):
    """is_circuit_open() 이 True 일 때 run_guarded 호출 전에 503 반환."""
    called = {"n": 0}

    async def fake_run_guarded(video_id, fn):
        called["n"] += 1
        return ({"title": "", "channel_name": "", "thumbnail_url": ""}, [], None)

    with patch("app.routers.extract.is_circuit_open", return_value=True), \
         patch("app.routers.extract.run_guarded", side_effect=fake_run_guarded):
        res = client.post("/extract", json={"youtube_url": VALID_URL})

    assert res.status_code == 503
    assert res.headers.get("X-Error-Code") == "CIRCUIT_OPEN"
    assert called["n"] == 0


# ── retryable 재시도 ───────────────────────────────────────────


def test_network_timeout_retries_once_then_fails_500(client):
    """NETWORK_TIMEOUT 두 번 연속이면 INTERNAL_ERROR 500."""
    call_count = {"n": 0}
    exc = YtDlpClassifiedError(YtDlpErrorClass.NETWORK_TIMEOUT, "read timed out")

    async def fake_run_guarded(video_id, fn):
        call_count["n"] += 1
        raise exc

    with patch("app.routers.extract.run_guarded", side_effect=fake_run_guarded), \
         patch("app.routers.extract.settings.ytdlp_backoff_seconds", 0):
        res = client.post("/extract", json={"youtube_url": VALID_URL})

    assert res.status_code == 500
    assert res.headers.get("X-Error-Code") == "INTERNAL_ERROR"
    assert call_count["n"] == 2  # 1차 + retry 1


def test_retryable_error_uses_configured_retry_count_and_backoff(client, monkeypatch):
    """retryable 에러는 설정된 횟수와 backoff 값을 사용한다."""
    call_count = {"n": 0}
    sleeps = []
    exc = YtDlpClassifiedError(YtDlpErrorClass.NETWORK_TIMEOUT, "read timed out")

    async def fake_run_guarded(video_id, fn):
        call_count["n"] += 1
        raise exc

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr("app.routers.extract.settings.ytdlp_retry_count", 2)
    monkeypatch.setattr("app.routers.extract.settings.ytdlp_backoff_seconds", 0.25)

    with patch("app.routers.extract.run_guarded", side_effect=fake_run_guarded), \
         patch("app.routers.extract.asyncio.sleep", side_effect=fake_sleep):
        res = client.post("/extract", json={"youtube_url": VALID_URL})

    assert res.status_code == 500
    assert res.headers.get("X-Error-Code") == "INTERNAL_ERROR"
    assert call_count["n"] == 3  # 1차 + retry 2
    assert sleeps == [0.25, 0.25]


def test_network_timeout_retry_succeeds_returns_200(client):
    """1회 retry 후 성공 → 200."""
    call_count = {"n": 0}

    async def fake_run_guarded(video_id, fn):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise YtDlpClassifiedError(YtDlpErrorClass.NETWORK_TIMEOUT, "timeout")
        return (
            {"title": "T", "channel_name": "C", "thumbnail_url": "http://t"},
            [],
            None,
        )

    with patch("app.routers.extract.run_guarded", side_effect=fake_run_guarded), \
         patch("app.routers.extract.settings.ytdlp_backoff_seconds", 0):
        res = client.post("/extract", json={"youtube_url": VALID_URL})

    assert res.status_code == 200
    assert call_count["n"] == 2
    body = res.json()
    assert body["video_id"] == VIDEO_ID
    assert body["cached"] is False


# ── 캐시 히트 ─────────────────────────────────────────────────────


def test_cache_hit_skips_guard(monkeypatch):
    """캐시 히트 시 run_guarded / circuit 진입하지 않는다."""
    cached_payload = {
        "id": "11111111-1111-1111-1111-111111111111",
        "title": "Cached Title",
        "channel_name": "Cached Channel",
        "thumbnail_url": "http://thumb",
        "chords": [],
        "lyrics": None,
    }

    async def _cache_get(_url):
        return cached_payload

    async def _cache_set(**kwargs):
        return "should-not-be-called"

    monkeypatch.setattr("app.routers.extract.cache_get", _cache_get)
    monkeypatch.setattr("app.routers.extract.cache_set", _cache_set)

    guard_called = {"n": 0}
    circuit_called = {"n": 0}

    async def fake_run_guarded(video_id, fn):
        guard_called["n"] += 1
        return ({}, [], None)

    def fake_circuit():
        circuit_called["n"] += 1
        return False

    client = TestClient(app, raise_server_exceptions=False)
    with patch("app.routers.extract.run_guarded", side_effect=fake_run_guarded), \
         patch("app.routers.extract.is_circuit_open", side_effect=fake_circuit):
        res = client.post("/extract", json={"youtube_url": VALID_URL})

    assert res.status_code == 200
    body = res.json()
    assert body["cached"] is True
    assert body["title"] == "Cached Title"
    assert guard_called["n"] == 0
    assert circuit_called["n"] == 0
