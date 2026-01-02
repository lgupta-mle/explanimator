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
from marker.convert import convert_single_pdf
from marker.models import load_all_models


class HybridResearchPaperParser:
    """
    Hybrid parser combining:
    - GROBID: Clean section structure, methodology extraction
    - Marker: Image extraction, table extraction
    """
    
    def __init__(
        self,
        grobid_url: str = "http://localhost:8070",
        output_base_dir: str = "./output_hybrid",
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
        self.marker_models = load_all_models()
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
            
            # Step 2: Extract images and tables with Marker
            print(f"  [2/2] Extracting images and tables with Marker...")
            full_text, marker_images, out_meta = convert_single_pdf(
                str(pdf_path),
                self.marker_models,
                max_pages=None,
                langs=None
            )
            
            # Save full markdown from Marker
            markdown_file = paper_output_dir / f"{paper_name}_full.md"
            with open(markdown_file, 'w', encoding='utf-8') as f:
                f.write(full_text)
            
            # Save Marker images
            saved_images = self._save_marker_images(marker_images, images_dir, paper_name)
            
            # Merge GROBID figure metadata with Marker images
            merged_figures = self._merge_figure_data(grobid_figures, saved_images)
            
            # Extract tables from Marker markdown
            tables = self._extract_tables_from_markdown(full_text, tables_dir, paper_name)
            
            # Merge with GROBID table metadata
            merged_tables = self._merge_table_data(grobid_tables, tables)
            
            # Prepare results
            results = {
                'paper_name': paper_name,
                'source_file': str(pdf_path),
                'output_directory': str(paper_output_dir),
                'tei_file': str(tei_path),
                'markdown_file': str(markdown_file),
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
        """Extract methodology section from GROBID TEI XML with improved subsection handling."""
        ns = {'tei': self._get_namespace(root)}
        body = root.find('.//tei:text/tei:body', ns)
        
        if body is None:
            return {'found': False, 'title': None, 'text': '', 'subsections': []}
        
        def get_section_title(div: ET.Element) -> str:
            head = div.find('tei:head', ns)
            if head is not None:
                # Get all text including nested elements
                return ''.join(head.itertext()).strip()
            return ''
        
        def get_section_text(div: ET.Element, include_subsections: bool = False) -> str:
            """Extract text from a section, optionally including subsections."""
            paras = []
            
            # Get direct paragraphs (not in subsections)
            for p in div.findall('tei:p', ns):
                txt = ''.join(p.itertext()).strip()
                if txt:
                    paras.append(txt)
            
            # If including subsections, recursively get their text
            if include_subsections:
                for subdiv in div.findall('tei:div', ns):
                    sub_text = get_section_text(subdiv, include_subsections=True)
                    if sub_text:
                        paras.append(sub_text)
            
            return '\n\n'.join(paras)
        
        def get_subsections(div: ET.Element, level: int = 1) -> List[Dict[str, Any]]:
            """Extract all subsections recursively with nested structure."""
            subs = []
            # Only get direct children divs, not all descendants
            for subdiv in div.findall('./tei:div', ns):
                title = get_section_title(subdiv)
                # Get only direct paragraphs, not from nested subsections
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
        for div in body.findall('tei:div', ns):
            title = get_section_title(div)
            title_lower = title.lower()
            
            if any(keyword in title_lower for keyword in self.methodology_keywords):
                # Found methodology section - extract with all subsections
                return {
                    'found': True,
                    'title': title,
                    'text': get_section_text(div, include_subsections=False),  # Only direct text
                    'subsections': get_subsections(div),
                    'full_text': get_section_text(div, include_subsections=True)  # Everything
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
    
    def _save_marker_images(self, images: Dict[str, Any], images_dir: Path, paper_name: str) -> List[Dict[str, Any]]:
        """Save images extracted by Marker."""
        saved_images = []
        
        for img_name, img_data in images.items():
            try:
                image_filename = f"{paper_name}_{img_name}"
                if not image_filename.endswith(('.png', '.jpg', '.jpeg')):
                    image_filename += '.png'
                
                image_path = images_dir / image_filename
                img_data.save(image_path)
                
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
    
    def _extract_tables_from_markdown(self, markdown_text: str, tables_dir: Path, paper_name: str) -> List[Dict[str, Any]]:
        """Extract tables from Marker markdown."""
        tables = []
        lines = markdown_text.split('\n')
        in_table = False
        current_table = []
        table_count = 0
        
        for line in lines:
            if '|' in line and line.strip().startswith('|'):
                if not in_table:
                    in_table = True
                    current_table = []
                current_table.append(line)
            else:
                if in_table and current_table:
                    table_count += 1
                    table_md = '\n'.join(current_table)
                    table_filename = f"{paper_name}_table_{table_count}.md"
                    table_path = tables_dir / table_filename
                    
                    with open(table_path, 'w', encoding='utf-8') as f:
                        f.write(table_md)
                    
                    tables.append({
                        'table_number': table_count,
                        'saved_as': str(table_path),
                        'rows': len(current_table),
                        'source': 'marker',
                        'status': 'saved'
                    })
                    
                    in_table = False
                    current_table = []
        
        return tables
    
    def _merge_table_data(self, grobid_tables: List[Dict], marker_tables: List[Dict]) -> List[Dict]:
        """Merge GROBID table metadata with Marker extracted tables."""
        merged = []
        
        max_count = max(len(grobid_tables), len(marker_tables))
        
        for idx in range(max_count):
            table_data = {'table_number': idx + 1}
            
            # Add GROBID caption if available
            if idx < len(grobid_tables):
                table_data['caption'] = grobid_tables[idx].get('caption', '')
            
            # Add Marker table file if available
            if idx < len(marker_tables):
                table_data.update({
                    'saved_as': marker_tables[idx].get('saved_as'),
                    'rows': marker_tables[idx].get('rows'),
                    'status': 'saved'
                })
            else:
                table_data['status'] = 'metadata_only'
            
            merged.append(table_data)
        
        return merged
    
    def _get_namespace(self, root: ET.Element) -> str:
        """Extract namespace from TEI root element."""
        if root.tag.startswith('{'):
            return root.tag.split('}')[0].strip('{')
        return 'http://www.tei-c.org/ns/1.0'
