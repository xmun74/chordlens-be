# Basic Pitch 마이그레이션 설계

## 목표

autochord(Chordino VAMP)를 Spotify Basic Pitch로 교체하여 코드 이름 정확도를 높이고, 기타 포지션 정보(fret, 오픈/바레 여부)를 출력에 추가한다.

## 배경

현재 스택은 Chordino(NNLS-Chroma VAMP 플러그인)를 사용하는 전통적 신호처리 기반이다. 코드 이름이 틀리는 문제(Am → C 등)가 주요 정확도 이슈다. Basic Pitch는 Spotify가 개발한 딥러닝 기반 노트 인식 모델로, 개별 노트의 MIDI 피치(옥타브 포함)를 정확히 감지한다. Apache 2.0 라이선스로 무료 사용 가능하며 활발히 유지보수된다.

## 성공 기준

- 코드 이름 정확도 개선 (primary)
- 코드 전환 타이밍 개선 (secondary)
- 코드 감지 수 적정화 — 과다/과소 방지 (secondary)

---

## 아키텍처

### 파이프라인 변경

```
[이전]
YouTube URL → yt-dlp (MP3) → ffmpeg (WAV 22050Hz) → Chordino VAMP → ChordItem[]

[이후]
YouTube URL → yt-dlp (MP3) → Basic Pitch (노트 이벤트) → 크로마 집계 + 템플릿 매칭 + 포지션 추정 → ChordItem[]
```

WAV 변환 단계가 제거된다. Basic Pitch는 MP3를 직접 처리한다.

### 변경 파일

| 파일 | 변경 내용 |
|------|-----------|
| `app/models/chord.py` | `ChordItem`에 `fret: int`, `voicing: str` 필드 추가 |
| `app/services/chord.py` | 전면 재작성 — Basic Pitch + 크로마 템플릿 매칭 + 포지션 추정 |
| `app/services/audio.py` | `convert_to_wav()` 제거 |
| `app/routers/extract.py` | WAV 변환 단계 제거, `recognize_chords(mp3_path)` 직접 호출 |
| `requirements.txt` | `autochord==0.1.3`, `tensorflow<2.16` 제거 → `basic-pitch` 추가 |
| `Dockerfile` | numpy 선행 설치 단계 제거 |

---

## 데이터 모델

### ChordItem (확장)

```python
class ChordItem(BaseModel):
    time: str      # "M:SS" 형식
    chord: str     # "Am7", "Cdim", "Gaug" 등
    fret: int      # 0 = 오픈 코드, 1~12 = 바레 프렛 위치
    voicing: str   # "open" | "barre"
```

**API 응답 호환성:** `fret`와 `voicing` 필드 추가로 기존 응답 형식이 변경된다. 프론트엔드에서 신규 필드를 처리해야 한다.

---

## chord.py 핵심 로직

### 1. 코드 템플릿 (12 루트 × 9 타입 = 108가지)

| 타입 | 표기 | 반음 간격 |
|------|------|-----------|
| Major | C | 0, 4, 7 |
| minor | Cm | 0, 3, 7 |
| dominant 7th | C7 | 0, 4, 7, 10 |
| major 7th | Cmaj7 | 0, 4, 7, 11 |
| minor 7th | Cm7 | 0, 3, 7, 10 |
| diminished | Cdim | 0, 3, 6 |
| augmented | Caug | 0, 4, 8 |
| suspended 2nd | Csus2 | 0, 2, 7 |
| suspended 4th | Csus4 | 0, 5, 7 |

루트 이름: C, C#, D, Eb, E, F, F#, G, Ab, A, Bb, B

### 2. 코드 인식 흐름

```
Basic Pitch predict(mp3_path)
  → note_events: [(start, end, midi_pitch, amplitude, pitch_bends), ...]
  → 1초 슬라이딩 윈도우
  → amplitude ≥ 0.3인 활성 노트 수집
  → pitch % 12 집계 → 크로마 벡터(12차원)
  → 코사인 유사도로 108개 템플릿과 비교
  → 유사도 ≥ 0.75이면 코드 레이블 결정
  → 인접 중복 제거
  → ChordItem(time, chord, fret, voicing)
```

### 3. 포지션 추정 로직

기타 표준 튜닝 개방현 MIDI 피치:

| 현 | 음 | MIDI |
|----|-----|------|
| 6번(저음 E) | E2 | 40 |
| 5번 | A2 | 45 |
| 4번 | D3 | 50 |
| 3번 | G3 | 55 |
| 2번 | B3 | 59 |
| 1번(고음 E) | E4 | 64 |

```python
OPEN_STRING_PITCHES = {40, 45, 50, 55, 59, 64}

def detect_voicing(midi_pitches):
    if any(p in OPEN_STRING_PITCHES for p in midi_pitches):
        return "open", 0
    lowest = min(midi_pitches)
    # 6번 현 기준 fret 추정 (근사값)
    fret = max(1, lowest - 40)
    return "barre", min(fret, 12)
```

**한계:** fret 추정은 근사값이다. 동일 코드를 여러 포지션으로 연주할 수 있어 완벽한 정확도는 보장되지 않는다.

### 4. 튜닝 파라미터

| 상수 | 기본값 | 역할 |
|------|--------|------|
| `_WINDOW_SEC` | 1.0 | 윈도우 크기 (타이밍 정밀도) |
| `_MIN_AMPLITUDE` | 0.3 | 노이즈 필터 |
| `_SIMILARITY_THRESHOLD` | 0.75 | 코드 결정 민감도 |

---

## 에러 처리

| 상황 | 처리 |
|------|------|
| 파일 없음 | `FileNotFoundError` |
| Basic Pitch 실패 | `RuntimeError` — 기존 `/extract` 500 핸들러로 전달 |
| 노트 이벤트 없음 | 빈 리스트 반환 |

---

## 테스트 전략

- `_chroma_to_chord()` 단위 테스트 — 알려진 크로마 벡터로 코드 레이블 검증
- `detect_voicing()` 단위 테스트 — 개방현 피치 포함/미포함 케이스
- `recognize_chords()` 통합 테스트 — Basic Pitch `predict()` mock
- 중복 제거, 빈 이벤트, 파일 없음 엣지케이스 테스트
