"""LLM-based translation for narration and display texts."""

import re
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

    def translate_all_narrations(self, narrations: List[str], target_lang: LanguageConfig) -> List[str]:
        """Batch translate all narration scripts in a single LLM call.

        Args:
            narrations: List of narration scripts (one per segment)
            target_lang: Target language config

        Returns:
            List of translated narrations in the same order
        """
        if not narrations:
            return []

        if len(narrations) == 1:
            return [self.translate_narration(narrations[0], target_lang)]

        # Build a single prompt with numbered, delimited sections
        sections = []
        for i, narration in enumerate(narrations):
            sections.append(f"=== SEGMENT {i+1} ===\n{narration}")
        combined = "\n\n".join(sections)

        messages = [
            {
                "role": "system",
                "content": (
                    f"You are a professional translator specializing in educational content. "
                    f"Translate ALL segments below to {target_lang.name}. "
                    f"Maintain the conversational 3Blue1Brown tone. "
                    f"Keep ALL math terms, LaTeX expressions, variable names, and formula references in English. "
                    f"Adapt idioms naturally to the target language. "
                    f"Output ONLY the translated segments, preserving the exact same delimiter format: "
                    f"'=== SEGMENT N ===' before each translated segment. "
                    f"Do NOT add any explanations or commentary."
                )
            },
            {"role": "user", "content": combined}
        ]

        response = call_openrouter(messages, model_name=TRANSLATION_MODEL)

        if "choices" in response and len(response["choices"]) > 0:
            content = response["choices"][0]["message"]["content"]
            # Parse by delimiter
            parts = re.split(r'===\s*SEGMENT\s+\d+\s*===\s*\n?', content)
            parts = [p.strip() for p in parts if p.strip()]

            if len(parts) == len(narrations):
                return parts

            print(f"  WARNING: Batch translation returned {len(parts)} segments, "
                  f"expected {len(narrations)}. Falling back to individual calls.")

        # Fallback to individual translation
        return [self.translate_narration(n, target_lang) for n in narrations]

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
