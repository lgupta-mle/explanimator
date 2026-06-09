"""Tests for US-013: Skip judge loop for hard mode."""
import json
import os
from unittest.mock import MagicMock, patch

import pytest
import yaml

from research_viz.config.pipeline_config import (
    LLMConfig,
    PipelineConfig,
    TierConfig,
    reset_config,
)
from research_viz.manim_generator.pdf_explanation_generator import (
    _validate_segment_count,
    generate_with_feedback_loop,
)
from research_viz.providers.llm_provider import LLMResponse


@pytest.fixture(autouse=True)
def isolate_config(tmp_path, monkeypatch):
    monkeypatch.setenv("ANVAYA_CONFIG_PATH", str(tmp_path / "config.yaml"))
    monkeypatch.delenv("ANVAYA_PROFILE", raising=False)
    reset_config()
    yield
    reset_config()


def _make_explanation(num_segments=2):
    return json.dumps({
        "paper_title": "Test",
        "segments": [{"id": i} for i in range(num_segments)],
    })


class TestValidateSegmentCount:
    def test_valid_2_segments(self):
        assert _validate_segment_count(_make_explanation(2)) is True

    def test_valid_3_segments(self):
        assert _validate_segment_count(_make_explanation(3)) is True

    def test_too_few_segments(self):
        assert _validate_segment_count(_make_explanation(1)) is False

    def test_too_many_segments(self):
        assert _validate_segment_count(_make_explanation(5)) is False

    def test_invalid_json(self):
        assert _validate_segment_count("not json") is False

    def test_no_segments_key(self):
        assert _validate_segment_count(json.dumps({"title": "x"})) is False


class TestSkipJudge:
    @patch("research_viz.manim_generator.pdf_explanation_generator.get_provider")
    @patch("research_viz.manim_generator.pdf_explanation_generator.create_pdf_llm_response")
    def test_hard_mode_skips_judge(self, mock_create, mock_provider, tmp_path):
        """When difficulty=hard and skip_judge=True, judge_explanation is not called."""
        yaml_data = {"llm": {"tiers": {"hard": {"skip_judge": True}}}}
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(yaml_data, f)
        os.environ["ANVAYA_CONFIG_PATH"] = str(config_path)
        reset_config()

        mock_response = MagicMock()
        mock_response.content = _make_explanation(2)
        mock_create.return_value = mock_response

        with patch("research_viz.manim_generator.pdf_explanation_generator.judge_explanation") as mock_judge:
            result = generate_with_feedback_loop("fake.pdf", difficulty="hard")
            mock_judge.assert_not_called()
            assert result is not None
            assert result["paper_title"] == "Test"

    @patch("research_viz.manim_generator.pdf_explanation_generator.get_provider")
    @patch("research_viz.manim_generator.pdf_explanation_generator.create_pdf_llm_response")
    def test_no_difficulty_runs_judge(self, mock_create, mock_provider, tmp_path):
        """Without difficulty, judge runs normally."""
        mock_response = MagicMock()
        mock_response.content = _make_explanation(2)
        mock_create.return_value = mock_response

        mock_judge_result = MagicMock()
        mock_judge_result.score = 1
        mock_judge_result.criteria_scores = {}

        with patch("research_viz.manim_generator.pdf_explanation_generator.judge_explanation", return_value=mock_judge_result) as mock_judge:
            result = generate_with_feedback_loop("fake.pdf")
            mock_judge.assert_called_once()

    @patch("research_viz.manim_generator.pdf_explanation_generator.get_provider")
    @patch("research_viz.manim_generator.pdf_explanation_generator.create_pdf_llm_response")
    def test_hard_mode_still_validates_segments(self, mock_create, mock_provider, tmp_path):
        """Even with skip_judge, segment count validation runs."""
        yaml_data = {"llm": {"tiers": {"hard": {"skip_judge": True}}}}
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(yaml_data, f)
        os.environ["ANVAYA_CONFIG_PATH"] = str(config_path)
        reset_config()

        # First call returns 5 segments (invalid), second returns 2 (valid)
        bad_response = MagicMock()
        bad_response.content = _make_explanation(5)
        good_response = MagicMock()
        good_response.content = _make_explanation(2)
        mock_create.side_effect = [bad_response, good_response]

        result = generate_with_feedback_loop("fake.pdf", difficulty="hard")
        assert result is not None
        assert mock_create.call_count == 2

    @patch("research_viz.manim_generator.pdf_explanation_generator.get_provider")
    @patch("research_viz.manim_generator.pdf_explanation_generator.create_pdf_llm_response")
    def test_hard_mode_uses_tier_model(self, mock_create, mock_provider, tmp_path):
        """Hard mode uses the tier-specific explanation model."""
        yaml_data = {"llm": {"tiers": {"hard": {
            "explanation_model": "fast/model",
            "skip_judge": True,
        }}}}
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(yaml_data, f)
        os.environ["ANVAYA_CONFIG_PATH"] = str(config_path)
        reset_config()

        mock_response = MagicMock()
        mock_response.content = _make_explanation(2)
        mock_create.return_value = mock_response

        generate_with_feedback_loop("fake.pdf", difficulty="hard")
        call_kwargs = mock_create.call_args
        assert call_kwargs[1]["model_name"] == "fast/model" or call_kwargs.kwargs["model_name"] == "fast/model"
