# tests/services/test_voicing.py
"""voicing 룩업 단위 테스트. guitar.json 실데이터 사용."""
import app.services.voicing as voicing
from app.services.voicing import Voicing, lookup_voicing


def test_lookup_c_major_open():
    # chords-db: C major 첫 position은 baseFret=1, barres=[], 개방현 포함 → open(fret 0).
    v = lookup_voicing("C")
    assert v.voicing == "open"
    assert v.fret == 0
    # 실제 운지 데이터가 채워진다.
    assert len(v.frets) == 6
    assert len(v.fingers) == 6
    assert v.base_fret == 1


def test_lookup_f_major_barre():
    # F major 첫 position은 baseFret=1, barres=[1] → barre.
    v = lookup_voicing("F")
    assert v.voicing == "barre"
    assert v.fret >= 1
    assert v.barres  # 바레 프렛 목록 존재


def test_lookup_ebm_carries_positions():
    # Ebm: chords-db Eb minor 첫 position(부분 운지). 운지 데이터가 손실 없이 전달돼야 한다.
    v = lookup_voicing("Ebm")
    assert len(v.frets) == 6
    assert len(v.fingers) == 6
    # 최소 한 현은 실제로 운지된다(-1/0이 아닌 값 존재).
    assert any(f > 0 for f in v.frets)


def test_lookup_bb_enharmonic():
    v = lookup_voicing("Bb")
    assert v.voicing in ("open", "barre")
    assert len(v.frets) == 6


def test_lookup_db_maps_to_csharp():
    # Db → enharmonic 매핑으로 "Csharp" 룩업. C#과 동일 결과.
    assert lookup_voicing("Db") == lookup_voicing("C#")


def test_lookup_a_minor_open():
    v = lookup_voicing("Am")
    assert v.voicing == "open"
    assert v.fret == 0


def test_lookup_unknown_chord_default():
    # chords-db 미수록/파싱 불가 → 빈 기본값(Voicing()).
    assert lookup_voicing("Am7b5") == Voicing()
    assert lookup_voicing("Zxy") == Voicing()
    assert lookup_voicing("") == Voicing()
    # 기본값은 빈 운지 + open/0.
    default = lookup_voicing("Zxy")
    assert default.frets == []
    assert default.voicing == "open"
    assert default.fret == 0


def test_lookup_empty_db_returns_default(monkeypatch):
    # _DB가 비어있으면(파일 부재 시나리오) 모든 룩업이 빈 기본값 반환.
    monkeypatch.setattr(voicing, "_DB", {})
    assert voicing.lookup_voicing("C") == Voicing()
    assert voicing.lookup_voicing("F") == Voicing()


def test_load_db_missing_file_returns_empty(monkeypatch):
    # 데이터 경로가 없으면 _load_db는 빈 dict 반환(예외 없이).
    monkeypatch.setattr(voicing, "_DATA_PATH", "/nonexistent/guitar.json")
    assert voicing._load_db() == {}
