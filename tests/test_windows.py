"""Window helpers: coherent gain, energy, ENBW against known closed forms."""

from __future__ import annotations

import numpy as np
import pytest

from ofo_analyzer.dsp.windows import coherent_gain, enbw, window, window_energy


def test_rectangular_window_constants():
    w = window("boxcar", 1024)
    assert coherent_gain(w) == pytest.approx(1.0)
    assert window_energy(w) == pytest.approx(1024.0)
    assert enbw(w, 48_000.0) == pytest.approx(48_000.0 / 1024.0)  # exactly one bin


def test_hann_window_constants():
    n = 4096
    w = window("hann", n)
    assert coherent_gain(w) == pytest.approx(0.5, abs=1e-12)
    # sum(w^2) = 3N/8 for the symmetric Hann window.
    assert window_energy(w) == pytest.approx(3 * n / 8, rel=1e-6)
    # ENBW = fs * sum(w^2)/sum(w)^2 = fs * (3N/8) / (N/2)^2 = 1.5 * fs/N.
    assert enbw(w, 48_000.0) == pytest.approx(1.5 * 48_000.0 / n, rel=1e-6)


def test_unknown_window_rejected():
    with pytest.raises(ValueError):
        window("bogus", 16)
    with pytest.raises(ValueError):
        window("hann", 0)
