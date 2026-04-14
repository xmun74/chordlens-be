import os
import autochord
from typing import List
from app.models.chord import ChordItem


# autochord가 지원하는 장조 12 + 단조 12 = 24개 코드
# Harte 표기 → 응답 표기 매핑
_CHORD_MAP = {
    "A:maj": "A",   "A#:maj": "A#", "B:maj": "B",
    "C:maj": "C",   "C#:maj": "C#", "D:maj": "D",
    "D#:maj": "D#", "E:maj": "E",   "F:maj": "F",
    "F#:maj": "F#", "G:maj": "G",   "G#:maj": "G#",
    "A:min": "Am",  "A#:min": "A#m","B:min": "Bm",
    "C:min": "Cm",  "C#:min": "C#m","D:min": "Dm",
    "D#:min": "D#m","E:min": "Em",  "F:min": "Fm",
    "F#:min": "F#m","G:min": "Gm",  "G#:min": "G#m",
}


def _normalize_chord(chord: str) -> str | None:
    """Harte 표기 코드명을 응답 표기로 변환한다. 미지원 코드는 None 반환."""
    return _CHORD_MAP.get(chord)


def _seconds_to_time_str(seconds: float) -> str:
    """초를 'M:SS' 형식 문자열로 변환한다."""
    total = int(seconds)
    return f"{total // 60}:{total % 60:02d}"


def recognize_chords(wav_path: str) -> List[ChordItem]:
    """WAV 파일에서 코드를 인식하고 정규화된 ChordItem 리스트를 반환한다.

    처리 규칙:
    - 무음(N) 제거
    - 24개 코드 외 미지원 코드 제거
    - 인접 중복 병합 (무음 구간 사이 동일 코드는 재등록)

    Raises:
        FileNotFoundError: WAV 파일이 존재하지 않는 경우
        RuntimeError: autochord 인식 실패
    """
    if not os.path.exists(wav_path):
        raise FileNotFoundError(f"WAV 파일을 찾을 수 없습니다: {wav_path}")

    try:
        raw_chords = autochord.recognize(wav_path)
    except Exception as e:
        raise RuntimeError(f"코드 인식 실패: {e}") from e

    items: List[ChordItem] = []
    prev_chord = None

    for start, _end, chord in raw_chords:
        # 무음 → 이전 코드 초기화 (무음 이후 동일 코드 재등록 허용)
        if chord == "N" or not chord:
            prev_chord = None
            continue

        normalized = _normalize_chord(chord)

        # 지원 범위(장조·단조 24개) 밖의 코드 무시
        if normalized is None:
            continue

        # 인접 중복 병합
        if normalized == prev_chord:
            continue

        items.append(ChordItem(time=_seconds_to_time_str(start), chord=normalized))
        prev_chord = normalized

    return items
