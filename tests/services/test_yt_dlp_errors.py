"""tests/services/test_yt_dlp_errors.py — yt-dlp 에러 메시지 분류 검증."""
import pytest

from app.services.yt_dlp_errors import (
    NON_RETRYABLE,
    YtDlpClassifiedError,
    YtDlpErrorClass,
    classify,
)


# ── classify ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "msg,expected",
    [
        # YOUTUBE_BOT_CHECK
        (
            "ERROR: Sign in to confirm you're not a bot. This helps protect our community.",
            YtDlpErrorClass.YOUTUBE_BOT_CHECK,
        ),
        ("confirm you're not a bot", YtDlpErrorClass.YOUTUBE_BOT_CHECK),
        # RATE_LIMIT
        ("ERROR: HTTP Error 429: Too Many Requests", YtDlpErrorClass.RATE_LIMIT),
        ("Too Many Requests from this IP", YtDlpErrorClass.RATE_LIMIT),
        # VIDEO_UNAVAILABLE
        ("Private video. Sign in if you've been granted access.", YtDlpErrorClass.VIDEO_UNAVAILABLE),
        ("This video is unavailable", YtDlpErrorClass.VIDEO_UNAVAILABLE),
        ("Video unavailable", YtDlpErrorClass.VIDEO_UNAVAILABLE),
        ("Sign in to confirm your age", YtDlpErrorClass.VIDEO_UNAVAILABLE),
        ("This video is age-restricted", YtDlpErrorClass.VIDEO_UNAVAILABLE),
        # AUTH_REQUIRED
        ("Use --cookies-from-browser to pass cookies", YtDlpErrorClass.AUTH_REQUIRED),
        # NETWORK_TIMEOUT
        ("The read operation timed out", YtDlpErrorClass.NETWORK_TIMEOUT),
        ("Connection reset by peer", YtDlpErrorClass.NETWORK_TIMEOUT),
        ("Temporary failure in name resolution", YtDlpErrorClass.NETWORK_TIMEOUT),
    ],
)
def test_classify_known_messages(msg, expected):
    assert classify(msg) == expected


def test_classify_unknown_message():
    assert classify("ERROR: 정체불명의 오류 abcxyz") == YtDlpErrorClass.UNKNOWN


def test_classify_empty_message():
    assert classify("") == YtDlpErrorClass.UNKNOWN


def test_classify_case_insensitive():
    """대소문자 무시 매칭."""
    assert classify("PRIVATE VIDEO") == YtDlpErrorClass.VIDEO_UNAVAILABLE
    assert classify("Sign In To Confirm You're Not A Bot") == YtDlpErrorClass.YOUTUBE_BOT_CHECK
    assert classify("HTTP error 429") == YtDlpErrorClass.RATE_LIMIT


# ── NON_RETRYABLE 집합 ───────────────────────────────────────────


def test_non_retryable_set_contents():
    assert YtDlpErrorClass.YOUTUBE_BOT_CHECK in NON_RETRYABLE
    assert YtDlpErrorClass.RATE_LIMIT in NON_RETRYABLE
    assert YtDlpErrorClass.VIDEO_UNAVAILABLE in NON_RETRYABLE
    assert YtDlpErrorClass.AUTH_REQUIRED in NON_RETRYABLE
    assert YtDlpErrorClass.NETWORK_TIMEOUT not in NON_RETRYABLE
    assert YtDlpErrorClass.UNKNOWN not in NON_RETRYABLE


# ── YtDlpClassifiedError ─────────────────────────────────────────


def test_classified_error_attributes():
    e = YtDlpClassifiedError(YtDlpErrorClass.RATE_LIMIT, "HTTP Error 429")
    assert e.error_class == YtDlpErrorClass.RATE_LIMIT
    assert e.original == "HTTP Error 429"
    assert "HTTP Error 429" in str(e)


def test_classified_error_is_exception():
    e = YtDlpClassifiedError(YtDlpErrorClass.UNKNOWN, "x")
    assert isinstance(e, Exception)
