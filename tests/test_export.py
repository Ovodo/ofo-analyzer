"""CSV exports: provenance headers and value integrity."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ofo_analyzer.dsp.export import export_spectrogram_csv, export_spectrum_csv
from ofo_analyzer.dsp.spectrogram import spectrogram
from ofo_analyzer.dsp.spectrum import amplitude_spectrum

FS = 48_000.0


def test_spectrum_csv_roundtrip(tmp_path: Path):
    t = np.arange(4096) / FS
    data = 0.2 * np.sin(2 * np.pi * 1000.0 * t)
    result = amplitude_spectrum(data, FS, n_fft=4096)
    path = export_spectrum_csv(result, tmp_path / "spec.csv", "2026-10-31T00:00:00Z")

    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("# OFO Analyzer spectrum export")
    assert any("units=digital full scale (uncalibrated)" in line for line in lines[:4])
    header = lines[4].split(",")
    assert header == ["frequency_hz", "amplitude_FS"]
    values = np.array([[float(v) for v in row.split(",")] for row in lines[5:]])
    assert values.shape == (2049, 2)
    assert np.allclose(values[:, 1], result.values)


def test_spectrogram_csv_long_format(tmp_path: Path):
    t = np.arange(2048) / FS
    data = 0.2 * np.sin(2 * np.pi * 1000.0 * t)
    result = spectrogram(data, FS, n_fft=1024, hop=512)
    path = export_spectrogram_csv(result, tmp_path / "sg.csv", "2026-10-31T00:00:00Z")

    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[3].split(",") == ["frame_time_s", "frequency_hz", "psd_db"]
    n_rows = result.values_db.shape[0] * result.values_db.shape[1]
    assert len(lines) - 4 == n_rows  # header lines + column names only
