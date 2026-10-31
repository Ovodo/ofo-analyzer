"""OFO Analyzer desktop application: device capture, waveform, level, spectrum.

Stage 2 scope: device/channel/sample-rate selection, live waveform, input
level meter with clipping warning, recording to WAV + sidecar, and
acquisition health status. A live FFT spectrum is included because the DSP
core is already available; it is display-only and makes no measurement
claims beyond digital FS units.

The UI never blocks the audio callback: a timer drains the block queue at
display rate, and only the most recent window is drawn.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

try:  # Qt/pyqtgraph are optional [ui] extras; core and tests run without them
    import pyqtgraph as pg
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QProgressBar,
        QPushButton,
        QSpinBox,
        QVBoxLayout,
        QWidget,
    )

    QT_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised on bare installs
    QT_AVAILABLE = False

from ofo_analyzer import __version__
from ofo_analyzer.acquisition.device import LiveSource
from ofo_analyzer.dsp.level import LevelMeter
from ofo_analyzer.dsp.spectrum import psd
from ofo_analyzer.recorder import LiveRecorder

SAMPLE_RATES = (44_100, 48_000, 96_000, 192_000)
FFT_SIZES = (2048, 4096, 8192, 16384)
METER_FLOOR_DB = -60.0
WAVEFORM_SECONDS = 2.0
PLOT_POINTS = 2000


def main() -> int:
    """Application entry point (``ofo-analyzer`` console script)."""
    if not QT_AVAILABLE:
        print("PySide6/pyqtgraph are not installed. Run: uv sync --all-extras", file=sys.stderr)
        return 1
    app = QApplication(sys.argv)
    app.setApplicationName(f"OFO Analyzer {__version__}")
    window = AnalyzerWindow()
    window.show()
    return app.exec()


if QT_AVAILABLE:

    class AnalyzerWindow(QMainWindow):
        """Single-window analyzer: controls, live plots, meter, recording."""

        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("OFO Analyzer — Open Frequency Observatory")
            self.resize(1180, 760)
            self.source = None
            self.recorder: LiveRecorder | None = None
            self.meter = LevelMeter()
            self._wave = np.zeros(0)
            self._samples_seen = 0
            self._clip_active = False

            central = QWidget()
            layout = QVBoxLayout(central)

            # --- controls ---------------------------------------------------
            controls = QHBoxLayout()
            self.device_combo = QComboBox()
            self.refresh_button = QPushButton("Refresh")
            self.channels_spin = QSpinBox()
            self.channels_spin.setRange(1, 8)
            self.channels_spin.setValue(1)
            self.rate_combo = QComboBox()
            for rate in SAMPLE_RATES:
                self.rate_combo.addItem(f"{rate:,} Hz", rate)
            self.rate_combo.setCurrentIndex(SAMPLE_RATES.index(48_000))
            self.fft_combo = QComboBox()
            for size in FFT_SIZES:
                self.fft_combo.addItem(f"FFT {size:,}", size)
            self.fft_combo.setCurrentIndex(FFT_SIZES.index(4096))
            self.start_button = QPushButton("▶ Start")
            self.record_check = QCheckBox("Record")
            self.status_label = QLabel("Idle.")
            self.status_label.setWordWrap(True)
            for widget, label in (
                (self.device_combo, "Device"),
                (self.channels_spin, "Channels"),
                (self.rate_combo, "Rate"),
                (self.fft_combo, "Spectrum"),
            ):
                box = QHBoxLayout()
                box.addWidget(QLabel(label + ":"))
                box.addWidget(widget)
                layout_control = QWidget()
                layout_control.setLayout(box)
                controls.addWidget(layout_control)
            controls.addWidget(self.refresh_button)
            controls.addWidget(self.start_button)
            controls.addWidget(self.record_check)
            controls.addStretch(1)
            layout.addLayout(controls)

            # --- plots -------------------------------------------------------
            pg.setConfigOptions(antialias=False, background="#10171b", foreground="#adc0c3")
            self.wave_plot = pg.PlotWidget(title="Waveform (digital FS units)")
            self.wave_plot.setLabel("bottom", "Time", units="s")
            self.wave_plot.showGrid(x=True, y=True, alpha=0.25)
            self.wave_curve = self.wave_plot.plot([], pen=pg.mkPen("#9be8a1", width=1))
            self.spectrum_plot = pg.PlotWidget(title="Live spectrum (dB FS/Hz, display only)")
            self.spectrum_plot.setLogMode(x=True, y=False)
            self.spectrum_plot.setLabel("bottom", "Frequency", units="Hz")
            self.spectrum_plot.setLabel("left", "PSD", units="FS^2/Hz")
            self.spectrum_plot.showGrid(x=True, y=True, alpha=0.25)
            self.spectrum_curve = self.spectrum_plot.plot([], pen=pg.mkPen("#7fd4ff", width=1))
            plots = QHBoxLayout()
            plots.addWidget(self.wave_plot, stretch=1)
            plots.addWidget(self.spectrum_plot, stretch=1)
            layout.addLayout(plots, stretch=1)

            # --- meter row ----------------------------------------------------
            meter_row = QHBoxLayout()
            self.peak_bar = QProgressBar()
            self.peak_bar.setRange(0, 100)
            self.peak_bar.setFormat("PEAK %p dBFS")
            self.peak_bar.setValue(0)
            self.rms_bar = QProgressBar()
            self.rms_bar.setRange(0, 100)
            self.rms_bar.setFormat("RMS %p dBFS")
            self.rms_bar.setValue(0)
            self.clip_label = QLabel("CLIP")
            self.clip_label.setStyleSheet("color:#577079;border:1px solid #314247;padding:4px 10px;")
            self.peak_label = QLabel("peak —")
            self.rms_label = QLabel("rms —")
            self.elapsed_label = QLabel("00:00")
            self.health_label = QLabel("health: idle")
            for w in (self.peak_bar, self.rms_bar):
                w.setFixedWidth(260)
            meter_row.addWidget(self.clip_label)
            meter_row.addWidget(self.peak_bar)
            meter_row.addWidget(self.rms_bar)
            meter_row.addWidget(self.peak_label)
            meter_row.addWidget(self.rms_label)
            meter_row.addWidget(self.elapsed_label)
            meter_row.addStretch(1)
            meter_row.addWidget(self.health_label)
            layout.addLayout(meter_row)
            layout.addWidget(self.status_label)

            self.setCentralWidget(central)

            # --- wiring ------------------------------------------------------
            self.refresh_button.clicked.connect(self.refresh_devices)
            self.start_button.clicked.connect(self.toggle_stream)
            self.record_check.toggled.connect(self.toggle_recording)
            self.record_check.setEnabled(False)

            self.timer = QTimer(self)
            self.timer.setInterval(33)  # ~30 fps display cadence
            self.timer.timeout.connect(self.drain_and_draw)

            self.refresh_devices()

        # -- device management ------------------------------------------------

        def refresh_devices(self) -> None:
            self.device_combo.clear()
            devices = LiveSource.list_input_devices()
            for device in devices:
                default_marker = " · default" if device["is_default_input"] else ""
                self.device_combo.addItem(
                    f"[{device['index']}] {device['name']}{default_marker}", device["index"]
                )
            self.start_button.setEnabled(bool(devices))
            if devices:
                self.set_status(f"{len(devices)} input device(s) found. Ready.")
            else:
                self.set_status("No input devices found. Connect an interface and press Refresh.")

        def _selected_device(self) -> int | None:
            return self.device_combo.currentData()

        # -- streaming ---------------------------------------------------------

        def toggle_stream(self) -> None:
            if self.source is None:
                self.start_stream()
            else:
                self.stop_stream()

        def start_stream(self) -> None:
            device = self._selected_device()
            if device is None:
                self.set_status("No input device selected.")
                return
            try:
                self.source = LiveSource(
                    device=device,
                    channels=self.channels_spin.value(),
                    sample_rate=self.rate_combo.currentData(),
                )
                self.source.start()
            except Exception as exc:
                self.source = None
                self.set_status(f"Could not start capture: {exc}")
                return
            self.meter = LevelMeter(sample_rate=self.source.sample_rate)
            self._wave = np.zeros(0)
            self._samples_seen = 0
            self._clip_active = False
            self.start_button.setText("■ Stop")
            self.record_check.setEnabled(True)
            self.device_combo.setEnabled(False)
            self.channels_spin.setEnabled(False)
            self.rate_combo.setEnabled(False)
            self.timer.start()
            self.set_status(
                f"Streaming from {self.source.device_name} at "
                f"{self.source.sample_rate:g} Hz, {self.source.channels} channel(s)."
            )

        def stop_stream(self) -> None:
            if self.record_check.isChecked():
                self.record_check.setChecked(False)
                self.toggle_recording(False)
            self.timer.stop()
            if self.source is not None:
                self.source.close()
                self.source = None
            self.start_button.setText("▶ Start")
            self.record_check.setEnabled(False)
            self.device_combo.setEnabled(True)
            self.channels_spin.setEnabled(True)
            self.rate_combo.setEnabled(True)
            self.set_status("Stopped.")

        # -- recording ----------------------------------------------------------

        def toggle_recording(self, checked: bool) -> None:
            if self.source is None:
                return
            if checked:
                out_dir = Path("recordings")
                self.recorder = LiveRecorder(self.source, out_dir)
                try:
                    self.recorder.open()
                except Exception as exc:
                    self.recorder = None
                    self.record_check.setChecked(False)
                    self.set_status(f"Could not start recording: {exc}")
                    return
                self.set_status(f"Recording to {self.recorder.wav_path}")
            else:
                if self.recorder is not None:
                    wav = self.recorder.wav_path
                    self.recorder.finalize()
                    self.set_status(f"Saved {wav} (+ sidecar)")
                    self.recorder = None

        # -- display loop ---------------------------------------------------------

        def drain_and_draw(self) -> None:
            if self.source is None:
                return
            blocks = self.source.queue.flush()
            if not blocks and self.source._stream is None:
                self.set_status("Device stream ended unexpectedly.")
                self.stop_stream()
                return
            if self.recorder is not None and blocks:
                try:
                    for block in blocks:
                        self.recorder.write_block(block)
                except Exception as exc:
                    self.set_status(f"Recording error: {exc}")
                    self.record_check.setChecked(False)
                    self.toggle_recording(False)
                    blocks = []
            for block in blocks:
                mono = block.data[:, 0]
                self._samples_seen += block.n_samples
                self.meter.update(mono, self.source.sample_rate)
                self._clip_active = self._clip_active or block.clipped
                keep = int(WAVEFORM_SECONDS * self.source.sample_rate)
                self._wave = np.concatenate((self._wave, mono))[-keep:]
            self.update_plots()
            self.update_meter()
            self.update_status_line()

        def update_plots(self) -> None:
            if self._wave.size == 0:
                return
            # Waveform, decimated for display only.
            step = max(1, self._wave.size // PLOT_POINTS)
            shown = self._wave[::step]
            t = np.arange(shown.size) * step / self.source.sample_rate
            self.wave_curve.setData(t, shown)
            # Spectrum from the most recent n_fft samples.
            n_fft = self.fft_combo.currentData()
            if self._wave.size >= n_fft:
                result = psd(self._wave[-n_fft:], self.source.sample_rate, n_fft=n_fft)
                mask = result.frequencies >= 20.0  # display band; device limits may differ
                db = 10.0 * np.log10(np.maximum(result.values[mask], 1e-20))
                self.spectrum_curve.setData(result.frequencies[mask], db)

        def update_meter(self) -> None:
            def bar_value(db: float) -> int:
                if db == float("-inf"):
                    return 0
                clamped = max(METER_FLOOR_DB, min(0.0, db))
                return int(round((clamped - METER_FLOOR_DB) / (0.0 - METER_FLOOR_DB) * 100))

            self.peak_bar.setValue(bar_value(self.meter.peak_dbfs))
            self.rms_bar.setValue(bar_value(self.meter.rms_dbfs))
            peak_db = self.meter.peak_dbfs
            rms_db = self.meter.rms_dbfs
            self.peak_label.setText("peak —" if peak_db == float("-inf") else f"peak {peak_db:.1f}")
            self.rms_label.setText("rms —" if rms_db == float("-inf") else f"rms {rms_db:.1f}")
            if self._clip_active:
                self.clip_label.setStyleSheet(
                    "color:#ff6b5e;border:1px solid #ff6b5e;padding:4px 10px;font-weight:700;"
                )
            else:
                self.clip_label.setStyleSheet("color:#577079;border:1px solid #314247;padding:4px 10px;")

        def update_status_line(self) -> None:
            assert self.source is not None
            elapsed = self._samples_seen / self.source.sample_rate
            minutes, seconds = divmod(int(elapsed), 60)
            self.elapsed_label.setText(f"{minutes:02d}:{seconds:02d}")
            health = self.source.queue.dropped_blocks
            overflow = self.source.overflow_events
            state = "OK" if (health == 0 and overflow == 0 and not self._clip_active) else "ATTENTION"
            self.health_label.setText(f"health: {state} · drops {health} · overflow {overflow}")

        def set_status(self, text: str) -> None:
            self.status_label.setText(text)

        def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
            if self.record_check.isChecked():
                self.record_check.setChecked(False)
                self.toggle_recording(False)
            if self.source is not None:
                self.stop_stream()
            super().closeEvent(event)


else:  # pragma: no cover
    AnalyzerWindow = None  # type: ignore[assignment,misc]
