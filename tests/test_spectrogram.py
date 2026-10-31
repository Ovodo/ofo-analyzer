"""Spectrogram correctness: frame math and per-frame tone recovery."""

from __future__ import annotations

import numpy as np
import pytest

from ofo_analyzer.dsp.spectrogram import spectrogram

FS = 48_000.0
N = 1024


def test_frame_count_and_times():
    x = np.zeros(N * 5)
    result = spectrogram(x, FS, n_fft=N, hop=N)
    assert result.values_db.shape == (5, N // 2 + 1)
    assert result.frame_times == pytest.approx([0.0, N / FS, 2 * N / FS, 3 * N / FS, 4 * N / FS])
    assert result.frequencies[-1] == pytest.approx(FS / 2)


def test_short_buffer_yields_no_frames():
    result = spectrogram(np.zeros(100), FS, n_fft=N)
    assert result.values_db.shape == (0, N // 2 + 1)
    assert result.frame_times.size == 0


def test_each_frame_finds_the_tone():
    """A steady tone must appear at the same peak bin in every frame."""
    spacing = FS / N
    freq = 64 * spacing  # bin-centered: 3000 Hz
    t = np.arange(N * 4) / FS
    x = 0.3 * np.sin(2 * np.pi * freq * t)
    result = spectrogram(x, FS, n_fft=N, hop=N // 2)
    assert result.values_db.shape[0] == 7  # 1 + (4096-1024)/512
    k_expected = int(np.round(freq / spacing))
    for row in result.values_db:
        k = int(np.argmax(row))
        assert k == k_expected


def test_frequencies_vary_across_frames():
    """Two half-buffer tones must land in different peak bins over time."""
    spacing = FS / N
    low, high = 16 * spacing, 64 * spacing
    t = np.arange(N * 2) / FS
    x = np.concatenate(
        (
            0.3 * np.sin(2 * np.pi * low * t[: N * 2]),
            0.3 * np.sin(2 * np.pi * high * t[: N * 2]),
        )
    )
    result = spectrogram(x, FS, n_fft=N, hop=N)
    peaks = [int(np.argmax(row)) for row in result.values_db]
    assert peaks[0] == int(np.round(low / spacing))
    assert peaks[-1] == int(np.round(high / spacing))


def test_db_floor_applied():
    result = spectrogram(np.zeros(N), FS, n_fft=N, hop=N)
    assert np.all(result.values_db <= -140.0)


def test_streaming_feed_matches_batch_times_and_peaks():
    """The live feed must reproduce the batch spectrogram's frame times."""
    from ofo_analyzer.dsp.spectrogram import StreamingSpectrogram

    spacing = FS / N
    freq = 32 * spacing
    t = np.arange(N * 3) / FS
    x = 0.3 * np.sin(2 * np.pi * freq * t)

    feed = StreamingSpectrogram(FS, n_fft=N, hop=N)
    frames = []
    for block in np.split(x, 6):  # uneven arrival, complete windows only
        frames.extend(feed.feed(block))

    batch = spectrogram(x, FS, n_fft=N, hop=N)
    assert [round(t_, 9) for t_, _ in frames] == pytest.approx(list(batch.frame_times))
    for (_, values_db), batch_row in zip(frames, batch.values_db, strict=True):
        assert np.allclose(values_db, batch_row, atol=1e-9)
        assert int(np.argmax(values_db)) == int(np.round(freq / spacing))


def test_streaming_feed_waits_for_complete_windows():
    from ofo_analyzer.dsp.spectrogram import StreamingSpectrogram

    feed = StreamingSpectrogram(FS, n_fft=N, hop=N)
    assert feed.feed(np.zeros(N - 1)) == []  # not enough samples yet
    frames = feed.feed(np.zeros(1))
    assert len(frames) == 1
    assert frames[0][0] == pytest.approx(0.0)
