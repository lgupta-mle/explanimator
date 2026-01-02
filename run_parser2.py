"""
Runner for GROBID + PyMuPDF Parser
"""
from src.research_viz.preprocessing.pdf_parser5 import GrobidPyMuPDFParser

# Initialize parser
parser = GrobidPyMuPDFParser(
    grobid_url="http://localhost:8070",
    output_base_dir="./output_grobid_pymupdf"
)

# Process all PDFs
resources_dir = "./resources"
results = parser.parse_directory(resources_dir)

# Print detailed summary
print("\n" + "=" * 70)
print("DETAILED EXTRACTION SUMMARY (GROBID + PyMuPDF)")
print("=" * 70)

for result in results:
    if result.get('status') == 'success':
        print(f"\n✓ {result['paper_name']}")
        
        # Methodology
        meth = result.get('methodology', {})
        print(f"   🧪 Methodology: {'Found' if meth.get('found') else 'Not found'}")
        if meth.get('found'):
            print(f"     Title: {meth.get('title')}")
            print(f"     Direct text: {len(meth.get('text', ''))} chars")
            print(f"     Full text (with subsections): {len(meth.get('full_text', ''))} chars")
            print(f"     Subsections: {len(meth.get('subsections', []))}")
            
            def print_subsections(subs, indent=3):
                for sub in subs:
                    level = sub.get('level', 1)
                    prefix = '  ' * (indent + level - 1)
                    title = sub.get('title', 'Untitled')
                    text_len = len(sub.get('text', ''))
                    print(f"{prefix}- {title}: {text_len} chars")
                    if 'subsections' in sub:
                        print_subsections(sub['subsections'], indent)
            
            print_subsections(meth.get('subsections', []))
        
        # Figures
        figs = result.get('figures', {})
        print(f"   🖼  Figures/Images: {figs.get('count', 0)} (PyMuPDF extraction)")
        for fig in figs.get('items', [])[:5]:  # Show first 5
            print(f"     ✓ Image {fig.get('figure_number')} (page {fig.get('page')})")
            print(f"       File: {fig.get('image_file')}")
            print(f"       Size: {fig.get('width')}x{fig.get('height')} ({fig.get('format')})")
            if fig.get('caption'):
                caption_preview = fig['caption'][:60] + '...' if len(fig['caption']) > 60 else fig['caption']
                print(f"       Caption: {caption_preview}")
        if figs.get('count', 0) > 5:
            print(f"     ... and {figs.get('count') - 5} more images")
        
        # Tables
        tabs = result.get('tables', {})
        print(f"   📋 Tables: {tabs.get('count', 0)} (GROBID metadata)")
        for tab in tabs.get('items', [])[:3]:  # Show first 3
            print(f"     ○ Table {tab.get('table_number')}")
            if tab.get('caption'):
                caption_preview = tab['caption'][:60] + '...' if len(tab['caption']) > 60 else tab['caption']
                print(f"       Caption: {caption_preview}")
        if tabs.get('count', 0) > 3:
            print(f"     ... and {tabs.get('count') - 3} more tables")
        
        print(f"\n   💾 Output directory: {result['output_directory']}")
    else:
        print(f"\n✗ {result['paper_name']}")
        print(f"   Error: {result.get('error', 'Unknown error')}")

print("\n" + "=" * 70)
print("\nNote: This parser combines:")
print("  - GROBID: Clean section structure and methodology extraction")
print("  - PyMuPDF: Comprehensive image extraction (all embedded images)")
print("=" * 70)
