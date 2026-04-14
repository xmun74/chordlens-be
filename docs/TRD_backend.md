# CodeLens — Backend Technical Requirements Document (TRD)

---

## 문서 정보

| 항목       | 내용                          |
| ---------- | ----------------------------- |
| 문서 번호  | TRD-BE-001                    |
| 프로젝트명 | CodeLens                      |
| 작성일     | 2026-04-13                    |
| 상태       | 확정                          |
| 레포 위치  | `codelens-backend` (멀티레포) |
| 연관 문서  | TRD_frontend.md, PRD.md       |

---

## 1. 기술 스택

| 항목           | 기술              | 버전            |
| -------------- | ----------------- | --------------- |
| 언어           | Python            | 3.11            |
| 웹 프레임워크  | FastAPI           | 0.111           |
| ASGI 서버      | uvicorn           | 0.29            |
| 오디오 추출    | yt-dlp            | 2024.4+         |
| 코드 인식      | autochord         | 0.1.3           |
| DB 클라이언트  | supabase-py       | 2.4             |
| 환경 변수 관리 | pydantic-settings | 2.2             |
| 리버스 프록시  | nginx             | -               |
| 프로세스 관리  | systemd           | -               |
| 배포 환경      | AWS EC2 t2.micro  | 프리티어 12개월 |
| CI/CD          | GitHub Actions    | -               |

---

## 2. 시스템 아키텍처

### 2-1. 전체 구성도

```
[Next.js — Vercel]
        │
        │ POST /extract { youtube_url }
        ▼
[FastAPI — AWS EC2 t2.micro]
        │
        ├─── 캐시 확인 ──────────────────► [Supabase DB]
        │         │ 히트 시 즉시 반환
        │         │ 미스 시 아래 파이프라인 실행
        │
        ├─── yt-dlp ──► YouTube → MP3 추출
        │
        ├─── autochord ──► MP3 → 기타 코드명 변환
        │
        └─── 결과 저장 ──────────────────► [Supabase DB]
                │
                ▼
        JSON Response 반환
        { id, title, channelName, thumbnailUrl, chords[] }
```

### 2-2. 레이어 구조

| 레이어  | 역할                                                   |
| ------- | ------------------------------------------------------ |
| Router  | HTTP 요청 수신, 응답 반환, 에러 처리                   |
| Service | 비즈니스 로직 — 오디오 추출, 코드 인식, 캐시 조회/저장 |
| Model   | 요청/응답 Pydantic 스키마                              |
| Core    | 환경 변수, 앱 설정                                     |

---

## 3. 핵심 처리 파이프라인

### 3-1. 코드 추출 파이프라인

```
YouTube URL 수신
      │
      ▼
URL 유효성 검사
      │ 실패 → 400 반환
      ▼
Supabase 캐시 조회 (video_url 기준)
      │ 캐시 히트 → 즉시 반환 (cached: true)
      │ 캐시 미스
      ▼
yt-dlp: YouTube → MP3 추출 (/tmp/codelens/ 임시 저장)
      │ 실패 → 500 반환
      ▼
ffmpeg: MP3 → WAV 변환 (autochord 입력 형식)
      │
      ▼
autochord: WAV → 코드명 리스트 변환
      │ [(시작시간, 종료시간, 코드명), ...]
      ▼
코드명 정규화 + 무음 제거 + 인접 중복 병합
      │
      ▼
Supabase 저장 + ID 발급
      │
      ▼
임시 파일 삭제 (MP3, WAV)
      │
      ▼
JSON Response 반환 (cached: false)
```

### 3-2. 캐싱 전략

동일 YouTube URL에 대한 재요청은 DB에서 즉시 반환한다. autochord 처리가 영상당 10~20초 소요되기 때문에 캐싱은 성능에 직접적인 영향을 준다.

- 캐시 키: `video_url`
- 캐시 저장소: Supabase `chord_results` 테이블
- 중복 저장 허용 (video_url Unique 제약 없음), 최신 1건 조회
- 캐시 만료 정책: 없음 (명시적 삭제 전까지 유지)

---

## 4. API 명세

### 4-1. POST /extract

| 항목 | 내용                                   |
| ---- | -------------------------------------- |
| 경로 | `POST /extract`                        |
| 역할 | YouTube URL → 기타 코드 분석 결과 반환 |
| 인증 | 없음 (v0.1 기준)                       |

**요청 바디**

| 필드          | 타입   | 필수 | 설명             |
| ------------- | ------ | ---- | ---------------- |
| `youtube_url` | string | Y    | YouTube 영상 URL |

**응답 바디 (200)**

| 필드            | 타입          | 설명                                   |
| --------------- | ------------- | -------------------------------------- |
| `id`            | string (uuid) | Supabase 저장 ID — 공유 링크용         |
| `title`         | string        | 영상 제목                              |
| `channel_name`  | string        | 채널명                                 |
| `thumbnail_url` | string        | 썸네일 URL                             |
| `chords`        | array         | `[{ time: "0:12", chord: "Am" }, ...]` |
| `cached`        | boolean       | 캐시 반환 여부                         |

**에러 응답**

| 상태코드 | 사유                            |
| -------- | ------------------------------- |
| 400      | 유효하지 않은 YouTube URL       |
| 400      | 비공개 / 연령 제한 영상         |
| 422      | 요청 바디 누락 (FastAPI 기본)   |
| 500      | 오디오 추출 또는 코드 인식 실패 |
| 504      | 처리 시간 초과 (60초)           |

---

### 4-2. GET /health

| 항목 | 내용                                       |
| ---- | ------------------------------------------ |
| 경로 | `GET /health`                              |
| 역할 | 서버 상태 확인 (EC2 모니터링, 배포 검증용) |
| 응답 | `{ "status": "ok" }`                       |

---

## 5. 데이터베이스 스키마

### chord_results 테이블

| 컬럼            | 타입        | 설명                              |
| --------------- | ----------- | --------------------------------- |
| `id`            | uuid, PK    | 자동 생성                         |
| `video_url`     | text        | YouTube URL (인덱스, Unique 아님) |
| `title`         | text        | 영상 제목                         |
| `channel_name`  | text        | 채널명                            |
| `thumbnail_url` | text        | 썸네일 URL                        |
| `chords`        | jsonb       | `[{ time, chord }]` 배열          |
| `created_at`    | timestamptz | 자동 생성                         |

**인덱스**

- `video_url` — 캐시 조회 성능
- `created_at DESC` — 최신 1건 조회 성능

---

## 6. 배포 아키텍처

### 6-1. 인프라 구성

```
GitHub (main 브랜치 푸시)
      │ GitHub Actions
      ▼
AWS EC2 t2.micro (Ubuntu 22.04)
  ├── nginx (리버스 프록시, 80/443 포트)
  │       │ proxy_pass
  │       ▼
  └── uvicorn (FastAPI, 8000 포트)
          │ systemd로 프로세스 관리
          │ 재시작 시 자동 복구
```

### 6-2. AWS EC2 스펙

| 항목          | 값                               |
| ------------- | -------------------------------- |
| 인스턴스 타입 | t2.micro                         |
| RAM           | 1GB + 스왑 1GB                   |
| OS            | Ubuntu 22.04 LTS                 |
| 스토리지      | EBS 20GB                         |
| 오픈 포트     | 22 (SSH), 80 (HTTP), 443 (HTTPS) |
| 프리티어 기간 | 계정 생성 후 12개월              |

> **스왑 메모리 필수:** autochord TensorFlow 모델이 약 400~500MB를 점유한다. 스왑 없이는 OOM으로 서버가 종료된다.

### 6-3. 프로세스 관리

FastAPI 서버는 systemd 서비스로 등록한다. EC2 재시작 또는 서버 비정상 종료 시 자동으로 재기동한다.

### 6-4. CI/CD

`backend/` 경로 변경이 포함된 `main` 브랜치 푸시 시 GitHub Actions가 EC2에 SSH 접속하여 자동 배포한다.

```
main 브랜치 푸시 (backend/** 변경)
      │ GitHub Actions
      ▼
EC2 SSH 접속
  └── git pull
  └── pip install -r requirements.txt
  └── systemctl restart codelens
```

---

## 7. 환경 변수

| 변수명           | 설명                               |
| ---------------- | ---------------------------------- |
| `SUPABASE_URL`   | Supabase 프로젝트 URL              |
| `SUPABASE_KEY`   | Supabase service_role 키           |
| `ALLOWED_ORIGIN` | CORS 허용 도메인 (Vercel 배포 URL) |

---

## 8. 비기능 요구사항

| 항목                | 기준                                       |
| ------------------- | ------------------------------------------ |
| 캐시 히트 응답 시간 | 500ms 이하                                 |
| 캐시 미스 처리 시간 | 3분 영상 기준 20초 이하                    |
| 요청 타임아웃       | 60초 초과 시 504 반환                      |
| 가동률              | systemd 자동 재시작으로 99% 이상 목표      |
| 임시 파일 관리      | 처리 성공/실패 무관하게 즉시 삭제          |
| 동시 요청           | t2.micro 단일 인스턴스 기준 순차 처리 허용 |

---

## 9. 제약 사항

| 항목           | 내용                                                                                     |
| -------------- | ---------------------------------------------------------------------------------------- |
| YouTube ToS    | yt-dlp 오디오 추출은 개인 프로젝트 수준에서만 운영. 상업화 시 YouTube Data API 전환 필요 |
| 코드 인식 범위 | 장조 12 + 단조 12 = 24개 코드만 지원. 7th, sus4, dim 등 확장 코드 미지원                 |
| t2.micro 성능  | RAM 1GB — 동시 요청 처리 시 성능 저하 가능. 트래픽 증가 시 인스턴스 타입 업그레이드 필요 |
| 비공개 영상    | yt-dlp로 접근 불가. 400 에러 반환                                                        |

---

## 10. 단계별 작업 단위

### Phase 1 — 로컬 환경 구성 및 파이프라인 검증

목표: 로컬에서 YouTube URL → 기타 코드 JSON 반환까지 전체 파이프라인 동작 확인

| 작업                     | 설명                                                               |
| ------------------------ | ------------------------------------------------------------------ |
| 프로젝트 초기 세팅       | `codelens-backend` 레포 생성, Python 가상환경, 디렉토리 구조 구성  |
| 의존성 설치              | yt-dlp, autochord, FastAPI, uvicorn, supabase-py, ffmpeg 설치 확인 |
| yt-dlp 오디오 추출 구현  | YouTube URL → MP3 추출, 임시 파일 저장/삭제                        |
| autochord 코드 인식 구현 | MP3 → WAV 변환 → 코드명 리스트 반환, 정규화 로직                   |
| FastAPI 서버 구성        | `POST /extract`, `GET /health` 엔드포인트 구현                     |
| 로컬 통합 테스트         | 실제 YouTube URL로 전체 파이프라인 동작 검증                       |

---

### Phase 2 — Supabase 연동

목표: 캐싱 적용 및 결과 영속화

| 작업                   | 설명                                      |
| ---------------------- | ----------------------------------------- |
| Supabase 프로젝트 생성 | `chord_results` 테이블 및 인덱스 생성     |
| 캐시 조회 구현         | `video_url` 기준 캐시 히트/미스 분기 처리 |
| 캐시 저장 구현         | 분석 결과 저장 및 UUID 반환               |
| 환경 변수 관리         | `pydantic-settings` 기반 설정 파일 구성   |
| CORS 설정              | `ALLOWED_ORIGIN` 기반 Next.js 도메인 허용 |

---

### Phase 3 — AWS EC2 배포

목표: EC2 프리티어에 서버 배포 및 24/7 운영 환경 구성

| 작업                | 설명                                              |
| ------------------- | ------------------------------------------------- |
| EC2 인스턴스 생성   | t2.micro, Ubuntu 22.04, 보안 그룹 포트 설정       |
| 서버 환경 구성      | Python 3.11, ffmpeg, nginx, 스왑 메모리(1GB) 설치 |
| 애플리케이션 배포   | 레포 클론, 가상환경 구성, 환경 변수 설정          |
| systemd 서비스 등록 | FastAPI 서버 자동 시작 및 재시작 설정             |
| nginx 설정          | 리버스 프록시, 포트 포워딩 설정                   |
| 배포 검증           | `GET /health` 응답 확인, 실제 요청 테스트         |

---

### Phase 4 — CI/CD 및 운영 자동화

목표: main 브랜치 푸시 시 EC2 자동 배포

| 작업                           | 설명                                     |
| ------------------------------ | ---------------------------------------- |
| GitHub Actions 워크플로우 작성 | `backend/**` 변경 시 EC2 SSH 배포 트리거 |
| GitHub Secrets 등록            | `EC2_HOST`, `EC2_SSH_KEY` 등록           |
| 자동 배포 검증                 | main 푸시 후 배포 및 헬스체크 자동 확인  |
