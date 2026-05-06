# tests/services/test_chord.py
import numpy as np
import pytest
from unittest.mock import patch
from app.services.chord import (
    _build_chord_templates,
    _chroma_to_chord,
    _detect_voicing,
    recognize_chords,
)
from app.models.chord import ChordItem


# ── _build_chord_templates ───────────────────────────────────────

def test_build_chord_templates_count():
    templates = _build_chord_templates()
    assert len(templates) == 108  # 12 roots × 9 types


def test_build_chord_templates_c_major():
    templates = _build_chord_templates()
    t = templates['C']
    assert t[0] == 1  # C
    assert t[4] == 1  # E
    assert t[7] == 1  # G
    assert t.sum() == 3


def test_build_chord_templates_am():
    templates = _build_chord_templates()
    t = templates['Am']
    assert t[9] == 1  # A
    assert t[0] == 1  # C
    assert t[4] == 1  # E


# ── _chroma_to_chord ─────────────────────────────────────────────

def test_chroma_to_chord_c_major():
    chroma = np.zeros(12)
    chroma[[0, 4, 7]] = 1  # C, E, G
    assert _chroma_to_chord(chroma) == 'C'


def test_chroma_to_chord_a_minor():
    chroma = np.zeros(12)
    chroma[[9, 0, 4]] = 1  # A, C, E
    assert _chroma_to_chord(chroma) == 'Am'


def test_chroma_to_chord_g_dominant7():
    chroma = np.zeros(12)
    chroma[[7, 11, 2, 5]] = 1  # G, B, D, F
    assert _chroma_to_chord(chroma) == 'G7'


def test_chroma_to_chord_d_minor7():
    chroma = np.zeros(12)
    chroma[[2, 5, 9, 0]] = 1  # D, F, A, C
    assert _chroma_to_chord(chroma) == 'Dm7'


def test_chroma_to_chord_b_diminished():
    chroma = np.zeros(12)
    chroma[[11, 2, 5]] = 1  # B, D, F
    assert _chroma_to_chord(chroma) == 'Bdim'


def test_chroma_to_chord_c_augmented():
    chroma = np.zeros(12)
    chroma[[0, 4, 8]] = 1  # C, E, G#
    assert _chroma_to_chord(chroma) == 'Caug'


def test_chroma_to_chord_empty_returns_none():
    assert _chroma_to_chord(np.zeros(12)) is None


def test_chroma_to_chord_uniform_returns_none():
    # 모든 피치 균일 → 유사도 낮음 → None
    assert _chroma_to_chord(np.ones(12) * 0.1) is None


# ── _detect_voicing ──────────────────────────────────────────────

def test_detect_voicing_open_when_open_string_present():
    # A2=45 는 개방현 → open
    voicing, fret = _detect_voicing([45, 52, 57, 60, 64])
    assert voicing == 'open'
    assert fret == 0


def test_detect_voicing_barre_when_no_open_string():
    # 46, 53, 58, 62, 65 은 모두 개방현이 아님
    voicing, fret = _detect_voicing([46, 53, 58, 62, 65])
    assert voicing == 'barre'
    assert fret >= 1


def test_detect_voicing_fret_capped_at_12():
    voicing, fret = _detect_voicing([70, 74, 77])
    assert voicing == 'barre'
    assert fret <= 12


# ── recognize_chords ─────────────────────────────────────────────

_FAKE_NOTE_EVENTS = [
    # (start, end, midi_pitch, amplitude, pitch_bends)
    # 윈도우 0~1s: Am (A=45, E=52, A=57, C=60, E=64)
    (0.0, 1.5, 45, 0.9, []),  # A2 (개방현)
    (0.0, 1.5, 52, 0.9, []),  # E3
    (0.0, 1.5, 57, 0.9, []),  # A3
    (0.0, 1.5, 60, 0.9, []),  # C4
    (0.0, 1.5, 64, 0.9, []),  # E4 (개방현)
    # 윈도우 2~3s: Em (E=40, B=47, E=52, G=55, B=59)
    (2.0, 3.5, 40, 0.9, []),  # E2 (개방현)
    (2.0, 3.5, 47, 0.9, []),  # B2
    (2.0, 3.5, 52, 0.9, []),  # E3
    (2.0, 3.5, 55, 0.9, []),  # G3 (개방현)
    (2.0, 3.5, 59, 0.9, []),  # B3 (개방현)
]


def test_recognize_chords_returns_chord_items(tmp_path):
    dummy = tmp_path / 'test.mp3'
    dummy.write_bytes(b'dummy')

    with patch('app.services.chord.predict', return_value=(None, None, _FAKE_NOTE_EVENTS)):
        result = recognize_chords(str(dummy))

    assert len(result) >= 1
    assert all(isinstance(item, ChordItem) for item in result)
    assert all(item.voicing in ('open', 'barre') for item in result)


def test_recognize_chords_first_chord_am_open(tmp_path):
    dummy = tmp_path / 'test.mp3'
    dummy.write_bytes(b'dummy')

    with patch('app.services.chord.predict', return_value=(None, None, _FAKE_NOTE_EVENTS)):
        result = recognize_chords(str(dummy))

    assert result[0].chord == 'Am'
    assert result[0].voicing == 'open'
    assert result[0].fret == 0


def test_recognize_chords_deduplicates_adjacent(tmp_path):
    dummy = tmp_path / 'test.mp3'
    dummy.write_bytes(b'dummy')

    repeated = [
        (0.0, 3.0, 45, 0.9, []),
        (0.0, 3.0, 52, 0.9, []),
        (0.0, 3.0, 57, 0.9, []),
        (0.0, 3.0, 60, 0.9, []),
        (0.0, 3.0, 64, 0.9, []),
    ]
    with patch('app.services.chord.predict', return_value=(None, None, repeated)):
        result = recognize_chords(str(dummy))

    chords = [item.chord for item in result]
    assert chords == list(dict.fromkeys(chords))


def test_recognize_chords_filters_low_amplitude(tmp_path):
    dummy = tmp_path / 'test.mp3'
    dummy.write_bytes(b'dummy')

    low_amp = [
        (0.0, 1.0, 45, 0.1, []),
        (0.0, 1.0, 52, 0.1, []),
        (0.0, 1.0, 57, 0.1, []),
    ]
    with patch('app.services.chord.predict', return_value=(None, None, low_amp)):
        result = recognize_chords(str(dummy))

    assert result == []


def test_recognize_chords_empty_events(tmp_path):
    dummy = tmp_path / 'test.mp3'
    dummy.write_bytes(b'dummy')

    with patch('app.services.chord.predict', return_value=(None, None, [])):
        result = recognize_chords(str(dummy))

    assert result == []


def test_recognize_chords_file_not_found():
    with pytest.raises(FileNotFoundError):
        recognize_chords('/nonexistent/path.mp3')
