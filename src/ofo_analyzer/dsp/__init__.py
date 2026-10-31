"""Digital signal processing: windows, spectra, and level metering.

Normalization rules (verified in tests):

- Amplitude spectra are divided by the window's coherent gain ``sum(w)/N``
  so a bin-centered sine of amplitude A reads approximately A at its peak.
- PSDs use window-energy normalization ``|X|^2 / (fs * sum(w^2))`` with an
  explicit ENBW (equivalent-noise bandwidth), so broadband levels are
  comparable across window choices.
- One-sided doubling multiplies interior bins only: DC and (for even N)
  Nyquist bins are never doubled.
- Bin spacing is fs/N; zero padding interpolates but does not add resolving
  power, so this package reports the physical bin spacing of the data.
"""

from ofo_analyzer.dsp.level import LevelMeter, clipping, peak, rms, to_dbfs
from ofo_analyzer.dsp.spectrum import SpectrumResult, amplitude_spectrum, bin_spacing, psd
from ofo_analyzer.dsp.windows import coherent_gain, window, window_energy

__all__ = [
    "LevelMeter",
    "SpectrumResult",
    "amplitude_spectrum",
    "bin_spacing",
    "clipping",
    "coherent_gain",
    "psd",
    "peak",
    "rms",
    "to_dbfs",
    "window",
    "window_energy",
]
