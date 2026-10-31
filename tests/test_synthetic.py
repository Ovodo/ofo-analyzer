"""Synthetic source: deterministic tones, correct indexing, block joins."""

from __future__ import annotations

import numpy as np
import pytest

from ofo_analyzer.acquisition.synthetic import SineSource


def test_sine_frequency_recovered(fs):
    source = SineSource(frequency=440.0, sample_rate=fs, block_size=1024, n_blocks=8)
    blocks = list(source.blocks())
    assert len(blocks) == 8
    joined = np.concatenate([b.data[:, 0] for b in blocks])
    # FFT-based check: peak bin within one bin of 440 Hz.
    from ofo_analyzer.dsp.spectrum import amplitude_spectrum, bin_spacing

    result = amplitude_spectrum(joined, fs, n_fft=8192, window_name="hann")
    k = int(np.argmax(result.values))
    assert abs(result.frequencies[k] - 440.0) <= bin_spacing(fs, 8192)


def test_blocks_join_continuously(fs):
    """Blocks must join without a discontinuity at the seam."""
    source = SineSource(frequency=1000.0, sample_rate=fs, block_size=512, n_blocks=4)
    joined = np.concatenate([b.data[:, 0] for b in source.blocks()])
    step = np.max(np.abs(np.diff(joined)))
    # Maximum consecutive-sample difference of a sampled sine is 2A*sin(pi*f/fs).
    assert step <= 0.5 * 2 * np.sin(np.pi * 1000.0 / fs) + 1e-12


def test_monotonic_indices_and_metadata(fs):
    source = SineSource(frequency=100.0, sample_rate=fs, block_size=256, n_blocks=5)
    blocks = list(source.blocks())
    for i, block in enumerate(blocks):
        assert block.first_sample_index == i * 256
        assert block.n_samples == 256
        assert block.session_id == source.session_id
    metadata = source.metadata()
    assert metadata.source_kind == "synthetic"
    assert metadata.sample_rate == fs
    assert "not a physical measurement" in metadata.site_notes.lower()


def test_noise_is_deterministic(fs):
    a = SineSource(noise_std=0.01, seed=7, n_blocks=2, block_size=64)
    b = SineSource(noise_std=0.01, seed=7, n_blocks=2, block_size=64)
    assert np.array_equal(a.blocks().__next__().data, b.blocks().__next__().data)


def test_invalid_parameters():
    with pytest.raises(ValueError):
        SineSource(frequency=0)
    with pytest.raises(ValueError):
        SineSource(channels=0)
