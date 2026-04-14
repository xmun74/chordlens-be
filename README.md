# CodeLens Backend

YouTube URL을 입력하면 기타 코드를 자동으로 분석해 반환하는 FastAPI 백엔드 서버.

## 기술 스택

| 항목 | 기술 |
|---|---|
| 언어 | Python 3.11 |
| 웹 프레임워크 | FastAPI 0.111 |
| ASGI 서버 | uvicorn 0.29 |
| 오디오 추출 | yt-dlp |
| 코드 인식 | autochord 0.1.3 + NNLS-Chroma VAMP |
| DB | Supabase (PostgreSQL) |
| 배포 | AWS EC2 t2.micro |

## 프로젝트 구조

```
codelens-be/
├── app/
│   ├── main.py              # FastAPI 앱 진입점, CORS, lifespan
│   ├── db.py                # Supabase AsyncClient 싱글턴
│   ├── core/
│   │   └── config.py        # 환경 변수 (pydantic-settings)
│   ├── models/
│   │   └── chord.py         # 요청/응답 Pydantic 스키마
│   ├── routers/
│   │   └── extract.py       # POST /extract, GET /health
│   └── services/
│       ├── audio.py         # yt-dlp 추출 + ffmpeg 변환
│       ├── chord.py         # autochord 코드 인식 + 정규화
│       └── cache.py         # Supabase 캐시 조회/저장
├── supabase/
│   └── schema.sql           # chord_results 테이블 + 인덱스 생성 SQL
├── requirements.txt
├── .env.example
└── Makefile
```

## 퀵 스타트

### 1. 저장소 클론 및 의존성 설치

```bash
git clone <repo-url>
cd codelens-be

# ffmpeg 설치 (미설치 시)
brew install ffmpeg

# 가상환경 생성 및 의존성 설치
python3.11 -m venv venv
source venv/bin/activate
pip install numpy
pip install "tensorflow<2.16"
pip install -r requirements.txt
```

### 2. NNLS-Chroma VAMP 플러그인 설치 (macOS)

autochord 코드 인식에 필요한 macOS 네이티브 플러그인을 빌드·설치한다.

```bash
brew install vamp-plugin-sdk boost

git clone https://github.com/c4dm/nnls-chroma.git /tmp/nnls-chroma
cd /tmp/nnls-chroma

VAMP_SDK=/opt/homebrew/Cellar/vamp-plugin-sdk/$(brew list --versions vamp-plugin-sdk | awk '{print $2}')/

make -f Makefile.osx \
  CXXFLAGS="-arch arm64 -O3 -ffast-math -I${VAMP_SDK}include -I/opt/homebrew/include -Wall -fPIC"

c++ -o nnls-chroma.dylib \
  chromamethods.o NNLSBase.o NNLSChroma.o Chordino.o Tuning.o plugins.o nnls.o viterbi.o \
  -arch arm64 -dynamiclib -install_name nnls-chroma.dylib \
  -L${VAMP_SDK}lib -lvamp-sdk \
  -exported_symbols_list vamp-plugin.list \
  -framework Accelerate

mkdir -p ~/Library/Audio/Plug-Ins/Vamp
cp nnls-chroma.dylib ~/Library/Audio/Plug-Ins/Vamp/

cd -
```

### 3. Supabase 테이블 생성

Supabase Dashboard → SQL Editor에서 `supabase/schema.sql` 전체를 실행한다.

### 4. 환경 변수 설정

```bash
cp .env.example .env
```

`.env` 파일을 열어 실제 값을 입력한다.

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key
ALLOWED_ORIGIN=http://localhost:3000
```

### 5. 서버 실행

```bash
make dev
```

서버가 `http://localhost:8000` 에서 실행된다.

## API

### `POST /extract`

YouTube URL을 분석해 기타 코드를 반환한다.

**요청**
```json
{ "youtube_url": "https://www.youtube.com/watch?v=..." }
```

**응답**
```json
{
  "id": "uuid",
  "title": "영상 제목",
  "channel_name": "채널명",
  "thumbnail_url": "https://...",
  "chords": [
    { "time": "0:12", "chord": "Am" },
    { "time": "0:16", "chord": "F" }
  ],
  "cached": false
}
```

**에러 코드**

| 코드 | 사유 |
|---|---|
| 400 | 유효하지 않은 URL / 비공개·연령제한 영상 |
| 500 | 오디오 추출 또는 코드 인식 실패 |
| 504 | 처리 시간 초과 (60초) |

### `GET /health`

```json
{ "status": "ok" }
```

## 처리 파이프라인

```
YouTube URL
    │
    ├─ Supabase 캐시 조회 → 히트 시 즉시 반환 (cached: true)
    │
    ├─ yt-dlp → MP3 추출
    ├─ ffmpeg → WAV 변환 (22050Hz, mono)
    ├─ autochord → 코드 인식 (장조·단조 24개)
    ├─ Supabase 저장
    └─ 응답 반환 (cached: false)
```

## 환경 변수

| 변수명 | 설명 |
|---|---|
| `SUPABASE_URL` | Supabase 프로젝트 URL |
| `SUPABASE_KEY` | Supabase service_role 키 |
| `ALLOWED_ORIGIN` | CORS 허용 도메인 (프론트엔드 URL) |
