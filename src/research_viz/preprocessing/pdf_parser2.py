"""
Hybrid PDF Parser: GROBID (text/sections) + PyMuPDF (images)
Combines GROBID's clean section extraction with PyMuPDF's comprehensive image extraction.
"""
import os
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
import requests
import xml.etree.ElementTree as ET
import fitz  # PyMuPDF
from PIL import Image
import io


class GrobidPyMuPDFParser:
    """
    Hybrid parser combining:
    - GROBID: Clean section structure, methodology extraction
    - PyMuPDF: Comprehensive image extraction (all embedded images)
    """
    
    def __init__(
        self,
        grobid_url: str = "http://localhost:8070",
        output_base_dir: str = "./output_grobid_pymupdf",
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
        """Parse a single PDF using GROBID + PyMuPDF."""
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
            
            # Step 2: Extract images with PyMuPDF
            print(f"  [2/2] Extracting images with PyMuPDF...")
            pymupdf_images = self._extract_images_with_pymupdf(str(pdf_path), images_dir, paper_name)
            
            # Merge GROBID figure metadata with PyMuPDF images
            merged_figures = self._merge_figure_data(grobid_figures, pymupdf_images)
            
            # Save table metadata from GROBID
            saved_tables = self._save_table_metadata(grobid_tables, tables_dir, paper_name)
            
            # Prepare results
            results = {
                'paper_name': paper_name,
                'source_file': str(pdf_path),
                'output_directory': str(paper_output_dir),
                'tei_file': str(tei_path),
                'methodology': methodology,
                'figures': {
                    'count': len(merged_figures),
                    'items': merged_figures,
                    'note': 'Images from PyMuPDF, captions from GROBID'
                },
                'tables': {
                    'count': len(saved_tables),
                    'items': saved_tables
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
    
    def _extract_images_with_pymupdf(self, pdf_path: str, images_dir: Path, paper_name: str) -> List[Dict[str, Any]]:
        """Extract all images from PDF using PyMuPDF."""
        images = []
        
        try:
            # Open PDF with PyMuPDF
            pdf_document = fitz.open(pdf_path)
            
            image_count = 0
            
            # Iterate through pages
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                
                # Get list of images on this page
                image_list = page.get_images(full=True)
                
                for img_index, img in enumerate(image_list):
                    image_count += 1
                    
                    # Get image xref (reference number)
                    xref = img[0]
                    
                    # Extract image
                    try:
                        base_image = pdf_document.extract_image(xref)
                        image_bytes = base_image["image"]
                        image_ext = base_image["ext"]
                        
                        # Save image
                        image_filename = f"{paper_name}_image_{image_count}.{image_ext}"
                        image_path = images_dir / image_filename
                        
                        with open(image_path, "wb") as img_file:
                            img_file.write(image_bytes)
                        
                        # Get image dimensions
                        try:
                            img_pil = Image.open(io.BytesIO(image_bytes))
                            width, height = img_pil.size
                        except:
                            width, height = None, None
                        
                        # Create metadata
                        image_data = {
                            'image_number': image_count,
                            'page': page_num + 1,  # 1-indexed
                            'saved_as': str(image_path),
                            'format': image_ext,
                            'width': width,
                            'height': height,
                            'size_bytes': len(image_bytes),
                            'source': 'pymupdf',
                            'status': 'saved'
                        }
                        
                        images.append(image_data)
                        
                    except Exception as e:
                        images.append({
                            'image_number': image_count,
                            'page': page_num + 1,
                            'source': 'pymupdf',
                            'status': 'error',
                            'error': str(e)
                        })
            
            pdf_document.close()
            
        except Exception as e:
            print(f"    Error extracting images with PyMuPDF: {str(e)}")
        
        return images
    
    def _merge_figure_data(self, grobid_figures: List[Dict], pymupdf_images: List[Dict]) -> List[Dict]:
        """Merge GROBID figure metadata with PyMuPDF extracted images."""
        merged = []
        
        # Use PyMuPDF images as primary (they have actual files)
        for img in pymupdf_images:
            if img.get('status') != 'saved':
                continue
            
            # Try to find matching GROBID caption
            # Simple heuristic: use figure number if counts match
            caption = ''
            img_num = img.get('image_number', 0)
            if img_num <= len(grobid_figures):
                caption = grobid_figures[img_num - 1].get('caption', '')
            
            merged.append({
                'figure_number': img_num,
                'page': img.get('page'),
                'image_file': img.get('saved_as'),
                'format': img.get('format'),
                'width': img.get('width'),
                'height': img.get('height'),
                'size_bytes': img.get('size_bytes'),
                'caption': caption,
                'source': 'pymupdf_image_grobid_caption',
                'status': 'saved'
            })
        
        return merged
    
    def _save_table_metadata(self, grobid_tables: List[Dict], tables_dir: Path, paper_name: str) -> List[Dict]:
        """Save table metadata from GROBID."""
        saved_tables = []
        
        for table in grobid_tables:
            table_num = table.get('table_number')
            caption = table.get('caption', '')
            
            # Save caption to file
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
