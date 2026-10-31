"""Level metering and clipping detection in digital FS units."""

from __future__ import annotations

import numpy as np
import pytest

from ofo_analyzer.dsp.level import LevelMeter, clipping, peak, rms, to_dbfs

FS = 48_000.0


def test_rms_of_sine():
    t = np.arange(48_000) / FS
    x = 0.5 * np.sin(2 * np.pi * 1000.0 * t)
    assert rms(x) == pytest.approx(0.5 / np.sqrt(2), rel=1e-6)
    assert peak(x) == pytest.approx(0.5, rel=1e-6)


def test_dbfs_conversions():
    assert to_dbfs(1.0) == pytest.approx(0.0)
    assert to_dbfs(0.5) == pytest.approx(-6.0206, abs=1e-4)
    assert to_dbfs(0.0) == float("-inf")
    with pytest.raises(ValueError):
        to_dbfs(-0.1)


def test_clipping_detection():
    t = np.arange(1000) / FS
    clean = 0.5 * np.sin(2 * np.pi * 100.0 * t)
    assert clipping(clean) is False
    hot = clean.copy()
    hot[10] = 1.0  # exactly full scale counts as clipped
    hot[11] = 1.02  # over full scale
    assert clipping(hot) is True
    # Custom threshold.
    assert clipping(clean, threshold=0.4) is True
    assert clipping(np.zeros(0)) is False


def test_level_meter_tracks_and_decays():
    meter = LevelMeter(sample_rate=FS)
    loud = 0.5 * np.sin(2 * np.pi * 100.0 * np.arange(480) / FS)
    silent = np.zeros(480)
    meter.update(loud)
    assert meter.peak_level == pytest.approx(0.5, rel=1e-3)
    first_peak = meter.peak_level
    meter.update(silent)
    # Exponential decay, never an instant drop to zero.
    assert 0 < meter.peak_level < first_peak
    assert meter.peak_dbfs < 0.0
