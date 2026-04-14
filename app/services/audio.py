import os
import glob
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


def _detect_subtitle_langs(youtube_url: str) -> list[str]:
    """영상의 원본 자막 언어를 감지한다.

    수동 자막이 있으면 그 언어들을 반환하고,
    없으면 영상의 원본 언어(automatic_captions 기준)를 반환한다.
    번역 자막(예: 일본어 영상의 ko 자동번역)은 포함하지 않는다.
    """
    opts = {"skip_download": True, "quiet": True, "no_warnings": True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)

        # 수동 자막 우선
        manual = list((info.get("subtitles") or {}).keys())
        if manual:
            print(f"[audio] 수동 자막 언어: {manual}", flush=True)
            return manual

        # 자동 자막 - 영상의 원본 언어만 사용 (번역본 제외)
        orig_lang = info.get("language") or ""
        auto_langs = list((info.get("automatic_captions") or {}).keys())
        print(f"[audio] 원본 언어: {orig_lang!r}, 자동 자막 목록: {auto_langs}", flush=True)

        if orig_lang and orig_lang in auto_langs:
            return [orig_lang]

        # language 필드가 없을 때: 번역 자막 코드를 제외하고 첫 번째 선택
        # YouTube 번역 자막은 일반적으로 2~5자 언어 코드 + "-" 없이 나오므로
        # 영상 제목/설명 언어와 교차 검증하기 어렵다 → 첫 번째 자동 자막 사용
        if auto_langs:
            # en이 있으면 우선, 없으면 첫 번째
            return ["en"] if "en" in auto_langs else [auto_langs[0]]

    except Exception as e:
        print(f"[audio] 자막 언어 감지 실패 (무시): {e}", flush=True)

    return ["en"]  # 감지 실패 시 영어 기본값


def extract_audio(youtube_url: str) -> tuple[str, dict]:
    """YouTube URL에서 MP3와 자막(VTT)을 함께 추출하고 영상 메타데이터를 반환한다.

    자막은 원본 언어로만 다운로드한다 (번역 자막 제외).

    Returns:
        (mp3_path, metadata) 튜플
        자막은 {TEMP_DIR}/{video_id}.{lang}.vtt 로 저장되며 lyrics.py에서 읽어간다.

    Raises:
        VideoUnavailableError: 비공개·연령제한·삭제된 영상
        RuntimeError: 그 외 다운로드 실패
    """
    _ensure_temp_dir()

    # 원본 자막 언어 감지 (429 방지를 위해 가벼운 info-only 호출)
    subtitle_langs = _detect_subtitle_langs(youtube_url)

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
        "ignoreerrors": True,
        "quiet": True,
        "no_warnings": True,
    }

    if subtitle_langs:
        ydl_opts.update({
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": subtitle_langs,
            "subtitlesformat": "vtt",
        })

    info = None
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
    except yt_dlp.utils.DownloadError as e:
        msg = str(e).lower()
        if any(keyword in msg for keyword in _UNAVAILABLE_KEYWORDS):
            raise VideoUnavailableError(str(e)) from e
        raise RuntimeError(str(e)) from e

    if not info:
        raise VideoUnavailableError("비공개 또는 접근할 수 없는 영상입니다.")

    video_id = info["id"]
    all_files = glob.glob(f"{TEMP_DIR}/{video_id}*")
    print(f"[audio] 다운로드 후 파일 목록: {all_files}", flush=True)

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
    """MP3를 autochord 입력용 WAV(22050Hz, mono)로 변환한다."""
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
