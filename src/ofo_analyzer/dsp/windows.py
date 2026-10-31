"""Window function helpers with explicit normalization constants."""

from __future__ import annotations

import numpy as np
from scipy.signal.windows import get_window

WINDOW_NAMES = ("boxcar", "hann", "hamming", "blackman", "blackmanharris")


def window(name: str, n: int) -> np.ndarray:
    """Return a periodic window of length ``n`` for spectral analysis.

    ``boxcar`` is the rectangular window. Periodic (DFT-even) windows are
    used, as intended for FFT work, so coherent-gain and energy closed
    forms hold exactly (e.g. hann: mean 0.5, energy 3N/8).
    """
    if n < 1:
        raise ValueError("window length must be >= 1")
    if name not in WINDOW_NAMES:
        raise ValueError(f"unknown window {name!r}; expected one of {WINDOW_NAMES}")
    return np.asarray(get_window(name, n), dtype=np.float64)


def coherent_gain(w: np.ndarray) -> float:
    """Mean of the window; the gain a coherent tone retains after windowing."""
    w = np.asarray(w, dtype=np.float64)
    return float(w.sum() / w.size)


def window_energy(w: np.ndarray) -> float:
    """Sum of squared window samples; the normalization constant for PSDs."""
    w = np.asarray(w, dtype=np.float64)
    return float(np.dot(w, w))


def enbw(w: np.ndarray, sample_rate: float) -> float:
    """Equivalent noise bandwidth in Hz: ``fs * sum(w^2) / sum(w)^2``."""
    w = np.asarray(w, dtype=np.float64)
    total = float(w.sum())
    if total <= 0:
        raise ValueError("window sums to zero; ENBW undefined")
    return float(sample_rate * np.dot(w, w) / (total * total))
