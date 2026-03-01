"""LLM-based translation for narration and display texts."""

from typing import List, Dict
from research_viz.schemas.language_schemas import LanguageConfig
from research_viz.utils.llm_utils import call_openrouter

TRANSLATION_MODEL = "deepseek/deepseek-v3.2"


class NarrationTranslator:
    """Translates narration scripts and display texts using LLM."""

    def translate_narration(self, narration: str, target_lang: LanguageConfig) -> str:
        """Translate a narration script while preserving math terms and tone."""
        messages = [
            {
                "role": "system",
                "content": (
                    f"You are a professional translator specializing in educational content. "
                    f"Translate to {target_lang.name}. Maintain the conversational 3Blue1Brown tone. "
                    f"Keep ALL math terms, LaTeX expressions, variable names, and formula references in English. "
                    f"Adapt idioms naturally to the target language. "
                    f"Output ONLY the translated text, no explanations."
                )
            },
            {"role": "user", "content": narration}
        ]

        response = call_openrouter(messages, model_name=TRANSLATION_MODEL)

        if "choices" in response and len(response["choices"]) > 0:
            return response["choices"][0]["message"]["content"]
        return narration  # fallback to original

    def translate_display_texts(self, texts: List[str], target_lang: LanguageConfig) -> Dict[str, str]:
        """Batch translate short display labels. Returns original -> translated mapping."""
        if not texts:
            return {}

        # Deduplicate (order-preserving)
        unique_texts = list(dict.fromkeys(texts))

        numbered_list = "\n".join(f"{i+1}. {t}" for i, t in enumerate(unique_texts))

        messages = [
            {
                "role": "system",
                "content": (
                    f"You are a translator. Translate each numbered line to {target_lang.name}. "
                    f"Keep math symbols, LaTeX, and variable names in English. "
                    f"Output ONLY the numbered translations in the same format, no explanations."
                )
            },
            {"role": "user", "content": numbered_list}
        ]

        response = call_openrouter(messages, model_name=TRANSLATION_MODEL)

        translations = {}
        if "choices" in response and len(response["choices"]) > 0:
            content = response["choices"][0]["message"]["content"]
            lines = content.strip().split("\n")
            for i, line in enumerate(lines):
                # Strip numbering (e.g., "1. translated text")
                parts = line.split(". ", 1)
                translated = parts[1] if len(parts) > 1 else line
                if i < len(unique_texts):
                    translations[unique_texts[i]] = translated.strip()

        # Fill in any missing translations with originals
        for text in unique_texts:
            if text not in translations:
                translations[text] = text

        return translations
