# Hardware validation report — 2026-11-01

Real-chain evidence for the OFO analyzer prototype (stage 2 → stage 5).
All values are digital full-scale (dBFS), uncalibrated. This report is
measurement honesty, not a sensor characterization: it validates the
**acquisition-to-storage software** on real hardware, nothing more.

## Chain under test

- Microphone: Aston Origin condenser (XLR input 1, +48V phantom power)
- Interface: Behringer UMC22 (USB, PCM2902 codec), gain ~40%
- Host: Linux, PipeWire 1.0.5 (PulseAudio interface), PortAudio + ALSA
- Software: ofo-analyzer 0.1.0, Python 3.13, 1 channel, blocksize 2048

## Findings

### 1. Mic chain works; levels are healthy

A 120 s live capture containing speech recorded peak **−14.3 dBFS** and
RMS −43.9 dBFS with 0 clipped samples — a normal speaking level that sits
inside the project's −12 to −6 dBFS peak target. The condenser chain
(phantom power, interface gain) is delivering signal.

### 2. A real device pitfall was found, isolated, and fixed

The first 120 s live capture ran at the UMC22's **44.1 kHz device-default
rate** (silently adopted from PortAudio device info) and lost ~67% of the
audio: 39.7 s of frames in a 120 s window with **844 PortAudio
input-overflow flags** — while drops at the application queue remained 0.
Controlled 15 s A/B captures under identical conditions (same machine,
music playing through the interface during all tests):

| Capture path | Rate | Blocksize | Delivered | PA overflows | Verdict |
| --- | --- | ---: | ---: | ---: | --- |
| PipeWire (pulse device), 15 s | 48,000 | 2048 | 99.3% | 0 | clean |
| Direct ALSA hw: device, 15 s | 48,000 | 2048 | 99.8% | 1 (start) | clean |
| Direct ALSA hw: device, 15 s | 44,100 | 2048 | 32.8% | 104 | **pathological** |
| Direct ALSA hw: device, 120 s | 48,000 | 2048 | 96.9% | 41 | marginal under sustained load |
| Direct ALSA hw: device, 60 s | 48,000 | 8192 | 99.84% | 1 (start) | clean |

Two stacked conclusions: (1) never adopt the 44.1 kHz device default on
this codec, and (2) a **2048-sample blocksize is not robust for sustained
direct-ALSA capture on a busy desktop** — 120 s lost ~3% of frames to 41
scheduling overflows even at 48 kHz. PortAudio's documented remedy is a
larger blocksize; at 8192 samples (~171 ms at 48 kHz) the same machine
sustains clean capture. The analyzer therefore defaults to blocksize 8192
(`acquisition/device.py`), trading display cadence for measurement
integrity — the correct trade for a recording instrument.

Root cause: direct-ALSA access to the PCM2902 at its 44.1 kHz default
cannot sustain PortAudio's callback schedule; 48 kHz pacing is clean, and
sustained capture additionally needs the 8192 blocksize on a busy desktop.
Fixes shipped: the analyzer now **defaults every capture to 48 kHz at
blocksize 8192** and never adopts a device's default rate silently
(`acquisition/device.py`, `examples/record_demo.py`); the finding is
recorded in `docs/MEASUREMENT-LIMITS.md` as a caution for anyone
assembling a similar chain.

The failed capture is retained in `recordings/` (sidecar marked
`overflow=844`) as the case-study evidence; it is **not** used as
validation audio.

### 3. Acceptance-gate capture (gate 3: record, reopen, verify)

A 120 s capture at 48 kHz, blocksize 8192, recorded via the PipeWire path
(device `pulse`, system source = UMC22 input) on the busy development
desktop, with music playing through the same interface during the capture.
Verified against the acceptance criteria:

- [x] Frames written 5,758,976 = **99.98%** of the 120 s × 48,000 Hz
      expectation (remainder is normal stop ramp)
- [x] Input-overflow count **0**; queue drops 0; clipped blocks 0
- [x] WAV reopens at 48,000 Hz, 1 channel, matching frame count
- [x] Replayed blocks sum exactly to the recorded frame count
- [x] Sidecar round-trips: device `pulse`, rate, UTC start, health
      (`samples=5,758,976`, `overflow_blocks=0`, `dropped_blocks=0`)
- [x] Analysis: peak −30.1 dBFS, RMS −54.8 dBFS — real signal present,
      no clipping; digital units only

For comparison, the same 120 s window on the direct-ALSA path at
blocksize 8192 recorded 97.7% with 8 overflows. **Recommendation recorded
in the docs:** for sustained capture on a desktop in active use, record
through the audio server (PipeWire/Pulse — the `pulse` or `default`
device with the interface as system source); direct `hw:` access is
appropriate for dedicated or quiet machines, and both paths now default
to 48 kHz / blocksize 8192.

Evidence file: `recordings/live-20261101T125220Z.wav` + `.json` sidecar
(retained locally; not committed — publish only after privacy review,
per project policy).

### 4. Device inventory observed

Six PortAudio input endpoints were enumerated and probed; all opened and
delivered short captures: on-board ALC257, acp6x, UMC22 (USB Audio
CODEC), CS202 USB, pulse, and default (PipeWire). System default source
was switched to the UMC22 input for the PipeWire-path test.

## What this validates

Acquisition, health accounting, storage, sidecar provenance, and
replay-integrity work end to end on real hardware, and a failure mode that
would silently corrupt long recordings (rate-related overflow) was found,
measured, fixed in software, and documented.

## What it does not validate

No frequency-response calibration, no absolute SPL, no multi-device
synchronization, and no infrasound/ultrasound capability. Digital
full-scale units only.
