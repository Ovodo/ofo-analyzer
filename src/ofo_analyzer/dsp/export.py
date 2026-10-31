"""Exports: spectra and spectrograms to CSV.

CSV is the interoperability format for the first instrument (spreadsheets
and other tools read it directly). Every export includes a provenance
header: sample rate, FFT size, window, normalization, units, and the note
that values are digital full-scale, not calibrated levels.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ofo_analyzer.dsp.spectrogram import SpectrogramResult
from ofo_analyzer.dsp.spectrum import SpectrumResult

SPECTRUM_HEADER = (
    "# OFO Analyzer spectrum export\n"
    "# kind={kind} window={window} n_fft={n_fft} sample_rate={sample_rate} Hz\n"
    "# bin_spacing={spacing:.6f} Hz enbw={enbw:.6f} Hz normalization={normalization}\n"
    "# units=digital full scale (uncalibrated); exported {exported_at}\n"
)


def _write_csv(path: str | Path, header_lines: list[str], columns: list[tuple[str, np.ndarray]]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    names = [name for name, _ in columns]
    data = [np.asarray(values) for _, values in columns]
    with open(path, "w", encoding="utf-8") as handle:
        handle.writelines(header_lines)
        handle.write(",".join(names) + "\n")
        for row in zip(*data, strict=False):
            handle.write(",".join(f"{float(value):.10g}" for value in row) + "\n")
    return path


def export_spectrum_csv(result: SpectrumResult, path: str | Path, exported_at: str) -> Path:
    """Export one spectrum (amplitude or PSD) to a two-column CSV."""
    normalization = (
        "coherent-gain one-sided amplitude"
        if result.kind == "amplitude"
        else "window-energy one-sided PSD"
    )
    units = "FS" if result.kind == "amplitude" else "FS^2/Hz"
    header_lines = SPECTRUM_HEADER.format(
        kind=result.kind,
        window=result.window_name,
        n_fft=result.n_fft,
        sample_rate=result.sample_rate,
        spacing=result.bin_spacing_hz,
        enbw=result.enbw_hz,
        normalization=normalization,
        exported_at=exported_at,
    ).splitlines(keepends=True)
    return _write_csv(
        path,
        header_lines,
        [("frequency_hz", result.frequencies), (f"{result.kind}_{units}", result.values)],
    )


def export_spectrogram_csv(result: SpectrogramResult, path: str | Path, exported_at: str) -> Path:
    """Export a spectrogram as long-format CSV: one row per (frame, bin)."""
    header_lines = [
        "# OFO Analyzer spectrogram export\n",
        f"# window={result.window_name} n_fft={result.n_fft} hop={result.hop} "
        f"sample_rate={result.sample_rate} Hz\n",
        f"# units=dB FS^2/Hz (floor -140); exported {exported_at}\n",
    ]
    freqs = np.repeat(result.frequencies, result.frame_times.size)
    times = np.tile(result.frame_times, result.frequencies.size)
    values = result.values_db.T.reshape(-1)
    return _write_csv(
        path,
        header_lines,
        [
            ("frame_time_s", times),
            ("frequency_hz", freqs),
            ("psd_db", values),
        ],
    )
