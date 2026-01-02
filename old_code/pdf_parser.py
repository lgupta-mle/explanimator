"""
This module contains the code to parse the PDF files and extract the text and images from them.
Uses Docling for advanced PDF understanding and extraction.
Uses PyMuPDF (fitz) for extracting actual images from PDFs.
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from docling.document_converter import DocumentConverter
import fitz  # PyMuPDF
from PIL import Image
import io


class ResearchPaperParser:
    """
    Parser for extracting methodology sections, figures, and tables from research papers
    using Docling.
    """
    
    def __init__(self, output_base_dir: str = "./output"):
        """
        Initialize the research paper parser.
        
        Args:
            output_base_dir: Base directory for saving extracted content
        """
        self.output_base_dir = Path(output_base_dir)
        self.output_base_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Docling converter with default settings
        self.converter = DocumentConverter()
        
        # Common methodology section keywords (case-insensitive)
        self.methodology_keywords = [
            'method', 'methods', 'methodology', 'methodologies',
            'materials and methods', 'experimental setup', 'experimental design',
            'approach', 'experimental', 'implementation', 'system design',
            'experimental procedure', 'procedure', 'experimental methods', 'technique',
            'model architecture', 'architecture'
        ]
    
    def parse_paper(self, pdf_path: str, paper_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Parse a single research paper and extract methodology, figures, and tables.
        
        Args:
            pdf_path: Path to the PDF file
            paper_name: Optional name for the paper (defaults to filename without extension)
            
        Returns:
            Dictionary containing extraction results and metadata
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        # Determine paper name
        if paper_name is None:
            paper_name = pdf_path.stem
        
        print(f"Processing: {paper_name}")
        
        # Create output directory for this paper
        paper_output_dir = self.output_base_dir / paper_name
        paper_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Convert the PDF
        print(f"  Converting PDF with Docling...")
        result = self.converter.convert(str(pdf_path))
        doc = result.document
        
        # Extract methodology section
        print(f"  Extracting methodology section...")
        methodology = self._extract_methodology(doc)
        
        # Extract figures metadata from Docling
        print(f"  Extracting figure metadata...")
        figures_metadata = self._extract_and_save_figures(doc, paper_output_dir, paper_name)
        
        # Extract actual images from PDF using PyMuPDF
        print(f"  Extracting images with PyMuPDF...")
        images = self._extract_images_with_pymupdf(str(pdf_path), paper_output_dir, paper_name)
        
        # Merge figures metadata with extracted images
        # Use images as the primary source since they're the actual extracted files
        merged_figures = []
        for img in images:
            # Try to find matching figure metadata from Docling
            figure_meta = None
            if img['status'] == 'saved':
                # Look for Docling figure on the same page
                for fig in figures_metadata:
                    if fig.get('page') == img.get('page'):
                        figure_meta = fig
                        break
                
                merged_item = {
                    'figure_number': img['image_number'],
                    'page': img['page'],
                    'image_file': img['saved_as'],
                    'format': img['format'],
                    'width': img['width'],
                    'height': img['height'],
                    'size_bytes': img['size_bytes'],
                    'caption': figure_meta.get('caption', '') if figure_meta else '',
                    'status': 'saved'
                }
                merged_figures.append(merged_item)
        
        # Extract and save tables
        print(f"  Extracting tables...")
        tables = self._extract_and_save_tables(doc, paper_output_dir, paper_name)
        
        # Prepare results
        results = {
            'paper_name': paper_name,
            'source_file': str(pdf_path),
            'output_directory': str(paper_output_dir),
            'methodology': methodology,
            'figures': {
                'count': len(merged_figures),
                'items': merged_figures,
                'note': 'Images extracted with PyMuPDF, metadata from Docling where available'
            },
            'tables': {
                'count': len(tables),
                'items': tables
            },
            'status': 'success'
        }
        
        # Save results as JSON
        results_file = paper_output_dir / f"{paper_name}_extraction_results.json"
        self._save_json(results, results_file)
        print(f"  ✓ Results saved to: {results_file}")
        
        return results
    
    def parse_directory(self, directory_path: str) -> List[Dict[str, Any]]:
        """
        Parse all PDF files in a directory.
        
        Args:
            directory_path: Path to directory containing PDF files
            
        Returns:
            List of results for each paper
        """
        directory_path = Path(directory_path)
        if not directory_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory_path}")
        
        # Find all PDF files
        pdf_files = list(directory_path.glob("*.pdf"))
        
        if not pdf_files:
            print(f"No PDF files found in {directory_path}")
            return []
        
        print(f"\nFound {len(pdf_files)} PDF file(s) to process\n")
        print("=" * 70)
        
        results = []
        for i, pdf_file in enumerate(pdf_files, 1):
            print(f"\n[{i}/{len(pdf_files)}] Processing: {pdf_file.name}")
            print("-" * 70)
            
            try:
                result = self.parse_paper(str(pdf_file))
                results.append(result)
                print(f"✓ Successfully processed: {pdf_file.name}")
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
    
    def _extract_methodology(self, doc) -> Dict[str, Any]:
        """
        Extract methodology section from the document.
        
        Args:
            doc: Docling document object
            
        Returns:
            Dictionary containing methodology section data
        """
        methodology_data = {
            'found': False,
            'title': None,
            'text': '',
            'subsections': []
        }
        
        current_section = None
        in_methodology = False
        methodology_content = []
        subsections = {}
        current_subsection = None
        
        # Iterate through document items
        for item_tuple in doc.iterate_items():
            # Handle tuple format (element, level) or just element
            if isinstance(item_tuple, tuple):
                item = item_tuple[0]
            else:
                item = item_tuple
            
            # Skip figures/pictures/tables - don't extract their content
            if item.label in ["picture", "figure", "table"]:
                continue
            
            # Check for section headers
            if item.label == "section_header":
                section_title = item.text.strip()
                section_title_lower = section_title.lower()
                
                # Check if this is a methodology section
                if any(keyword in section_title_lower for keyword in self.methodology_keywords):
                    in_methodology = True
                    methodology_data['found'] = True
                    methodology_data['title'] = section_title
                    current_section = section_title
                    current_subsection = None
                elif in_methodology:
                    # We've moved to a new section, stop collecting
                    # But check if it's a subsection (indented or numbered)
                    if self._is_likely_subsection(section_title):
                        current_subsection = section_title
                        subsections[current_subsection] = []
                    else:
                        # New main section, stop methodology extraction
                        break
            
            # Collect text content if we're in methodology section
            elif in_methodology and item.label in ["paragraph", "text", "list_item"]:
                text = item.text.strip()
                if text:
                    # Filter out very short text that might be figure labels
                    # (like "MatMul", "Linear", etc.)
                    if len(text) > 15 or any(char in text for char in ['.', ',', ';', ':', '(', ')']):
                        if current_subsection:
                            subsections[current_subsection].append(text)
                        else:
                            methodology_content.append(text)
        
        # Compile the methodology text
        if methodology_data['found']:
            methodology_data['text'] = '\n\n'.join(methodology_content)
            methodology_data['subsections'] = [
                {
                    'title': title,
                    'text': '\n\n'.join(content)
                }
                for title, content in subsections.items()
            ]
        
        return methodology_data
    
    def _is_likely_subsection(self, title: str) -> bool:
        """
        Heuristic to determine if a section title is likely a subsection.
        
        Args:
            title: Section title
            
        Returns:
            True if likely a subsection
        """
        # Check for numbered subsections (e.g., "3.1", "3.1.1")
        if len(title.split()) > 0:
            first_word = title.split()[0]
            if '.' in first_word and first_word.replace('.', '').isdigit():
                # Count dots to determine nesting level
                dot_count = first_word.count('.')
                return dot_count >= 1
        
        return False
    
    def _extract_and_save_figures(self, doc, output_dir: Path, paper_name: str) -> List[Dict[str, Any]]:
        """
        Extract figures from document and save them.
        
        Args:
            doc: Docling document object
            output_dir: Directory to save figures
            paper_name: Name of the paper
            
        Returns:
            List of figure metadata
        """
        figures_dir = output_dir / "figures"
        figures_dir.mkdir(exist_ok=True)
        
        figures = []
        figure_count = 0
        
        for item_tuple in doc.iterate_items():
            # Handle tuple format (element, level) or just element
            if isinstance(item_tuple, tuple):
                item = item_tuple[0]
            else:
                item = item_tuple
            
            if item.label == "picture":
                figure_count += 1
                
                # Get caption if available
                caption = ""
                if hasattr(item, 'caption') and item.caption:
                    caption = item.caption
                
                # Create figure metadata
                figure_data = {
                    'figure_number': figure_count,
                    'caption': caption,
                    'page': getattr(item, 'page', None),
                }
                
                # Try to save the image
                try:
                    # Get image data from the item
                    if hasattr(item, 'image') and item.image:
                        image_filename = f"{paper_name}_figure_{figure_count}.png"
                        image_path = figures_dir / image_filename
                        
                        # Save image
                        with open(image_path, 'wb') as f:
                            f.write(item.image)
                        
                        figure_data['saved_as'] = str(image_path)
                        figure_data['status'] = 'saved'
                    else:
                        figure_data['status'] = 'no_image_data'
                
                except Exception as e:
                    figure_data['status'] = 'error'
                    figure_data['error'] = str(e)
                
                figures.append(figure_data)
        
        return figures
    
    def _extract_and_save_tables(self, doc, output_dir: Path, paper_name: str) -> List[Dict[str, Any]]:
        """
        Extract tables from document and save them.
        
        Args:
            doc: Docling document object
            output_dir: Directory to save tables
            paper_name: Name of the paper
            
        Returns:
            List of table metadata
        """
        tables_dir = output_dir / "tables"
        tables_dir.mkdir(exist_ok=True)
        
        tables = []
        table_count = 0
        
        for item_tuple in doc.iterate_items():
            # Handle tuple format (element, level) or just element
            if isinstance(item_tuple, tuple):
                item = item_tuple[0]
            else:
                item = item_tuple
            
            if item.label == "table":
                table_count += 1
                
                # Get caption if available
                caption = ""
                if hasattr(item, 'caption') and item.caption:
                    caption = item.caption
                
                # Create table metadata
                table_data = {
                    'table_number': table_count,
                    'caption': caption,
                    'page': getattr(item, 'page', None),
                }
                
                # Try to extract table content
                try:
                    # Get table as markdown or text
                    if hasattr(item, 'export_to_markdown'):
                        table_content = item.export_to_markdown()
                    else:
                        table_content = str(item.text) if hasattr(item, 'text') else ""
                    
                    if table_content:
                        # Save table as markdown
                        table_filename = f"{paper_name}_table_{table_count}.md"
                        table_path = tables_dir / table_filename
                        
                        with open(table_path, 'w', encoding='utf-8') as f:
                            f.write(f"# Table {table_count}\n\n")
                            if caption:
                                f.write(f"**Caption:** {caption}\n\n")
                            f.write(table_content)
                        
                        table_data['saved_as'] = str(table_path)
                        table_data['status'] = 'saved'
                        
                        # Also save as JSON for structured access
                        table_json_filename = f"{paper_name}_table_{table_count}.json"
                        table_json_path = tables_dir / table_json_filename
                        self._save_json({
                            'table_number': table_count,
                            'caption': caption,
                            'content': table_content
                        }, table_json_path)
                        table_data['json_file'] = str(table_json_path)
                    else:
                        table_data['status'] = 'no_content'
                
                except Exception as e:
                    table_data['status'] = 'error'
                    table_data['error'] = str(e)
                
                tables.append(table_data)
        
        return tables
    
    def _extract_images_with_pymupdf(self, pdf_path: str, output_dir: Path, paper_name: str) -> List[Dict[str, Any]]:
        """
        Extract all images from PDF using PyMuPDF.
        
        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory to save images
            paper_name: Name of the paper
            
        Returns:
            List of image metadata
        """
        images_dir = output_dir / "images"
        images_dir.mkdir(exist_ok=True)
        
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
                            'status': 'saved'
                        }
                        
                        images.append(image_data)
                        
                    except Exception as e:
                        images.append({
                            'image_number': image_count,
                            'page': page_num + 1,
                            'status': 'error',
                            'error': str(e)
                        })
            
            pdf_document.close()
            
        except Exception as e:
            print(f"    Error extracting images with PyMuPDF: {str(e)}")
        
        return images
    
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
    """
    Main function to process research papers from the resources directory.
    """
    # Initialize parser
    parser = ResearchPaperParser(output_base_dir="./output")
    
    # Process all papers in resources directory
    resources_dir = "/Users/apopat/Desktop/GraphViz/research-paper-graphviz/resources"
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