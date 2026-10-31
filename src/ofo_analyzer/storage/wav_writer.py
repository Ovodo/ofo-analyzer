"""Streaming WAV writer.

Raw recordings are written once, never modified, and keep the native
sample rate. The default subtype is 16-bit PCM (about 346 MB/hour mono at
48 ksample/s in decimal units); FLOAT keeps exact sample values for
synthetic/DSP verification at double the size.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from ofo_analyzer.models import SampleBlock

SUBTYPES = ("PCM_16", "PCM_24", "PCM_32", "FLOAT")


class WavWriter:
    """Appends sample blocks to a WAV file; tracks frames and clipping."""

    def __init__(self, path: str | Path, sample_rate: float, channels: int, subtype: str = "PCM_16") -> None:
        if subtype not in SUBTYPES:
            raise ValueError(f"subtype must be one of {SUBTYPES}")
        self.path = Path(path)
        self.sample_rate = float(sample_rate)
        self.channels = int(channels)
        self.subtype = subtype
        self.frames = 0
        self.clipped_blocks = 0
        self._handle = sf.SoundFile(
            str(self.path),
            mode="w",
            samplerate=int(self.sample_rate),
            channels=self.channels,
            subtype=subtype,
        )

    def write(self, block: SampleBlock) -> None:
        if block.channels != self.channels:
            raise ValueError(f"block has {block.channels} channels, writer expects {self.channels}")
        data = np.asarray(block.data, dtype=np.float64)
        if block.clipped:
            self.clipped_blocks += 1
        self._handle.write(data)
        self.frames += int(data.shape[0])

    def close(self) -> None:
        """Finalize the file. Safe to call more than once."""
        if self._handle is not None:
            self._handle.close()
            self._handle = None  # type: ignore[assignment]

    def __enter__(self) -> WavWriter:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
