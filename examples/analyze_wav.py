"""Analyze a WAV recording: levels, spectrum peak, and integrity report.

    uv run python examples/analyze_wav.py recordings/demo.wav

This is an uncalibrated, digital-full-scale report. It prints the peak
frequency of the windowed spectrum — a property of the recording, not a
physical source identification.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

from ofo_analyzer.dsp.level import rms, to_dbfs
from ofo_analyzer.dsp.spectrum import amplitude_spectrum, bin_spacing
from ofo_analyzer.storage.sidecar import read_sidecar


def main() -> int:
    parser = argparse.ArgumentParser(description="Report levels and spectrum peak of a WAV file.")
    parser.add_argument("wav", type=Path)
    parser.add_argument("--n-fft", type=int, default=4096)
    args = parser.parse_args()

    path: Path = args.wav
    if not path.is_file():
        print(f"file not found: {path}", file=sys.stderr)
        return 1

    data, rate = sf.read(str(path), dtype="float64", always_2d=True)
    duration = data.shape[0] / rate
    mono = data[:, 0]

    clipped_samples = int(np.count_nonzero(np.max(np.abs(data), axis=1) >= 1.0))
    spectrum = amplitude_spectrum(mono, rate, n_fft=args.n_fft)
    peak_bin = int(np.argmax(spectrum.values))
    peak_hz = spectrum.frequencies[peak_bin]
    peak_amp = spectrum.values[peak_bin]

    print(f"file:            {path.name}")
    print(f"duration:        {duration:.3f} s ({data.shape[0]} frames)")
    print(f"sample rate:     {rate:,} Hz · {data.shape[1]} channel(s)")
    print(f"peak level:      {to_dbfs(float(np.max(np.abs(mono)))):.1f} dBFS")
    print(f"rms level:       {to_dbfs(rms(mono)):.1f} dBFS")
    print(f"clipped samples: {clipped_samples}{'  ⚠ clipping detected' if clipped_samples else ''}")
    print(
        f"fft:             n={spectrum.n_fft:,} · {spectrum.window_name} · "
        f"spacing {bin_spacing(rate, args.n_fft):.3f} Hz · ENBW {spectrum.enbw_hz:.3f} Hz"
    )
    print(f"spectrum peak:   {peak_hz:.2f} Hz at {peak_amp:.4f} FS (digital units)")
    print("note:            uncalibrated digital-full-scale values; not sound-pressure levels")

    sidecar = path.with_suffix(".json")
    if sidecar.is_file():
        payload = read_sidecar(sidecar)
        health = payload.get("health", {})
        source = payload.get("source_kind", "?")
        drops = health.get("dropped_blocks", "?")
        overflow = health.get("overflow_blocks", "?")
        print(f"sidecar:         {sidecar.name} · source={source} · drops={drops} overflow={overflow}")
    else:
        print("sidecar:         (none found; provenance unknown)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
