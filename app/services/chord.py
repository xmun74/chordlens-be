import autochord
from typing import List
from app.models.chord import ChordItem


def seconds_to_time_str(seconds: float) -> str:
    """초를 'M:SS' 형식 문자열로 변환한다."""
    total_seconds = int(seconds)
    minutes = total_seconds // 60
    secs = total_seconds % 60
    return f"{minutes}:{secs:02d}"


def recognize_chords(wav_path: str) -> List[ChordItem]:
    """WAV 파일에서 코드를 인식하고 정규화된 ChordItem 리스트를 반환한다."""
    raw_chords = autochord.recognize(wav_path)
    # raw_chords: [(start_time, end_time, chord_name), ...]

    items: List[ChordItem] = []
    prev_chord = None

    for start, end, chord in raw_chords:
        # 무음(N) 제거
        if chord == "N" or not chord:
            prev_chord = None
            continue

        # 인접 중복 병합
        if chord == prev_chord:
            continue

        items.append(ChordItem(time=seconds_to_time_str(start), chord=chord))
        prev_chord = chord

    return items
