"""
Runner for Hybrid Parser (GROBID + Marker)

Note: Make sure you have set DATALAB_API_KEY in the .env file
located at: src/research_viz/preprocessing/.env
"""
from src.research_viz.preprocessing.pdf_parser1 import HybridResearchPaperParser

# Initialize hybrid parser
# API key will be automatically loaded from .env file
parser = HybridResearchPaperParser(
    grobid_url="http://localhost:8070",
    output_base_dir="./output_grobid_marker2",
    datalab_api_key=True  # Use API key from .env file
)

# Process all PDFs
resources_dir = "./resources"
results = parser.parse_directory(resources_dir)

# Print detailed summary
print("\n" + "=" * 70)
print("DETAILED EXTRACTION SUMMARY (HYBRID: GROBID + MARKER)")
print("=" * 70)

for result in results:
    if result.get('status') == 'success':
        print(f"\n✓ {result['paper_name']}")
        
        # Introduction
        intro = result.get('introduction', {})
        print(f"   📖 Introduction: {'Found' if intro.get('found') else 'Not found'}")
        if intro.get('found'):
            print(f"     Title: {intro.get('title')}")
            print(f"     Direct text: {len(intro.get('text', ''))} chars")
            print(f"     Full text (with subsections): {len(intro.get('full_text', ''))} chars")
            print(f"     Subsections: {len(intro.get('subsections', []))}")
        
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
        
        # Related Works
        related = result.get('related_works', {})
        print(f"   📚 Related Works: {'Found' if related.get('found') else 'Not found'}")
        if related.get('found'):
            print(f"     Title: {related.get('title')}")
            print(f"     Direct text: {len(related.get('text', ''))} chars")
            print(f"     Full text (with subsections): {len(related.get('full_text', ''))} chars")
            print(f"     Subsections: {len(related.get('subsections', []))}")
        
        # Figures
        figs = result.get('figures', {})
        print(f"   🖼  Figures: {figs.get('count', 0)}")
        for fig in figs.get('items', [])[:3]:  # Show first 3
            status = '✓ Image saved' if fig.get('has_image_file') else '○ Metadata only'
            print(f"     {status} - Figure {fig.get('figure_number')}")
            if fig.get('caption'):
                caption_preview = fig['caption'][:80] + '...' if len(fig['caption']) > 80 else fig['caption']
                print(f"       Caption: {caption_preview}")
        if figs.get('count', 0) > 3:
            print(f"     ... and {figs.get('count') - 3} more figures")
        
        # Tables
        tabs = result.get('tables', {})
        print(f"   📋 Tables: {tabs.get('count', 0)}")
        for tab in tabs.get('items', [])[:3]:  # Show first 3
            status = '✓ Saved' if tab.get('status') == 'saved' else '○ Metadata only'
            print(f"     {status} - Table {tab.get('table_number')}")
            if tab.get('caption'):
                caption_preview = tab['caption'][:80] + '...' if len(tab['caption']) > 80 else tab['caption']
                print(f"       Caption: {caption_preview}")
        if tabs.get('count', 0) > 3:
            print(f"     ... and {tabs.get('count') - 3} more tables")
        
        print(f"\n   💾 Output directory: {result['output_directory']}")
    else:
        print(f"\n✗ {result['paper_name']}")
        print(f"   Error: {result.get('error', 'Unknown error')}")

print("\n" + "=" * 70)
