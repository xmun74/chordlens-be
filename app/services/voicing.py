"""코드명 → (fret, voicing) 룩업 서비스.

운지 데이터 출처: @tombatossals/chords-db (MIT)
  https://github.com/tombatossals/chords-db (lib/guitar.json)
  라이선스 원문/저작자 표기: app/services/data/LICENSE-chords-db

guitar.json 구조:
  { "keys": [...], "suffixes": [...],
    "chords": { "C": [ {suffix, positions:[{frets, fingers, baseFret, barres, ...}]}, ... ],
                "Csharp": [...], ... } }
  - chords 키는 샵 기반 영문 표기(C, Csharp, D, Eb, E, F, Fsharp, G, Ab, A, Bb, B).
"""
import json
import os
from dataclasses import dataclass, field
from typing import List, Literal, Optional, Tuple

from app.core.logging import get_logger

logger = get_logger(__name__)

_DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "guitar.json")


@dataclass(frozen=True)
class Voicing:
    """코드 운지 데이터. chords-db position을 그대로 담는다.

    frets/fingers: 6현(저음 E현→고음 e현 순), -1=뮤트, 0=개방.
    base_fret: 다이어그램 시작 프렛. barres: 바레 프렛(base_fret 상대) 목록.
    fret/voicing: 구 호환용 파생값.
    """

    frets: List[int] = field(default_factory=list)
    fingers: List[int] = field(default_factory=list)
    base_fret: int = 1
    barres: List[int] = field(default_factory=list)
    fret: int = 0
    voicing: Literal["open", "barre"] = "open"


# 룩업 실패 시 안전 기본값 (빈 운지 → FE는 코드명만 표시)
_DEFAULT = Voicing()

# 루트 enharmonic → chords-db 키 매핑.
# chords-db는 C#/F#만 "sharp" 표기, 나머지 흑건은 flat 표기(Eb, Ab, Bb) 사용.
_ROOT_TO_DB_KEY = {
    "C": "C",
    "C#": "Csharp", "Db": "Csharp",
    "D": "D",
    "D#": "Eb", "Eb": "Eb",
    "E": "E", "Fb": "E",
    "F": "F", "E#": "F",
    "F#": "Fsharp", "Gb": "Fsharp",
    "G": "G",
    "G#": "Ab", "Ab": "Ab",
    "A": "A",
    "A#": "Bb", "Bb": "Bb",
    "B": "B", "Cb": "B",
}

# 코드 suffix 표기 → chords-db suffix.
# "" (메이저) → "major". 그 외 마이너/세븐스/sus 등 매핑.
_SUFFIX_TO_DB = {
    "": "major",
    "m": "minor",
    "7": "7",
    "maj7": "maj7",
    "m7": "m7",
    "dim": "dim",
    "aug": "aug",
    "sus2": "sus2",
    "sus4": "sus4",
}


def _load_db() -> dict:
    """guitar.json을 1회 로드. 부재/손상 시 빈 dict 반환(경고 로깅)."""
    try:
        with open(_DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("chords", {})
    except FileNotFoundError:
        logger.warning("guitar.json 미발견: %s — 모든 voicing 룩업이 기본값 반환", _DATA_PATH)
        return {}
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("guitar.json 로드 실패: %s — 모든 voicing 룩업이 기본값 반환", e)
        return {}


# 모듈 로드 시 1회 캐시.
_DB: dict = _load_db()


def _parse_chord(chord: str) -> Optional[Tuple[str, str]]:
    """코드명 → (root, suffix 표시). 파싱 실패 시 None.

    root: [A-G] + 선택적 #/b. 나머지가 suffix 표시 문자열.
    """
    if not chord:
        return None
    root = chord[0]
    if root not in "ABCDEFG":
        return None
    rest = chord[1:]
    if rest[:1] in ("#", "b"):
        root += rest[0]
        rest = rest[1:]
    return root, rest


def lookup_voicing(chord: str) -> Voicing:
    """코드명 → Voicing(운지 데이터). 실패 시 빈 기본값(_DEFAULT).

    chords-db의 첫 번째 position을 그대로 담아 반환한다. FE가 frets/fingers/base_fret/
    barres로 다이어그램을 직접 렌더하므로 운지 데이터를 손실 없이 전달한다.
    fret/voicing은 구 호환용 파생값: barres가 비고 base_fret==1이며 개방현(0) 포함 시 open,
    그 외 barre(fret=base_fret).
    """
    if not _DB:
        return _DEFAULT

    parsed = _parse_chord(chord)
    if parsed is None:
        return _DEFAULT
    root, suffix = parsed

    db_key = _ROOT_TO_DB_KEY.get(root)
    db_suffix = _SUFFIX_TO_DB.get(suffix)
    if db_key is None or db_suffix is None:
        return _DEFAULT

    entries = _DB.get(db_key)
    if not entries:
        return _DEFAULT

    position = None
    for entry in entries:
        if entry.get("suffix") == db_suffix:
            positions = entry.get("positions")
            if positions:
                position = positions[0]
            break

    if position is None:
        return _DEFAULT

    frets = list(position.get("frets") or [])
    fingers = list(position.get("fingers") or [])
    base_fret = position.get("baseFret", 1)
    barres = list(position.get("barres") or [])

    if not barres and base_fret == 1 and any(f == 0 for f in frets):
        derived_voicing: Literal["open", "barre"] = "open"
        derived_fret = 0
    else:
        derived_voicing = "barre"
        derived_fret = base_fret

    return Voicing(
        frets=frets,
        fingers=fingers,
        base_fret=base_fret,
        barres=barres,
        fret=derived_fret,
        voicing=derived_voicing,
    )
