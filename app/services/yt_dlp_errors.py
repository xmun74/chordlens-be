"""yt-dlp 에러 메시지를 정형화된 ErrorClass로 분류한다.

원본 메시지(yt_dlp.utils.DownloadError 의 str)에서 알려진 키워드를 부분일치로 검색해
`YtDlpErrorClass` 로 매핑한다. 라우터는 이 클래스 → HTTP 상태코드 매핑만 담당한다.
"""
from enum import Enum


class YtDlpErrorClass(str, Enum):
    YOUTUBE_BOT_CHECK = "youtube_bot_check"   # non-retryable, circuit-open trigger
    RATE_LIMIT = "rate_limit"                  # non-retryable
    VIDEO_UNAVAILABLE = "video_unavailable"    # non-retryable
    AUTH_REQUIRED = "auth_required"            # non-retryable
    NETWORK_TIMEOUT = "network_timeout"        # retryable
    UNKNOWN = "unknown"                        # retryable (보수적으로 1회만)


# non-retryable 클래스 집합 — Router가 retry 여부 판단에 사용한다.
NON_RETRYABLE: frozenset[YtDlpErrorClass] = frozenset(
    {
        YtDlpErrorClass.YOUTUBE_BOT_CHECK,
        YtDlpErrorClass.RATE_LIMIT,
        YtDlpErrorClass.VIDEO_UNAVAILABLE,
        YtDlpErrorClass.AUTH_REQUIRED,
    }
)

# 메시지 키워드 → 클래스 매핑 (소문자 부분일치).
# 우선순위: BOT_CHECK > RATE_LIMIT > VIDEO_UNAVAILABLE > AUTH_REQUIRED > NETWORK_TIMEOUT
# NOTE: "you're"의 아포스트로피는 yt-dlp가 U+2019(곡선)을 사용하므로
#       아포스트로피를 포함하지 않는 키워드로 매칭한다.
_KEYWORD_MAP: list[tuple[str, YtDlpErrorClass]] = [
    ("not a bot", YtDlpErrorClass.YOUTUBE_BOT_CHECK),
    ("http error 429", YtDlpErrorClass.RATE_LIMIT),
    ("too many requests", YtDlpErrorClass.RATE_LIMIT),
    ("private video", YtDlpErrorClass.VIDEO_UNAVAILABLE),
    ("video unavailable", YtDlpErrorClass.VIDEO_UNAVAILABLE),
    ("this video is unavailable", YtDlpErrorClass.VIDEO_UNAVAILABLE),
    ("sign in to confirm your age", YtDlpErrorClass.VIDEO_UNAVAILABLE),
    ("age-restricted", YtDlpErrorClass.VIDEO_UNAVAILABLE),
    ("use --cookies-from-browser", YtDlpErrorClass.AUTH_REQUIRED),
    ("read timed out", YtDlpErrorClass.NETWORK_TIMEOUT),
    ("the read operation timed out", YtDlpErrorClass.NETWORK_TIMEOUT),
    ("connection reset", YtDlpErrorClass.NETWORK_TIMEOUT),
    ("temporary failure in name resolution", YtDlpErrorClass.NETWORK_TIMEOUT),
]


def classify(msg: str) -> YtDlpErrorClass:
    """yt-dlp 원본 에러 메시지를 ErrorClass 로 분류한다. 알 수 없으면 UNKNOWN."""
    if not msg:
        return YtDlpErrorClass.UNKNOWN
    lower = msg.lower()
    for keyword, cls in _KEYWORD_MAP:
        if keyword in lower:
            return cls
    return YtDlpErrorClass.UNKNOWN


class YtDlpClassifiedError(Exception):
    """yt-dlp 에러를 ErrorClass와 함께 전파하는 예외.

    Service 레이어에서 raise, Router 레이어에서 catch → HTTPException 매핑.
    """

    def __init__(self, error_class: YtDlpErrorClass, original: str):
        super().__init__(original)
        self.error_class = error_class
        self.original = original

    def __repr__(self) -> str:  # 디버깅 가독성용
        return f"YtDlpClassifiedError({self.error_class.value}, {self.original!r})"
