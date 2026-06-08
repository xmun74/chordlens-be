# tests/services/test_chord.py
"""코드 인식 서비스 테스트.

Chordino(Vamp 바이너리 의존)는 단위테스트에서 호출하지 않고 patch 한다.
normalize_chord/lookup_voicing(via recognize_chords)는 실제 로직을 검증한다.
"""
from collections import namedtuple
from unittest.mock import MagicMock, patch

import pytest

from app.models.chord import ChordItem
from app.services.chord import (
    _seconds_to_time_str,
    normalize_chord,
    recognize_chords,
)

# 라이브러리의 ChordChange와 동일 필드(chord, timestamp)를 가진 대체 NamedTuple.
ChordChange = namedtuple("ChordChange", ["chord", "timestamp"])


def _patch_chordino(changes):
    """Chordino mock 컨텍스트. instance.extract가 changes를 반환."""
    mock_cls = MagicMock()
    instance = mock_cls.return_value
    instance.extract.return_value = changes
    return patch("app.services.chord.Chordino", mock_cls)


def _dummy_mp3(tmp_path):
    p = tmp_path / "test.mp3"
    p.write_bytes(b"dummy")
    return str(p)


# ── _seconds_to_time_str ─────────────────────────────────────────

def test_seconds_to_time_str_zero():
    assert _seconds_to_time_str(0.0) == "0:00"


def test_seconds_to_time_str_minute():
    assert _seconds_to_time_str(65.0) == "1:05"


# ── normalize_chord (정규화 실로직) ───────────────────────────────

def test_normalize_chord_colon_min():
    assert normalize_chord("C:min") == "Cm"


def test_normalize_chord_colon_dominant7():
    assert normalize_chord("G:7") == "G7"


def test_normalize_chord_colon_maj7():
    assert normalize_chord("C:maj7") == "Cmaj7"


def test_normalize_chord_colon_maj_dropped():
    assert normalize_chord("C:maj") == "C"


def test_normalize_chord_slash_removed():
    assert normalize_chord("C/E") == "C"


def test_normalize_chord_n_returns_none():
    assert normalize_chord("N") is None


def test_normalize_chord_empty_returns_none():
    assert normalize_chord("") is None


def test_normalize_chord_idempotent():
    assert normalize_chord("Am7") == "Am7"


def test_normalize_chord_invalid_root_returns_none():
    assert normalize_chord("xyz") is None


# ── recognize_chords (정상) ──────────────────────────────────────

def test_recognize_chords_returns_chord_items(tmp_path):
    audio = _dummy_mp3(tmp_path)
    changes = [ChordChange("Cm", 0.0), ChordChange("G7", 3.0)]
    with _patch_chordino(changes):
        result = recognize_chords(audio)

    assert len(result) == 2
    assert all(isinstance(item, ChordItem) for item in result)
    assert all(item.voicing in ("open", "barre") for item in result)


def test_recognize_chords_first_chord_lookup(tmp_path):
    audio = _dummy_mp3(tmp_path)
    with _patch_chordino([ChordChange("Cm", 0.0)]):
        result = recognize_chords(audio)

    assert result[0].chord == "Cm"
    # chords-db: C minor 첫 position은 baseFret=1, barres=[] → open.
    assert result[0].voicing == "open"
    assert result[0].fret == 0


def test_recognize_chords_carries_voicing_data(tmp_path):
    # ChordItem이 chords-db 운지 데이터(frets/fingers/base_fret/barres)를 실어 보낸다.
    audio = _dummy_mp3(tmp_path)
    with _patch_chordino([ChordChange("Ebm", 0.0)]):
        result = recognize_chords(audio)

    item = result[0]
    assert item.chord == "Ebm"
    assert len(item.frets) == 6
    assert len(item.fingers) == 6
    assert item.base_fret >= 1
    # Ebm은 chords-db에 존재 → 실제 운지가 채워진다.
    assert any(f > 0 for f in item.frets)


def test_recognize_chords_time_format(tmp_path):
    audio = _dummy_mp3(tmp_path)
    changes = [ChordChange("C", 0.0), ChordChange("G", 65.0)]
    with _patch_chordino(changes):
        result = recognize_chords(audio)

    assert result[0].time == "0:00"
    assert result[1].time == "1:05"


def test_recognize_chords_skips_no_chord(tmp_path):
    audio = _dummy_mp3(tmp_path)
    changes = [ChordChange("Cm", 0.0), ChordChange("N", 2.0), ChordChange("G7", 3.0)]
    with _patch_chordino(changes):
        result = recognize_chords(audio)

    chords = [item.chord for item in result]
    assert "N" not in chords
    assert chords == ["Cm", "G7"]


def test_recognize_chords_deduplicates_adjacent(tmp_path):
    audio = _dummy_mp3(tmp_path)
    changes = [ChordChange("C", 0.0), ChordChange("C", 1.0), ChordChange("G", 2.0)]
    with _patch_chordino(changes):
        result = recognize_chords(audio)

    assert [item.chord for item in result] == ["C", "G"]


def test_recognize_chords_same_chord_after_n_is_new_item(tmp_path):
    # N 이후 동일 코드 재등장 → prev 리셋되어 새 항목으로 기록.
    audio = _dummy_mp3(tmp_path)
    changes = [ChordChange("C", 0.0), ChordChange("N", 1.0), ChordChange("C", 2.0)]
    with _patch_chordino(changes):
        result = recognize_chords(audio)

    assert [item.chord for item in result] == ["C", "C"]
    assert [item.time for item in result] == ["0:00", "0:02"]


# ── recognize_chords (에러) ──────────────────────────────────────

def test_recognize_chords_file_not_found():
    with pytest.raises(FileNotFoundError):
        recognize_chords("/nonexistent/path.mp3")


def test_recognize_chords_extract_raises_runtime_error(tmp_path):
    audio = _dummy_mp3(tmp_path)
    mock_cls = MagicMock()
    mock_cls.return_value.extract.side_effect = RuntimeError("vamp boom")
    with patch("app.services.chord.Chordino", mock_cls):
        with pytest.raises(RuntimeError, match="코드 인식 실패"):
            recognize_chords(audio)


def test_recognize_chords_empty_changes(tmp_path):
    audio = _dummy_mp3(tmp_path)
    with _patch_chordino([]):
        result = recognize_chords(audio)

    assert result == []
