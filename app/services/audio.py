import os
import subprocess
import tempfile
import yt_dlp


TEMP_DIR = "/tmp/codelens"


def ensure_temp_dir():
    os.makedirs(TEMP_DIR, exist_ok=True)


def extract_audio(youtube_url: str) -> tuple[str, dict]:
    """YouTube URL에서 MP3를 추출하고 영상 메타데이터를 반환한다."""
    ensure_temp_dir()

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

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=True)

    video_id = info["id"]
    mp3_path = f"{TEMP_DIR}/{video_id}.mp3"

    metadata = {
        "title": info.get("title", ""),
        "channel_name": info.get("uploader", ""),
        "thumbnail_url": info.get("thumbnail", ""),
    }

    return mp3_path, metadata


def convert_to_wav(mp3_path: str) -> str:
    """MP3를 autochord 입력용 WAV로 변환한다."""
    wav_path = mp3_path.replace(".mp3", ".wav")
    subprocess.run(
        ["ffmpeg", "-i", mp3_path, "-ar", "22050", "-ac", "1", wav_path, "-y"],
        check=True,
        capture_output=True,
    )
    return wav_path


def cleanup_files(*paths: str):
    """임시 파일을 삭제한다."""
    for path in paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except OSError:
            pass
