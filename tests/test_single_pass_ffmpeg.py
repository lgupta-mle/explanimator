"""Tests for US-009: Single-pass ffmpeg filter chain."""

import os
import subprocess
from unittest.mock import patch, MagicMock, call

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


class TestSyncVideoAudioSinglePass:
    """Tests for sync_video_audio_single_pass function."""

    @patch(f"{MODULE}.subprocess.run")
    @patch(f"{MODULE}.get_audio_duration", return_value=10.0)
    @patch(f"{MODULE}.get_video_duration", return_value=10.0)
    def test_no_speed_change_needed(self, mock_vdur, mock_adur, mock_run):
        """When video and audio are same duration, only tpad + audio merge, no setpts."""
        from research_viz.manim_generator.pdf_to_manim_pipeline import sync_video_audio_single_pass

        result = sync_video_audio_single_pass("v.mp4", "a.wav", "out.mp4")
        assert result is True
        assert mock_run.call_count == 1

        cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(cmd)
        # Should have tpad for the 0.5s buffer but no setpts
        assert "setpts" not in cmd_str
        assert "tpad" in cmd_str
        assert "out.mp4" in cmd_str

    @patch(f"{MODULE}.subprocess.run")
    @patch(f"{MODULE}.get_audio_duration", return_value=12.0)
    @patch(f"{MODULE}.get_video_duration", return_value=10.0)
    def test_speed_adjust_within_limits(self, mock_vdur, mock_adur, mock_run):
        """When speed change is within max_speed_change, uses setpts filter."""
        from research_viz.manim_generator.pdf_to_manim_pipeline import sync_video_audio_single_pass

        # 10s video → 12s audio = 16.7% speed change, within 30% limit
        result = sync_video_audio_single_pass("v.mp4", "a.wav", "out.mp4")
        assert result is True

        cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(cmd)
        assert "setpts" in cmd_str
        assert "tpad" in cmd_str  # 0.5s buffer padding
        assert "libx264" in cmd_str  # must re-encode when filtering

    @patch(f"{MODULE}.subprocess.run")
    @patch(f"{MODULE}.get_audio_duration", return_value=20.0)
    @patch(f"{MODULE}.get_video_duration", return_value=10.0)
    def test_speed_change_exceeds_limit_video_short(self, mock_vdur, mock_adur, mock_run):
        """When speed change exceeds limit and video is shorter, pads with tpad only."""
        from research_viz.manim_generator.pdf_to_manim_pipeline import sync_video_audio_single_pass

        # 10s video → 20s audio = 100% change, exceeds 30% limit
        result = sync_video_audio_single_pass("v.mp4", "a.wav", "out.mp4")
        assert result is True

        cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(cmd)
        # No speed adjust, just tpad to extend
        assert "setpts" not in cmd_str
        assert "tpad" in cmd_str

    @patch(f"{MODULE}.subprocess.run")
    @patch(f"{MODULE}.get_audio_duration", return_value=5.0)
    @patch(f"{MODULE}.get_video_duration", return_value=10.0)
    def test_speed_change_exceeds_limit_video_long(self, mock_vdur, mock_adur, mock_run):
        """When speed change exceeds limit and video is longer, trims with -t flag."""
        from research_viz.manim_generator.pdf_to_manim_pipeline import sync_video_audio_single_pass

        # 10s video → 5s audio = 100% change, exceeds 30% limit
        result = sync_video_audio_single_pass("v.mp4", "a.wav", "out.mp4")
        assert result is True

        cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(cmd)
        assert "setpts" not in cmd_str
        assert "-t" in cmd

    @patch(f"{MODULE}.subprocess.run")
    @patch(f"{MODULE}.get_audio_duration", return_value=10.0)
    @patch(f"{MODULE}.get_video_duration", return_value=0.0)
    def test_zero_video_duration_returns_false(self, mock_vdur, mock_adur, mock_run):
        """Returns False when video duration is 0."""
        from research_viz.manim_generator.pdf_to_manim_pipeline import sync_video_audio_single_pass

        result = sync_video_audio_single_pass("v.mp4", "a.wav", "out.mp4")
        assert result is False
        mock_run.assert_not_called()

    @patch(f"{MODULE}.subprocess.run")
    @patch(f"{MODULE}.get_audio_duration", return_value=0.0)
    @patch(f"{MODULE}.get_video_duration", return_value=10.0)
    def test_zero_audio_duration_returns_false(self, mock_vdur, mock_adur, mock_run):
        """Returns False when audio duration is 0."""
        from research_viz.manim_generator.pdf_to_manim_pipeline import sync_video_audio_single_pass

        result = sync_video_audio_single_pass("v.mp4", "a.wav", "out.mp4")
        assert result is False
        mock_run.assert_not_called()

    @patch(f"{MODULE}.subprocess.run", side_effect=subprocess.CalledProcessError(1, "ffmpeg"))
    @patch(f"{MODULE}.get_audio_duration", return_value=10.0)
    @patch(f"{MODULE}.get_video_duration", return_value=10.0)
    def test_ffmpeg_failure_returns_false(self, mock_vdur, mock_adur, mock_run):
        """Returns False when ffmpeg command fails."""
        from research_viz.manim_generator.pdf_to_manim_pipeline import sync_video_audio_single_pass

        result = sync_video_audio_single_pass("v.mp4", "a.wav", "out.mp4")
        assert result is False

    @patch(f"{MODULE}.subprocess.run")
    @patch(f"{MODULE}.get_audio_duration", return_value=10.0)
    @patch(f"{MODULE}.get_video_duration", return_value=10.0)
    def test_single_ffmpeg_invocation(self, mock_vdur, mock_adur, mock_run):
        """Verifies only ONE subprocess.run call (single-pass, no double re-encode)."""
        from research_viz.manim_generator.pdf_to_manim_pipeline import sync_video_audio_single_pass

        sync_video_audio_single_pass("v.mp4", "a.wav", "out.mp4")
        assert mock_run.call_count == 1

    @patch(f"{MODULE}.subprocess.run")
    @patch(f"{MODULE}.get_audio_duration", return_value=10.0)
    @patch(f"{MODULE}.get_video_duration", return_value=10.0)
    def test_audio_codec_in_output(self, mock_vdur, mock_adur, mock_run):
        """Output includes AAC audio encoding."""
        from research_viz.manim_generator.pdf_to_manim_pipeline import sync_video_audio_single_pass

        sync_video_audio_single_pass("v.mp4", "a.wav", "out.mp4")
        cmd = mock_run.call_args[0][0]
        assert "-c:a" in cmd
        assert "aac" in cmd

    @patch(f"{MODULE}.subprocess.run")
    @patch(f"{MODULE}.get_audio_duration", return_value=10.0)
    @patch(f"{MODULE}.get_video_duration", return_value=10.05)
    def test_near_equal_durations_no_speed_adjust(self, mock_vdur, mock_adur, mock_run):
        """When durations differ by < 0.1s, no setpts applied."""
        from research_viz.manim_generator.pdf_to_manim_pipeline import sync_video_audio_single_pass

        sync_video_audio_single_pass("v.mp4", "a.wav", "out.mp4")
        cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(cmd)
        assert "setpts" not in cmd_str

    @patch(f"{MODULE}.subprocess.run")
    @patch(f"{MODULE}.get_audio_duration", return_value=10.0)
    @patch(f"{MODULE}.get_video_duration", return_value=8.0)
    def test_speed_adjust_with_custom_max(self, mock_vdur, mock_adur, mock_run):
        """Custom max_speed_change is respected."""
        from research_viz.manim_generator.pdf_to_manim_pipeline import sync_video_audio_single_pass

        # 8s → 10s = 20% change. With max=0.1 (10%), should NOT use setpts
        sync_video_audio_single_pass("v.mp4", "a.wav", "out.mp4", max_speed_change=0.1)
        cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(cmd)
        assert "setpts" not in cmd_str

        mock_run.reset_mock()

        # With max=0.3 (30%), should use setpts
        sync_video_audio_single_pass("v.mp4", "a.wav", "out.mp4", max_speed_change=0.3)
        cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(cmd)
        assert "setpts" in cmd_str
