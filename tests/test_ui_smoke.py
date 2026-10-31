"""Offscreen construction smoke tests for the Qt UI (no display required).

Exercising widget construction catches import errors, typos in Qt slot
names, and layout wiring — everything short of actual rendering.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

pytest.importorskip("PySide6", reason="PySide6 [ui] extra not installed")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ofo_analyzer.dsp.spectrogram import StreamingSpectrogram  # noqa: E402


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


class FakeSource:
    """Minimal stand-in with the attributes update_plots/close need."""

    sample_rate = 48_000.0
    channels = 1
    overflow_events = 0

    def close(self) -> None:
        pass


def test_window_constructs_offscreen():
    from ofo_analyzer.ui.app import AnalyzerWindow

    _app()
    window = AnalyzerWindow()
    try:
        assert window.windowTitle().startswith("OFO Analyzer")
        assert window.start_button.text().startswith("▶")
        assert window.fft_combo.currentData() == 4096
        assert window.rate_combo.currentData() == 48_000
        # Meter updates accept synthetic data without a device.
        window.meter.update(np.zeros(64) + 0.1)
        window.update_meter()
        window.set_status("test")
        assert window.status_label.text() == "test"
        # Recording toggle must not crash when no source is running.
        window.toggle_recording(True)
        window.toggle_recording(False)
        # Spectrogram feed path: fake stream state, then drive the draw loop.
        window.source = FakeSource()
        window._spec_feed = StreamingSpectrogram(48_000, n_fft=2048)
        tone = 0.3 * np.sin(2 * np.pi * 3000.0 * np.arange(8192) / window.source.sample_rate)
        for frame_time, values_db in window._spec_feed.feed(tone):
            window._spec_cols.append(values_db)
            window._spec_times.append(frame_time)
        window.update_plots()
        # 8192 samples, n_fft 2048, hop 512: (8192-2048)/512 + 1 = 13 frames.
        assert len(window._spec_cols) == 13
    finally:
        window.source = None
        window.close()
        window.deleteLater()


def test_fft_change_resets_feed_clock():
    from ofo_analyzer.ui.app import AnalyzerWindow

    _app()
    window = AnalyzerWindow()
    try:
        window._spec_feed = StreamingSpectrogram(48_000, n_fft=4096)
        window._spec_feed.feed(np.zeros(5000))
        consumed_before = window._spec_feed.consumed
        window.fft_combo.setCurrentIndex(0)  # switch to 2048 -> handler runs
        assert window._spec_feed.n_fft == 2048
        assert window._spec_feed.consumed == consumed_before  # clock preserved
        assert window._spec_cols == []
    finally:
        window.close()
        window.deleteLater()
