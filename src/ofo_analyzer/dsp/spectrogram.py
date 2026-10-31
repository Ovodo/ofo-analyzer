"""Rolling spectrogram computation.

A spectrogram is a sequence of windowed spectra over time. Frames advance
by ``hop`` samples; the result is labeled with its frame times (relative
to the start of the analyzed buffer) and the same frequency axis as a
single spectrum. Normalization is the same as :func:`~ofo_analyzer.dsp.spectrum.psd`,
and the returned magnitudes are dB (10·log10) clamped to a floor so a
display can never show negative-infinity pixels.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ofo_analyzer.dsp.spectrum import psd

DB_FLOOR = -140.0


@dataclass(frozen=True)
class SpectrogramResult:
    """Rolling spectrogram with explicit analysis settings."""

    frequencies: np.ndarray
    frame_times: np.ndarray  # seconds; frame start times within the buffer
    values_db: np.ndarray  # (frames, bins) dB FS^2/Hz
    sample_rate: float
    n_fft: int
    hop: int
    window_name: str


class StreamingSpectrogram:
    """Incremental spectrogram for live display.

    Feed audio samples as they arrive; complete windows are returned as
    (frame_time_seconds, values_db) pairs with sample-accurate frame times
    measured from the start of the feed. Displaying decimated or partial
    frames is a UI choice; this class always computes from complete,
    correctly-ordered windows.
    """

    def __init__(
        self,
        sample_rate: float,
        n_fft: int = 4096,
        hop: int | None = None,
        window_name: str = "hann",
    ) -> None:
        if n_fft < 2:
            raise ValueError("n_fft must be >= 2")
        self.sample_rate = float(sample_rate)
        self.n_fft = int(n_fft)
        self.hop = int(hop if hop is not None else max(1, n_fft // 4))
        self.window_name = window_name
        self._pending = np.zeros(0, dtype=np.float64)
        self._consumed = 0
        self.frequencies = np.fft.rfftfreq(self.n_fft, d=1.0 / self.sample_rate)

    @property
    def consumed(self) -> int:
        """Total samples fed since construction (or the last reset)."""
        return self._consumed

    def set_clock(self, consumed: int) -> None:
        """Preserve the frame-time origin across a parameter change.

        The pending buffer is discarded, so a short spectral gap exists
        after a reset; display users should clear their columns too.
        """
        self._consumed = int(consumed)
        self._pending = np.zeros(0, dtype=np.float64)

    def feed(self, samples: np.ndarray) -> list[tuple[float, np.ndarray]]:
        """Consume samples; return completed (frame_time_s, values_db) frames."""
        incoming = np.asarray(samples, dtype=np.float64)
        self._pending = np.concatenate((self._pending, incoming))
        self._consumed += int(incoming.size)
        out: list[tuple[float, np.ndarray]] = []
        while self._pending.size >= self.n_fft:
            window_data = self._pending[: self.n_fft]
            result = psd(
                window_data, self.sample_rate, n_fft=self.n_fft, window_name=self.window_name
            )
            values_db = 10.0 * np.log10(np.maximum(result.values, 1e-20))
            values_db = np.maximum(values_db, DB_FLOOR)
            # Global start index of the window at the head of the pending buffer.
            frame_start_index = self._consumed - self._pending.size
            out.append((frame_start_index / self.sample_rate, values_db))
            self._pending = self._pending[self.hop :]
        return out


def spectrogram(
    data: np.ndarray,
    sample_rate: float,
    n_fft: int = 4096,
    hop: int | None = None,
    window_name: str = "hann",
) -> SpectrogramResult:
    """Compute a full-buffer spectrogram in dB FS^2/Hz.

    Frames cover ``[0, len - n_fft]`` inclusive, advancing by ``hop``
    (default: n_fft // 4). Buffers shorter than ``n_fft`` yield no frames.
    """
    x = np.asarray(data, dtype=np.float64)
    if x.ndim != 1:
        raise ValueError("spectrogram input must be 1-D")
    if n_fft < 2:
        raise ValueError("n_fft must be >= 2")
    hop = int(hop if hop is not None else max(1, n_fft // 4))
    frames = 1 + (x.size - n_fft) // hop
    if frames < 1:
        return SpectrogramResult(
            frequencies=np.array([]),
            frame_times=np.array([]),
            values_db=np.zeros((0, n_fft // 2 + 1)),
            sample_rate=float(sample_rate),
            n_fft=n_fft,
            hop=hop,
            window_name=window_name,
        )
    values_db = np.empty((frames, n_fft // 2 + 1), dtype=np.float64)
    frame_times = np.arange(frames) * hop / float(sample_rate)
    for i in range(frames):
        result = psd(x[i * hop : i * hop + n_fft], sample_rate, n_fft=n_fft, window_name=window_name)
        values_db[i] = 10.0 * np.log10(np.maximum(result.values, 1e-20))
    return SpectrogramResult(
        frequencies=result.frequencies,
        frame_times=frame_times,
        values_db=np.maximum(values_db, DB_FLOOR),
        sample_rate=float(sample_rate),
        n_fft=n_fft,
        hop=hop,
        window_name=window_name,
    )
