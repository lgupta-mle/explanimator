"""Tests for language schemas."""

from research_viz.schemas.language_schemas import LanguageConfig, SUPPORTED_LANGUAGES


def test_all_expected_languages_present():
    expected = {"en", "es", "fr", "de", "ja", "zh", "ko", "hi", "ar", "ru", "pt"}
    assert set(SUPPORTED_LANGUAGES.keys()) == expected


def test_english_config():
    en = SUPPORTED_LANGUAGES["en"]
    assert en.name == "English"
    assert en.script == "latin"
    assert en.rtl is False
    assert en.font is None


def test_cjk_languages_have_fonts():
    for code in ("ja", "zh", "ko"):
        lang = SUPPORTED_LANGUAGES[code]
        assert lang.script == "cjk"
        assert lang.font is not None
        assert "Noto Sans" in lang.font


def test_arabic_is_rtl():
    ar = SUPPORTED_LANGUAGES["ar"]
    assert ar.rtl is True
    assert ar.script == "arabic"
    assert ar.font is not None


def test_hindi_has_devanagari():
    hi = SUPPORTED_LANGUAGES["hi"]
    assert hi.script == "devanagari"
    assert hi.font == "Noto Sans Devanagari"


def test_latin_languages_have_no_font():
    for code in ("en", "es", "fr", "de", "pt"):
        assert SUPPORTED_LANGUAGES[code].font is None
        assert SUPPORTED_LANGUAGES[code].script == "latin"


def test_language_config_model():
    config = LanguageConfig(code="test", name="Test", script="test", rtl=False)
    assert config.font is None
