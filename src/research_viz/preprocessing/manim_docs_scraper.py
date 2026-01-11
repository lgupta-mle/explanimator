"""
Scrape Manim Community documentation from https://docs.manim.community/en/stable/

Extracts documentation pages, code examples, API references, and metadata.
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
import json
import os
import time
from pathlib import Path
import re
from research_viz.schemas.manim_docs_schemas import (
    DocPage, CodeExample, MethodSignature
)


class ManimDocsScraper:
    """Scrapes Manim Community documentation with metadata preservation."""

    def __init__(
        self,
        base_url: str = "https://docs.manim.community/en/stable/",
        output_dir: str = "data/manim_docs/raw",
        delay_seconds: float = 0.5
    ):
        """
        Args:
            base_url: Base URL for Manim documentation
            output_dir: Directory to save scraped pages
            delay_seconds: Delay between requests to be polite
        """
        self.base_url = base_url.rstrip('/')
        self.output_dir = output_dir
        self.delay_seconds = delay_seconds
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ManimRAGBot/1.0 (Educational Research Project)'
        })

    def scrape_all(self) -> Dict[str, List[DocPage]]:
        """
        Scrape all documentation sections.

        Returns:
            Dictionary mapping section names to lists of DocPage objects
        """
        sections = {
            'api_reference': f'{self.base_url}/reference.html',
            'tutorials': f'{self.base_url}/tutorials/index.html',
            'guides': f'{self.base_url}/guides/index.html',
            'reference_manual': f'{self.base_url}/reference_index.html'
        }

        results = {}
        for section_name, section_url in sections.items():
            print(f"Scraping section: {section_name}")
            results[section_name] = self.scrape_section(section_name, section_url)
            print(f"  Scraped {len(results[section_name])} pages")

        return results

    def scrape_section(self, section_name: str, section_url: str) -> List[DocPage]:
        """
        Scrape a specific documentation section.

        Args:
            section_name: Name of the section
            section_url: Starting URL for the section

        Returns:
            List of DocPage objects
        """
        pages = []
        visited_urls = set()

        section_dir = os.path.join(self.output_dir, section_name)
        os.makedirs(section_dir, exist_ok=True)

        urls_to_visit = [section_url]

        while urls_to_visit:
            url = urls_to_visit.pop(0)

            if url in visited_urls:
                continue

            if not url.startswith(self.base_url):
                continue

            visited_urls.add(url)

            try:
                doc_page = self.parse_page(url, section_name)
                if doc_page:
                    pages.append(doc_page)

                    filename = self._url_to_filename(url)
                    filepath = os.path.join(section_dir, filename)
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(doc_page.model_dump(), f, indent=2)

                    if section_name == 'api_reference':
                        soup = BeautifulSoup(
                            self.session.get(url).content,
                            'html.parser'
                        )
                        for link in soup.find_all('a', href=True):
                            href = link['href']
                            if href.startswith('reference/'):
                                full_url = f"{self.base_url}/{href}"
                                if full_url not in visited_urls:
                                    urls_to_visit.append(full_url)

                time.sleep(self.delay_seconds)

            except Exception as e:
                print(f"  Error scraping {url}: {e}")
                continue

        return pages

    def parse_page(self, url: str, section: str) -> Optional[DocPage]:
        """
        Parse a single documentation page.

        Args:
            url: URL of the page
            section: Section name

        Returns:
            DocPage object or None if parsing fails
        """
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
        except Exception as e:
            print(f"    Failed to fetch {url}: {e}")
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        title = self._extract_title(soup)
        breadcrumb = self._extract_breadcrumb(soup)
        content = self._extract_content(soup)
        code_examples = self._extract_code_examples(soup)
        method_signatures = self._extract_method_signatures(soup)
        related_classes = self._extract_related_classes(content)
        tags = self._extract_tags(content, title)

        return DocPage(
            url=url,
            title=title,
            section=section,
            breadcrumb=breadcrumb,
            content=content,
            code_examples=code_examples,
            method_signatures=method_signatures,
            related_classes=related_classes,
            tags=tags
        )

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract page title."""
        title_tag = soup.find('h1')
        if title_tag:
            return title_tag.get_text(strip=True)

        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text(strip=True)

        return "Untitled"

    def _extract_breadcrumb(self, soup: BeautifulSoup) -> List[str]:
        """Extract breadcrumb navigation."""
        breadcrumb = []

        breadcrumb_nav = soup.find('nav', class_='breadcrumb')
        if breadcrumb_nav:
            links = breadcrumb_nav.find_all('a')
            for link in links:
                breadcrumb.append(link.get_text(strip=True))

        breadcrumb_div = soup.find('div', class_='related')
        if breadcrumb_div:
            links = breadcrumb_div.find_all('a')
            for link in links:
                text = link.get_text(strip=True)
                if text and text not in ['next', 'previous', 'index', 'modules']:
                    breadcrumb.append(text)

        return breadcrumb

    def _extract_content(self, soup: BeautifulSoup) -> str:
        """Extract main content text."""
        content_parts = []

        main_content = soup.find('div', class_='body')
        if not main_content:
            main_content = soup.find('div', role='main')
        if not main_content:
            main_content = soup.find('article')

        if main_content:
            for element in main_content.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'li', 'dt', 'dd']):
                text = element.get_text(strip=True)
                if text:
                    content_parts.append(text)

        return '\n\n'.join(content_parts)

    def _extract_code_examples(self, soup: BeautifulSoup) -> List[CodeExample]:
        """Extract code examples with surrounding context."""
        code_examples = []

        code_blocks = soup.find_all('pre')

        for block in code_blocks:
            code_elem = block.find('code')
            if not code_elem:
                code_text = block.get_text(strip=True)
            else:
                code_text = code_elem.get_text(strip=True)

            if len(code_text) < 10:
                continue

            context = ""
            prev_sibling = block.find_previous_sibling(['p', 'h2', 'h3', 'h4'])
            if prev_sibling:
                context = prev_sibling.get_text(strip=True)

            language = "python"
            class_attr = code_elem.get('class', []) if code_elem else []
            for cls in class_attr:
                if cls.startswith('language-'):
                    language = cls.replace('language-', '')
                elif cls in ['python', 'bash', 'console', 'text']:
                    language = cls

            output_desc = None
            next_sibling = block.find_next_sibling('p')
            if next_sibling:
                next_text = next_sibling.get_text(strip=True)
                if 'output' in next_text.lower() or 'result' in next_text.lower():
                    output_desc = next_text

            code_examples.append(CodeExample(
                code=code_text,
                language=language,
                context=context,
                output_description=output_desc
            ))

        return code_examples

    def _extract_method_signatures(self, soup: BeautifulSoup) -> List[MethodSignature]:
        """Extract method/function signatures from API docs."""
        signatures = []

        dt_elements = soup.find_all('dt', class_=['sig', 'method', 'function', 'class'])

        for dt in dt_elements:
            sig_name = dt.find('span', class_='sig-name')
            if not sig_name:
                continue

            name = sig_name.get_text(strip=True)

            class_name = None
            class_elem = dt.find('span', class_='sig-prename')
            if class_elem:
                class_name = class_elem.get_text(strip=True).rstrip('.')

            parameters = []
            param_list = dt.find('em', class_='sig-param')
            if param_list:
                parameters = [p.strip() for p in param_list.get_text().split(',')]

            return_type = None
            return_elem = dt.find('span', class_='sig-return')
            if return_elem:
                return_type = return_elem.get_text(strip=True)

            description = ""
            dd = dt.find_next_sibling('dd')
            if dd:
                desc_p = dd.find('p')
                if desc_p:
                    description = desc_p.get_text(strip=True)

            signatures.append(MethodSignature(
                name=name,
                class_name=class_name,
                parameters=parameters,
                return_type=return_type,
                description=description
            ))

        return signatures

    def _extract_related_classes(self, content: str) -> List[str]:
        """Extract Manim class names mentioned in content."""
        manim_classes = set()

        common_classes = [
            'Scene', 'Circle', 'Square', 'Rectangle', 'Text', 'MathTex', 'Tex',
            'Arrow', 'Line', 'Dot', 'VGroup', 'VMobject', 'Mobject',
            'Create', 'Write', 'FadeIn', 'FadeOut', 'Transform', 'ReplacementTransform',
            'AnimationGroup', 'Succession', 'LaggedStart',
            'MoveTo', 'Shift', 'Rotate', 'ScaleInPlace', 'GrowFromCenter',
            'Indicate', 'Flash', 'Circumscribe', 'ShowPassingFlash',
            'Matrix', 'Axes', 'NumberPlane', 'Graph', 'ParametricFunction',
            'ThreeDScene', 'Camera', 'MovingCamera'
        ]

        for cls in common_classes:
            if cls in content:
                manim_classes.add(cls)

        return list(manim_classes)

    def _extract_tags(self, content: str, title: str) -> List[str]:
        """Extract topic tags based on content."""
        tags = set()

        content_lower = content.lower() + " " + title.lower()

        tag_keywords = {
            'animation': ['animate', 'animation', 'play', 'run_time'],
            'geometry': ['circle', 'square', 'rectangle', 'polygon', 'shape'],
            'text': ['text', 'tex', 'latex', 'mathtex', 'paragraph'],
            'math': ['equation', 'formula', 'matrix', 'vector', 'mathematical'],
            'graph': ['axes', 'graph', 'plot', 'coordinate', 'function'],
            '3d': ['three', '3d', 'camera', 'perspective', 'depth'],
            'transformation': ['transform', 'morph', 'shift', 'rotate', 'scale'],
            'color': ['color', 'rgb', 'gradient', 'fill', 'stroke'],
            'timing': ['wait', 'duration', 'lag', 'rate', 'speed']
        }

        for tag, keywords in tag_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                tags.add(tag)

        return list(tags)

    def _url_to_filename(self, url: str) -> str:
        """Convert URL to valid filename."""
        filename = url.replace(self.base_url, '').strip('/')
        filename = filename.replace('/', '_').replace('.html', '')
        if not filename:
            filename = 'index'
        return f"{filename}.json"

    def save(self, docs: Dict[str, List[DocPage]]) -> None:
        """Save all documents to disk."""
        for section_name, pages in docs.items():
            section_dir = os.path.join(self.output_dir, section_name)
            os.makedirs(section_dir, exist_ok=True)

            for page in pages:
                filename = self._url_to_filename(page.url)
                filepath = os.path.join(section_dir, filename)
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(page.model_dump(), f, indent=2)

    def load(self) -> Dict[str, List[DocPage]]:
        """Load documents from disk."""
        docs = {}

        for section_name in ['api_reference', 'tutorials', 'guides', 'reference_manual']:
            section_dir = os.path.join(self.output_dir, section_name)
            if not os.path.exists(section_dir):
                continue

            pages = []
            for filename in os.listdir(section_dir):
                if not filename.endswith('.json'):
                    continue

                filepath = os.path.join(section_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    pages.append(DocPage.model_validate(data))

            docs[section_name] = pages

        return docs