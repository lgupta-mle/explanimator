"""Tests for multi-language batch mode in pdf_to_manim_pipeline."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from research_viz.schemas.language_schemas import SUPPORTED_LANGUAGES
from research_viz.manim_generator.pdf_to_manim_pipeline import (
    _run_for_language,
    ManimSceneCode,
)
from research_viz.config.difficulty import DIFFICULTY_CONFIGS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_EXPLANATION = {
    "paper_title": "Test Paper",
    "opening_question": "What is this?",
    "running_example": "Example",
    "segments": [
        {
            "segment_id": "seg_01",
            "title": "Intro",
            "narration_script": "Hello, this is segment one.",
            "intuition": "An intuitive explanation.",
            "technical": "Technical details.",
        },
        {
            "segment_id": "seg_02",
            "title": "Body",
            "narration_script": "Now let us discuss segment two.",
            "intuition": "More intuition.",
            "technical": "More technical.",
        },
    ],
}

SAMPLE_SCENE_CODES = [
    ManimSceneCode(
        scene_id="seg_01",
        code='class Seg01(Scene):\n    def construct(self):\n        t = Text("Hello World")\n        self.play(Create(t))\n',
        class_name="Seg01",
    ),
    ManimSceneCode(
        scene_id="seg_02",
        code='class Seg02(Scene):\n    def construct(self):\n        t = Text("Gradient Descent")\n        self.play(Create(t))\n',
        class_name="Seg02",
    ),
]


# ---------------------------------------------------------------------------
# Tests: language list parsing in main()
# ---------------------------------------------------------------------------

def test_languages_flag_parsed_correctly():
    """--languages should be split, validated, and deduplicated."""
    from research_viz.manim_generator.pdf_to_manim_pipeline import main

    with tempfile.TemporaryDirectory() as tmpdir:
        # Write a dummy explanation so main() can load it
        exp_path = os.path.join(tmpdir, "test_explanation.json")
        with open(exp_path, "w") as f:
            json.dump(SAMPLE_EXPLANATION, f)

        # Patch heavy functions to avoid real LLM / TTS calls
        with patch(
            "research_viz.manim_generator.pdf_to_manim_pipeline.generate_all_scenes",
            return_value=SAMPLE_SCENE_CODES,
        ), patch(
            "research_viz.manim_generator.pdf_to_manim_pipeline._run_for_language",
            return_value=tmpdir,
        ) as mock_run:
            main(
                explanation_path=exp_path,
                output_dir=tmpdir,
                languages="en,es",
                generate_audio=False,
                render_video=False,
            )

        # _run_for_language should be called once per language
        assert mock_run.call_count == 2
        called_langs = [call.kwargs["language"] for call in mock_run.call_args_list]
        assert called_langs == ["en", "es"]


def test_languages_flag_rejects_invalid_code():
    """An invalid language code in --languages should cause an early return."""
    from research_viz.manim_generator.pdf_to_manim_pipeline import main

    with tempfile.TemporaryDirectory() as tmpdir:
        exp_path = os.path.join(tmpdir, "test_explanation.json")
        with open(exp_path, "w") as f:
            json.dump(SAMPLE_EXPLANATION, f)

        # Should print an error and return without calling anything
        with patch(
            "research_viz.manim_generator.pdf_to_manim_pipeline.generate_all_scenes"
        ) as mock_gen:
            main(
                explanation_path=exp_path,
                output_dir=tmpdir,
                languages="en,xx_invalid",
                generate_audio=False,
                render_video=False,
            )
            mock_gen.assert_not_called()


def test_languages_deduplicates():
    """Duplicate codes in --languages should be collapsed."""
    from research_viz.manim_generator.pdf_to_manim_pipeline import main

    with tempfile.TemporaryDirectory() as tmpdir:
        exp_path = os.path.join(tmpdir, "test_explanation.json")
        with open(exp_path, "w") as f:
            json.dump(SAMPLE_EXPLANATION, f)

        with patch(
            "research_viz.manim_generator.pdf_to_manim_pipeline.generate_all_scenes",
            return_value=SAMPLE_SCENE_CODES,
        ), patch(
            "research_viz.manim_generator.pdf_to_manim_pipeline._run_for_language",
            return_value=tmpdir,
        ) as mock_run:
            main(
                explanation_path=exp_path,
                output_dir=tmpdir,
                languages="es,es,es",
                generate_audio=False,
                render_video=False,
            )

        assert mock_run.call_count == 1


# ---------------------------------------------------------------------------
# Tests: _run_for_language
# ---------------------------------------------------------------------------

def test_run_for_language_english_no_translation():
    """English should skip translation entirely and save code."""
    with tempfile.TemporaryDirectory() as tmpdir:
        exp_path = os.path.join(tmpdir, "test_explanation.json")
        with open(exp_path, "w") as f:
            json.dump(SAMPLE_EXPLANATION, f)

        run_dir = _run_for_language(
            language="en",
            explanation=SAMPLE_EXPLANATION,
            scene_codes_english=SAMPLE_SCENE_CODES,
            pdf_stem="test",
            output_dir=tmpdir,
            difficulty="medium",
            difficulty_config=DIFFICULTY_CONFIGS["medium"],
            generate_audio=False,
            tts_voice="nova",
            render_video=False,
            video_quality="l",
            sync_mode="segment",
            max_speed_change=0.3,
            used_explanation_path=exp_path,
        )

        # Check output directory was created
        assert os.path.isdir(run_dir)

        # Code file should exist with original English text
        code_path = os.path.join(run_dir, "test_animation.py")
        assert os.path.isfile(code_path)
        code_content = open(code_path).read()
        assert "Hello World" in code_content

        # Scene metadata should exist
        meta_path = os.path.join(run_dir, "test_scene_metadata.json")
        assert os.path.isfile(meta_path)

        # No translated explanation should be saved for English
        translated_path = os.path.join(run_dir, "test_explanation_en.json")
        assert not os.path.exists(translated_path)


def test_run_for_language_non_english_translates():
    """Non-English should translate narrations and display texts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        exp_path = os.path.join(tmpdir, "test_explanation.json")
        with open(exp_path, "w") as f:
            json.dump(SAMPLE_EXPLANATION, f)

        mock_translate_all = MagicMock(return_value=[
            "Hola, este es el segmento uno.",
            "Ahora discutamos el segmento dos.",
        ])
        mock_translate_display = MagicMock(return_value={
            "Hello World": "Hola Mundo",
            "Gradient Descent": "Descenso de Gradiente",
        })

        with patch(
            "research_viz.translation.translator.NarrationTranslator.translate_all_narrations",
            mock_translate_all,
        ), patch(
            "research_viz.translation.translator.NarrationTranslator.translate_display_texts",
            mock_translate_display,
        ):
            run_dir = _run_for_language(
                language="es",
                explanation=SAMPLE_EXPLANATION,
                scene_codes_english=SAMPLE_SCENE_CODES,
                pdf_stem="test",
                output_dir=tmpdir,
                difficulty="medium",
                difficulty_config=DIFFICULTY_CONFIGS["medium"],
                generate_audio=False,
                tts_voice="nova",
                render_video=False,
                video_quality="l",
                sync_mode="segment",
                max_speed_change=0.3,
                used_explanation_path=exp_path,
            )

        # Translated explanation should exist
        translated_path = os.path.join(run_dir, "test_explanation_es.json")
        assert os.path.isfile(translated_path)
        with open(translated_path, "r") as f:
            translated = json.load(f)
        assert translated["segments"][0]["narration_script"] == "Hola, este es el segmento uno."

        # Code should contain translated display text
        code_path = os.path.join(run_dir, "test_animation.py")
        code_content = open(code_path).read()
        assert "Hola Mundo" in code_content
        assert "Descenso de Gradiente" in code_content


def test_run_for_language_reuses_existing_translation():
    """If a translated explanation already exists on disk, skip LLM translation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        exp_path = os.path.join(tmpdir, "test_explanation.json")
        with open(exp_path, "w") as f:
            json.dump(SAMPLE_EXPLANATION, f)

        # Pre-create the translated explanation
        run_dir = os.path.join(tmpdir, "test_medium_es")
        Path(run_dir).mkdir(parents=True)
        pre_translated = SAMPLE_EXPLANATION.copy()
        pre_translated["segments"] = [
            {**seg, "narration_script": f"Pre-translated: {seg['narration_script']}"}
            for seg in SAMPLE_EXPLANATION["segments"]
        ]
        translated_path = os.path.join(run_dir, "test_explanation_es.json")
        with open(translated_path, "w") as f:
            json.dump(pre_translated, f)

        with patch(
            "research_viz.translation.translator.NarrationTranslator.translate_all_narrations"
        ) as mock_translate:
            mock_translate_display = MagicMock(return_value={})
            with patch(
                "research_viz.translation.translator.NarrationTranslator.translate_display_texts",
                mock_translate_display,
            ):
                _run_for_language(
                    language="es",
                    explanation=SAMPLE_EXPLANATION,
                    scene_codes_english=SAMPLE_SCENE_CODES,
                    pdf_stem="test",
                    output_dir=tmpdir,
                    difficulty="medium",
                    difficulty_config=DIFFICULTY_CONFIGS["medium"],
                    generate_audio=False,
                    tts_voice="nova",
                    render_video=False,
                    video_quality="l",
                    sync_mode="segment",
                    max_speed_change=0.3,
                    used_explanation_path=exp_path,
                )

            # translate_all_narrations should NOT have been called
            mock_translate.assert_not_called()


def test_run_for_language_does_not_mutate_english_scenes():
    """_run_for_language must not mutate the English scene_codes list."""
    import copy
    original_codes = [sc.code for sc in SAMPLE_SCENE_CODES]

    with tempfile.TemporaryDirectory() as tmpdir:
        exp_path = os.path.join(tmpdir, "test_explanation.json")
        with open(exp_path, "w") as f:
            json.dump(SAMPLE_EXPLANATION, f)

        with patch(
            "research_viz.translation.translator.NarrationTranslator.translate_all_narrations",
            return_value=["Translated A", "Translated B"],
        ), patch(
            "research_viz.translation.translator.NarrationTranslator.translate_display_texts",
            return_value={"Hello World": "CHANGED", "Gradient Descent": "CHANGED"},
        ):
            _run_for_language(
                language="ja",
                explanation=SAMPLE_EXPLANATION,
                scene_codes_english=SAMPLE_SCENE_CODES,
                pdf_stem="test",
                output_dir=tmpdir,
                difficulty="medium",
                difficulty_config=DIFFICULTY_CONFIGS["medium"],
                generate_audio=False,
                tts_voice="nova",
                render_video=False,
                video_quality="l",
                sync_mode="segment",
                max_speed_change=0.3,
                used_explanation_path=exp_path,
            )

    # Original scene codes must be unchanged
    for sc, orig_code in zip(SAMPLE_SCENE_CODES, original_codes):
        assert sc.code == orig_code, "English scene code was mutated!"
