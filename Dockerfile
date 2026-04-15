# ── 베이스 이미지 ────────────────────────────────────────
# tensorflow 2.15 지원 최신 slim (python 3.11)
FROM python:3.11-slim

# ── 시스템 패키지 ─────────────────────────────────────────
# ffmpeg: 오디오 변환 / gcc: 일부 pip 패키지 빌드
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# ── 작업 디렉토리 ─────────────────────────────────────────
WORKDIR /app

# ── 의존성 설치 (레이어 캐시 활용) ────────────────────────
# requirements.txt가 바뀌지 않으면 이 레이어는 재빌드 안 함
COPY requirements.txt .
# vamp 패키지가 빌드 시 numpy를 필요로 하므로 먼저 설치
RUN pip install --no-cache-dir numpy
RUN pip install --no-cache-dir -r requirements.txt

# ── 소스 코드 복사 ────────────────────────────────────────
COPY app/ ./app/

# ── 임시 파일 디렉토리 ────────────────────────────────────
RUN mkdir -p /tmp/chordlens

# ── 포트 ──────────────────────────────────────────────────
EXPOSE 8000

# ── 실행 ──────────────────────────────────────────────────
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
