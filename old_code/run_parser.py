"""
Simple script to run the PDF parser on research papers.
"""
from src.research_viz.preprocessing.pdf_parser import ResearchPaperParser

# Initialize parser with output directory
parser = ResearchPaperParser(output_base_dir="./output")

# Process all PDFs in resources directory
resources_dir = "./resources"
results = parser.parse_directory(resources_dir)

# Print detailed summary
print("\n" + "=" * 70)
print("DETAILED EXTRACTION SUMMARY")
print("=" * 70)

for result in results:
    if result.get('status') == 'success':
        print(f"\n📄 {result['paper_name']}")
        print(f"   Source: {result['source_file']}")
        
        # Methodology info
        if result['methodology']['found']:
            print(f"\n   ✓ Methodology Section Found:")
            print(f"     Title: {result['methodology']['title']}")
            print(f"     Text length: {len(result['methodology']['text'])} characters")
            print(f"     Subsections: {len(result['methodology']['subsections'])}")
            if result['methodology']['subsections']:
                for subsec in result['methodology']['subsections']:
                    print(f"       - {subsec['title']}")
        else:
            print(f"\n   ✗ Methodology section not found")
        
        # Figures/Images info (merged from Docling + PyMuPDF)
        print(f"\n   🖼️  Figures/Images: {result['figures']['count']}")
        for fig in result['figures']['items'][:10]:  # Show first 10
            if fig['status'] == 'saved':
                caption_preview = fig['caption'][:50] if fig['caption'] else "No caption"
                print(f"     ✓ Figure {fig['figure_number']}: {fig['format'].upper()} {fig['width']}x{fig['height']} (page {fig['page']})")
                if fig['caption']:
                    print(f"       Caption: {caption_preview}...")
        if result['figures']['count'] > 10:
            print(f"     ... and {result['figures']['count'] - 10} more figures")
        
        # Tables info
        print(f"\n   📋 Tables: {result['tables']['count']}")
        for table in result['tables']['items']:
            status_icon = "✓" if table['status'] == 'saved' else "✗"
            caption_preview = table['caption'][:60] if table['caption'] else "No caption"
            print(f"     {status_icon} Table {table['table_number']}: {caption_preview}...")
        
        print(f"\n   💾 Output directory: {result['output_directory']}")
    else:
        print(f"\n✗ {result['paper_name']}")
        print(f"   Error: {result.get('error', 'Unknown error')}")

print("\n" + "=" * 70)
