"""Tests for batched narration translation in translator.py."""

from unittest.mock import patch, MagicMock
from research_viz.translation.translator import NarrationTranslator
from research_viz.schemas.language_schemas import LanguageConfig


SPANISH = LanguageConfig(code="es", name="Spanish", script="latin", rtl=False)


def _mock_openrouter_response(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


def test_translate_all_narrations_single():
    """Single narration should delegate to translate_narration."""
    translator = NarrationTranslator()
    with patch.object(translator, "translate_narration", return_value="Hola mundo.") as mock:
        result = translator.translate_all_narrations(["Hello world."], SPANISH)
    assert result == ["Hola mundo."]
    mock.assert_called_once()


def test_translate_all_narrations_batch_parses_delimiters():
    """Batch call should parse === SEGMENT N === delimiters from LLM response."""
    translator = NarrationTranslator()
    response_content = (
        "=== SEGMENT 1 ===\n"
        "Primera narración traducida.\n\n"
        "=== SEGMENT 2 ===\n"
        "Segunda narración traducida.\n\n"
        "=== SEGMENT 3 ===\n"
        "Tercera narración traducida."
    )

    with patch("research_viz.translation.translator.call_openrouter",
               return_value=_mock_openrouter_response(response_content)):
        result = translator.translate_all_narrations(
            ["First narration.", "Second narration.", "Third narration."],
            SPANISH
        )

    assert len(result) == 3
    assert result[0] == "Primera narración traducida."
    assert result[1] == "Segunda narración traducida."
    assert result[2] == "Tercera narración traducida."


def test_translate_all_narrations_fallback_on_mismatch():
    """If LLM returns wrong number of segments, fall back to individual calls."""
    translator = NarrationTranslator()
    # LLM returns only 1 segment instead of 2
    bad_response = "=== SEGMENT 1 ===\nOnly one segment."

    with patch("research_viz.translation.translator.call_openrouter",
               return_value=_mock_openrouter_response(bad_response)):
        with patch.object(translator, "translate_narration",
                          side_effect=["Fallback A", "Fallback B"]) as mock:
            result = translator.translate_all_narrations(
                ["Narration A", "Narration B"],
                SPANISH
            )

    assert result == ["Fallback A", "Fallback B"]
    assert mock.call_count == 2


def test_translate_all_narrations_empty():
    """Empty list returns empty list."""
    translator = NarrationTranslator()
    assert translator.translate_all_narrations([], SPANISH) == []


def test_translate_all_narrations_prompt_contains_all_segments():
    """The batched prompt should include all narrations with correct delimiters."""
    translator = NarrationTranslator()
    narrations = ["Narration one.", "Narration two."]

    with patch("research_viz.translation.translator.call_openrouter",
               return_value=_mock_openrouter_response(
                   "=== SEGMENT 1 ===\nUno.\n\n=== SEGMENT 2 ===\nDos.")) as mock_call:
        translator.translate_all_narrations(narrations, SPANISH)

    # Verify the prompt sent to LLM contains both segments
    call_args = mock_call.call_args
    messages = call_args[0][0]
    user_content = messages[1]["content"]
    assert "=== SEGMENT 1 ===" in user_content
    assert "=== SEGMENT 2 ===" in user_content
    assert "Narration one." in user_content
    assert "Narration two." in user_content


def test_translate_display_texts_deduplicates():
    """translate_display_texts should deduplicate inputs."""
    translator = NarrationTranslator()
    response = "1. Gradiente\n2. Función de pérdida"

    with patch("research_viz.translation.translator.call_openrouter",
               return_value=_mock_openrouter_response(response)):
        result = translator.translate_display_texts(
            ["Gradient", "Loss Function", "Gradient", "Gradient"],  # duplicates
            SPANISH
        )

    # Should have translations for both unique texts
    assert "Gradient" in result
    assert "Loss Function" in result
    assert result["Gradient"] == "Gradiente"
