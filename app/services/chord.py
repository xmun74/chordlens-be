import os
import numpy as np
from typing import List
from basic_pitch.inference import predict
from app.models.chord import ChordItem

_WINDOW_SEC = 1.0
_MIN_AMPLITUDE = 0.3
_SIMILARITY_THRESHOLD = 0.75

_ROOT_NAMES = ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']
_OPEN_STRING_PITCHES = frozenset({40, 45, 50, 55, 59, 64})  # E2, A2, D3, G3, B3, E4


def _build_chord_templates() -> dict:
    templates: dict = {}
    for i, root in enumerate(_ROOT_NAMES):
        chord_types = {
            root:           [0, 4, 7],
            f'{root}m':     [0, 3, 7],
            f'{root}7':     [0, 4, 7, 10],
            f'{root}maj7':  [0, 4, 7, 11],
            f'{root}m7':    [0, 3, 7, 10],
            f'{root}dim':   [0, 3, 6],
            f'{root}aug':   [0, 4, 8],
            f'{root}sus2':  [0, 2, 7],
            f'{root}sus4':  [0, 5, 7],
        }
        for name, ivs in chord_types.items():
            t = np.zeros(12)
            t[[(i + iv) % 12 for iv in ivs]] = 1
            templates[name] = t
    return templates


_TEMPLATES = _build_chord_templates()


def _chroma_to_chord(chroma: np.ndarray) -> str | None:
    norm = np.linalg.norm(chroma)
    if norm < 1e-6:
        return None
    unit = chroma / norm
    scores = {
        name: float(np.dot(unit, t / np.linalg.norm(t)))
        for name, t in _TEMPLATES.items()
    }
    best, score = max(scores.items(), key=lambda x: x[1])
    return best if score >= _SIMILARITY_THRESHOLD else None


def _detect_voicing(midi_pitches: list) -> tuple:
    if any(p in _OPEN_STRING_PITCHES for p in midi_pitches):
        return 'open', 0
    lowest = min(midi_pitches)
    fret = max(1, lowest - 40)
    return 'barre', min(fret, 12)


def _seconds_to_time_str(seconds: float) -> str:
    total = int(seconds)
    return f'{total // 60}:{total % 60:02d}'


def recognize_chords(audio_path: str) -> List[ChordItem]:
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f'오디오 파일을 찾을 수 없습니다: {audio_path}')

    try:
        _, _, note_events = predict(audio_path)
    except Exception as e:
        raise RuntimeError(f'코드 인식 실패: {e}') from e

    if not note_events:
        return []

    max_time = max(note[1] for note in note_events)
    items: List[ChordItem] = []
    prev_chord = None
    seen_times: set = set()

    t = 0.0
    while t < max_time:
        window_end = t + _WINDOW_SEC
        active = [
            n for n in note_events
            if n[0] < window_end and n[1] > t and n[3] >= _MIN_AMPLITUDE
        ]

        if active:
            chroma = np.zeros(12)
            for n in active:
                chroma[n[2] % 12] += 1

            chord = _chroma_to_chord(chroma)
            if chord and chord != prev_chord:
                time_str = _seconds_to_time_str(t)
                if time_str not in seen_times:
                    voicing, fret = _detect_voicing([n[2] for n in active])
                    items.append(ChordItem(
                        time=time_str,
                        chord=chord,
                        fret=fret,
                        voicing=voicing,
                    ))
                    seen_times.add(time_str)
                prev_chord = chord
        else:
            prev_chord = None

        t += _WINDOW_SEC

    return items
