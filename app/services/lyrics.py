import os
import re
import glob
from app.services.audio import TEMP_DIR

# 가사로 보기 어려운 메타 텍스트 패턴 (음향 효과, 박수 등)
_NOISE_PATTERN = re.compile(r"^\[.*?\]$|^\(.*?\)$", re.IGNORECASE)

# VTT 타임스탬프: 00:00:12.340 또는 0:12.340
_VTT_TIMESTAMP = re.compile(r"(\d+):(\d{2}):(\d{2})\.\d+")


def _vtt_to_seconds(ts: str) -> float:
    m = _VTT_TIMESTAMP.match(ts)
    if not m:
        return 0.0
    h, minute, sec = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return h * 3600 + minute * 60 + sec


def _seconds_to_time_str(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 60}:{total % 60:02d}"


def _parse_vtt(vtt_path: str) -> list[dict]:
    """VTT 파일을 파싱해 [{time, text}] 리스트를 반환한다."""
    with open(vtt_path, encoding="utf-8") as f:
        content = f.read()

    lines = []
    # 큐 블록: 타임스탬프 라인 다음에 텍스트
    blocks = re.split(r"\n{2,}", content.strip())

    for block in blocks:
        block_lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not block_lines:
            continue

        # 타임스탬프 라인 탐색
        ts_line = next((l for l in block_lines if "-->" in l), None)
        if not ts_line:
            continue

        start_ts = ts_line.split("-->")[0].strip()
        seconds = _vtt_to_seconds(start_ts)

        # 타임스탬프 라인 이후의 텍스트 수집
        ts_idx = block_lines.index(ts_line)
        text_parts = block_lines[ts_idx + 1:]

        # HTML 태그 제거 (<c>, <i> 등 VTT 인라인 태그)
        text = " ".join(
            re.sub(r"<[^>]+>", "", part) for part in text_parts
        ).strip()

        if not text or _NOISE_PATTERN.match(text):
            continue

        lines.append({"time": _seconds_to_time_str(seconds), "text": text})

    # 동일 time에 중복 항목 제거 (자동 자막이 같은 줄을 여러 큐에 나누는 경우)
    seen_times: dict[str, str] = {}
    deduped = []
    for item in lines:
        t = item["time"]
        if t in seen_times:
            # 이미 등록된 time이면 텍스트가 더 길 때만 교체
            if len(item["text"]) > len(seen_times[t]):
                seen_times[t] = item["text"]
                deduped = [d for d in deduped if d["time"] != t]
                deduped.append(item)
        else:
            seen_times[t] = item["text"]
            deduped.append(item)

    return deduped


def extract_lyrics(video_id: str) -> list[dict] | None:
    """extract_audio() 가 이미 저장한 VTT 파일을 파싱해 가사 리스트를 반환한다.

    자막 다운로드는 extract_audio() 에서 오디오와 함께 처리하므로
    여기서는 파일 탐색·파싱만 수행한다.
    """
    # VTT 파일 탐색: 언어 우선순위 → 없으면 아무 VTT나 사용
    all_vtt = glob.glob(f"{TEMP_DIR}/{video_id}*.vtt")
    print(f"[lyrics] 전체 VTT 파일: {all_vtt}", flush=True)

    # audio.py에서 이미 원본 언어만 다운로드했으므로 첫 번째 파일 사용
    vtt_path = all_vtt[0] if all_vtt else None

    print(f"[lyrics] VTT 파일: {vtt_path}", flush=True)

    if not vtt_path or not os.path.exists(vtt_path):
        print("[lyrics] 자막 파일 없음 → None 반환", flush=True)
        return None

    try:
        result = _parse_vtt(vtt_path) or None
        print(f"[lyrics] 파싱 결과 ({len(result) if result else 0}줄): {result[:3] if result else None}", flush=True)
        return result
    except Exception as e:
        print(f"[lyrics] VTT 파싱 실패: {e}", flush=True)
        return None
    finally:
        # VTT 임시 파일 정리
        for f in glob.glob(f"{TEMP_DIR}/{video_id}*.vtt"):
            try:
                os.remove(f)
            except OSError:
                pass
