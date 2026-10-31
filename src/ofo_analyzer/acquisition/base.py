"""Common contract for all acquisition sources.

Sources are iterated as block generators. Every source must:

- produce monotonically indexed :class:`~ofo_analyzer.models.SampleBlock`
  instances in digital full-scale units,
- never fabricate dropped or missing samples,
- make failures explicit (raise :class:`AcquisitionError`), and
- expose the nominal sample rate so DSP code can label spectra correctly.
"""

from __future__ import annotations

from collections.abc import Iterator

from ofo_analyzer.models import SampleBlock


class AcquisitionError(RuntimeError):
    """Raised when a source cannot start, read, or continue acquisition."""


class AudioSource:
    """Base class for block-generating acquisition sources."""

    sample_rate: float
    channels: int
    block_size: int
    label: str = "source"

    def blocks(self) -> Iterator[SampleBlock]:
        """Yield consecutive sample blocks; raises AcquisitionError on failure."""
        raise NotImplementedError

    def close(self) -> None:
        """Release underlying resources. Safe to call more than once."""
