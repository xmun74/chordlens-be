"""코드 인식 서비스.

엔진: Chordino(NNLS-Chroma) via chord-extractor. 풀 믹스 화성 인식 전용.
fret/voicing은 오디오에서 추정하지 않고 @tombatossals/chords-db(MIT) 룩업으로 산출한다
(app/services/voicing.py 참조).

라이선스 메모: Chordino/NNLS-Chroma는 GPL. 본 백엔드는 import 실행(내부 서버 전용)만
하며 바이너리/소스를 재배포하지 않는다. Docker 이미지를 외부 배포하면 GPL 의무가
발동할 수 있으므로 "내부 서버 실행 전용" 전제를 유지한다.
"""
import os
import re
from typing import List, Optional

from app.models.chord import ChordItem
from app.services.voicing import lookup_voicing

# chord-extractor(Vamp 바이너리 의존)는 일부 환경(테스트 등)에 미설치일 수 있다.
# 임포트 가드를 두어 모듈 수집이 깨지지 않게 한다. 런타임에서 Chordino가 None이면
# extract() 시도 시 RuntimeError로 변환된다. (테스트는 이 심볼을 patch 한다.)
try:
    from chord_extractor.extractors import Chordino
    _CHORDINO_IMPORT_ERROR = None
except Exception as _e:  # pragma: no cover - 미설치 환경 가드
    Chordino = None
    _CHORDINO_IMPORT_ERROR = repr(_e)  # 실제 임포트 실패 원인 보존(디버깅용)

_NO_CHORD = "N"

# mir_eval 스타일 콜론 표기 변환 (긴 표기 우선 매칭).
_COLON_REPLACEMENTS = [
    (":maj7", "maj7"),
    (":min7", "m7"),
    (":min", "m"),
    (":maj", ""),
    (":dim", "dim"),
    (":aug", "aug"),
    (":sus2", "sus2"),
    (":sus4", "sus4"),
    (":7", "7"),
]

_ROOT_RE = re.compile(r"^[A-G][#b]?")


def _seconds_to_time_str(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 60}:{total % 60:02d}"


def normalize_chord(label: str) -> Optional[str]:
    """Chordino 라벨 → 기존 표기 정규화. 무화음/매칭 실패 시 None.

    규칙:
      1. "N" → None (무화음).
      2. 슬래시 분리: 베이스음(전위) 제거. "C/E" → "C".
      3. mir_eval 콜론 표기 변환: ":min"→"m", ":maj7"→"maj7", ":7"→"7", ":maj"→"" 등.
      4. 루트([A-G][#b]?) 매칭 실패 또는 빈 문자열 → None.
    표시 문자열은 사람이 읽는 표기(Cm, G7)를 그대로 보존한다.
    chords-db 키 변환(Db→Csharp 등)은 voicing 룩업 내부에서만 처리.
    """
    if label is None:
        return None
    label = label.strip()
    if label == "" or label == _NO_CHORD:
        return None

    # 슬래시(전위) 제거.
    label = label.split("/")[0]

    # 콜론 표기 변환.
    for pattern, repl in _COLON_REPLACEMENTS:
        if pattern in label:
            label = label.replace(pattern, repl)
    # 잔여 콜론 제거.
    label = label.replace(":", "")

    label = label.strip()
    if not label or not _ROOT_RE.match(label):
        return None
    return label


def recognize_chords(audio_path: str) -> List[ChordItem]:
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {audio_path}")

    if Chordino is None:
        raise RuntimeError(
            "코드 인식 실패: chord-extractor(Chordino)를 불러올 수 없습니다. "
            f"임포트 오류: {_CHORDINO_IMPORT_ERROR}. "
            "Docker 이미지를 'make build'로 재빌드했는지 확인하세요."
        )

    try:
        chordino = Chordino(roll_on=1)  # pop 곡 기본 파라미터
        changes = chordino.extract(audio_path)  # List[ChordChange] = (chord, timestamp)
    except Exception as e:
        raise RuntimeError(f"코드 인식 실패: {e}") from e

    if not changes:
        return []

    items: List[ChordItem] = []
    prev = None
    for change in changes:
        chord = normalize_chord(change.chord)
        if chord is None:  # 무화음(N) → 스킵, prev 리셋.
            prev = None
            continue
        if chord == prev:  # 인접 중복 제거.
            continue

        v = lookup_voicing(chord)
        items.append(ChordItem(
            time=_seconds_to_time_str(change.timestamp),
            chord=chord,
            fret=v.fret,
            voicing=v.voicing,
            frets=v.frets,
            fingers=v.fingers,
            base_fret=v.base_fret,
            barres=v.barres,
        ))
        prev = chord

    return items
