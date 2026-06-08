# ── 베이스 이미지 ────────────────────────────────────────
FROM python:3.11-slim

# ── 시스템 패키지 ─────────────────────────────────────────
# ffmpeg: yt-dlp 오디오 추출용
# curl/unzip/ca-certificates: Deno 설치용
# libsndfile1: chord-extractor(Chordino/vamp) 오디오 디코딩 런타임 의존
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gcc \
    g++ \
    curl \
    unzip \
    ca-certificates \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# ── Deno 설치 ────────────────────────────────────────────
# yt-dlp[default]가 일부 추출기에서 Deno 런타임을 사용
ENV DENO_INSTALL=/usr/local
RUN curl -fsSL https://deno.land/install.sh | sh -s -- -y \
    && deno --version

# ── 작업 디렉토리 ─────────────────────────────────────────
WORKDIR /app

# ── 의존성 설치 ───────────────────────────────────────────
# chord-extractor의 의존 vamp는 setup.py가 빌드 타임에 numpy를 import 한다.
# PEP517 빌드 격리 환경엔 numpy가 없으므로, numpy(+setuptools/wheel) 선설치 후
# vamp만 --no-build-isolation 으로 빌드해 선설치 numpy를 사용하게 한다.
# chord-extractor는 linux 64-bit용 Chordino 바이너리를 동봉하므로 별도 VAMP_PATH 설정
# 불필요(linux/amd64 빌드 전제). 비표준 아키텍처면 VAMP_PATH 지정 필요.
COPY requirements.txt .
# setuptools<81: chord-extractor 런타임이 pkg_resources(구 setuptools 모듈)를 import 한다.
#   최신 setuptools(81+)는 pkg_resources를 제거해 ImportError 발생 → 버전 고정.
# wheel: vamp를 --no-build-isolation 으로 빌드할 때 메인 env에 빌드 도구 필요.
RUN pip install --no-cache-dir "setuptools<81" wheel
RUN pip install --no-cache-dir "numpy<2"
RUN pip install --no-cache-dir --no-build-isolation vamp==1.1.0
RUN pip install --no-cache-dir -r requirements.txt

# ── 소스 코드 복사 ────────────────────────────────────────
COPY app/ ./app/

# ── 임시 파일 디렉토리 ────────────────────────────────────
RUN mkdir -p /tmp/chordlens

# ── 포트 ──────────────────────────────────────────────────
EXPOSE 8000

# ── 실행 ──────────────────────────────────────────────────
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
