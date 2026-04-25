"""Checkpoint management for pipeline stage completion."""

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Checkpoint:
    stage_name: str
    artifact_paths: list[str]
    artifact_hashes: dict[str, str]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Checkpoint":
        return cls(**data)


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def write_checkpoint(run_dir: str, stage_name: str, artifact_paths: list[str]) -> Path:
    """Write a checkpoint file after a stage completes successfully.

    Args:
        run_dir: Directory for this pipeline run
        stage_name: Name of the completed stage
        artifact_paths: Paths to artifacts produced by this stage

    Returns:
        Path to the written checkpoint file
    """
    hashes = {}
    for p in artifact_paths:
        if Path(p).exists():
            hashes[p] = _sha256(p)

    cp = Checkpoint(
        stage_name=stage_name,
        artifact_paths=artifact_paths,
        artifact_hashes=hashes,
    )

    cp_dir = Path(run_dir) / "checkpoints"
    cp_dir.mkdir(parents=True, exist_ok=True)
    cp_path = cp_dir / f"{stage_name}.json"
    with open(cp_path, "w") as f:
        json.dump(cp.to_dict(), f, indent=2)
    return cp_path


def read_checkpoints(run_dir: str) -> dict[str, Checkpoint]:
    """Read all checkpoint files from a run directory.

    Returns:
        Dict mapping stage_name to Checkpoint
    """
    cp_dir = Path(run_dir) / "checkpoints"
    if not cp_dir.exists():
        return {}

    checkpoints = {}
    for cp_file in cp_dir.glob("*.json"):
        with open(cp_file) as f:
            data = json.load(f)
        cp = Checkpoint.from_dict(data)
        checkpoints[cp.stage_name] = cp
    return checkpoints


def validate_checkpoint(checkpoint: Checkpoint) -> bool:
    """Validate that checkpoint artifacts still match their recorded hashes.

    Returns:
        True if all artifacts exist and hashes match
    """
    for path, expected_hash in checkpoint.artifact_hashes.items():
        if not Path(path).exists():
            return False
        if _sha256(path) != expected_hash:
            return False
    return True
