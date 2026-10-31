"""Core data models shared across acquisition, DSP, storage, and UI.

Design rules (see docs/MEASUREMENT-LIMITS.md):

- Samples carry a monotonic ``first_sample_index`` so gaps from dropped
  blocks are detectable; missing samples are never fabricated as zeros.
- Every session carries explicit metadata: units are digital full-scale
  units unless a calibration identifier is present, and quality flags are
  recorded rather than hidden.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np

from ofo_analyzer import SCHEMA_VERSION, __version__


@dataclass
class SampleBlock:
    """A contiguous block of samples from one acquisition session.

    Attributes:
        session_id: Identifier of the session this block belongs to.
        first_sample_index: Monotonic index of the first sample in this
            block, counted from session start. Gaps between consecutive
            blocks' indices mean samples were dropped and must be reported.
        data: Array of shape (samples, channels) in digital full-scale units.
        channels: Number of channels interleaved along axis 1 of ``data``.
        timestamp_utc: UTC wall-clock time of ``first_sample_index``.
        overflow: PortAudio reported an input overflow for this block.
        clipped: Any sample reached or exceeded digital full scale.
    """

    session_id: str
    first_sample_index: int
    data: np.ndarray
    channels: int
    timestamp_utc: datetime
    overflow: bool = False
    clipped: bool = False

    def __post_init__(self) -> None:
        if self.data.ndim != 2:
            raise ValueError("SampleBlock.data must be 2-D (samples, channels)")
        if self.data.shape[1] != self.channels:
            raise ValueError("channel count does not match data shape")
        if self.data.size and not self.clipped:
            self.clipped = bool(np.max(np.abs(self.data)) >= 1.0)

    @property
    def n_samples(self) -> int:
        return int(self.data.shape[0])


@dataclass
class SessionMetadata:
    """Provenance recorded beside every recording or analysis result."""

    session_id: str
    started_at_utc: datetime
    sample_rate: float
    channels: int
    physical_quantity: str = "sound pressure (uncalibrated digital)"
    units: str = "FS (digital full scale)"
    instrument: str = "unknown"
    gain_setting: str = "unrecorded"
    calibration_id: str | None = None
    calibration_date_utc: datetime | None = None
    clock_source: str = "host audio callback clock"
    clock_uncertainty_note: str = "USB audio clocks drift; UTC labels are start-time annotations, not synchronization"
    site_notes: str = ""
    software_version: str = __version__
    schema_version: int = SCHEMA_VERSION
    source_kind: str = "synthetic"  # synthetic | wav_file | live_device

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "software_version": self.software_version,
            "started_at_utc": self.started_at_utc.isoformat(),
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "physical_quantity": self.physical_quantity,
            "units": self.units,
            "instrument": self.instrument,
            "gain_setting": self.gain_setting,
            "calibration_id": self.calibration_id,
            "calibration_date_utc": self.calibration_date_utc.isoformat() if self.calibration_date_utc else None,
            "clock_source": self.clock_source,
            "clock_uncertainty_note": self.clock_uncertainty_note,
            "site_notes": self.site_notes,
            "source_kind": self.source_kind,
        }


@dataclass
class SessionHealth:
    """Cumulative acquisition health counters, surfaced in the UI and sidecars."""

    blocks: int = 0
    samples: int = 0
    overflow_blocks: int = 0
    dropped_blocks: int = 0
    clipped_blocks: int = 0
    expected_next_index: int | None = None
    history: list[tuple[str, int]] = field(default_factory=list)

    def update(self, block: SampleBlock) -> None:
        self.blocks += 1
        self.samples += block.n_samples
        if block.overflow:
            self.overflow_blocks += 1
        if block.clipped:
            self.clipped_blocks += 1
        if self.expected_next_index is not None and block.first_sample_index > self.expected_next_index:
            gap = block.first_sample_index - self.expected_next_index
            self.dropped_blocks += 1
            self.history.append(("dropped_samples", gap))
        self.expected_next_index = block.first_sample_index + block.n_samples

    @property
    def ok(self) -> bool:
        return self.overflow_blocks == 0 and self.dropped_blocks == 0 and self.clipped_blocks == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "blocks": self.blocks,
            "samples": self.samples,
            "overflow_blocks": self.overflow_blocks,
            "dropped_blocks": self.dropped_blocks,
            "clipped_blocks": self.clipped_blocks,
            "history": [list(entry) for entry in self.history],
        }


def utc_now() -> datetime:
    """Timezone-aware UTC now, the only clock convention used by this package."""
    return datetime.now(UTC)
