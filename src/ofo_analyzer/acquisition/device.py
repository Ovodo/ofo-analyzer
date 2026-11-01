"""Live capture from a PortAudio input device (stage 2).

The PortAudio callback only enqueues blocks into a bounded queue and records
overflow; disk writes and analysis happen in other threads so plotting can
never stall acquisition, and a full queue drops blocks rather than blocking
the audio thread (the gap is preserved via ``first_sample_index``).

Levels are digital full-scale units. A gain knob or a microphone being
plugged in does not make this a calibrated SPL instrument.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterator

from ofo_analyzer.acquisition.base import AcquisitionError, AudioSource
from ofo_analyzer.acquisition.block_queue import BlockQueue
from ofo_analyzer.models import SampleBlock, SessionMetadata, utc_now


class LiveSource(AudioSource):
    """Streams audio from a PortAudio input device."""

    label = "live_device"

    def __init__(
        self,
        device: int | None = None,
        channels: int = 1,
        sample_rate: float | None = None,
        block_size: int = 8192,
        queue_blocks: int = 64,
    ) -> None:
        try:
            import sounddevice as sd
        except OSError as exc:  # PortAudio library missing
            raise AcquisitionError(
                "sounddevice/PortAudio is unavailable on this system. "
                "Install PortAudio (e.g. 'sudo apt install libportaudio2') to use live capture."
            ) from exc
        self._sd = sd
        self.device_index = device
        self.channels = channels
        # Default to 48 kHz per the OFO plan ("Default to 48 kHz when
        # supported"). Some USB codecs chronically overflow through direct
        # ALSA at their 44.1 kHz device default (observed on the PCM2902 in
        # the Behringer UMC22, 2026-11-01: ~33% delivered frames with
        # constant input overflow); 48 kHz paces cleanly. Users may still
        # select 44.1 kHz explicitly.
        self.sample_rate = float(sample_rate) if sample_rate is not None else 48_000.0
        # Default blocksize 8192 (~171 ms at 48 kHz): measured 2026-11-01 on
        # the UMC22 direct-ALSA path, 2048 produced 41 input overflows in a
        # 120 s capture (3% frame loss on a busy desktop); 8192 delivered
        # 99.84% with one start-up overflow. PortAudio's documented remedy
        # for overflows is a larger blocksize/latency; measurement integrity
        # outweighs display cadence for this instrument.
        self.block_size = block_size
        self.queue = BlockQueue(max_blocks=queue_blocks)
        self.session_id = f"live-{uuid.uuid4().hex[:8]}"
        self._stream: sd.InputStream | None = None
        self._index = 0
        self.overflow_events = 0
        self._started_at: object | None = None
        self._resolve_device(device, channels, sample_rate)

    # -- configuration -----------------------------------------------------

    @staticmethod
    def available() -> bool:
        """True when sounddevice + PortAudio import and enumerate devices."""
        try:
            import sounddevice as sd

            sd.query_devices()
            return True
        except Exception:
            return False

    @staticmethod
    def list_input_devices() -> list[dict[str, object]]:
        """List devices with at least one input channel, with their defaults."""
        try:
            import sounddevice as sd
        except OSError:
            return []
        devices: list[dict[str, object]] = []
        for index, info in enumerate(sd.query_devices()):
            if int(info.get("max_input_channels", 0)) >= 1:
                devices.append(
                    {
                        "index": index,
                        "name": info.get("name", "?"),
                        "max_input_channels": info.get("max_input_channels"),
                        "default_sample_rate": info.get("default_samplerate"),
                        "is_default_input": index == sd.default.device[0],
                    }
                )
        return devices

    def _resolve_device(self, device: int | None, channels: int, sample_rate: float | None) -> None:
        sd = self._sd
        if device is None:
            device = sd.default.device[0]
        try:
            info = sd.query_devices(device)
        except Exception as exc:
            raise AcquisitionError(f"unknown input device {device!r}: {exc}") from exc
        if int(info.get("max_input_channels", 0)) < 1:
            raise AcquisitionError(f"device {device} ({info.get('name')}) has no input channels")
        if channels < 1 or channels > int(info["max_input_channels"]):
            raise AcquisitionError(
                f"channel count {channels} exceeds device {device} ({info.get('name')}) "
                f"max input channels {info['max_input_channels']}"
            )
        self.device_index = int(device)
        self.device_name = str(info.get("name", "?"))
        # When the caller did not choose a rate, keep the 48 kHz default
        # (see __init__); adopting the device's own default (often 44.1 kHz)
        # is avoided deliberately based on the overflow findings above.

    # -- acquisition -------------------------------------------------------

    def metadata(self) -> SessionMetadata:
        return SessionMetadata(
            session_id=self.session_id,
            started_at_utc=utc_now(),
            sample_rate=self.sample_rate,
            channels=self.channels,
            source_kind="live_device",
            instrument=f"{self.device_name} (device {self.device_index})",
            gain_setting="hardware gain not controlled by this software",
            site_notes="Live capture in digital full-scale units; no calibration applied.",
        )

    def _callback(self, indata, frames, time_info, status) -> None:  # noqa: ANN001 (PortAudio signature)
        # Callback contract: enqueue, count overflow, never block, never compute.
        overflow = bool(status)  # any PortAudio flag (input_overflow, etc.)
        if overflow:
            self.overflow_events += 1
        self.queue.put(
            SampleBlock(
                session_id=self.session_id,
                first_sample_index=self._index,
                data=indata.copy(),
                channels=self.channels,
                timestamp_utc=utc_now(),
                overflow=overflow,
            )
        )
        self._index += int(frames)

    def start(self) -> None:
        if self._stream is not None:
            raise AcquisitionError("live source already started")
        try:
            self._stream = self._sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                blocksize=self.block_size,
                device=self.device_index,
                dtype="float32",
                callback=self._callback,
            )
            self._stream.start()
        except Exception as exc:
            self._stream = None
            raise AcquisitionError(
                f"cannot open input stream on device {self.device_index} ({self.device_name}) "
                f"at {self.sample_rate:g} Hz / {self.channels} ch: {exc}"
            ) from exc

    def stop(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None
                self.queue.close()

    def blocks(self) -> Iterator[SampleBlock]:
        """Yield blocks from the queue until the stream is stopped and drained."""
        if self._stream is None:
            self.start()
        while True:
            if self._stream is None and self.queue.closed:
                return
            block = self.queue.get(timeout=0.25)
            if block is not None:
                yield block
            elif self._stream is None:
                return
            else:
                time.sleep(0.01)

    def close(self) -> None:
        self.stop()
