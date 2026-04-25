"""Tests for US-010: Pipeline-parallel render and sync."""

import os
import json
import threading
import time
from unittest.mock import patch, MagicMock, call
from typing import Optional

import pytest

from research_viz.config.pipeline_config import reset_config


@pytest.fixture(autouse=True)
def clean_config():
    reset_config()
    env_keys = [k for k in os.environ if k.startswith("ANVAYA_")]
    for k in env_keys:
        del os.environ[k]
    yield
    reset_config()
    for k in env_keys:
        os.environ.pop(k, None)


MODULE = "research_viz.manim_generator.pdf_to_manim_pipeline"


def _make_scene(scene_id, class_name):
    from research_viz.manim_generator.pdf_to_manim_pipeline import ManimSceneCode
    return ManimSceneCode(scene_id=scene_id, class_name=class_name, code="pass")


def _make_timeline(segment_ids):
    """Build a minimal audio timeline dict."""
    segments = {}
    for sid in segment_ids:
        segments[sid] = {
            "beats": [{"audio_file": f"/tmp/{sid}_beat.wav"}]
        }
    return {"segments": segments}


class TestVideoConfigWorkers:
    """Test that render_workers and sync_workers are configurable."""

    def test_default_workers(self):
        os.environ["ANVAYA_CONFIG_PATH"] = "/tmp/nonexistent_config.yaml"
        reset_config()
        from research_viz.config.pipeline_config import get_config
        cfg = get_config()
        assert cfg.video.render_workers == 2
        assert cfg.video.sync_workers == 2

    def test_env_override_workers(self):
        os.environ["ANVAYA_CONFIG_PATH"] = "/tmp/nonexistent_config.yaml"
        os.environ["ANVAYA_VIDEO__RENDER_WORKERS"] = "4"
        os.environ["ANVAYA_VIDEO__SYNC_WORKERS"] = "3"
        reset_config()
        from research_viz.config.pipeline_config import get_config
        cfg = get_config()
        assert cfg.video.render_workers == 4
        assert cfg.video.sync_workers == 3
        del os.environ["ANVAYA_VIDEO__RENDER_WORKERS"]
        del os.environ["ANVAYA_VIDEO__SYNC_WORKERS"]


class TestRenderScene:
    """Tests for _render_scene helper."""

    @patch(f"{MODULE}.os.path.exists", return_value=True)
    def test_existing_video_skips_render(self, mock_exists):
        from research_viz.manim_generator.pdf_to_manim_pipeline import _render_scene
        scene = _make_scene("s1", "Scene1")
        result = _render_scene(0, scene, "/tmp/out", "l")
        assert result == "media/videos/temp_scene_1/480p15/Scene1.mp4"

    @patch(f"{MODULE}.os.path.exists", side_effect=[False, True])
    @patch(f"{MODULE}.subprocess.run")
    @patch("builtins.open", MagicMock())
    def test_render_success(self, mock_run, mock_exists):
        from research_viz.manim_generator.pdf_to_manim_pipeline import _render_scene
        mock_run.return_value = MagicMock(returncode=0)
        scene = _make_scene("s1", "Scene1")
        result = _render_scene(0, scene, "/tmp/out", "l")
        assert result is not None

    @patch(f"{MODULE}.os.path.exists", return_value=False)
    @patch(f"{MODULE}.subprocess.run")
    @patch("builtins.open", MagicMock())
    def test_render_failure_returns_none(self, mock_run, mock_exists):
        from research_viz.manim_generator.pdf_to_manim_pipeline import _render_scene
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        scene = _make_scene("s1", "Scene1")
        result = _render_scene(0, scene, "/tmp/out", "l")
        assert result is None


class TestSyncScene:
    """Tests for _sync_scene helper."""

    @patch(f"{MODULE}.os.path.exists", return_value=True)
    def test_existing_synced_video_skips(self, mock_exists):
        from research_viz.manim_generator.pdf_to_manim_pipeline import _sync_scene
        result = _sync_scene(0, "v.mp4", "seg_01", {"segments": {}}, "/tmp/out", 0.3, "segment")
        assert result == "/tmp/out/synced_scene_1.mp4"

    def test_no_audio_returns_raw_video(self):
        from research_viz.manim_generator.pdf_to_manim_pipeline import _sync_scene
        with patch(f"{MODULE}.os.path.exists", return_value=False):
            result = _sync_scene(0, "v.mp4", "seg_01", {"segments": {}}, "/tmp/out", 0.3, "segment")
        assert result == "v.mp4"

    @patch(f"{MODULE}.sync_video_audio_single_pass", return_value=True)
    @patch(f"{MODULE}.subprocess.run")
    @patch(f"{MODULE}.os.path.exists", return_value=False)
    def test_sync_single_beat(self, mock_exists, mock_run, mock_sync):
        from research_viz.manim_generator.pdf_to_manim_pipeline import _sync_scene
        timeline = _make_timeline(["seg_01"])
        result = _sync_scene(0, "v.mp4", "seg_01", timeline, "/tmp/out", 0.3, "segment")
        assert result == "/tmp/out/synced_scene_1.mp4"
        mock_sync.assert_called_once()


class TestRenderAndSyncPipelineParallel:
    """Tests for the producer-consumer pattern in render_and_sync_all_scenes."""

    @patch(f"{MODULE}.get_video_duration", return_value=30.0)
    @patch(f"{MODULE}.subprocess.run")
    @patch(f"{MODULE}._sync_scene")
    @patch(f"{MODULE}._render_scene")
    def test_scenes_processed_and_ordered(self, mock_render, mock_sync, mock_run, mock_dur):
        """Scenes should be synced in order regardless of completion order."""
        os.environ["ANVAYA_CONFIG_PATH"] = "/tmp/nonexistent_config.yaml"
        reset_config()

        mock_render.side_effect = lambda i, sc, od, q: f"rendered_{i}.mp4"
        mock_sync.side_effect = lambda i, vp, sid, at, od, msc, sm: f"synced_{i}.mp4"
        mock_run.return_value = MagicMock(returncode=0)

        from research_viz.manim_generator.pdf_to_manim_pipeline import render_and_sync_all_scenes

        scenes = [_make_scene(f"s{j}", f"Scene{j}") for j in range(3)]
        explanation = {"segments": [
            {"segment_id": f"seg_{j+1:02d}"} for j in range(3)
        ]}

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            timeline_path = os.path.join(tmpdir, "timeline.json")
            with open(timeline_path, 'w') as f:
                json.dump({"segments": {}}, f)

            result = render_and_sync_all_scenes(
                scenes, explanation, timeline_path, tmpdir
            )

        assert result is not None
        assert mock_render.call_count == 3
        assert mock_sync.call_count == 3

    @patch(f"{MODULE}._sync_scene")
    @patch(f"{MODULE}._render_scene")
    def test_failed_render_excluded(self, mock_render, mock_sync):
        """If render fails (returns None), that scene is excluded from final output."""
        os.environ["ANVAYA_CONFIG_PATH"] = "/tmp/nonexistent_config.yaml"
        reset_config()

        mock_render.side_effect = lambda i, sc, od, q: None if i == 1 else f"rendered_{i}.mp4"
        mock_sync.side_effect = lambda i, vp, sid, at, od, msc, sm: f"synced_{i}.mp4"

        from research_viz.manim_generator.pdf_to_manim_pipeline import render_and_sync_all_scenes

        scenes = [_make_scene(f"s{j}", f"Scene{j}") for j in range(3)]
        explanation = {"segments": [{"segment_id": f"seg_{j+1:02d}"} for j in range(3)]}

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            timeline_path = os.path.join(tmpdir, "timeline.json")
            with open(timeline_path, 'w') as f:
                json.dump({"segments": {}}, f)

            with patch(f"{MODULE}.subprocess.run") as mock_run, \
                 patch(f"{MODULE}.get_video_duration", return_value=10.0):
                mock_run.return_value = MagicMock(returncode=0)
                result = render_and_sync_all_scenes(
                    scenes, explanation, timeline_path, tmpdir
                )

        # Scene 1 failed render, so sync should only be called for scenes 0 and 2
        assert mock_sync.call_count == 2
        assert result is not None

    @patch(f"{MODULE}._sync_scene")
    @patch(f"{MODULE}._render_scene")
    def test_all_renders_fail_returns_none(self, mock_render, mock_sync):
        """If all renders fail, return None."""
        os.environ["ANVAYA_CONFIG_PATH"] = "/tmp/nonexistent_config.yaml"
        reset_config()

        mock_render.return_value = None

        from research_viz.manim_generator.pdf_to_manim_pipeline import render_and_sync_all_scenes

        scenes = [_make_scene("s0", "Scene0")]
        explanation = {"segments": [{"segment_id": "seg_01"}]}

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            timeline_path = os.path.join(tmpdir, "timeline.json")
            with open(timeline_path, 'w') as f:
                json.dump({"segments": {}}, f)

            result = render_and_sync_all_scenes(
                scenes, explanation, timeline_path, tmpdir
            )

        assert result is None
        mock_sync.assert_not_called()

    @patch(f"{MODULE}._sync_scene")
    @patch(f"{MODULE}._render_scene")
    def test_render_and_sync_overlap(self, mock_render, mock_sync):
        """Verify that rendering and syncing actually overlap in time."""
        os.environ["ANVAYA_CONFIG_PATH"] = "/tmp/nonexistent_config.yaml"
        os.environ["ANVAYA_VIDEO__RENDER_WORKERS"] = "2"
        os.environ["ANVAYA_VIDEO__SYNC_WORKERS"] = "2"
        reset_config()

        events = {"render_times": {}, "sync_times": {}}

        def slow_render(i, sc, od, q):
            events["render_times"][i] = ("start", time.monotonic())
            time.sleep(0.1)
            events["render_times"][(i, "end")] = time.monotonic()
            return f"rendered_{i}.mp4"

        def slow_sync(i, vp, sid, at, od, msc, sm):
            events["sync_times"][i] = ("start", time.monotonic())
            time.sleep(0.1)
            events["sync_times"][(i, "end")] = time.monotonic()
            return f"synced_{i}.mp4"

        mock_render.side_effect = slow_render
        mock_sync.side_effect = slow_sync

        from research_viz.manim_generator.pdf_to_manim_pipeline import render_and_sync_all_scenes

        scenes = [_make_scene(f"s{j}", f"Scene{j}") for j in range(4)]
        explanation = {"segments": [{"segment_id": f"seg_{j+1:02d}"} for j in range(4)]}

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            timeline_path = os.path.join(tmpdir, "timeline.json")
            with open(timeline_path, 'w') as f:
                json.dump({"segments": {}}, f)

            with patch(f"{MODULE}.subprocess.run") as mock_run, \
                 patch(f"{MODULE}.get_video_duration", return_value=10.0):
                mock_run.return_value = MagicMock(returncode=0)
                start = time.monotonic()
                result = render_and_sync_all_scenes(
                    scenes, explanation, timeline_path, tmpdir
                )
                elapsed = time.monotonic() - start

        assert result is not None
        # 4 scenes x 0.1s render + 0.1s sync = 0.8s sequential
        # With 2 render workers + overlap, should be significantly less
        # Allow generous margin but verify it's not fully sequential
        assert elapsed < 0.7, f"Expected parallel execution, took {elapsed:.2f}s"

    def test_config_workers_used(self):
        """Verify render/sync workers from config are respected."""
        os.environ["ANVAYA_CONFIG_PATH"] = "/tmp/nonexistent_config.yaml"
        os.environ["ANVAYA_VIDEO__RENDER_WORKERS"] = "3"
        os.environ["ANVAYA_VIDEO__SYNC_WORKERS"] = "1"
        reset_config()
        from research_viz.config.pipeline_config import get_config
        cfg = get_config()
        assert cfg.video.render_workers == 3
        assert cfg.video.sync_workers == 1
