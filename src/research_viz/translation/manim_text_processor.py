"""Post-process Manim code to replace Text() strings with translations."""

import re
from typing import List, Dict, Tuple
from research_viz.schemas.language_schemas import LanguageConfig


class ManimTextProcessor:
    """Extract and replace Text() strings in Manim code for translation."""

    # Matches standalone Text("...") or Text('...'), NOT MarkupText/BulletedText etc.
    _TEXT_PATTERN = re.compile(r'(?<!\w)Text\(\s*(["\'])(.+?)\1')
    _FONT_SIZE_PATTERN = re.compile(r'font_size=(\d+)')

    def _find_text_calls(self, code: str) -> List[Tuple[int, int]]:
        """Find start/end positions of standalone Text() calls with balanced parens."""
        results = []
        i = 0
        while i < len(code):
            idx = code.find('Text(', i)
            if idx == -1:
                break
            # Skip if preceded by a word character (e.g., MarkupText, BulletedText)
            if idx > 0 and (code[idx - 1].isalnum() or code[idx - 1] == '_'):
                i = idx + 5
                continue
            # Find matching closing paren via depth counting
            depth = 1
            j = idx + 5  # after 'Text('
            while j < len(code) and depth > 0:
                if code[j] == '(':
                    depth += 1
                elif code[j] == ')':
                    depth -= 1
                j += 1
            if depth == 0:
                results.append((idx, j))
            i = j
        return results

    def extract_text_strings(self, code: str) -> List[str]:
        """Extract all string content from Text() calls in Manim code."""
        return [m.group(2) for m in self._TEXT_PATTERN.finditer(code)]

    def translate_code_texts(
        self,
        code: str,
        translations: Dict[str, str],
        lang_config: LanguageConfig
    ) -> str:
        """
        Replace Text() string contents with translations and inject font params.

        - Replaces Text("english") with Text("translated")
        - Leaves MathTex(r"...") untouched
        - For non-Latin scripts: injects font= param into Text() calls
        - For CJK: reduces font_size within Text() calls only
        """
        def _replace_text_call(match: re.Match) -> str:
            quote = match.group(1)
            original = match.group(2)
            translated = translations.get(original, original)
            return f'Text({quote}{translated}{quote}'

        result = self._TEXT_PATTERN.sub(_replace_text_call, code)

        # Inject font parameter and reduce CJK font size within Text() calls
        if lang_config.font or lang_config.script == "cjk":
            calls = self._find_text_calls(result)
            # Process in reverse order to preserve string offsets
            for start, end in reversed(calls):
                text_call = result[start:end]

                # CJK font_size reduction (scoped to this Text() call only)
                if lang_config.script == "cjk":
                    def _reduce_font_size(m: re.Match) -> str:
                        size = int(m.group(1))
                        return f'font_size={max(20, int(size * 0.875))}'
                    text_call = self._FONT_SIZE_PATTERN.sub(_reduce_font_size, text_call)

                # Font injection (only if not already present)
                if lang_config.font and 'font=' not in text_call:
                    last_paren = text_call.rfind(')')
                    text_call = text_call[:last_paren] + f', font="{lang_config.font}"' + text_call[last_paren:]

                result = result[:start] + text_call + result[end:]

        return result
