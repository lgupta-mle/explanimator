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
        """Extract methodology section from GROBID TEI XML with nested subsections."""
        ns = {'tei': self._get_namespace(root)}
        body = root.find('.//tei:text/tei:body', ns)
        
        if body is None:
            return {'found': False, 'title': None, 'text': '', 'subsections': []}
        
        def get_section_title(div: ET.Element) -> str:
            head = div.find('tei:head', ns)
            if head is not None:
                return ''.join(head.itertext()).strip()
            return ''
        
        def get_section_text(div: ET.Element, include_subsections: bool = False) -> str:
            """Extract text from a section, optionally including subsections."""
            paras = []
            
            # Get direct paragraphs (not in subsections)
            for p in div.findall('./tei:p', ns):
                txt = ''.join(p.itertext()).strip()
                if txt:
                    paras.append(txt)
            
            # If including subsections, recursively get their text
            if include_subsections:
                for subdiv in div.findall('./tei:div', ns):
                    sub_text = get_section_text(subdiv, include_subsections=True)
                    if sub_text:
                        paras.append(sub_text)
            
            return '\n\n'.join(paras)
        
        def get_subsections(div: ET.Element, level: int = 1) -> List[Dict[str, Any]]:
            """Extract all subsections recursively with nested structure."""
            subs = []
            # Only get direct children divs
            for subdiv in div.findall('./tei:div', ns):
                title = get_section_title(subdiv)
                # Get only direct paragraphs
                direct_paras = []
                for p in subdiv.findall('./tei:p', ns):
                    txt = ''.join(p.itertext()).strip()
                    if txt:
                        direct_paras.append(txt)
                direct_text = '\n\n'.join(direct_paras)
                
                # Recursively get nested subsections
                nested_subs = get_subsections(subdiv, level + 1)
                
                if title or direct_text or nested_subs:
                    sub_data = {
                        'title': title,
                        'text': direct_text,
                        'level': level
                    }
                    if nested_subs:
                        sub_data['subsections'] = nested_subs
                    subs.append(sub_data)
            return subs
        
        # Find methodology section
        for div in body.findall('./tei:div', ns):
            title = get_section_title(div)
            title_lower = title.lower()
            
            if any(keyword in title_lower for keyword in self.methodology_keywords):
                # Found methodology section
                return {
                    'found': True,
                    'title': title,
                    'text': get_section_text(div, include_subsections=False),
                    'subsections': get_subsections(div),
                    'full_text': get_section_text(div, include_subsections=True)
                }
        
        return {'found': False, 'title': None, 'text': '', 'subsections': []}
    
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
