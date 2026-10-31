"""Spectrum correctness: tones, normalization, and the DC/Nyquist edge cases.

These are acceptance-gate tests from the OFO architecture: isolated
bin-centered tones must land within one FFT bin of their true frequency,
and amplitude/PSD normalization must be verified independently, including
the never-doubled DC and Nyquist bins.
"""

from __future__ import annotations

import numpy as np
import pytest

from ofo_analyzer.dsp.spectrum import amplitude_spectrum, bin_spacing, psd

FS = 48_000.0
N = 4096
SPACING = FS / N  # 11.71875 Hz


def tone(frequency: float, amplitude: float = 0.25, n: int = N, fs: float = FS) -> np.ndarray:
    t = np.arange(n) / fs
    return amplitude * np.sin(2 * np.pi * frequency * t)


@pytest.mark.parametrize(
    "bin_index",
    [8, 85, 1024],  # low band, mid band, Nyquist half-band
)
def test_bin_centered_tone_amplitude(bin_index):
    freq = bin_index * SPACING  # exactly on an FFT bin
    result = amplitude_spectrum(tone(freq), FS, n_fft=N, window_name="boxcar")
    k = int(np.argmax(result.values))
    # Peak within one physical FFT bin of the true frequency.
    assert abs(result.frequencies[k] - freq) <= bin_spacing(FS, N)
    # Exact amplitude recovery for the rectangular window.
    assert result.values[k] == pytest.approx(0.25, rel=1e-6)


def test_bin_centered_tone_hann_amplitude():
    freq = 85 * SPACING
    result = amplitude_spectrum(tone(freq), FS, n_fft=N, window_name="hann")
    k = int(np.argmax(result.values))
    assert abs(result.frequencies[k] - freq) <= bin_spacing(FS, N)
    assert result.values[k] == pytest.approx(0.25, rel=1e-3)


def test_off_bin_tone_within_one_bin():
    spacing = bin_spacing(FS, N)
    freq = 85 * spacing + spacing / 3  # deliberately off-bin
    result = amplitude_spectrum(tone(freq), FS, n_fft=N, window_name="hann")
    k = int(np.argmax(result.values))
    assert abs(result.frequencies[k] - freq) <= spacing


def test_psd_peak_power_of_sine():
    """A sine of amplitude A carries A^2/2 power; the peak-bin PSD must match."""
    freq = 85 * SPACING  # bin-centered
    result = psd(tone(freq), FS, n_fft=N, window_name="boxcar")
    k = int(np.argmax(result.values))
    # Peak-bin PSD value = A^2/2 / bin_spacing (all lobe power in one bin).
    assert result.values[k] == pytest.approx(0.25**2 / 2 / bin_spacing(FS, N), rel=1e-6)


def test_psd_integrates_to_signal_power():
    """Sum(PSD * df) must reconstruct total signal power (Parseval check)."""
    amplitude = 0.25
    result = psd(tone(1000.0, amplitude=amplitude), FS, n_fft=N, window_name="hann")
    total = float(np.sum(result.values) * result.bin_spacing_hz)
    assert total == pytest.approx(amplitude**2 / 2, rel=0.05)  # window loss ~ few %


def test_dc_bin_is_never_doubled():
    """A DC offset A must read A at bin 0 (not 2A)."""
    data = np.full(N, 0.5)
    result = amplitude_spectrum(data, FS, n_fft=N, window_name="boxcar")
    assert result.frequencies[0] == 0.0
    assert result.values[0] == pytest.approx(0.5, rel=1e-9)


def test_nyquist_bin_is_never_doubled():
    """A Nyquist-rate alternating signal of amplitude A must read A (not 2A)."""
    data = 0.5 * (-1.0) ** np.arange(N)
    result = amplitude_spectrum(data, FS, n_fft=N, window_name="boxcar")
    assert result.frequencies[-1] == pytest.approx(FS / 2)
    assert result.values[-1] == pytest.approx(0.5, rel=1e-9)


def test_result_carries_analysis_settings():
    result = psd(tone(100.0), FS, n_fft=N)
    assert result.kind == "psd"
    assert result.window_name == "hann"
    assert result.n_fft == N
    assert result.bin_spacing_hz == pytest.approx(FS / N)
    assert result.enbw_hz == pytest.approx(1.5 * FS / N, rel=1e-6)
    amp = amplitude_spectrum(tone(100.0), FS, n_fft=N)
    assert amp.kind == "amplitude"
    assert amp.values.shape == amp.frequencies.shape


def test_rejects_bad_input():
    with pytest.raises(ValueError):
        amplitude_spectrum(np.zeros((4, 4)), FS)
    with pytest.raises(ValueError):
        psd(np.zeros(1), FS)
