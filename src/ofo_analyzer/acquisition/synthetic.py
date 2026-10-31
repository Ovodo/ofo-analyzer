"""Deterministic synthetic sources for validating DSP and storage.

Synthetic validation is a software check only: a correct tone spectrum
proves the analysis code is correct, not that any physical sensor works.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import numpy as np

from ofo_analyzer.acquisition.base import AudioSource
from ofo_analyzer.models import SampleBlock, SessionMetadata, utc_now


class SineSource(AudioSource):
    """Sine tone with optional deterministic white noise, in digital FS units."""

    label = "synthetic"

    def __init__(
        self,
        frequency: float = 440.0,
        amplitude: float = 0.5,
        sample_rate: float = 48_000.0,
        channels: int = 1,
        block_size: int = 1024,
        noise_std: float = 0.0,
        n_blocks: int | None = None,
        seed: int = 0,
    ) -> None:
        if frequency <= 0:
            raise ValueError("frequency must be positive")
        if not 0 < amplitude:
            raise ValueError("amplitude must be positive")
        if channels < 1:
            raise ValueError("channels must be >= 1")
        self.frequency = frequency
        self.amplitude = amplitude
        self.sample_rate = sample_rate
        self.channels = channels
        self.block_size = block_size
        self.noise_std = noise_std
        self.n_blocks = n_blocks
        self._rng = np.random.default_rng(seed)
        self.session_id = f"syn-{uuid.uuid4().hex[:8]}"
        self._index = 0
        self._block_no = 0

    def metadata(self) -> SessionMetadata:
        return SessionMetadata(
            session_id=self.session_id,
            started_at_utc=utc_now(),
            sample_rate=self.sample_rate,
            channels=self.channels,
            source_kind="synthetic",
            instrument=(
                f"SineSource({self.frequency:g} Hz, amplitude {self.amplitude:g} FS, "
                f"noise_std {self.noise_std:g})"
            ),
            site_notes="Deterministic synthetic signal; not a physical measurement.",
        )

    def blocks(self) -> Iterator[SampleBlock]:
        while self.n_blocks is None or self._block_no < self.n_blocks:
            # The absolute sample index makes blocks join continuously:
            # no per-block phase bookkeeping is needed or permitted.
            t = (np.arange(self.block_size) + self._index) / self.sample_rate
            data = self.amplitude * np.sin(2 * np.pi * self.frequency * t)
            if self.noise_std > 0:
                data = data + self._rng.normal(0.0, self.noise_std, self.block_size)
            block_data = np.repeat(data[:, None], self.channels, axis=1)
            yield SampleBlock(
                session_id=self.session_id,
                first_sample_index=self._index,
                data=block_data,
                channels=self.channels,
                timestamp_utc=utc_now(),
            )
            self._index += self.block_size
            self._block_no += 1
