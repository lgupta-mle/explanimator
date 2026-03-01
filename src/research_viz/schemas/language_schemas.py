"""Language configuration for multilingual support."""

from pydantic import BaseModel
from typing import Optional


class LanguageConfig(BaseModel):
    code: str          # ISO 639-1
    name: str          # Full name
    script: str        # "latin", "cjk", "devanagari", "arabic", "cyrillic"
    rtl: bool          # Right-to-left
    font: Optional[str] = None  # Manim font for Text() objects, None for Latin scripts


SUPPORTED_LANGUAGES = {
    "en": LanguageConfig(code="en", name="English", script="latin", rtl=False, font=None),
    "es": LanguageConfig(code="es", name="Spanish", script="latin", rtl=False, font=None),
    "fr": LanguageConfig(code="fr", name="French", script="latin", rtl=False, font=None),
    "de": LanguageConfig(code="de", name="German", script="latin", rtl=False, font=None),
    "ja": LanguageConfig(code="ja", name="Japanese", script="cjk", rtl=False, font="Noto Sans JP"),
    "zh": LanguageConfig(code="zh", name="Chinese", script="cjk", rtl=False, font="Noto Sans SC"),
    "ko": LanguageConfig(code="ko", name="Korean", script="cjk", rtl=False, font="Noto Sans KR"),
    "hi": LanguageConfig(code="hi", name="Hindi", script="devanagari", rtl=False, font="Noto Sans Devanagari"),
    "ar": LanguageConfig(code="ar", name="Arabic", script="arabic", rtl=True, font="Noto Sans Arabic"),
    "ru": LanguageConfig(code="ru", name="Russian", script="cyrillic", rtl=False, font=None),
    "pt": LanguageConfig(code="pt", name="Portuguese", script="latin", rtl=False, font=None),
}
