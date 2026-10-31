# Measurement limits: what this prototype can and cannot claim

OFO Analyzer is honest instrumentation software. These limits are part of
the tool, not a disclaimer bolted on afterwards.

## Units and calibration

- All levels are **digital full-scale units (dBFS)**. 0 dBFS is the full
  range of the converter; it is not a physical sound-pressure level.
- No calibration is applied or assumed. Displaying Pa, Pa²/Hz, or dB SPL
  requires a valid full-chain calibration (microphone + interface + gain),
  recorded in the session sidecar with an identifier and date.
- A microphone's specified bandwidth is a manufacturer claim, not a
  verification of this recording chain's usable band.

## Sampling and bandwidth

- The analysis band is bounded by the **actual device sample rate and the
  anti-aliasing performed before sampling**. Post-capture filtering cannot
  recover energy already aliased into the recorded band.
- Bin spacing is fs/N and is reported with every spectrum. Zero padding
  interpolates but does not add resolving power; the tool reports the
  physical bin spacing of the data.
- A sample-rate limit is not a guarantee of usable sensor bandwidth.

## Acquisition integrity

- Missing samples are **never fabricated**: dropped blocks appear as gaps
  in the monotonic sample index and are counted in session health.
- Overflow (PortAudio input overflow) is counted and surfaced, not hidden.
- Clipping is detected at digital full scale and flagged per block, in the
  UI, and in sidecars.
- UTC timestamps are start-of-block annotations, not synchronization.
  Independent USB clocks drift; multi-device coherent timing is not claimed.

## Interpretation

- A spectrum peak is a property of the recording. Identifying a physical
  source from a frequency peak alone is not supported.
- Synthetic-source tests validate **software correctness only**. They say
  nothing about any physical sensor's performance.
- Raw recordings are immutable. Filtered or derived outputs are separate
  files with their own provenance; the original is never overwritten.
- Human-response, health, or geophysical-interpretation claims are outside
  this prototype's scope entirely.
