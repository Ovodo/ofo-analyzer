"""JSON sidecars: the provenance record beside every recording.

The sidecar, not the file name, carries the acquisition truth: device,
sample rate, units, calibration status, and quality flags. Write once
alongside a finished recording; readers must not silently repair
discrepancies between a sidecar and its audio file.
"""

from __future__ import annotations

import json
from pathlib import Path

from ofo_analyzer import SCHEMA_VERSION


def write_sidecar(path: str | Path, payload: dict[str, object]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    enriched = {"schema_version": SCHEMA_VERSION, **payload}
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(enriched, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
    tmp.replace(path)  # atomic on the same filesystem
    return path


def read_sidecar(path: str | Path) -> dict[str, object]:
    with open(Path(path), encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"sidecar {path} is not a JSON object")
    version = payload.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ValueError(f"sidecar {path} has schema {version!r}, expected {SCHEMA_VERSION}")
    return payload
