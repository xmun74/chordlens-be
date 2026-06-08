"""tests/conftest.py — 테스트 환경 부트스트랩.

코드 인식 엔진(Chordino, chord-extractor)은 chord.py 내부 임포트 가드로 처리되며
테스트는 `app.services.chord.Chordino` 심볼을 patch 한다. 별도 stub 불필요.
"""
import os


# ── 환경 변수 기본값 ─────────────────────────────────────────
os.environ.setdefault("SUPABASE_URL", "http://localhost.test")
os.environ.setdefault("SUPABASE_KEY", "test-key")
