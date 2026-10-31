"""Thread-safe bounded queue for audio blocks.

The audio callback must never block: when the queue is full the block is
dropped and counted, and the gap is preserved via the block's own
``first_sample_index`` (the consumer detects the discontinuity). Missing
samples are never silently replaced with zeros.
"""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable

from ofo_analyzer.models import SampleBlock


class BlockQueue:
    """Bounded, thread-safe hand-off between the audio callback and workers."""

    def __init__(self, max_blocks: int = 64, on_drop: Callable[[int], None] | None = None) -> None:
        self._queue: queue.Queue[SampleBlock] = queue.Queue(maxsize=max_blocks)
        self._closed = threading.Event()
        self.dropped_blocks = 0
        self._on_drop = on_drop

    def put(self, block: SampleBlock) -> None:
        """Enqueue a block; drop and count it when full instead of blocking."""
        try:
            self._queue.put_nowait(block)
        except queue.Full:
            self.dropped_blocks += 1
            if self._on_drop is not None:
                self._on_drop(block.n_samples)

    def get(self, timeout: float | None = 0.1) -> SampleBlock | None:
        """Return the next block, or None on timeout/closed-and-drained."""
        if self._closed.is_set() and self._queue.empty():
            return None
        try:
            return self._queue.get(timeout=timeout if timeout is not None else None)
        except queue.Empty:
            return None

    def close(self) -> None:
        """Stop accepting new blocks; queued blocks remain readable."""
        self._closed.set()

    @property
    def closed(self) -> bool:
        return self._closed.is_set()

    def flush(self) -> list[SampleBlock]:
        """Drain all currently queued blocks without waiting."""
        out: list[SampleBlock] = []
        while True:
            try:
                out.append(self._queue.get_nowait())
            except queue.Empty:
                return out
