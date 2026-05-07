# ── 베이스 이미지 ────────────────────────────────────────
FROM python:3.11-slim

# ── 시스템 패키지 ─────────────────────────────────────────
# ffmpeg: yt-dlp 오디오 추출용
# curl/unzip/ca-certificates: Deno 설치용
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gcc \
    g++ \
    curl \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ── Deno 설치 ────────────────────────────────────────────
# yt-dlp[default]가 일부 추출기에서 Deno 런타임을 사용
ENV DENO_INSTALL=/usr/local
RUN curl -fsSL https://deno.land/install.sh | sh -s -- -y \
    && deno --version

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
