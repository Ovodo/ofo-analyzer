"""Recording pipeline: WAV + sidecar round trips and health accounting."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from ofo_analyzer.acquisition.synthetic import SineSource
from ofo_analyzer.acquisition.wavfile import WavReplaySource
from ofo_analyzer.models import SessionHealth
from ofo_analyzer.recorder import LiveRecorder
from ofo_analyzer.storage.sidecar import read_sidecar
from ofo_analyzer.storage.wav_writer import WavWriter

FS = 48_000.0


def test_record_and_replay_roundtrip(tmp_path: Path):
    """Record a synthetic session, reopen it, verify counts and sidecar."""
    source = SineSource(frequency=440.0, sample_rate=FS, n_blocks=100, block_size=1024)
    recorder = LiveRecorder(source, tmp_path, base_name="roundtrip", subtype="PCM_16")
    recorder.start()
    recorder.stop(timeout=10)

    assert recorder.error is None
    assert recorder.frames_written == 100 * 1024

    with sf.SoundFile(str(recorder.wav_path)) as handle:
        assert handle.frames == 100 * 1024
        assert handle.samplerate == int(FS)
        assert handle.channels == 1

    sidecar = read_sidecar(recorder.sidecar_path)
    assert sidecar["source_kind"] == "synthetic"
    assert sidecar["frames_written"] == 100 * 1024
    assert sidecar["schema_version"] == 1
    assert sidecar["health"]["blocks"] == 100
    assert sidecar["health"]["dropped_blocks"] == 0

    # Replaying the file yields the same sample count and duration.
    replay = WavReplaySource(recorder.wav_path, block_size=4096)
    blocks = list(replay.blocks())
    assert sum(b.n_samples for b in blocks) == 100 * 1024
    assert replay.sample_rate == FS


def test_replayed_tone_still_reads_correct_frequency(tmp_path: Path):
    """End to end: record 1 s of 440 Hz, replay, recover the peak bin."""
    seconds = 1.0
    source = SineSource(
        frequency=440.0,
        amplitude=0.4,
        sample_rate=FS,
        block_size=1024,
        n_blocks=int(seconds * FS / 1024),
    )
    recorder = LiveRecorder(source, tmp_path, base_name="tone", subtype="FLOAT")
    recorder.start()
    recorder.stop(timeout=10)

    from ofo_analyzer.dsp.spectrum import amplitude_spectrum, bin_spacing

    data, rate = sf.read(str(recorder.wav_path), dtype="float64")
    result = amplitude_spectrum(data, rate, n_fft=4096)
    k = int(np.argmax(result.values))
    assert abs(result.frequencies[k] - 440.0) <= bin_spacing(rate, 4096)


def test_health_detects_dropped_gap():
    """SessionHealth must report gaps in first_sample_index, never hide them."""
    from ofo_analyzer.models import SampleBlock, utc_now

    health = SessionHealth()
    sid = "session"
    b1 = SampleBlock(sid, 0, np.zeros((16, 1)), 1, utc_now())
    b2 = SampleBlock(sid, 32, np.zeros((16, 1)), 1, utc_now())  # gap: 16 samples lost
    b3 = SampleBlock(sid, 48, np.zeros((16, 1)), 1, utc_now())
    health.update(b1)
    health.update(b2)
    health.update(b3)
    assert health.blocks == 3
    assert health.samples == 48
    assert health.dropped_blocks == 1
    assert health.history == [("dropped_samples", 16)]
    assert health.ok is False


def test_wav_writer_rejects_channel_mismatch(tmp_path: Path):
    from ofo_analyzer.models import SampleBlock, utc_now

    writer = WavWriter(tmp_path / "bad.wav", sample_rate=FS, channels=2)
    with pytest.raises(ValueError):
        writer.write(SampleBlock("s", 0, np.zeros((8, 1)), 1, utc_now()))
    writer.close()


def test_wav_writer_requires_known_subtype(tmp_path: Path):
    with pytest.raises(ValueError):
        WavWriter(tmp_path / "bad.wav", sample_rate=FS, channels=1, subtype="MP3")
