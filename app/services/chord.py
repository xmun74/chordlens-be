import os
import pkg_resources
import librosa
import vamp
import autochord  # noqa: F401 — VAMP 플러그인을 시스템 경로에 복사·초기화
from scipy.signal import resample
from typing import List
from app.models.chord import ChordItem


_SAMPLE_RATE = 44100
_VAMP_PLUGIN_KEY = 'nnls-chroma:chordino'

# 시작 시 VAMP 상태 출력
_vamp_lib = pkg_resources.resource_filename('autochord', 'res/nnls-chroma.so')
for _p in vamp.vampyhost.get_plugin_path():
    _so = os.path.join(_p, 'nnls-chroma.so')


def _seconds_to_time_str(seconds: float) -> str:
    """초를 'M:SS' 형식 문자열로 변환한다."""
    total = int(seconds)
    return f"{total // 60}:{total % 60:02d}"


def recognize_chords(wav_path: str) -> List[ChordItem]:
    """WAV 파일에서 Chordino로 코드를 인식하고 ChordItem 리스트를 반환한다.

    autochord(장조·단조 24개)와 달리 Chordino simplechord 출력은
    7th, maj7, min7 등 확장 코드를 포함한다.

    처리 규칙:
    - 무음(N) 제거
    - 인접 중복 병합

    Raises:
        FileNotFoundError: WAV 파일이 존재하지 않는 경우
        RuntimeError: 코드 인식 실패
    """
    if not os.path.exists(wav_path):
        raise FileNotFoundError(f"WAV 파일을 찾을 수 없습니다: {wav_path}")

    try:
        samples, fs = librosa.load(wav_path, sr=None, mono=True)
        if fs != _SAMPLE_RATE:
            samples = resample(samples, num=int(len(samples) * _SAMPLE_RATE / fs))

        output = vamp.collect(samples, _SAMPLE_RATE, _VAMP_PLUGIN_KEY)
    except Exception as e:
        raise RuntimeError(f"코드 인식 실패: {e}") from e

    items: List[ChordItem] = []
    prev_chord = None
    seen_times: set[str] = set()

    for event in output.get('list', []):
        chord = str(event.get('label', '')).strip()
        timestamp = float(event['timestamp'])

        if not chord or chord == 'N':
            prev_chord = None
            continue

        if chord == prev_chord:
            continue

        time_str = _seconds_to_time_str(timestamp)

        # 같은 초에 이미 코드가 있으면 건너뜀 (타임라인 겹침 방지)
        if time_str in seen_times:
            continue

        seen_times.add(time_str)
        items.append(ChordItem(time=time_str, chord=chord))
        prev_chord = chord

    return items
