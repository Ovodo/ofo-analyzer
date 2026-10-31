"""Peak/RMS levels in digital full-scale units and clipping detection.

Levels are dBFS: 0 dBFS equals digital full scale. These are not acoustic
levels; converting to SPL requires a valid full-chain calibration, which
this prototype does not perform.
"""

from __future__ import annotations

import numpy as np

CLIP_THRESHOLD = 1.0  # digital full scale


def peak(data: np.ndarray) -> float:
    """Maximum absolute sample value."""
    x = np.asarray(data, dtype=np.float64)
    if x.size == 0:
        raise ValueError("cannot compute peak of empty data")
    return float(np.max(np.abs(x)))


def rms(data: np.ndarray) -> float:
    """Root-mean-square level over the given samples."""
    x = np.asarray(data, dtype=np.float64)
    if x.size == 0:
        raise ValueError("cannot compute RMS of empty data")
    return float(np.sqrt(np.mean(x * x)))


def to_dbfs(level: float) -> float:
    """Convert a linear FS level to dBFS; silence maps to ``-inf``."""
    if level < 0:
        raise ValueError("level must be non-negative")
    return float(-np.inf) if level == 0 else float(20.0 * np.log10(level))


def clipping(data: np.ndarray, threshold: float = CLIP_THRESHOLD) -> bool:
    """True when any sample reaches or exceeds digital full scale."""
    return bool(np.max(np.abs(np.asarray(data, dtype=np.float64))) >= threshold) if np.asarray(data).size else False


class LevelMeter:
    """Rolling peak/RMS meter with decay, for live UI displays.

    ``update`` is cheap and safe to call from any thread at UI rates.
    """

    def __init__(self, decay_seconds: float = 0.4, sample_rate: float = 48_000.0) -> None:
        self.decay_seconds = decay_seconds
        self.sample_rate = sample_rate
        self.peak_level = 0.0
        self.rms_level = 0.0
        self._peak_hold_counts = 0

    def update(self, data: np.ndarray, sample_rate: float | None = None) -> tuple[float, float]:
        """Update meter state from a block; return (peak, rms) linear levels."""
        if sample_rate is not None and sample_rate != self.sample_rate:
            self.sample_rate = float(sample_rate)
        block_peak = peak(data)
        block_rms = rms(data)
        # Peak with exponential decay toward zero so the bar falls visibly.
        self.peak_level = max(block_peak, self.peak_level * 0.9)
        self.rms_level = max(block_rms, self.rms_level * 0.9)
        return self.peak_level, self.rms_level

    @property
    def peak_dbfs(self) -> float:
        return to_dbfs(self.peak_level)

    @property
    def rms_dbfs(self) -> float:
        return to_dbfs(self.rms_level)
