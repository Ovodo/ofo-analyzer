"""Windowed FFT spectra: amplitude spectrum and power spectral density."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ofo_analyzer.dsp.windows import enbw, window, window_energy

DEFAULT_WINDOW = "hann"


@dataclass(frozen=True)
class SpectrumResult:
    """A one-sided spectrum with its analysis settings attached.

    Amplitudes are digital FS units (amplitude spectrum) or FS^2/Hz (PSD).
    ``window``, ``n_fft``, ``bin_spacing_hz`` and ``enbw_hz`` travel with the
    result so plots and exports never have unlabeled spectra.
    """

    frequencies: np.ndarray
    values: np.ndarray
    sample_rate: float
    n_fft: int
    window_name: str
    kind: str  # "amplitude" | "psd"
    bin_spacing_hz: float
    enbw_hz: float


def bin_spacing(sample_rate: float, n_fft: int) -> float:
    """Physical FFT resolution: fs/N. Zero padding does not change this."""
    if n_fft <= 0:
        raise ValueError("n_fft must be positive")
    return float(sample_rate) / n_fft


def _one_sided_indices(n_fft: int) -> tuple[np.ndarray, np.ndarray]:
    """Bins and interior mask for a one-sided spectrum.

    Returns (indices, is_doubled): DC (index 0) and, for even N, the Nyquist
    bin (index N/2) appear once; all interior bins are doubled.
    """
    if n_fft % 2 == 0:
        indices = np.arange(n_fft // 2 + 1)
        doubled = np.ones(indices.shape, dtype=bool)
        doubled[0] = False  # DC
        doubled[-1] = False  # Nyquist
    else:
        indices = np.arange((n_fft + 1) // 2)
        doubled = np.ones(indices.shape, dtype=bool)
        doubled[0] = False  # DC only edge for odd N
    return indices, doubled


def _prepare(
    data: np.ndarray, sample_rate: float, n_fft: int | None, window_name: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, int]:
    x = np.asarray(data, dtype=np.float64)
    if x.ndim != 1:
        raise ValueError("spectrum input must be 1-D")
    n = int(n_fft or x.size)
    if n < 2:
        raise ValueError("need at least 2 samples")
    if n < x.size:
        x = x[:n]  # analyze the first n samples (documented truncation)
    w = window(window_name, n)
    spectrum = np.fft.rfft(x * w, n=n)  # zero-pads when n > len(x)
    indices, doubled = _one_sided_indices(n)
    return x, w, spectrum, indices, doubled, n


def amplitude_spectrum(
    data: np.ndarray,
    sample_rate: float,
    n_fft: int | None = None,
    window_name: str = DEFAULT_WINDOW,
) -> SpectrumResult:
    """One-sided windowed amplitude spectrum in digital FS units.

    A real bin-centered sine of amplitude A appears at approximately A
    (exact for the rectangular window); interior bins are doubled, DC and
    Nyquist are not. Coherent-gain normalization: divide by ``sum(w)``.
    """
    x, w, spectrum, indices, doubled, n = _prepare(data, sample_rate, n_fft, window_name)
    values = np.abs(spectrum[indices]) / float(w.sum())
    values[doubled] *= 2.0
    freqs = indices * bin_spacing(sample_rate, n)
    return SpectrumResult(
        frequencies=freqs,
        values=values,
        sample_rate=float(sample_rate),
        n_fft=n,
        window_name=window_name,
        kind="amplitude",
        bin_spacing_hz=bin_spacing(sample_rate, n),
        enbw_hz=enbw(w, sample_rate),
    )


def psd(
    data: np.ndarray,
    sample_rate: float,
    n_fft: int | None = None,
    window_name: str = DEFAULT_WINDOW,
) -> SpectrumResult:
    """One-sided power spectral density in FS^2/Hz.

    Window-energy normalization ``|X|^2 / (fs * sum(w^2))``; interior bins
    are doubled, DC and Nyquist are not. For a bin-centered sine of
    amplitude A the peak-bin power approximates A^2/2.
    """
    x, w, spectrum, indices, doubled, n = _prepare(data, sample_rate, n_fft, window_name)
    values = (np.abs(spectrum[indices]) ** 2) / (float(sample_rate) * window_energy(w))
    values[doubled] *= 2.0
    freqs = indices * bin_spacing(sample_rate, n)
    return SpectrumResult(
        frequencies=freqs,
        values=values,
        sample_rate=float(sample_rate),
        n_fft=n,
        window_name=window_name,
        kind="psd",
        bin_spacing_hz=bin_spacing(sample_rate, n),
        enbw_hz=enbw(w, sample_rate),
    )
