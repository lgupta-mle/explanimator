"""Tests for Manim text processor (extraction and replacement)."""

from research_viz.translation.manim_text_processor import ManimTextProcessor
from research_viz.schemas.language_schemas import LanguageConfig


def test_extract_text_strings():
    processor = ManimTextProcessor()
    code = '''
title = Text("Hello World", font_size=36)
label = Text('Another label')
eq = MathTex(r"E=mc^2")
desc = Text("Description here", color=WHITE)
'''
    texts = processor.extract_text_strings(code)
    assert "Hello World" in texts
    assert "Another label" in texts
    assert "Description here" in texts
    assert len(texts) == 3  # MathTex should NOT be extracted


def test_translate_code_texts_basic():
    processor = ManimTextProcessor()
    code = 'title = Text("Hello World")\nlabel = Text("Goodbye")'
    translations = {"Hello World": "Hola Mundo", "Goodbye": "Adiós"}
    lang = LanguageConfig(code="es", name="Spanish", script="latin", rtl=False)

    result = processor.translate_code_texts(code, translations, lang)
    assert 'Text("Hola Mundo")' in result
    assert 'Text("Adiós")' in result


def test_translate_preserves_mathtex():
    processor = ManimTextProcessor()
    code = 'eq = MathTex(r"E=mc^2")\ntitle = Text("Energy")'
    translations = {"Energy": "Energía"}
    lang = LanguageConfig(code="es", name="Spanish", script="latin", rtl=False)

    result = processor.translate_code_texts(code, translations, lang)
    assert 'MathTex(r"E=mc^2")' in result
    assert 'Text("Energía")' in result


def test_font_injection_for_cjk():
    processor = ManimTextProcessor()
    code = 'title = Text("Hello")'
    translations = {"Hello": "こんにちは"}
    lang = LanguageConfig(code="ja", name="Japanese", script="cjk", rtl=False, font="Noto Sans JP")

    result = processor.translate_code_texts(code, translations, lang)
    assert 'font="Noto Sans JP"' in result
    assert "こんにちは" in result


def test_font_not_injected_for_latin():
    processor = ManimTextProcessor()
    code = 'title = Text("Hello")'
    translations = {"Hello": "Hola"}
    lang = LanguageConfig(code="es", name="Spanish", script="latin", rtl=False)

    result = processor.translate_code_texts(code, translations, lang)
    assert "font=" not in result


def test_font_not_duplicated():
    processor = ManimTextProcessor()
    code = 'title = Text("Hello", font="Arial")'
    translations = {"Hello": "こんにちは"}
    lang = LanguageConfig(code="ja", name="Japanese", script="cjk", rtl=False, font="Noto Sans JP")

    result = processor.translate_code_texts(code, translations, lang)
    # Should keep existing font, not add another
    assert result.count("font=") == 1


def test_cjk_font_size_reduction():
    processor = ManimTextProcessor()
    code = 'title = Text("Hello", font_size=32)'
    translations = {"Hello": "こんにちは"}
    lang = LanguageConfig(code="ja", name="Japanese", script="cjk", rtl=False, font="Noto Sans JP")

    result = processor.translate_code_texts(code, translations, lang)
    assert "font_size=28" in result  # 32 * 0.875 = 28


def test_no_translation_keeps_original():
    processor = ManimTextProcessor()
    code = 'title = Text("Untranslated")'
    translations = {}  # empty
    lang = LanguageConfig(code="es", name="Spanish", script="latin", rtl=False)

    result = processor.translate_code_texts(code, translations, lang)
    assert 'Text("Untranslated")' in result


# --- New tests for bug fixes ---

def test_subclass_names_not_matched():
    """MarkupText, BulletedText etc. should NOT be extracted or translated."""
    processor = ManimTextProcessor()
    code = '''
markup = MarkupText("Bold text")
bullet = BulletedText("Item 1")
plain = Text("Plain text")
'''
    texts = processor.extract_text_strings(code)
    assert texts == ["Plain text"]


def test_font_size_scoped_to_text_calls():
    """font_size reduction should only affect Text() calls, not MathTex or config."""
    processor = ManimTextProcessor()
    code = 'eq = MathTex(r"x^2", font_size=32)\ntitle = Text("Hello", font_size=32)'
    translations = {"Hello": "こんにちは"}
    lang = LanguageConfig(code="ja", name="Japanese", script="cjk", rtl=False, font="Noto Sans JP")

    result = processor.translate_code_texts(code, translations, lang)
    # MathTex font_size should be unchanged
    assert 'MathTex(r"x^2", font_size=32)' in result
    # Text font_size should be reduced
    assert "font_size=28" in result


def test_nested_parens_in_text_call():
    """Font injection should handle nested parentheses like color=RED.mix(BLUE, 0.5)."""
    processor = ManimTextProcessor()
    code = 'label = Text("Hello", color=RED.mix(BLUE, 0.5))'
    translations = {"Hello": "こんにちは"}
    lang = LanguageConfig(code="ja", name="Japanese", script="cjk", rtl=False, font="Noto Sans JP")

    result = processor.translate_code_texts(code, translations, lang)
    assert 'font="Noto Sans JP"' in result
    # The nested call should remain intact
    assert "RED.mix(BLUE, 0.5)" in result


def test_multiline_text_call():
    """Text() calls spanning multiple lines should be handled."""
    processor = ManimTextProcessor()
    code = '''title = Text(
    "Hello World",
    font_size=36,
    color=WHITE
)'''
    texts = processor.extract_text_strings(code)
    assert "Hello World" in texts


def test_extract_skips_mathtex_subclasses():
    """Tex, MathTex should not be matched."""
    processor = ManimTextProcessor()
    code = 'eq = Tex(r"x^2")\nmt = MathTex(r"y=mx+b")\nt = Text("label")'
    texts = processor.extract_text_strings(code)
    assert texts == ["label"]
