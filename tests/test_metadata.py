"""Metadata and sidecar serialization."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from ofo_analyzer.models import SampleBlock, SessionHealth, SessionMetadata, utc_now
from ofo_analyzer.storage.sidecar import read_sidecar, write_sidecar


def test_metadata_roundtrip_fields(tmp_path: Path):
    meta = SessionMetadata(
        session_id="sess-1",
        started_at_utc=utc_now(),
        sample_rate=48_000.0,
        channels=2,
        source_kind="live_device",
        instrument="UMC22",
        calibration_id=None,
    )
    path = write_sidecar(tmp_path / "sess-1.json", meta.to_dict())
    loaded = read_sidecar(path)
    assert loaded["session_id"] == "sess-1"
    assert loaded["sample_rate"] == 48_000.0
    assert loaded["channels"] == 2
    assert loaded["calibration_id"] is None
    assert loaded["schema_version"] == 1
    assert "FS" in str(loaded["units"]).upper() or "full scale" in str(loaded["units"]).lower()


def test_sidecar_rejects_wrong_schema(tmp_path: Path):
    path = tmp_path / "future.json"
    path.write_text('{"schema_version": 99, "session_id": "x"}', encoding="utf-8")
    with pytest.raises(ValueError):
        read_sidecar(path)


def test_sample_block_validation():
    with pytest.raises(ValueError):
        SampleBlock("s", 0, np.zeros(8), 1, utc_now())  # 1-D rejected
    with pytest.raises(ValueError):
        SampleBlock("s", 0, np.zeros((8, 2)), 1, utc_now())  # channel mismatch
    block = SampleBlock("s", 0, np.full((8, 1), 2.0), 1, utc_now())  # over full scale
    assert block.clipped is True


def test_health_ok_initially():
    health = SessionHealth()
    assert health.ok is True
    assert health.to_dict() == {
        "blocks": 0,
        "samples": 0,
        "overflow_blocks": 0,
        "dropped_blocks": 0,
        "clipped_blocks": 0,
        "history": [],
    }
