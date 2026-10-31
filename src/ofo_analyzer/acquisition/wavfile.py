"""WAV file replay source.

File replay is used for offline analysis and reproducibility tests. It
inherits whatever calibration (usually none) the file's metadata declares;
the sidecar, not the file name, is the provenance record.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import soundfile as sf

from ofo_analyzer.acquisition.base import AcquisitionError, AudioSource
from ofo_analyzer.models import SampleBlock, SessionMetadata, utc_now


class WavReplaySource(AudioSource):
    """Streams an existing WAV file as consecutive sample blocks."""

    label = "wav_file"

    def __init__(self, path: str | Path, block_size: int = 4096) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            raise AcquisitionError(f"WAV file not found: {self.path}")
        with sf.SoundFile(str(self.path)) as handle:
            self.sample_rate = float(handle.samplerate)
            self.channels = int(handle.channels)
            self.frames = int(handle.frames)
            self.subtype = str(handle.subtype)
        self.block_size = block_size
        self.session_id = f"replay-{uuid.uuid4().hex[:8]}"
        self._handle: sf.SoundFile | None = None

    def metadata(self) -> SessionMetadata:
        return SessionMetadata(
            session_id=self.session_id,
            started_at_utc=utc_now(),
            sample_rate=self.sample_rate,
            channels=self.channels,
            source_kind="wav_file",
            instrument=f"replay of {self.path.name} ({self.subtype}, {self.frames} frames)",
            site_notes=f"Replayed from {self.path}. Provenance is the original recording's sidecar.",
        )

    def blocks(self) -> Iterator[SampleBlock]:
        try:
            self._handle = sf.SoundFile(str(self.path))
        except Exception as exc:  # pragma: no cover - depends on file state
            raise AcquisitionError(f"cannot open {self.path}: {exc}") from exc
        assert self._handle is not None
        index = 0
        start = utc_now()
        try:
            while True:
                data = self._handle.read(self.block_size, dtype="float64", always_2d=True)
                if data.shape[0] == 0:
                    return
                # Guard against non-finite samples in damaged files.
                if not np.isfinite(data).all():
                    raise AcquisitionError("non-finite samples in replayed file")
                yield SampleBlock(
                    session_id=self.session_id,
                    first_sample_index=index,
                    data=data,
                    channels=self.channels,
                    timestamp_utc=start,
                )
                index += data.shape[0]
        finally:
            self.close()

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None
