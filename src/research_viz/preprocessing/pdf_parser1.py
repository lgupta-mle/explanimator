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
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered


class HybridResearchPaperParser:
    """
    Hybrid parser combining:
    - GROBID: Clean section structure, methodology extraction, table metadata
    - Marker: Image extraction only (optimized - skips text processing)
    
    This approach is optimized to avoid duplicate text processing:
    - GROBID handles all text/section extraction
    - Marker only extracts images (faster than full processing)
    """
    
    def __init__(
        self,
        grobid_url: str = "http://localhost:8070",
        output_base_dir: str = "./output_grobid_marker",
        timeout: int = 180
    ):
        self.grobid_url = grobid_url.rstrip("/")
        self.timeout = timeout
        self.output_base_dir = Path(output_base_dir)
        self.output_base_dir.mkdir(parents=True, exist_ok=True)
        
        self.methodology_keywords = [
            'method', 'methods', 'methodology', 'methodologies',
            'materials and methods', 'experimental setup', 'experimental design',
            'approach', 'experimental', 'implementation', 'system design',
            'experimental procedure', 'procedure', 'experimental methods', 'technique',
            'model architecture', 'architecture', 'model', 'framework'
        ]
        
        # Load Marker models once
        print("Loading Marker models for image extraction...")
        self.marker_models = create_model_dict()
        print("Marker models loaded!")
    
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
            methodology = self._extract_methodology_from_tei(root)
            grobid_figures = self._extract_figure_metadata_from_tei(root)
            grobid_tables = self._extract_table_metadata_from_tei(root)
            
            # Step 2: Extract images with Marker (optimized - images only)
            print(f"  [2/2] Extracting images with Marker...")
            converter = PdfConverter(
                artifact_dict=self.marker_models,
                config={
                    "use_llm": False,
                    "paginate_output": False,  # Skip pagination
                    "extract_images": True      # Ensure images are extracted
                }
            )
            rendered = converter(str(pdf_path))
            
            # Extract only images, skip text processing
            marker_images = rendered.images if hasattr(rendered, 'images') else {}
            out_meta = getattr(rendered, "metadata", {})
            
            # Save Marker images
            saved_images = self._save_marker_images(marker_images, images_dir, paper_name)
            
            # Merge GROBID figure metadata with Marker images
            merged_figures = self._merge_figure_data(grobid_figures, saved_images)
            
            # Use GROBID table metadata (no need to extract from Marker markdown)
            merged_tables = self._save_table_metadata(grobid_tables, tables_dir, paper_name)
            
            # Prepare results
            results = {
                'paper_name': paper_name,
                'source_file': str(pdf_path),
                'output_directory': str(paper_output_dir),
                'tei_file': str(tei_path),
                'methodology': methodology,
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
    
    def _extract_methodology_from_tei(self, root: ET.Element) -> Dict[str, Any]:
        """Extract methodology section from GROBID TEI XML.
        
        GROBID outputs a flat structure where subsections are siblings, not children.
        We use section numbers (e.g., 3, 3.1, 3.2, 3.2.1) to build the hierarchy.
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
        
        # Priority keywords for scoring
        exact_keywords = ['methodology', 'method', 'methods']
        secondary_keywords = ['approach', 'implementation', 'system design', 'experimental design']
        
        all_divs = body.findall('./tei:div', ns)
        candidates = []
        
        # Find all matching sections and score them
        for idx, div in enumerate(all_divs):
            title = get_section_title(div)
            section_num = get_section_number(div)
            title_lower = title.lower().strip()
            
            score = 0
            
            # Exact match with "methodology" or "method" = highest priority
            if title_lower in exact_keywords or title_lower == 'methodology':
                score = 100
            # Title is exactly one of the exact keywords
            elif any(title_lower == keyword for keyword in exact_keywords):
                score = 90
            # Title contains exact keyword as a standalone word
            elif any(f' {keyword} ' in f' {title_lower} ' or title_lower.startswith(keyword + ' ') or title_lower.endswith(' ' + keyword) for keyword in exact_keywords):
                score = 80
            # Secondary keywords
            elif any(keyword in title_lower for keyword in secondary_keywords):
                score = 50
            # Any other methodology keyword
            elif any(keyword in title_lower for keyword in self.methodology_keywords):
                score = 30
            
            if score > 0:
                candidates.append((score, idx, div, title, section_num))
        
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
    
    def _save_marker_images(self, images: Dict[str, Any], images_dir: Path, paper_name: str) -> List[Dict[str, Any]]:
        """Save images extracted by Marker (matches pdf_parser2.py logic)."""
        saved_images = []
        
        for img_name, img_data in images.items():
            try:
                # Marker returns images as PIL Image objects
                safe_img_name = str(img_name).replace("/", "_").replace(os.sep, "_")
                image_filename = f"{paper_name}_{safe_img_name}"
                if not image_filename.endswith(('.png', '.jpg', '.jpeg')):
                    image_filename += '.png'
                
                image_path = images_dir / image_filename
                
                # Save the image
                img_data.save(image_path)
                
                # Get image info
                width, height = img_data.size
                
                saved_images.append({
                    'figure_number': len(saved_images) + 1,
                    'filename': img_name,
                    'saved_as': str(image_path),
                    'width': width,
                    'height': height,
                    'format': img_data.format or 'PNG',
                    'source': 'marker',
                    'status': 'saved'
                })
            except Exception as e:
                saved_images.append({
                    'filename': img_name,
                    'source': 'marker',
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
    
    def _save_table_metadata(self, grobid_tables: List[Dict], tables_dir: Path, paper_name: str) -> List[Dict]:
        """Save table metadata from GROBID (no Marker table extraction needed)."""
        saved_tables = []
        
        for table in grobid_tables:
            table_num = table.get('table_number')
            caption = table.get('caption', '')
            
            # Save caption to file for reference
            caption_file = tables_dir / f"{paper_name}_table_{table_num}_caption.txt"
            with open(caption_file, 'w', encoding='utf-8') as f:
                f.write(caption)
            
            saved_tables.append({
                'table_number': table_num,
                'caption': caption,
                'caption_file': str(caption_file),
                'source': 'grobid',
                'status': 'metadata_only'
            })
        
        return saved_tables
    
    def _get_namespace(self, root: ET.Element) -> str:
        """Extract namespace from TEI root element."""
        if root.tag.startswith('{'):
            return root.tag.split('}')[0].strip('{')
        return 'http://www.tei-c.org/ns/1.0'
