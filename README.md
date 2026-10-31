# OFO Analyzer

Local-first acoustic signal acquisition and analysis prototype for the
[Open Frequency Observatory](https://ovd.world/research/ofo) (OFO) project.

> **Status:** concept & development — stage 1 (processing foundation) and
> stage 2 (live acquisition) prototype. Not a calibrated instrument.
> Amplitudes are digital units relative to full scale, not sound-pressure levels.

## What it does

- **Sources:** synthetic test signals, WAV file replay, and live capture from
  any PortAudio input device (e.g. the Behringer UMC22 audio interface).
- **Analysis:** windowed FFT amplitude spectra and power spectral densities
  with explicit, test-verified normalization; peak/RMS levels in dBFS with
  clipping detection.
- **Recording:** streaming WAV capture with a JSON metadata sidecar that
  preserves acquisition settings, sample-rate, timestamps, and quality flags
  (overflow, dropped blocks, clipping).
- **UI:** device/channel/sample-rate selection, live waveform, input level
  meter, clipping indicator, elapsed time, and acquisition health status.

See `docs/ROADMAP.md` for the staged delivery plan and
`docs/MEASUREMENT-LIMITS.md` for what this prototype can and cannot claim.

## Install

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/). PortAudio is needed
for live capture (`libportaudio2` on Debian/Ubuntu).

```bash
uv sync --all-extras
```

## Usage

Run the desktop app (device capture, waveform, level meter, recording):

```bash
uv run ofo-analyzer
```

Headless helpers (no GUI required):

```bash
# capture 10 seconds from the default input to recordings/
uv run python examples/record_demo.py --seconds 10

# analyze a WAV file: peak frequency, level, duration
uv run python examples/analyze_wav.py recordings/demo.wav
```

Run the test suite:

```bash
uv run pytest
```

## Scientific design notes

- Audio callbacks only enqueue blocks; disk writes and analysis run in
  workers so plotting can never stall acquisition.
- Missing samples are never silently inserted as zeros: dropped blocks are
  recorded as gaps in the monotonic sample index with quality flags.
- One-sided spectra double interior bins only; DC and Nyquist bins are never
  doubled. Amplitude spectra use coherent-gain normalization; PSDs use
  window-energy/`fs` normalization with explicit ENBW.
- Raw recordings are immutable; any filtered or derived output is written
  separately with its provenance recorded.
- Displayed levels are dBFS (digital full scale). Absolute SPL or Pa claims
  require a valid full-chain calibration, which this prototype does not provide.

## License

MIT for original software in this repository (see `LICENSE`). Documentation is
proposed CC BY 4.0. No claim is made over third-party hardware or firmware.
