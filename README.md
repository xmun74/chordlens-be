# ChordLens Backend

YouTube URL을 입력하면 기타 코드를 자동으로 분석해 반환하는 FastAPI 백엔드 서버.

## 기술 스택

| 항목               | 기술                                               |
| ------------------ | -------------------------------------------------- |
| 언어               | Python 3.11                                        |
| 웹 프레임워크      | FastAPI 0.111                                      |
| ASGI 서버          | uvicorn 0.29                                       |
| 오디오 추출        | yt-dlp                                             |
| 코드 인식          | Chordino (chord-extractor 0.1.3, NNLS-Chroma VAMP) |
| 운지(fret/voicing) | @tombatossals/chords-db (MIT) 룩업                 |
| DB                 | Supabase (PostgreSQL)                              |
| 배포               | AWS EC2 t3.small + Docker, GitHub Actions CI/CD    |

> 코드 **인식**은 Chordino(풀 믹스 화성 인식)가 담당하고, fret/voicing(운지)은 오디오에서
> 추정하지 않고 chords-db 운지 데이터를 코드명으로 룩업해 산출한다.

## 아키텍쳐

<img width="1600" height="800" alt="Image" src="https://github.com/user-attachments/assets/c678f233-3cb4-4c2a-9da5-d2bd48184a23" />

## 프로젝트 구조

```
chordlens-be/
├── app/
│   ├── main.py              # FastAPI 앱, CORS, lifespan, GET /health
│   ├── db.py                # Supabase AsyncClient 싱글턴
│   ├── core/
│   │   ├── config.py        # 환경 변수 (pydantic-settings)
│   │   └── logging.py       # 구조화 로깅
│   ├── models/
│   │   ├── chord.py         # /extract 요청·응답, ChordItem 스키마
│   │   └── result.py        # /results 목록·상세 스키마
│   ├── routers/
│   │   ├── extract.py       # POST /extract
│   │   └── results.py       # GET /results, /results/popular, /results/{id}, POST /results/{id}/view
│   └── services/
│       ├── audio.py             # yt-dlp 오디오(MP3) + 자막 추출
│       ├── chord.py             # Chordino 코드 인식 + 라벨 정규화
│       ├── voicing.py           # chords-db 룩업 → fret/voicing/운지(frets, fingers, barres)
│       ├── lyrics.py            # 자막(VTT) → 가사 파싱
│       ├── cache.py             # Supabase 캐시 조회/저장
│       ├── result_service.py    # /results 조회 + 조회수
│       ├── yt_dlp_errors.py     # yt-dlp 에러 분류
│       ├── yt_dlp_guard.py      # 서킷 브레이커 + single-flight
│       └── data/
│           ├── guitar.json          # chords-db 운지 DB (MIT)
│           └── LICENSE-chords-db    # chords-db 라이선스/출처
├── supabase/
│   └── schema.sql           # chord_results 테이블 + 인덱스 생성 SQL
├── .github/workflows/
│   └── deploy.yml           # CI(pytest) + CD(EC2 배포)
├── requirements.txt
├── .env.example
└── Makefile
```

## Quick Start

### 1. 저장소 클론

```bash
git clone <repo-url>
cd chordlens-be
```

### 2. Docker 이미지 빌드

```bash
docker build -t chordlens-be .
```

> `requirements.txt`를 변경했다면 반드시 재빌드해야 한다(`make dev`는 빌드하지 않고 기존
> 이미지를 실행만 한다). 의존성 설치는 `vamp`의 빌드 격리 이슈와 `pkg_resources` 호환을
> 위해 `numpy<2` 선설치 → `vamp` `--no-build-isolation` 빌드 → `setuptools<81` 순으로 처리한다
> (Dockerfile 참고).

### 3. Supabase 테이블 생성

Supabase Dashboard → SQL Editor에서 `supabase/schema.sql` 전체를 실행한다.

### 4. 환경 변수 설정

```bash
cp .env.example .env
```

`.env` 파일을 열어 실제 값을 입력한다. 자세한 변수 목록은 아래 [환경 변수](#환경-변수) 참고.

### 5. 서버 실행

```bash
# Docker 컨테이너로 서버가 실행되며 `http://localhost:8000` 에서 응답.
make dev
```

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
  "video_id": "video_id",
  "title": "영상 제목",
  "channel_name": "채널명",
  "thumbnail_url": "https://...",
  "chords": [
    {
      "time": "0:12",
      "chord": "Am",
      "fret": 0,
      "voicing": "open",
      "frets": [-1, 0, 2, 2, 1, 0],
      "fingers": [0, 0, 2, 3, 1, 0],
      "base_fret": 1,
      "barres": []
    }
  ],
  "lyrics": [{ "time": "0:12", "text": "가사 한 줄" }],
  "cached": false
}
```

- `frets`/`fingers`: 6현 배열(저음 E현 → 고음 e현 순), `-1`=뮤트, `0`=개방. 프런트엔드는 이
  운지 데이터로 코드 다이어그램을 직접 렌더한다.
- `base_fret`: 다이어그램 시작 프렛. `barres`: 바레가 걸리는(base_fret 상대) 프렛 목록.
- `lyrics`: 자막이 있는 경우에만 포함(없으면 `null`).

**에러 코드** (HTTP status + `X-Error-Code` 응답 헤더)

| status | X-Error-Code                         | 사유                                      |
| ------ | ------------------------------------ | ----------------------------------------- |
| 400    | `INVALID_URL` / `VIDEO_UNAVAILABLE`  | 유효하지 않은 URL / 비공개·접근 불가 영상 |
| 401    | `AUTH_REQUIRED`                      | 쿠키/로그인이 필요한 영상                 |
| 429    | `RATE_LIMIT`                         | YouTube 요청이 일시적으로 제한됨          |
| 500    | `INTERNAL_ERROR`                     | 오디오 추출 또는 코드 인식 실패           |
| 503    | `YOUTUBE_BOT_CHECK` / `CIRCUIT_OPEN` | 봇 감지 / 서버 보호(서킷 오픈)            |
| 504    | `PIPELINE_TIMEOUT`                   | 처리 시간 초과 (기본 60초)                |

### `GET /results`

분석 결과 목록을 최신순으로 반환한다. 쿼리: `limit`(기본 20), `offset`(기본 0).

### `GET /results/popular`

조회수 기준 인기 결과 목록을 반환한다. 쿼리: `limit`(기본 20).

### `GET /results/{id}`

단일 분석 결과 상세를 반환한다(코드 + 가사 포함).

### `POST /results/{id}/view`

조회수를 1 증가시킨다(`204 No Content`).

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
    ├─ 서킷 브레이커 확인 (봇 감지 시 503 차단) + single-flight(동일 영상 중복 호출 합치기)
    ├─ yt-dlp → MP3 추출 (+ 자막 VTT 인라인 다운로드)
    ├─ Chordino → 코드 인식 (메이저/마이너/7/maj7/m7/dim/aug/sus 등, 무화음 N 제외)
    ├─ chords-db 룩업 → 각 코드의 fret/voicing/운지(frets, fingers, barres) 산출
    ├─ 자막 VTT 파싱 → 가사(lyrics)
    ├─ Supabase 저장
    └─ 응답 반환 (cached: false)
```

## 환경 변수

| 변수명                          | 기본값                  | 설명                                 |
| ------------------------------- | ----------------------- | ------------------------------------ |
| `SUPABASE_URL`                  | (필수)                  | Supabase 프로젝트 URL                |
| `SUPABASE_KEY`                  | (필수)                  | Supabase service_role 키             |
| `ALLOWED_ORIGIN`                | `http://localhost:3000` | CORS 허용 도메인 (프론트엔드 URL)    |
| `YOUTUBE_COOKIES_PATH`          | `""`                    | yt-dlp 쿠키 파일 경로                |
| `YTDLP_PROXY_URL`               | `""`                    | yt-dlp 프록시 URL                    |
| `YTDLP_PROXY_COUNTRY`           | `""`                    | 프록시 국가 코드(로깅/식별용)        |
| `YTDLP_USE_COOKIES`             | `false`                 | 쿠키 파일 사용 여부                  |
| `YT_DLP_CONCURRENCY`            | `1`                     | 동시 yt-dlp 워커 수(기본 직렬화)     |
| `YOUTUBE_CIRCUIT_OPEN_SECONDS`  | `1800`                  | 봇 감지 시 서킷이 열려 있는 시간(초) |
| `YT_DLP_TIMEOUT_SECONDS`        | `60`                    | yt-dlp 한 호출의 소켓 타임아웃(초)   |
| `INFLIGHT_WAIT_TIMEOUT_SECONDS` | `120`                   | single-flight 대기 최대 시간(초)     |
| `YTDLP_RETRY_COUNT`             | `1`                     | retryable 에러 추가 재시도 횟수      |
| `YTDLP_BACKOFF_SECONDS`         | `1.0`                   | 재시도 전 대기 시간(초)              |

## CI/CD

`.github/workflows/deploy.yml` (GitHub Actions, `name: CI-CD-server`):

- **CI (`test` job)** — `main` push 및 PR에서 실행. 의존성 설치 후 `python -m pytest tests/`.
  prod와 동일한 설치 절차를 써서 의존성/버전 오류도 사전에 잡는다.
- **CD (`deploy` job)** — `main` push에서 **test 통과 시에만** EC2에 SSH 접속 →
  `git pull` → `docker build` → 컨테이너 교체.
- 배포 스크립트는 `set -e`로 동작하여, `docker build` 실패 시 기존 컨테이너를 유지한다
  (구 이미지 재기동/다운타임 방지).

## 라이선스 메모

- **코드 인식**: Chordino / NNLS-Chroma (`chord-extractor`) — **GPL**. 본 백엔드는 서버 내부
  실행(import)만 하며 바이너리/소스를 재배포하지 않으므로 GPL 소스 공개 의무가 발동하지
  않는다. Docker 이미지를 외부 배포할 경우 의무가 발동할 수 있으므로 "내부 서버 실행 전용"
  전제를 유지한다.
- **운지 데이터**: `@tombatossals/chords-db` — **MIT**. 원문/저작자 표기는
  `app/services/data/LICENSE-chords-db` 참고.
