"""Offscreen construction smoke test for the Qt UI (no display required).

Exercising widget construction catches import errors, typos in Qt slot
names, and layout wiring — everything short of actual rendering.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6", reason="PySide6 [ui] extra not installed")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_window_constructs_offscreen():
    from PySide6.QtWidgets import QApplication

    from ofo_analyzer.ui.app import AnalyzerWindow

    app = QApplication.instance() or QApplication([])
    window = AnalyzerWindow()
    try:
        assert window.windowTitle().startswith("OFO Analyzer")
        assert window.start_button.text().startswith("▶")
        assert window.fft_combo.currentData() == 4096
        assert window.rate_combo.currentData() == 48_000
        # Meter updates accept synthetic data without a device.
        import numpy as np

        window.meter.update(np.zeros(64) + 0.1)
        window.update_meter()
        window.set_status("test")
        assert window.status_label.text() == "test"
        # Recording toggle must not crash when no source is running.
        window.toggle_recording(True)
        window.toggle_recording(False)
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()
