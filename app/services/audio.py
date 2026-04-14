import os
import subprocess
import yt_dlp


TEMP_DIR = "/tmp/codelens"

# 비공개/연령제한 영상 판별 키워드
_UNAVAILABLE_KEYWORDS = (
    "private video",
    "video unavailable",
    "this video is unavailable",
    "sign in to confirm your age",
    "age-restricted",
)


class VideoUnavailableError(Exception):
    """비공개·연령제한·삭제된 영상에 대한 예외"""


def _ensure_temp_dir():
    os.makedirs(TEMP_DIR, exist_ok=True)


def extract_audio(youtube_url: str) -> tuple[str, dict]:
    """YouTube URL에서 MP3를 추출하고 영상 메타데이터를 반환한다.

    Returns:
        (mp3_path, metadata) 튜플

    Raises:
        VideoUnavailableError: 비공개·연령제한·삭제된 영상
        RuntimeError: 그 외 다운로드 실패
    """
    _ensure_temp_dir()

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": f"{TEMP_DIR}/%(id)s.%(ext)s",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
    except yt_dlp.utils.DownloadError as e:
        msg = str(e).lower()
        if any(keyword in msg for keyword in _UNAVAILABLE_KEYWORDS):
            raise VideoUnavailableError(str(e)) from e
        raise RuntimeError(str(e)) from e

    # postprocessor 적용 후 실제 파일 경로 확인
    video_id = info["id"]
    mp3_path = f"{TEMP_DIR}/{video_id}.mp3"
    if not os.path.exists(mp3_path):
        raise RuntimeError(f"MP3 파일 생성 실패: {mp3_path}")

    metadata = {
        "title": info.get("title", ""),
        "channel_name": info.get("uploader", ""),
        "thumbnail_url": info.get("thumbnail", ""),
    }

    return mp3_path, metadata


def convert_to_wav(mp3_path: str) -> str:
    """MP3를 autochord 입력용 WAV(22050Hz, mono)로 변환한다.

    Raises:
        RuntimeError: ffmpeg 변환 실패
    """
    wav_path = mp3_path.replace(".mp3", ".wav")
    result = subprocess.run(
        ["ffmpeg", "-i", mp3_path, "-ar", "22050", "-ac", "1", wav_path, "-y"],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 변환 실패: {result.stderr.decode()}")
    return wav_path


def cleanup_files(*paths: str):
    """임시 파일을 삭제한다. 성공·실패 무관하게 항상 호출한다."""
    for path in paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except OSError:
            pass
