"""Acquisition sources: synthetic, WAV replay, and live device capture."""

from ofo_analyzer.acquisition.base import AudioSource
from ofo_analyzer.acquisition.block_queue import BlockQueue
from ofo_analyzer.acquisition.synthetic import SineSource
from ofo_analyzer.acquisition.wavfile import WavReplaySource

__all__ = ["AudioSource", "BlockQueue", "SineSource", "WavReplaySource"]


def __getattr__(name: str):  # pragma: no cover - import guard for optional live capture
    if name == "LiveSource":
        from ofo_analyzer.acquisition.device import LiveSource

        return LiveSource
    raise AttributeError(name)
