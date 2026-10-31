"""Recorder: writes blocks from a source into WAV + JSON sidecar.

Two modes:

- **Self-contained** (:meth:`start`/:meth:`stop`): a worker thread consumes
  ``source.blocks()`` — used by headless examples and tests.
- **UI-driven**: the app pulls blocks from the source queue and calls
  :meth:`write_block` directly (single writer, no hidden threads).

Raw recordings are written once and never modified; any later derived data
(filters, translations) is a separate file with its own provenance.
"""

from __future__ import annotations

import threading
from pathlib import Path

from ofo_analyzer.acquisition.base import AcquisitionError, AudioSource
from ofo_analyzer.models import SessionHealth
from ofo_analyzer.storage.sidecar import write_sidecar
from ofo_analyzer.storage.wav_writer import WavWriter

DEFAULT_SUBTYPE = "PCM_16"


class LiveRecorder:
    """Record from an :class:`AudioSource` into WAV + sidecar."""

    def __init__(
        self,
        source: AudioSource,
        out_dir: str | Path,
        base_name: str | None = None,
        subtype: str = DEFAULT_SUBTYPE,
    ) -> None:
        self.source = source
        self.out_dir = Path(out_dir)
        self.base_name = base_name or source.session_id
        self.subtype = subtype
        self.health = SessionHealth()
        self.frames_written = 0
        self._writer: WavWriter | None = None
        self._thread: threading.Thread | None = None
        self._error: BaseException | None = None

    @property
    def wav_path(self) -> Path:
        return self.out_dir / f"{self.base_name}.wav"

    @property
    def sidecar_path(self) -> Path:
        return self.out_dir / f"{self.base_name}.json"

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def error(self) -> BaseException | None:
        return self._error

    # -- UI-driven mode -----------------------------------------------------

    def open(self) -> None:
        """Create the WAV writer and sidecar base; call before write_block."""
        if self._writer is not None:
            raise RuntimeError("recorder already open")
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._writer = WavWriter(
            self.wav_path,
            sample_rate=self.source.sample_rate,
            channels=self.source.channels,
            subtype=self.subtype,
        )

    def write_block(self, block) -> None:  # SampleBlock
        if self._writer is None:
            raise RuntimeError("recorder not open; call open() first")
        self.health.update(block)
        self._writer.write(block)
        self.frames_written = self._writer.frames

    def finalize(self) -> None:
        """Close the WAV, then write the sidecar with health and metadata."""
        if self._writer is None:
            return
        self._writer.close()
        self._writer = None
        payload: dict[str, object] = {}
        metadata = getattr(self.source, "metadata", None)
        if callable(metadata):
            payload.update(metadata().to_dict())
        payload["health"] = self.health.to_dict()
        payload["frames_written"] = self.frames_written
        write_sidecar(self.sidecar_path, payload)

    # -- self-contained mode -------------------------------------------------

    def start(self) -> None:
        if self.running:
            raise RuntimeError("recorder already running")
        self._thread = threading.Thread(target=self._run, name="ofo-recorder", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the source, drain remaining blocks, finalize files."""
        close = getattr(self.source, "stop", None) or getattr(self.source, "close", None)
        if callable(close):
            close()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None
        self.finalize()

    def _run(self) -> None:
        try:
            self.open()
            for block in self.source.blocks():
                self.write_block(block)
            self.finalize()
        except BaseException as exc:  # surface worker failure to callers
            self._error = exc
            if self._writer is not None:
                self._writer.close()
                self._writer = None
            raise


__all__ = ["LiveRecorder", "AcquisitionError"]
