"""
Runner for GROBID-based parser
"""
from src.research_viz.preprocessing.pdf_parser3 import GrobidResearchPaperParser

parser = GrobidResearchPaperParser(base_url="http://localhost:8070", output_base_dir="./output_grobid")

resources_dir = "./resources"
results = parser.parse_directory(resources_dir)

print("\n" + "=" * 70)
print("DETAILED EXTRACTION SUMMARY (GROBID)")
print("=" * 70)

for result in results:
    if result.get("status") == "success":
        print(f"\n✓ {result['paper_name']}")
        # Methodology
        meth = result.get("methodology", {})
        print(f"   🧪 Methodology: {'Found' if meth.get('found') else 'Not found'}")
        if meth.get('found'):
            print(f"     Title: {meth.get('title')}")
            print(f"     Text length: {len(meth.get('text', ''))} chars")
            print(f"     Subsections: {len(meth.get('subsections', []))}")
        # Figures
        figs = result.get("figures", {})
        print(f"   🖼  Figures: {figs.get('count', 0)} (metadata)")
        # Tables
        tabs = result.get("tables", {})
        print(f"   📋 Tables: {tabs.get('count', 0)} (saved TEI XML)")
        print(f"   💾 Output directory: {result['output_directory']}")
    else:
        print(f"\n✗ {result['paper_name']}")
        print(f"   Error: {result.get('error', 'Unknown error')}")

print("\n" + "=" * 70)
