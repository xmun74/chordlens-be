"""tests/conftest.py — 테스트 환경 부트스트랩.

heavy 의존성(basic_pitch)을 stub 처리해 chord 서비스 import 만으로도
무거운 ML 라이브러리 로딩 없이 라우터 테스트를 돌릴 수 있게 한다.
"""
import os
import sys
import types


# ── 환경 변수 기본값 ─────────────────────────────────────────
os.environ.setdefault("SUPABASE_URL", "http://localhost.test")
os.environ.setdefault("SUPABASE_KEY", "test-key")


# ── basic_pitch stub ────────────────────────────────────────
# basic_pitch.inference.predict 만 노출하면 충분 — 실제 호출은 테스트가 mock 한다.
if "basic_pitch" not in sys.modules:
    basic_pitch = types.ModuleType("basic_pitch")
    inference = types.ModuleType("basic_pitch.inference")

    def _stub_predict(*_args, **_kwargs):  # pragma: no cover — 테스트는 별도 mock
        raise RuntimeError("basic_pitch.inference.predict stub called without mock")

    inference.predict = _stub_predict
    basic_pitch.inference = inference
    sys.modules["basic_pitch"] = basic_pitch
    sys.modules["basic_pitch.inference"] = inference
