"""
Hybrid PDF Parser: GROBID (text/sections) + Marker (images/tables)
Combines the best of both tools for research paper extraction.
"""
import os
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
import requests
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
from datalab_sdk import DatalabClient, ConvertOptions

load_dotenv()

class HybridResearchPaperParser:
    """
    Hybrid parser combining:
    - GROBID: Clean section structure, methodology extraction, figure/table metadata
    - Marker: Image and table extraction from PDF
    
    This approach leverages the strengths of both tools:
    - GROBID handles text/section extraction and provides captions
    - Marker extracts actual images and tables from the PDF
    """
    
    def __init__(
        self,
        grobid_url: str = "http://localhost:8070",
        output_base_dir: str = "./output_grobid_marker",
        timeout: int = 180,
        datalab_api_key: bool = True
    ):
        self.grobid_url = grobid_url.rstrip("/")
        self.timeout = timeout
        self.output_base_dir = Path(output_base_dir)
        self.output_base_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Datalab client for Marker API
        print("Initializing Datalab Marker client...")
        if datalab_api_key:
            DATALAB_API_KEY = os.getenv("DATALAB_API_KEY")
            if not DATALAB_API_KEY:
                raise ValueError("DATALAB_API_KEY not found in environment. Please set it in .env file")
            self.datalab_client = DatalabClient(api_key=DATALAB_API_KEY)
        else:
            self.datalab_client = DatalabClient()  # Will use default auth
        print("✓ Datalab client initialized")
        
        self.methodology_keywords = [
            'method', 'methods', 'methodology', 'methodologies',
            'materials and methods', 'experimental setup', 'experimental design',
            'approach', 'experimental', 'implementation', 'system design',
            'experimental procedure', 'procedure', 'experimental methods', 'technique',
            'model architecture', 'architecture', 'model', 'framework'
        ]
        
        self.related_works_keywords = [
            'related work', 'related works', 'background', 'preliminaries',
            'literature review', 'prior work', 'previous work'
        ]
        
        self.introduction_keywords = [
            'introduction', 'intro', 'overview', 'motivation'
        ]
    
    def parse_directory(self, directory_path: str) -> List[Dict[str, Any]]:
        """Parse all PDFs in a directory."""
        directory = Path(directory_path)
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        pdf_files = sorted(directory.glob("*.pdf"))
        if not pdf_files:
            print(f"No PDF files found in {directory}")
            return []
        
        print(f"\nFound {len(pdf_files)} PDF files to process")
        print("=" * 70)
        
        results = []
        for pdf_file in pdf_files:
            try:
                result = self.parse_paper(str(pdf_file))
                results.append(result)
            except Exception as e:
                error_result = {
                    'paper_name': pdf_file.stem,
                    'source_file': str(pdf_file),
                    'status': 'error',
                    'error': str(e)
                }
                results.append(error_result)
                print(f"✗ Error processing {pdf_file.name}: {str(e)}")
        
        # Save summary
        summary_file = self.output_base_dir / "extraction_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump({
                'total_papers': len(pdf_files),
                'successful': sum(1 for r in results if r.get('status') == 'success'),
                'failed': sum(1 for r in results if r.get('status') == 'error'),
                'results': results
            }, f, indent=2, ensure_ascii=False)
        
        print("\n" + "=" * 70)
        print(f"Processing complete! Summary saved to: {summary_file}")
        return results
    
    def parse_paper(self, pdf_path: str, paper_name: Optional[str] = None) -> Dict[str, Any]:
        """Parse a single PDF using hybrid approach."""
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        
        if paper_name is None:
            paper_name = pdf_path.stem
        
        print(f"\nProcessing: {paper_name}")
        
        # Create output directories
        paper_output_dir = self.output_base_dir / paper_name
        images_dir = paper_output_dir / "images"
        tables_dir = paper_output_dir / "tables"
        paper_output_dir.mkdir(parents=True, exist_ok=True)
        images_dir.mkdir(exist_ok=True)
        tables_dir.mkdir(exist_ok=True)
        
        try:
            # Step 1: Extract text and sections with GROBID
            print(f"  [1/2] Extracting text and sections with GROBID...")
            tei_xml = self._process_with_grobid(str(pdf_path))
            tei_path = paper_output_dir / f"{paper_name}.tei.xml"
            with open(tei_path, 'w', encoding='utf-8') as f:
                f.write(tei_xml)
            
            root = ET.fromstring(tei_xml)
            introduction = self._extract_section_from_tei(root, self.introduction_keywords, 'introduction')
            methodology = self._extract_section_from_tei(root, self.methodology_keywords, 'methodology')
            related_works = self._extract_section_from_tei(root, self.related_works_keywords, 'related_works')
            grobid_figures = self._extract_figure_metadata_from_tei(root)
            grobid_tables = self._extract_table_metadata_from_tei(root)
            
            # Step 2: Extract images and tables with Marker API
            print(f"  [2/2] Extracting images and tables with Marker API...")
            
            # Configure conversion options
            options = ConvertOptions(
                output_format="markdown",
                mode="accurate",
                paginate=False
            )
            
            # Convert PDF using Datalab API
            result = self.datalab_client.convert(str(pdf_path), options=options)
            
            # Extract markdown and images
            full_text = result.markdown
            marker_images = result.images if hasattr(result, 'images') else {}
            out_meta = getattr(result, "metadata", {})
            
            # Save Marker images
            saved_images = self._save_marker_images(marker_images, images_dir, paper_name)
            
            # Merge GROBID figure metadata with Marker images
            merged_figures = self._merge_figure_data(grobid_figures, saved_images)
            
            # Extract tables from Marker markdown
            marker_tables = self._extract_tables_from_markdown(full_text, tables_dir, paper_name)
            
            # Merge GROBID table metadata with Marker tables
            merged_tables = self._merge_table_data(grobid_tables, marker_tables)
            
            # Prepare results
            results = {
                'paper_name': paper_name,
                'source_file': str(pdf_path),
                'output_directory': str(paper_output_dir),
                'tei_file': str(tei_path),
                'introduction': introduction,
                'methodology': methodology,
                'related_works': related_works,
                'figures': {
                    'count': len(merged_figures),
                    'items': merged_figures
                },
                'tables': {
                    'count': len(merged_tables),
                    'items': merged_tables
                },
                'metadata': {
                    'total_pages': out_meta.get('pages', 0),
                    'languages': out_meta.get('languages', [])
                },
                'status': 'success'
            }
            
            # Save results
            results_file = paper_output_dir / f"{paper_name}_extraction_results.json"
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"  ✓ Results saved to: {results_file}")
            
            return results
            
        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'paper_name': paper_name,
                'source_file': str(pdf_path),
                'status': 'error',
                'error': str(e)
            }
    
    def _process_with_grobid(self, pdf_path: str) -> str:
        """Send PDF to GROBID and get TEI XML."""
        url = f"{self.grobid_url}/api/processFulltextDocument"
        with open(pdf_path, 'rb') as f:
            files = {'input': f}
            data = {
                'consolidateHeader': 1,
                'consolidateCitations': 1,
                'teiCoordinates': 'true',
                'segmentSentences': 1,
                'generateIDs': 1
            }
            resp = requests.post(url, files=files, data=data, timeout=self.timeout)
        
        if resp.status_code != 200:
            raise RuntimeError(f"GROBID error {resp.status_code}: {resp.text[:500]}")
        return resp.text
    
    def _extract_section_from_tei(self, root: ET.Element, keywords: List[str], section_type: str) -> Dict[str, Any]:
        """Extract a section (methodology, related works, etc.) from GROBID TEI XML.
        
        GROBID outputs a flat structure where subsections are siblings, not children.
        We use section numbers (e.g., 3, 3.1, 3.2, 3.2.1) to build the hierarchy.
        
        Args:
            root: TEI XML root element
            keywords: List of keywords to match in section titles
            section_type: Type of section being extracted (for logging)
        """
        ns = {'tei': self._get_namespace(root)}
        body = root.find('.//tei:text/tei:body', ns)
        
        if body is None:
            return {'found': False, 'title': None, 'text': '', 'subsections': []}
        
        def get_section_title(div: ET.Element) -> str:
            head = div.find('tei:head', ns)
            if head is not None:
                return ''.join(head.itertext()).strip()
            return ''
        
        def get_section_number(div: ET.Element) -> str:
            """Extract section number from head element."""
            head = div.find('tei:head', ns)
            if head is not None:
                n_attr = head.get('n', '').strip()
                # Normalize: remove trailing dot for consistency
                return n_attr.rstrip('.')
            return ''
        
        def get_section_text(div: ET.Element) -> str:
            """Extract text from direct paragraphs only."""
            paras = []
            for p in div.findall('./tei:p', ns):
                txt = ''.join(p.itertext()).strip()
                if txt:
                    paras.append(txt)
            return '\n\n'.join(paras)
        
        def build_hierarchy(all_divs, parent_num):
            """Build hierarchical structure from flat list based on section numbers."""
            subs = []
            i = 0
            while i < len(all_divs):
                div, num = all_divs[i]
                
                # Check if this is a direct child (e.g., 3.1 is child of 3, 3.2.1 is child of 3.2)
                if num.startswith(parent_num + '.'):
                    # Count dots to determine if it's a direct child
                    parent_dots = parent_num.count('.')
                    current_dots = num.count('.')
                    
                    if current_dots == parent_dots + 1:
                        # This is a direct child
                        title = get_section_title(div)
                        direct_text = get_section_text(div)
                        
                        # Find nested subsections
                        nested_subs = build_hierarchy(all_divs[i+1:], num)
                        
                        sub_data = {
                            'title': title,
                            'text': direct_text,
                            'level': current_dots,
                            'section_number': num
                        }
                        if nested_subs:
                            sub_data['subsections'] = nested_subs
                        subs.append(sub_data)
                
                i += 1
            
            return subs
        
        all_divs = body.findall('./tei:div', ns)
        candidates = []
        
        # Find all matching sections - check if title CONTAINS any keyword
        for idx, div in enumerate(all_divs):
            title = get_section_title(div)
            section_num = get_section_number(div)
            title_lower = title.lower().strip()
            
            # Check if title contains any of the keywords
            for keyword in keywords:
                if keyword in title_lower:
                    # Score based on how well it matches
                    score = 100 if title_lower == keyword else 80
                    candidates.append((score, idx, div, title, section_num))
                    break  # Only count first match
        
        if not candidates:
            return {'found': False, 'title': None, 'text': '', 'subsections': []}
        
        # Pick the best candidate (highest score)
        candidates.sort(key=lambda x: x[0], reverse=True)
        score, idx, div, title, section_num = candidates[0]
        
        # Get all remaining divs to check for subsections
        remaining_divs = [(d, get_section_number(d)) for d in all_divs[idx+1:]]
        
        # Build hierarchy from flat structure
        subsections = build_hierarchy(remaining_divs, section_num)
        
        # Get full text by collecting this section + all subsections
        all_text_parts = [get_section_text(div)]
        for d, num in remaining_divs:
            if num.startswith(section_num + '.'):
                text = get_section_text(d)
                if text:
                    all_text_parts.append(text)
        
        return {
            'found': True,
            'section_type': section_type,
            'title': title,
            'section_number': section_num,
            'text': get_section_text(div),
            'subsections': subsections,
            'full_text': '\n\n'.join(all_text_parts)
        }
    
    def _extract_figure_metadata_from_tei(self, root: ET.Element) -> List[Dict[str, Any]]:
        """Extract figure metadata from GROBID TEI."""
        ns = {'tei': self._get_namespace(root)}
        figures = []
        
        for idx, fig in enumerate(root.findall('.//tei:figure', ns), 1):
            caption_el = fig.find('tei:figDesc', ns) or fig.find('tei:head', ns)
            caption = ''.join(caption_el.itertext()).strip() if caption_el is not None else ''
            
            figures.append({
                'figure_number': idx,
                'caption': caption,
                'source': 'grobid'
            })
        
        return figures
    
    def _extract_table_metadata_from_tei(self, root: ET.Element) -> List[Dict[str, Any]]:
        """Extract table metadata from GROBID TEI."""
        ns = {'tei': self._get_namespace(root)}
        tables = []
        
        for idx, tbl in enumerate(root.findall('.//tei:table', ns), 1):
            head = tbl.find('tei:head', ns)
            caption = ''.join(head.itertext()).strip() if head is not None else ''
            
            tables.append({
                'table_number': idx,
                'caption': caption,
                'source': 'grobid'
            })
        
        return tables
    
    def _save_marker_images(self, marker_images: Dict, images_dir: Path, paper_name: str) -> List[Dict]:
        """Save images extracted by Marker API."""
        from PIL import Image
        import io
        
        saved_images = []
        
        for img_name, img_data in marker_images.items():
            try:
                # img_data is bytes from API
                image_filename = img_name
                if not any(image_filename.endswith(ext) for ext in ['.png', '.jpg', '.jpeg']):
                    image_filename = f"{paper_name}_{img_name}.png"
                
                image_path = images_dir / image_filename
                
                # Save image bytes to file
                with open(image_path, 'wb') as f:
                    f.write(img_data)
                
                # Get image info using PIL
                img = Image.open(io.BytesIO(img_data))
                width, height = img.size
                img_format = img.format or 'PNG'
                
                saved_images.append({
                    'figure_number': len(saved_images) + 1,
                    'filename': img_name,
                    'saved_as': str(image_path),
                    'width': width,
                    'height': height,
                    'format': img_format,
                    'source': 'marker_api',
                    'status': 'saved'
                })
            except Exception as e:
                saved_images.append({
                    'filename': img_name,
                    'source': 'marker_api',
                    'status': 'error',
                    'error': str(e)
                })
        
        return saved_images
    
    def _merge_figure_data(self, grobid_figures: List[Dict], marker_images: List[Dict]) -> List[Dict]:
        """Merge GROBID figure metadata with Marker extracted images."""
        merged = []
        
        # Start with Marker images (they have the actual files)
        for img in marker_images:
            # Try to find matching GROBID caption
            fig_num = img.get('figure_number', 0)
            caption = ''
            
            if fig_num <= len(grobid_figures):
                caption = grobid_figures[fig_num - 1].get('caption', '')
            
            merged.append({
                **img,
                'caption': caption if caption else img.get('caption', ''),
                'has_image_file': img.get('status') == 'saved'
            })
        
        # Add any GROBID figures that don't have images
        for idx, gfig in enumerate(grobid_figures, 1):
            if idx > len(marker_images):
                merged.append({
                    'figure_number': idx,
                    'caption': gfig.get('caption', ''),
                    'source': 'grobid',
                    'has_image_file': False,
                    'status': 'metadata_only'
                })
        
        return merged
    
    def _extract_tables_from_markdown(self, markdown_text: str, tables_dir: Path, paper_name: str) -> List[Dict]:
        """Extract tables from Marker markdown output."""
        import re
        
        tables = []
        # Find all markdown tables (lines starting with |)
        table_pattern = r'((?:\|.+\|\n)+)'
        matches = re.finditer(table_pattern, markdown_text)
        
        for idx, match in enumerate(matches, 1):
            table_md = match.group(1).strip()
            
            # Skip if it's just a separator line
            lines = table_md.split('\n')
            if len(lines) < 2:
                continue
            
            # Skip if all lines are separators
            if all('---' in line or '===' in line for line in lines):
                continue
            
            # Save table as markdown file
            table_file = tables_dir / f"{paper_name}_table_{idx}.md"
            with open(table_file, 'w', encoding='utf-8') as f:
                f.write(table_md)
            
            # Parse table to get row/col count
            rows = [line for line in lines if not all(c in '|-:= ' for c in line)]
            cols = len(rows[0].split('|')) - 2 if rows else 0  # -2 for leading/trailing |
            
            tables.append({
                'table_number': idx,
                'file': str(table_file),
                'rows': len(rows),
                'columns': cols,
                'source': 'marker',
                'status': 'extracted'
            })
        
        return tables
    
    def _merge_table_data(self, grobid_tables: List[Dict], marker_tables: List[Dict]) -> List[Dict]:
        """Merge GROBID table metadata with Marker extracted tables."""
        merged = []
        
        # Match by table number
        for marker_table in marker_tables:
            table_num = marker_table.get('table_number')
            caption = ''
            
            # Find matching GROBID caption
            if table_num <= len(grobid_tables):
                caption = grobid_tables[table_num - 1].get('caption', '')
            
            merged.append({
                **marker_table,
                'caption': caption,
                'has_content': marker_table.get('status') == 'extracted'
            })
        
        # Add any GROBID tables that weren't extracted by Marker
        for idx, grobid_table in enumerate(grobid_tables, 1):
            if idx > len(marker_tables):
                merged.append({
                    'table_number': idx,
                    'caption': grobid_table.get('caption', ''),
                    'source': 'grobid',
                    'status': 'metadata_only',
                    'has_content': False
                })
        
        return merged
    
    def _get_namespace(self, root: ET.Element) -> str:
        """Extract namespace from TEI root element."""
        if root.tag.startswith('{'):
            return root.tag.split('}')[0].strip('{')
        return 'http://www.tei-c.org/ns/1.0'
