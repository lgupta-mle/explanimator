"""
PDF Parser using Marker for research paper extraction.
Marker is specifically designed for converting academic PDFs to Markdown with figures and tables.
Requires Python 3.10+
"""
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered


class MarkerResearchPaperParser:
    """
    Parser for extracting methodology sections, figures, and tables from research papers
    using Marker.
    """
    
    def __init__(self, output_base_dir: str = "./output_marker"):
        """
        Initialize the research paper parser with Marker.
        
        Args:
            output_base_dir: Base directory for saving extracted content
        """
        self.output_base_dir = Path(output_base_dir)
        self.output_base_dir.mkdir(parents=True, exist_ok=True)
        
        # Keywords to identify methodology sections
        self.methodology_keywords = [
            'method', 'methods', 'methodology', 'methodologies',
            'materials and methods', 'experimental setup', 'experimental design',
            'approach', 'experimental', 'implementation', 'system design',
            'experimental procedure', 'procedure', 'experimental methods', 'technique',
            'model architecture', 'architecture'
        ]
        
        # Load Marker models once
        print("Loading Marker models (this may take a moment)...")
        self.model_lst = create_model_dict()
        print("Models loaded successfully!")
    
    def parse_paper(self, pdf_path: str, paper_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Parse a single research paper PDF.
        
        Args:
            pdf_path: Path to the PDF file
            paper_name: Optional name for the paper (defaults to filename)
            
        Returns:
            Dictionary containing extracted data
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        
        if paper_name is None:
            paper_name = pdf_path.stem
        
        print(f"\nProcessing: {paper_name}")
        
        # Create output directory for this paper
        paper_output_dir = self.output_base_dir / paper_name
        paper_output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Convert PDF to Markdown using Marker
            print(f"  Converting PDF with Marker...")
            converter = PdfConverter(
                artifact_dict=self.model_lst,
                config={"use_llm": False}
            )

            rendered = converter(str(pdf_path))
            full_text, _, images = text_from_rendered(rendered)
            out_meta = getattr(rendered, "metadata", {})
            
            # Save the full markdown
            markdown_file = paper_output_dir / f"{paper_name}_full.md"
            with open(markdown_file, 'w', encoding='utf-8') as f:
                f.write(full_text)
            print(f"  Saved full markdown to: {markdown_file}")
            
            # Extract methodology section
            print(f"  Extracting methodology section...")
            methodology = self._extract_methodology_from_markdown(full_text)

            methodology_file = None
            if methodology.get('found'):
                methodology_file = paper_output_dir / f"{paper_name}_methodology.md"
                with open(methodology_file, 'w', encoding='utf-8') as f:
                    f.write(methodology.get('text', ''))
            
            # Save extracted images
            print(f"  Saving extracted images...")
            saved_images = self._save_images(images, paper_output_dir, paper_name)
            
            # Extract tables from markdown
            print(f"  Extracting tables...")
            tables = self._extract_tables_from_markdown(full_text, paper_output_dir, paper_name)
            
            # Prepare results
            results = {
                'paper_name': paper_name,
                'source_file': str(pdf_path),
                'output_directory': str(paper_output_dir),
                'markdown_file': str(markdown_file),
                'methodology_file': str(methodology_file) if methodology_file else None,
                'methodology': methodology,
                'figures': {
                    'count': len(saved_images),
                    'items': saved_images
                },
                'tables': {
                    'count': len(tables),
                    'items': tables
                },
                'metadata': {
                    'total_pages': len(out_meta.get('page_stats', [])) if isinstance(out_meta.get('page_stats', None), list) else 0,
                    'table_of_contents': out_meta.get('table_of_contents', None)
                },
                'status': 'success'
            }
            
            # Save results as JSON
            results_file = paper_output_dir / f"{paper_name}_extraction_results.json"
            self._save_json(results, results_file)
            print(f"  Results saved to: {results_file}")
            
            return results
            
        except Exception as e:
            print(f"  Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'paper_name': paper_name,
                'source_file': str(pdf_path),
                'status': 'error',
                'error': str(e)
            }
    
    def parse_directory(self, directory_path: str) -> List[Dict[str, Any]]:
        """
        Parse all PDF files in a directory.
        
        Args:
            directory_path: Path to directory containing PDFs
            
        Returns:
            List of results for each paper
        """
        directory = Path(directory_path)
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        pdf_files = list(directory.glob("*.pdf"))
        
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
        self._save_json({
            'total_papers': len(pdf_files),
            'successful': sum(1 for r in results if r.get('status') == 'success'),
            'failed': sum(1 for r in results if r.get('status') == 'error'),
            'results': results
        }, summary_file)
        
        print("\n" + "=" * 70)
        print(f"Processing complete! Summary saved to: {summary_file}")
        
        return results
    
    def _extract_methodology_from_markdown(self, markdown_text: str) -> Dict[str, Any]:
        """
        Extract methodology section from markdown text.
        
        Args:
            markdown_text: Full markdown text of the paper
            
        Returns:
            Dictionary containing methodology data
        """
        methodology_data = {
            'found': False,
            'title': None,
            'text': '',
            'subsections': []
        }
        
        # Split into lines for processing
        lines = markdown_text.split('\n')
        
        in_methodology = False
        methodology_lines = []
        current_subsection = None
        subsections = {}
        methodology_title = None
        
        for i, line in enumerate(lines):
            # Check for section headers (markdown headers or numbered section titles)
            header_text = None
            level = None
            if line.startswith('#'):
                header_match = re.match(r'^(#+)\s+(.+)$', line)
                if header_match:
                    level = len(header_match.group(1))
                    header_text = header_match.group(2).strip()
            else:
                numbered_match = re.match(r'^(\d+(?:\.\d+)*)\s+(.+)$', line.strip())
                if numbered_match:
                    section_num = numbered_match.group(1)
                    header_text = (section_num + " " + numbered_match.group(2)).strip()
                    level = section_num.count('.') + 1
                else:
                    # Some PDFs yield plain headings without markdown markers or numbering
                    # (often all-caps like "METHODS" / "METHODOLOGY").
                    candidate = line.strip()
                    plain_heading_match = re.match(r'^[A-Za-z][A-Za-z\s\-:&]{2,}$', candidate)
                    if plain_heading_match and len(candidate) <= 80 and candidate == candidate.upper():
                        header_text = candidate
                        level = 1

            if header_text is not None and level is not None:
                header_lower = header_text.lower()

                # Check if this is a methodology section
                if not in_methodology and any(keyword in header_lower for keyword in self.methodology_keywords):
                    in_methodology = True
                    methodology_data['found'] = True
                    methodology_data['title'] = header_text
                    methodology_title = header_text
                    current_subsection = None
                    continue

                # If we're in methodology
                elif in_methodology:
                    # Check if this is a subsection (higher level number = subsection)
                    if level > 1 and any(keyword in header_lower for keyword in self.methodology_keywords + ['encoder', 'decoder', 'attention', 'layer', 'training']):
                        current_subsection = header_text
                        subsections[current_subsection] = []
                        continue
                    elif level <= 2 and not any(keyword in header_lower for keyword in self.methodology_keywords):
                        # New main section, stop methodology extraction
                        break
            
            # Collect content if in methodology
            if in_methodology:
                line_stripped = line.strip()
                if line_stripped and not line_stripped.startswith('#'):
                    # Skip image references
                    if not line_stripped.startswith('!['):
                        if current_subsection:
                            subsections[current_subsection].append(line_stripped)
                        else:
                            methodology_lines.append(line_stripped)
        
        # Compile results
        if methodology_data['found']:
            methodology_data['text'] = '\n\n'.join(methodology_lines)
            methodology_data['subsections'] = [
                {
                    'title': title,
                    'text': '\n\n'.join(content)
                }
                for title, content in subsections.items()
            ]
        
        return methodology_data
    
    def _save_images(self, images: Dict[str, Any], output_dir: Path, paper_name: str) -> List[Dict[str, Any]]:
        """
        Save extracted images from Marker.
        
        Args:
            images: Dictionary of images from Marker
            output_dir: Directory to save images
            paper_name: Name of the paper
            
        Returns:
            List of image metadata
        """
        images_dir = output_dir / "images"
        images_dir.mkdir(exist_ok=True)
        
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
                
                image_info = {
                    'figure_number': len(saved_images) + 1,
                    'filename': img_name,
                    'saved_as': str(image_path),
                    'width': width,
                    'height': height,
                    'format': img_data.format or 'PNG',
                    'status': 'saved'
                }
                
                saved_images.append(image_info)
                
            except Exception as e:
                saved_images.append({
                    'filename': img_name,
                    'status': 'error',
                    'error': str(e)
                })
        
        return saved_images
    
    def _extract_tables_from_markdown(self, markdown_text: str, output_dir: Path, paper_name: str) -> List[Dict[str, Any]]:
        """
        Extract tables from markdown text.
        
        Args:
            markdown_text: Full markdown text
            output_dir: Directory to save tables
            paper_name: Name of the paper
            
        Returns:
            List of table metadata
        """
        tables_dir = output_dir / "tables"
        tables_dir.mkdir(exist_ok=True)
        
        tables = []
        
        # Find all markdown tables
        lines = markdown_text.split('\n')
        in_table = False
        current_table = []
        table_count = 0
        
        for line in lines:
            # Check if line is part of a markdown table
            if '|' in line and line.strip().startswith('|'):
                if not in_table:
                    in_table = True
                    current_table = []
                current_table.append(line)
            else:
                if in_table and current_table:
                    # End of table
                    table_count += 1
                    
                    # Save table as markdown
                    table_md = '\n'.join(current_table)
                    table_filename = f"{paper_name}_table_{table_count}.md"
                    table_path = tables_dir / table_filename
                    
                    with open(table_path, 'w', encoding='utf-8') as f:
                        f.write(table_md)
                    
                    # Try to find caption (usually before or after table)
                    caption = ""
                    
                    tables.append({
                        'table_number': table_count,
                        'caption': caption,
                        'saved_as': str(table_path),
                        'rows': len(current_table),
                        'status': 'saved'
                    })
                    
                    in_table = False
                    current_table = []
        
        return tables
    
    def _save_json(self, data: Dict[str, Any], filepath: Path):
        """
        Save data as JSON file.
        
        Args:
            data: Data to save
            filepath: Path to save file
        """
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    """Main function to demonstrate usage."""
    parser = MarkerResearchPaperParser(output_base_dir="./output_marker")
    
    # Process all PDFs in resources directory
    resources_dir = "./resources"
    results = parser.parse_directory(resources_dir)
    
    # Print summary
    print("\n" + "=" * 70)
    print("EXTRACTION SUMMARY")
    print("=" * 70)
    
    for result in results:
        if result.get('status') == 'success':
            print(f"\n✓ {result['paper_name']}")
            print(f"  Methodology: {'Found' if result['methodology']['found'] else 'Not found'}")
            if result['methodology']['found']:
                print(f"    Title: {result['methodology']['title']}")
                print(f"    Text length: {len(result['methodology']['text'])} characters")
                print(f"    Subsections: {len(result['methodology']['subsections'])}")
            print(f"  Figures/Images: {result['figures']['count']}")
            print(f"  Tables: {result['tables']['count']}")
            print(f"  Output: {result['output_directory']}")
        else:
            print(f"\n✗ {result['paper_name']}: {result.get('error', 'Unknown error')}")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
