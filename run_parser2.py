"""
Script to run the Marker-based PDF parser on research papers.
"""
from src.research_viz.preprocessing.pdf_parser2 import MarkerResearchPaperParser

# Initialize parser with output directory
parser = MarkerResearchPaperParser(output_base_dir="./output_marker")

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
        print(f"   Markdown: {result['markdown_file']}")
        
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
        
        # Figures/Images info
        print(f"\n   🖼️  Figures/Images: {result['figures']['count']}")
        for fig in result['figures']['items'][:5]:  # Show first 5
            if fig['status'] == 'saved':
                print(f"     ✓ Figure {fig['figure_number']}: {fig['format']} {fig['width']}x{fig['height']}")
        if result['figures']['count'] > 5:
            print(f"     ... and {result['figures']['count'] - 5} more figures")
        
        # Tables info
        print(f"\n   📋 Tables: {result['tables']['count']}")
        for table in result['tables']['items'][:3]:  # Show first 3
            if table['status'] == 'saved':
                print(f"     ✓ Table {table['table_number']}: {table['rows']} rows")
        if result['tables']['count'] > 3:
            print(f"     ... and {result['tables']['count'] - 3} more tables")
        
        
        print(f"\n   💾 Output directory: {result['output_directory']}")
    else:
        print(f"\n✗ {result['paper_name']}")
        print(f"   Error: {result.get('error', 'Unknown error')}")

print("\n" + "=" * 70)
