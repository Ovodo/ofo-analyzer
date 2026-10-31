"""Live-source behavior without requiring real hardware.

Hardware-dependent tests are skipped when no input device exists, but
configuration errors (bad device, bad channel count) must always raise
clear AcquisitionErrors, never silently succeed.
"""

from __future__ import annotations

import numpy as np
import pytest

from ofo_analyzer.acquisition.base import AcquisitionError
from ofo_analyzer.acquisition.block_queue import BlockQueue
from ofo_analyzer.acquisition.device import LiveSource
from ofo_analyzer.models import SampleBlock, utc_now


def test_portaudio_available_or_clearly_missing():
    """`available()` is a bool; either state is acceptable, confusion is not."""
    assert isinstance(LiveSource.available(), bool)
    assert isinstance(LiveSource.list_input_devices(), list)


def test_block_queue_drops_and_counts():
    queue = BlockQueue(max_blocks=2)
    block = SampleBlock("s", 0, np.zeros((8, 1)), 1, utc_now())
    queue.put(block)
    queue.put(block)
    queue.put(block)  # exceeds capacity: dropped, not blocked
    assert queue.dropped_blocks == 1
    assert len(queue.flush()) == 2
    assert queue.flush() == []


def test_block_queue_close_drains():
    queue = BlockQueue(max_blocks=4)
    queue.put(SampleBlock("s", 0, np.zeros((8, 1)), 1, utc_now()))
    queue.close()
    assert queue.closed is True
    assert queue.get(timeout=0.05) is not None  # queued block still readable
    assert queue.get(timeout=0.05) is None  # then drained


def test_invalid_channel_count_rejected():
    if not LiveSource.available():
        pytest.skip("PortAudio unavailable on this machine")
    devices = LiveSource.list_input_devices()
    if not devices:
        pytest.skip("no input device connected")
    max_channels = max(int(d["max_input_channels"]) for d in devices)
    with pytest.raises(AcquisitionError):
        LiveSource(channels=max_channels + 5)


def test_unknown_device_rejected():
    if not LiveSource.available():
        pytest.skip("PortAudio unavailable on this machine")
    with pytest.raises(AcquisitionError):
        LiveSource(device=99_999)


@pytest.mark.skipif(not LiveSource.available(), reason="PortAudio unavailable")
def test_live_capture_smoke():
    """If hardware exists: open the default input, capture a moment, close."""
    devices = LiveSource.list_input_devices()
    if not devices:
        pytest.skip("no input device connected")
    source = LiveSource(channels=1, sample_rate=48_000)
    try:
        source.start()
        got = []
        for block in source.blocks():
            got.append(block)
            if sum(b.n_samples for b in got) > 8_192:
                break
        assert got, "no blocks arrived from the live source"
        assert all(b.first_sample_index >= 0 for b in got)
    finally:
        source.close()
