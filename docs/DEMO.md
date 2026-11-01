# Reproducing the OFO Analyzer demonstration

This is the grant-demonstration package: a complete, ordered sequence a
reviewer (or any other person) can follow on their own Linux machine to
verify the analyzer works. Estimated time: ~15 minutes plus hardware.

Everything below was verified on Ubuntu-family Linux, 2026-11-01.
Python 3.12/3.13, PortAudio via `libportaudio2`.

## 1. Install

```bash
git clone <repository-url>
cd ofo-analyzer
uv sync --all-extras        # installs Python deps incl. the Qt UI
sudo apt install libportaudio2   # system PortAudio, for live capture
```

## 2. Run the test suite

```bash
uv run pytest
```

Expected: **49 passed, 3 skipped** (the 3 skipped are hardware tests on
machines with no input device; on a machine with inputs they run too).
The suite verifies, without any hardware:

- Bin-centered sine tones recover their frequency within one FFT bin
  and their exact amplitude (rectangular window).
- One-sided spectra double interior bins only; DC and Nyquist are never
  doubled; Hann closed forms (coherent gain 0.5, energy 3N/8, ENBW 1.5 fs/N).
- PSD of a sine integrates to the signal power; peak-bin power matches A²/2.
- The streaming spectrogram matches the batch computation frame-for-frame.
- A recording round-trips: record → close → reopen → identical sample
  counts and sidecar metadata; a 440 Hz tone's peak bin survives the roundtrip.
- Dropped blocks are counted as index gaps, never fabricated.
- The UI constructs headlessly (offscreen) including spectrogram drawing.

See `docs/TEST-REPORT-2026-11-01.md` in this repository for the actual output
of the run that shipped this release.

## 3. Exercise the pipeline without hardware

```bash
uv run python examples/record_demo.py --synthetic --seconds 2
uv run python examples/analyze_wav.py recordings/<demo-file>.wav
```

Expected: a 440 Hz tone recording of ~2 s; the analysis reports peak
≈ −8 dBFS, RMS ≈ −11 dBFS, spectrum peak within one bin of 440 Hz, and
`source=synthetic` in the sidecar summary. This validates the full
record → storage → analysis pipeline in digital units only.

## 4. Exercise live capture (any input device)

```bash
# list your devices first (Python one-liner)
uv run python -c "from ofo_analyzer.acquisition.device import LiveSource as L; [print(d) for d in L.list_input_devices()]"

uv run python examples/record_demo.py --device <index> --seconds 10
```

Expected: `health: drops=0 overflow=0` in the output, and a sidecar
recording the device name, sample rate, and channel count.

Or run the desktop application and observe live:

```bash
uv run ofo-analyzer
```

- Waveform moves with the input signal
- Peak/RMS meters track in dBFS; the CLIP indicator lights on over-range samples
- Spectrum and rolling spectrogram update while recording
- Recording writes WAV + JSON sidecar into `recordings/`

## 5. What the demonstration does and does not show

**Does:** the acquisition → analysis → storage software works end to end,
levels are honest digital full-scale values, failures are visible, and
every result carries its provenance.

**Does not:** any calibrated acoustic measurement, sensor characterization,
or environmental interpretation. See `docs/MEASUREMENT-LIMITS.md`.

## Hardware validation evidence (2026-11-01)

Real-chain capture, Behringer UMC22 interface, uncalibrated:

See `docs/VALIDATION-2026-11-01.md` for the recorded evidence file, its
analysis report, and acceptance-gate results.
