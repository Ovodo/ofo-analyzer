"""Shared pytest fixtures for the OFO analyzer test suite."""

from __future__ import annotations

import pytest


FS = 48_000.0


@pytest.fixture()
def fs() -> float:
    return FS
