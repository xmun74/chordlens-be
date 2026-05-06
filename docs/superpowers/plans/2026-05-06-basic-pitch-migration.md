# Basic Pitch 마이그레이션 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** autochord(Chordino VAMP)를 Basic Pitch로 교체하고, 코드 타입 확장(108가지) 및 기타 포지션(fret, open/barre) 정보를 `ChordItem`에 추가한다.

**Architecture:** Basic Pitch로 MP3에서 MIDI 노트 이벤트를 추출하고, 1초 슬라이딩 윈도우로 크로마 벡터를 생성한 뒤 코사인 유사도 템플릿 매칭으로 코드 레이블을 결정한다. 감지된 노트의 MIDI 피치로 기타 개방현 여부를 판단해 open/barre와 fret을 추정한다. WAV 변환 단계를 제거해 파이프라인을 단순화한다.

**Tech Stack:** `basic-pitch` (Spotify), `numpy`, FastAPI, pytest

---

## 변경 파일 목록

| 파일 | 작업 |
|------|------|
| `app/models/chord.py` | `ChordItem`에 `fret: int`, `voicing: str` 추가 |
| `app/services/chord.py` | 전면 재작성 — Basic Pitch + 크로마 템플릿 + 포지션 추정 |
| `app/services/audio.py` | `convert_to_wav()` 함수 제거 |
| `app/routers/extract.py` | WAV 변환 단계 제거, MP3 직접 전달 |
| `requirements.txt` | `autochord`, `tensorflow` 제거 → `basic-pitch` 추가 |
| `Dockerfile` | numpy 선행 설치 단계 제거 |
| `tests/__init__.py` | 신규 생성 |
| `tests/services/__init__.py` | 신규 생성 |
| `tests/services/test_chord.py` | 신규 생성 — 단위/통합 테스트 |

---

### Task 1: ChordItem 모델 확장

**Files:**
- Modify: `app/models/chord.py`

- [ ] **Step 1: ChordItem에 fret, voicing 필드 추가**

`app/models/chord.py`를 아래로 교체한다:

```python
from pydantic import BaseModel
from typing import List, Optional
import uuid


class ExtractRequest(BaseModel):
    youtube_url: str


class ChordItem(BaseModel):
    time: str
    chord: str
    fret: int
    voicing: str  # "open" | "barre"


class LyricLine(BaseModel):
    time: str
    text: str


class ExtractResponse(BaseModel):
    id: uuid.UUID
    video_id: str
    title: str
    channel_name: str
    thumbnail_url: str
    chords: List[ChordItem]
    lyrics: Optional[List[LyricLine]] = None
    cached: bool
```

- [ ] **Step 2: 모델 임포트 확인**

```bash
cd /Users/mun/Documents/chordlens-be && python -c "from app.models.chord import ChordItem; c = ChordItem(time='0:05', chord='Am', fret=0, voicing='open'); print(c)"
```

Expected: `time='0:05' chord='Am' fret=0 voicing='open'`

- [ ] **Step 3: 커밋**

```bash
git add app/models/chord.py
git commit -m "feat: ChordItem에 fret, voicing 필드 추가"
```

---

### Task 2: 테스트 인프라 구성 및 실패 테스트 작성

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/services/__init__.py`
- Create: `tests/services/test_chord.py`

- [ ] **Step 1: 테스트 디렉토리 초기화**

```bash
touch /Users/mun/Documents/chordlens-be/tests/__init__.py
touch /Users/mun/Documents/chordlens-be/tests/services/__init__.py
```

- [ ] **Step 2: 테스트 파일 작성**

```python
# tests/services/test_chord.py
import numpy as np
import pytest
from unittest.mock import patch
from app.services.chord import (
    _build_chord_templates,
    _chroma_to_chord,
    _detect_voicing,
    recognize_chords,
)
from app.models.chord import ChordItem


# ── _build_chord_templates ───────────────────────────────────────

def test_build_chord_templates_count():
    templates = _build_chord_templates()
    assert len(templates) == 108  # 12 roots × 9 types


def test_build_chord_templates_c_major():
    templates = _build_chord_templates()
    t = templates['C']
    assert t[0] == 1  # C
    assert t[4] == 1  # E
    assert t[7] == 1  # G
    assert t.sum() == 3


def test_build_chord_templates_am():
    templates = _build_chord_templates()
    t = templates['Am']
    assert t[9] == 1  # A
    assert t[0] == 1  # C
    assert t[4] == 1  # E


# ── _chroma_to_chord ─────────────────────────────────────────────

def test_chroma_to_chord_c_major():
    chroma = np.zeros(12)
    chroma[[0, 4, 7]] = 1  # C, E, G
    assert _chroma_to_chord(chroma) == 'C'


def test_chroma_to_chord_a_minor():
    chroma = np.zeros(12)
    chroma[[9, 0, 4]] = 1  # A, C, E
    assert _chroma_to_chord(chroma) == 'Am'


def test_chroma_to_chord_g_dominant7():
    chroma = np.zeros(12)
    chroma[[7, 11, 2, 5]] = 1  # G, B, D, F
    assert _chroma_to_chord(chroma) == 'G7'


def test_chroma_to_chord_d_minor7():
    chroma = np.zeros(12)
    chroma[[2, 5, 9, 0]] = 1  # D, F, A, C
    assert _chroma_to_chord(chroma) == 'Dm7'


def test_chroma_to_chord_b_diminished():
    chroma = np.zeros(12)
    chroma[[11, 2, 5]] = 1  # B, D, F
    assert _chroma_to_chord(chroma) == 'Bdim'


def test_chroma_to_chord_c_augmented():
    chroma = np.zeros(12)
    chroma[[0, 4, 8]] = 1  # C, E, G#
    assert _chroma_to_chord(chroma) == 'Caug'


def test_chroma_to_chord_empty_returns_none():
    assert _chroma_to_chord(np.zeros(12)) is None


def test_chroma_to_chord_uniform_returns_none():
    # 모든 피치 균일 → 유사도 낮음 → None
    assert _chroma_to_chord(np.ones(12) * 0.1) is None


# ── _detect_voicing ──────────────────────────────────────────────

def test_detect_voicing_open_when_open_string_present():
    # A2=45 는 개방현 → open
    voicing, fret = _detect_voicing([45, 52, 57, 60, 64])
    assert voicing == 'open'
    assert fret == 0


def test_detect_voicing_barre_when_no_open_string():
    # 46, 53, 58, 62, 65 은 모두 개방현이 아님
    voicing, fret = _detect_voicing([46, 53, 58, 62, 65])
    assert voicing == 'barre'
    assert fret >= 1


def test_detect_voicing_fret_capped_at_12():
    voicing, fret = _detect_voicing([70, 74, 77])
    assert voicing == 'barre'
    assert fret <= 12


# ── recognize_chords ─────────────────────────────────────────────

_FAKE_NOTE_EVENTS = [
    # (start, end, midi_pitch, amplitude, pitch_bends)
    # 윈도우 0~1s: Am (A=45, E=52, A=57, C=60, E=64)
    (0.0, 1.5, 45, 0.9, []),  # A2 (개방현)
    (0.0, 1.5, 52, 0.9, []),  # E3
    (0.0, 1.5, 57, 0.9, []),  # A3
    (0.0, 1.5, 60, 0.9, []),  # C4
    (0.0, 1.5, 64, 0.9, []),  # E4 (개방현)
    # 윈도우 2~3s: Em (E=40, B=47, E=52, G=55, B=59)
    (2.0, 3.5, 40, 0.9, []),  # E2 (개방현)
    (2.0, 3.5, 47, 0.9, []),  # B2
    (2.0, 3.5, 52, 0.9, []),  # E3
    (2.0, 3.5, 55, 0.9, []),  # G3 (개방현)
    (2.0, 3.5, 59, 0.9, []),  # B3 (개방현)
]


def test_recognize_chords_returns_chord_items(tmp_path):
    dummy = tmp_path / 'test.mp3'
    dummy.write_bytes(b'dummy')

    with patch('app.services.chord.predict', return_value=(None, None, _FAKE_NOTE_EVENTS)):
        result = recognize_chords(str(dummy))

    assert len(result) >= 1
    assert all(isinstance(item, ChordItem) for item in result)
    assert all(item.voicing in ('open', 'barre') for item in result)


def test_recognize_chords_first_chord_am_open(tmp_path):
    dummy = tmp_path / 'test.mp3'
    dummy.write_bytes(b'dummy')

    with patch('app.services.chord.predict', return_value=(None, None, _FAKE_NOTE_EVENTS)):
        result = recognize_chords(str(dummy))

    assert result[0].chord == 'Am'
    assert result[0].voicing == 'open'
    assert result[0].fret == 0


def test_recognize_chords_deduplicates_adjacent(tmp_path):
    dummy = tmp_path / 'test.mp3'
    dummy.write_bytes(b'dummy')

    repeated = [
        (0.0, 3.0, 45, 0.9, []),
        (0.0, 3.0, 52, 0.9, []),
        (0.0, 3.0, 57, 0.9, []),
        (0.0, 3.0, 60, 0.9, []),
        (0.0, 3.0, 64, 0.9, []),
    ]
    with patch('app.services.chord.predict', return_value=(None, None, repeated)):
        result = recognize_chords(str(dummy))

    chords = [item.chord for item in result]
    assert chords == list(dict.fromkeys(chords))


def test_recognize_chords_filters_low_amplitude(tmp_path):
    dummy = tmp_path / 'test.mp3'
    dummy.write_bytes(b'dummy')

    low_amp = [
        (0.0, 1.0, 45, 0.1, []),
        (0.0, 1.0, 52, 0.1, []),
        (0.0, 1.0, 57, 0.1, []),
    ]
    with patch('app.services.chord.predict', return_value=(None, None, low_amp)):
        result = recognize_chords(str(dummy))

    assert result == []


def test_recognize_chords_empty_events(tmp_path):
    dummy = tmp_path / 'test.mp3'
    dummy.write_bytes(b'dummy')

    with patch('app.services.chord.predict', return_value=(None, None, [])):
        result = recognize_chords(str(dummy))

    assert result == []


def test_recognize_chords_file_not_found():
    with pytest.raises(FileNotFoundError):
        recognize_chords('/nonexistent/path.mp3')
```

- [ ] **Step 3: 테스트 실행 — 실패 확인**

```bash
cd /Users/mun/Documents/chordlens-be && python -m pytest tests/services/test_chord.py -v
```

Expected: `ImportError` 또는 `ModuleNotFoundError` (`_build_chord_templates` 등이 chord.py에 없으므로)

- [ ] **Step 4: 커밋**

```bash
git add tests/
git commit -m "test: chord 서비스 실패 테스트 작성"
```

---

### Task 3: 의존성 교체

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: requirements.txt 수정**

```
fastapi==0.111.0
uvicorn==0.29.0
yt-dlp
basic-pitch
supabase>=2.4
pydantic-settings>=2.2
python-multipart
```

- [ ] **Step 2: basic-pitch 설치**

```bash
pip install basic-pitch
```

Expected: `Successfully installed basic-pitch-...` 포함

- [ ] **Step 3: 임포트 확인**

```bash
python -c "from basic_pitch.inference import predict; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: 커밋**

```bash
git add requirements.txt
git commit -m "chore: autochord/tensorflow → basic-pitch 의존성 교체"
```

---

### Task 4: chord.py 재작성

**Files:**
- Modify: `app/services/chord.py`

- [ ] **Step 1: chord.py 전면 교체**

```python
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
```

- [ ] **Step 2: 테스트 실행 — 통과 확인**

```bash
cd /Users/mun/Documents/chordlens-be && python -m pytest tests/services/test_chord.py -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 3: 커밋**

```bash
git add app/services/chord.py
git commit -m "feat: Basic Pitch 기반 코드 인식 엔진 구현 (108 코드 타입, fret/voicing 추정)"
```

---

### Task 5: 파이프라인 단순화

**Files:**
- Modify: `app/services/audio.py`
- Modify: `app/routers/extract.py`

- [ ] **Step 1: audio.py에서 convert_to_wav 제거**

`app/services/audio.py`의 `convert_to_wav` 함수 전체(아래 블록)를 삭제한다:

```python
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
```

`import subprocess`도 더 이상 사용하지 않으므로 함께 제거한다.

- [ ] **Step 2: extract.py 파이프라인 수정**

`app/routers/extract.py`의 import 줄을 수정한다:

```python
from app.services.audio import extract_audio, cleanup_files, VideoUnavailableError
```

`_run_pipeline` 함수를 아래로 교체한다:

```python
def _run_pipeline(youtube_url: str) -> tuple:
    mp3_path = None
    try:
        mp3_path, metadata = extract_audio(youtube_url)
        chords = recognize_chords(mp3_path)

        video_id = _parse_video_id(youtube_url)
        raw_lyrics = extract_lyrics(video_id)
        lyrics = [LyricLine(**l) for l in raw_lyrics] if raw_lyrics else None

        return metadata, chords, lyrics
    finally:
        cleanup_files(mp3_path)
```

- [ ] **Step 3: 서버 기동 확인**

```bash
cd /Users/mun/Documents/chordlens-be && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Expected: `Application startup complete.` 출력

- [ ] **Step 4: 커밋**

```bash
git add app/services/audio.py app/routers/extract.py
git commit -m "refactor: WAV 변환 단계 제거, MP3 직접 Basic Pitch에 전달"
```

---

### Task 6: Dockerfile 업데이트

**Files:**
- Modify: `Dockerfile`

- [ ] **Step 1: Dockerfile 수정**

```dockerfile
# ── 베이스 이미지 ────────────────────────────────────────
FROM python:3.11-slim

# ── 시스템 패키지 ─────────────────────────────────────────
# ffmpeg: yt-dlp 오디오 추출용
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# ── 작업 디렉토리 ─────────────────────────────────────────
WORKDIR /app

# ── 의존성 설치 ───────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── 소스 코드 복사 ────────────────────────────────────────
COPY app/ ./app/

# ── 임시 파일 디렉토리 ────────────────────────────────────
RUN mkdir -p /tmp/chordlens

# ── 포트 ──────────────────────────────────────────────────
EXPOSE 8000

# ── 실행 ──────────────────────────────────────────────────
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: 커밋**

```bash
git add Dockerfile
git commit -m "chore: Dockerfile에서 vamp 우회용 numpy 선행 설치 제거"
```
