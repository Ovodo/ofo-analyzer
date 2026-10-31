# OFO Analyzer roadmap

Staged delivery, matching the OFO project plan (see the main site's
research pages and the project milestones). Each stage has a completion
check that can actually be verified, not a demo.

## Stage 1 — Processing foundation ✅ (2026-10-31)

Synthetic signals, WAV input, spectrum and metadata model.

- Known tones appear at the expected frequency within one FFT bin ✓
- Amplitude/PSD normalization verified independently, including DC and
  Nyquist edge cases (never doubled) ✓
- Window coherent gain / energy / ENBW closed-form checks ✓
- Record → reopen → replay roundtrip preserves sample counts, metadata,
  and a 440 Hz tone's peak bin ✓
- Dropped-block gaps counted in session health, never fabricated ✓

## Stage 2 — Live acquisition ✅ code-complete (2026-10-31)

Device/channel/sample-rate selection, waveform, level meter, clipping
warning, recording.

- Bounded queue: callback enqueues only; overflow and drops counted ✓
- LiveSource opens PortAudio devices with clear errors for bad device or
  channel-count settings ✓
- UI: waveform + spectrum plots, peak/RMS dBFS meters, clip indicator,
  elapsed time, health status, WAV+sidecar recording ✓
- Offscreen UI construction smoke test ✓
- **Pending on hardware**: real-capture validation needs PortAudio
  (`sudo apt install libportaudio2` on Ubuntu) and a connected input
  (e.g. the UMC22). Hardware tests skip gracefully when absent.

## Stage 3 — Analysis interface (in progress, 2026-10-31)

Spectrogram (rolling), configurable FFT/window controls, CSV export of
spectra, session replay for review.

- Rolling spectrogram in the UI, sample-accurate frame times from a
  streaming STFT (clock preserved across FFT-size changes) ✓
- CSV exports with provenance headers (spectrum + long-format
  spectrogram), via `analyze_wav.py --csv/--spectrogram` ✓
- Batch spectrogram verified against the streaming feed frame-for-frame ✓

Completion check (remaining): window/overlap controls persisted to
sidecars; plotting stays responsive during a 10-minute live recording; a
dropped device produces a visible error.

## Stage 4 — Recording and replay robustness

Long-recording splitting, retention policy, replay of any recorded
session with its original sidecar, explicit calibration-status display.

Completion check: a ten-minute recording reopens correctly; any dropped
blocks are reported in the sidecar and UI.

## Stage 5 — Grant demonstration package

Installation guide, an example recording with its sidecar, a test report
generated from `pytest`, and screenshots.

Completion check: another person can reproduce the demonstration from the
instructions alone.

## Out of scope for the first instrument

Event detection, environmental correlations, infrasound/ultrasound
hardware claims, multi-device synchronization, cloud services.
