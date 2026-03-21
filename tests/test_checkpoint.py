"""Tests for US-014: Checkpoint write on stage completion."""

import json

import pytest

from research_viz.pipeline.checkpoint import (
    Checkpoint,
    read_checkpoints,
    validate_checkpoint,
    write_checkpoint,
)


@pytest.fixture
def run_dir(tmp_path):
    return str(tmp_path / "run_001")


@pytest.fixture
def sample_artifact(tmp_path):
    f = tmp_path / "output.json"
    f.write_text('{"result": "ok"}')
    return str(f)


class TestWriteCheckpoint:
    def test_creates_checkpoint_file(self, run_dir, sample_artifact):
        cp_path = write_checkpoint(run_dir, "explanation", [sample_artifact])
        assert cp_path.exists()
        assert cp_path.name == "explanation.json"

    def test_checkpoint_contains_stage_name(self, run_dir, sample_artifact):
        cp_path = write_checkpoint(run_dir, "explanation", [sample_artifact])
        data = json.loads(cp_path.read_text())
        assert data["stage_name"] == "explanation"

    def test_checkpoint_contains_artifact_paths(self, run_dir, sample_artifact):
        cp_path = write_checkpoint(run_dir, "tts", [sample_artifact])
        data = json.loads(cp_path.read_text())
        assert sample_artifact in data["artifact_paths"]

    def test_checkpoint_contains_sha256_hashes(self, run_dir, sample_artifact):
        cp_path = write_checkpoint(run_dir, "tts", [sample_artifact])
        data = json.loads(cp_path.read_text())
        assert sample_artifact in data["artifact_hashes"]
        assert len(data["artifact_hashes"][sample_artifact]) == 64

    def test_checkpoint_contains_timestamp(self, run_dir, sample_artifact):
        cp_path = write_checkpoint(run_dir, "tts", [sample_artifact])
        data = json.loads(cp_path.read_text())
        assert isinstance(data["timestamp"], float)

    def test_creates_checkpoints_directory(self, run_dir, sample_artifact):
        write_checkpoint(run_dir, "explanation", [sample_artifact])
        from pathlib import Path
        assert (Path(run_dir) / "checkpoints").is_dir()

    def test_missing_artifact_skips_hash(self, run_dir):
        cp_path = write_checkpoint(run_dir, "explanation", ["/nonexistent/file.json"])
        data = json.loads(cp_path.read_text())
        assert "/nonexistent/file.json" in data["artifact_paths"]
        assert "/nonexistent/file.json" not in data["artifact_hashes"]

    def test_multiple_artifacts(self, run_dir, tmp_path):
        f1 = tmp_path / "a.json"
        f2 = tmp_path / "b.json"
        f1.write_text("aaa")
        f2.write_text("bbb")
        cp_path = write_checkpoint(run_dir, "codegen", [str(f1), str(f2)])
        data = json.loads(cp_path.read_text())
        assert len(data["artifact_hashes"]) == 2


class TestReadCheckpoints:
    def test_reads_all_checkpoints(self, run_dir, sample_artifact):
        write_checkpoint(run_dir, "explanation", [sample_artifact])
        write_checkpoint(run_dir, "tts", [sample_artifact])
        cps = read_checkpoints(run_dir)
        assert "explanation" in cps
        assert "tts" in cps

    def test_empty_dir_returns_empty_dict(self, run_dir):
        cps = read_checkpoints(run_dir)
        assert cps == {}

    def test_checkpoint_is_dataclass(self, run_dir, sample_artifact):
        write_checkpoint(run_dir, "explanation", [sample_artifact])
        cps = read_checkpoints(run_dir)
        cp = cps["explanation"]
        assert isinstance(cp, Checkpoint)
        assert cp.stage_name == "explanation"


class TestValidateCheckpoint:
    def test_valid_checkpoint(self, run_dir, sample_artifact):
        write_checkpoint(run_dir, "explanation", [sample_artifact])
        cps = read_checkpoints(run_dir)
        assert validate_checkpoint(cps["explanation"]) is True

    def test_modified_artifact_fails(self, run_dir, sample_artifact):
        write_checkpoint(run_dir, "explanation", [sample_artifact])
        # Modify the artifact after checkpoint
        with open(sample_artifact, "w") as f:
            f.write("modified content")
        cps = read_checkpoints(run_dir)
        assert validate_checkpoint(cps["explanation"]) is False

    def test_missing_artifact_fails(self, run_dir, tmp_path):
        f = tmp_path / "temp.json"
        f.write_text("data")
        write_checkpoint(run_dir, "explanation", [str(f)])
        f.unlink()
        cps = read_checkpoints(run_dir)
        assert validate_checkpoint(cps["explanation"]) is False

    def test_no_artifacts_is_valid(self, run_dir):
        write_checkpoint(run_dir, "explanation", [])
        cps = read_checkpoints(run_dir)
        assert validate_checkpoint(cps["explanation"]) is True
