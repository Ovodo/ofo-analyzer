"""Record a short audible-band demo to WAV + JSON sidecar (headless).

With live hardware:
    uv run python examples/record_demo.py --seconds 10

Without an input device/PortAudio, a labeled synthetic tone is recorded
instead so the pipeline can still be exercised end to end:
    uv run python examples/record_demo.py --synthetic

The synthetic fallback is clearly labeled in the sidecar; it is software
validation, not a physical measurement.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from ofo_analyzer.acquisition.base import AcquisitionError
from ofo_analyzer.recorder import LiveRecorder


def build_source(seconds: float, synthetic: bool, channels: int, sample_rate: float | None):
    if not synthetic:
        try:
            from ofo_analyzer.acquisition.device import LiveSource

            source = LiveSource(channels=channels, sample_rate=sample_rate)
            # Fail fast with a clear reason if the device cannot open.
            print(f"Live device: [{source.device_index}] {source.device_name} "
                  f"@ {source.sample_rate:g} Hz")
            return source
        except AcquisitionError as exc:
            print(f"live capture unavailable: {exc}", file=sys.stderr)
            print("falling back to synthetic tone (clearly labeled in sidecar)", file=sys.stderr)
    from ofo_analyzer.acquisition.synthetic import SineSource

    rate = sample_rate or 48_000.0
    block_size = 1024
    n_blocks = max(1, int(seconds * rate / block_size))
    print(f"Synthetic tone: 440 Hz, {rate:g} Hz, {n_blocks} blocks")
    return SineSource(
        frequency=440.0, amplitude=0.4, sample_rate=rate, block_size=block_size, n_blocks=n_blocks
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a short OFO demo capture.")
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--channels", type=int, default=1)
    parser.add_argument(
        "--rate",
        type=float,
        default=48_000,
        help="sample rate (Hz); default 48000 (the device default is NOT adopted; "
        "44.1 kHz via direct ALSA overflowed chronically on the UMC22)",
    )
    parser.add_argument(
        "--device",
        type=int,
        default=None,
        help="PortAudio device index (see 'LiveSource.list_input_devices()'); default: system default input",
    )
    parser.add_argument("--synthetic", action="store_true", help="force the synthetic fallback tone")
    parser.add_argument("--out", default="recordings", help="output directory")
    args = parser.parse_args()

    if not args.synthetic and args.device is not None:
        try:
            from ofo_analyzer.acquisition.device import LiveSource

            source = LiveSource(device=args.device, channels=args.channels, sample_rate=args.rate)
            print(f"Live device: [{source.device_index}] {source.device_name} "
                  f"@ {source.sample_rate:g} Hz")
        except AcquisitionError as exc:
            print(f"cannot open device {args.device}: {exc}", file=sys.stderr)
            return 1
        seconds = args.seconds
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        recorder = LiveRecorder(source, Path(args.out), base_name=f"live-{stamp}")
        print(f"Recording {seconds:g} s to {recorder.wav_path} ...")
        recorder.start()
        try:
            import time

            time.sleep(seconds)
        finally:
            recorder.stop(timeout=10)
        return _report(recorder)

    source = build_source(args.seconds, args.synthetic, args.channels, args.rate)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    recorder = LiveRecorder(source, Path(args.out), base_name=f"demo-{stamp}")
    print(f"Recording {args.seconds:g} s to {recorder.wav_path} ...")

    if getattr(source, "label", "") == "live_device":
        recorder.start()
        try:
            import time

            time.sleep(args.seconds)
        finally:
            recorder.stop(timeout=10)
    else:
        # Synthetic/WAV sources terminate on their own.
        recorder.start()
        recorder.stop(timeout=30)
    return _report(recorder)


def _report(recorder: LiveRecorder) -> int:
    if recorder.error is not None:
        print(f"recording failed: {recorder.error}", file=sys.stderr)
        return 1
    health = recorder.health
    print(f"done: {recorder.frames_written} frames")
    print(f"  wav:     {recorder.wav_path}")
    print(f"  sidecar: {recorder.sidecar_path}")
    print(
        f"  health:  drops={health.dropped_blocks} "
        f"overflow={health.overflow_blocks} clipped={health.clipped_blocks}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
