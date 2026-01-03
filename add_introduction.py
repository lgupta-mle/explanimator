"""
Script to extract introduction section and append to existing extraction results.
This updates existing JSON files without re-running the full extraction.
"""
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List


def extract_introduction_from_tei(tei_file_path: Path) -> Dict[str, Any]:
    """Extract introduction section from existing GROBID TEI XML file."""
    
    introduction_keywords = [
        'introduction', 'intro', 'overview', 'motivation'
    ]
    
    # Read TEI XML
    with open(tei_file_path, 'r', encoding='utf-8') as f:
        tei_xml = f.read()
    
    root = ET.fromstring(tei_xml)
    ns = {'tei': root.tag.split('}')[0].strip('{')}
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
            
            if num.startswith(parent_num + '.'):
                parent_dots = parent_num.count('.')
                current_dots = num.count('.')
                
                if current_dots == parent_dots + 1:
                    title = get_section_title(div)
                    direct_text = get_section_text(div)
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
    
    all_divs = body.findall('./tei:div', ns)
    candidates = []
    
    # Find all matching sections - check if title CONTAINS any keyword
    for idx, div in enumerate(all_divs):
        title = get_section_title(div)
        section_num = get_section_number(div)
        title_lower = title.lower().strip()
        
        # Check if title contains any of the keywords
        for keyword in introduction_keywords:
            if keyword in title_lower:
                # Score based on how well it matches
                score = 100 if title_lower == keyword else 80
                candidates.append((score, idx, div, title, section_num))
                break  # Only count first match
    
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
        'section_type': 'introduction',
        'title': title,
        'section_number': section_num,
        'text': get_section_text(div),
        'subsections': subsections,
        'full_text': '\n\n'.join(all_text_parts)
    }


def update_extraction_results(output_dir: Path):
    """Update all extraction result JSON files in the output directory."""
    
    # Find all paper directories
    paper_dirs = [d for d in output_dir.iterdir() if d.is_dir() and d.name != '__pycache__']
    
    updated_count = 0
    skipped_count = 0
    
    for paper_dir in paper_dirs:
        paper_name = paper_dir.name
        
        # Find TEI XML file
        tei_file = paper_dir / f"{paper_name}.tei.xml"
        if not tei_file.exists():
            print(f"⚠️  Skipping {paper_name}: TEI file not found")
            skipped_count += 1
            continue
        
        # Find extraction results JSON
        json_file = paper_dir / f"{paper_name}_extraction_results.json"
        if not json_file.exists():
            print(f"⚠️  Skipping {paper_name}: JSON file not found")
            skipped_count += 1
            continue
        
        # Extract introduction
        print(f"📖 Extracting introduction for: {paper_name}")
        introduction = extract_introduction_from_tei(tei_file)
        
        if introduction['found']:
            print(f"   ✓ Found: {introduction['title']}")
            print(f"   Text: {len(introduction['text'])} chars")
            print(f"   Subsections: {len(introduction['subsections'])}")
        else:
            print(f"   ✗ Introduction not found")
        
        # Load existing JSON
        with open(json_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
        
        # Add introduction (insert at beginning of sections)
        results['introduction'] = introduction
        
        # Save updated JSON
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"   💾 Updated: {json_file}")
        updated_count += 1
    
    print(f"\n{'='*70}")
    print(f"Summary:")
    print(f"  Updated: {updated_count} papers")
    print(f"  Skipped: {skipped_count} papers")
    print(f"{'='*70}")


if __name__ == "__main__":
    # Update both output directories
    output_dirs = [
        Path("./output_grobid_marker"),
        Path("./output_grobid_pymupdf")
    ]
    
    for output_dir in output_dirs:
        if output_dir.exists():
            print(f"\n{'='*70}")
            print(f"Processing: {output_dir}")
            print(f"{'='*70}")
            update_extraction_results(output_dir)
        else:
            print(f"\n⚠️  Directory not found: {output_dir}")
