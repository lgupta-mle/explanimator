import os
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
import requests
import xml.etree.ElementTree as ET


class GrobidResearchPaperParser:
    def __init__(self, base_url: str = "http://localhost:8070", output_base_dir: str = "./output_grobid", timeout: int = 180):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.output_base_dir = Path(output_base_dir)
        self.output_base_dir.mkdir(parents=True, exist_ok=True)
        self.methodology_keywords = [
            'method', 'methods', 'methodology', 'methodologies',
            'materials and methods', 'experimental setup', 'experimental design',
            'approach', 'experimental', 'implementation', 'system design',
            'experimental procedure', 'procedure', 'experimental methods', 'technique',
            'model architecture', 'architecture'
        ]

    def parse_directory(self, directory_path: str) -> List[Dict[str, Any]]:
        directory = Path(directory_path)
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        pdf_files = sorted(directory.glob("*.pdf"))
        if not pdf_files:
            print(f"No PDF files found in {directory}")
            return []

        print(f"\nFound {len(pdf_files)} PDF files to process")
        print("=" * 70)

        results: List[Dict[str, Any]] = []
        for pdf_file in pdf_files:
            try:
                res = self.parse_paper(str(pdf_file))
                results.append(res)
            except Exception as e:
                results.append({
                    "paper_name": pdf_file.stem,
                    "source_file": str(pdf_file),
                    "status": "error",
                    "error": str(e),
                })
                print(f"✗ Error processing {pdf_file.name}: {e}")

        summary_file = self.output_base_dir / "extraction_summary.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump({
                "total_papers": len(pdf_files),
                "successful": sum(1 for r in results if r.get("status") == "success"),
                "failed": sum(1 for r in results if r.get("status") == "error"),
                "results": results,
            }, f, indent=2, ensure_ascii=False)

        print("\n" + "=" * 70)
        print(f"Processing complete! Summary saved to: {summary_file}")
        return results

    def parse_paper(self, pdf_path: str, paper_name: Optional[str] = None) -> Dict[str, Any]:
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        if paper_name is None:
            paper_name = pdf_path.stem

        print(f"\nProcessing: {paper_name}")
        paper_output_dir = self.output_base_dir / paper_name
        figures_dir = paper_output_dir / "figures"
        tables_dir = paper_output_dir / "tables"
        paper_output_dir.mkdir(parents=True, exist_ok=True)
        figures_dir.mkdir(parents=True, exist_ok=True)
        tables_dir.mkdir(parents=True, exist_ok=True)

        tei_xml = self._process_with_grobid(str(pdf_path))
        tei_path = paper_output_dir / f"{paper_name}.tei.xml"
        with open(tei_path, "w", encoding="utf-8") as f:
            f.write(tei_xml)

        root = ET.fromstring(tei_xml)
        methodology = self._extract_methodology_from_tei(root)
        figures = self._extract_figures_from_tei(root, figures_dir, paper_name)
        tables = self._extract_tables_from_tei(root, tables_dir, paper_name)

        results = {
            "paper_name": paper_name,
            "source_file": str(pdf_path),
            "output_directory": str(paper_output_dir),
            "tei_file": str(tei_path),
            "methodology": methodology,
            "figures": {"count": len(figures), "items": figures},
            "tables": {"count": len(tables), "items": tables},
            "status": "success",
        }

        results_file = paper_output_dir / f"{paper_name}_extraction_results.json"
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"  Results saved to: {results_file}")
        return results

    def _process_with_grobid(self, pdf_path: str) -> str:
        url = f"{self.base_url}/api/processFulltextDocument"
        files = {"input": open(pdf_path, "rb")}
        data = {
            "consolidateHeader": 1,
            "consolidateCitations": 1,
            "teiCoordinates": "seg",
            "segmentSentences": 1,
            "generateIDs": 1,
        }
        try:
            resp = requests.post(url, files=files, data=data, timeout=self.timeout)
        finally:
            files["input"].close()
        if resp.status_code != 200:
            raise RuntimeError(f"GROBID error {resp.status_code}: {resp.text[:500]}")
        return resp.text

    def _extract_methodology_from_tei(self, root: ET.Element) -> Dict[str, Any]:
        ns = {"tei": self._ns(root)}
        body = root.find(".//tei:text/tei:body", ns)
        if body is None:
            return {"found": False, "title": None, "text": "", "subsections": []}

        def text_content(el: Optional[ET.Element]) -> str:
            if el is None:
                return ""
            return re.sub(r"\s+", " ", " ".join(el.itertext())).strip()

        def section_title(div: ET.Element) -> str:
            head = div.find("tei:head", ns)
            return text_content(head)

        def gather_text(div: ET.Element) -> str:
            paras = []
            for p in div.findall(".//tei:p", ns):
                txt = text_content(p)
                if txt:
                    paras.append(txt)
            return "\n\n".join(paras)

        def gather_subsections(div: ET.Element) -> List[Dict[str, Any]]:
            subs: List[Dict[str, Any]] = []
            for sub in div.findall("tei:div", ns):
                ttl = section_title(sub)
                text = gather_text(sub)
                subs.append({"title": ttl, "text": text})
            return subs

        # find first section whose title matches keywords
        for div in body.findall("tei:div", ns):
            title = section_title(div)
            title_low = title.lower()
            if any(k in title_low for k in self.methodology_keywords):
                return {
                    "found": True,
                    "title": title,
                    "text": gather_text(div),
                    "subsections": gather_subsections(div),
                }
        return {"found": False, "title": None, "text": "", "subsections": []}

    def _extract_figures_from_tei(self, root: ET.Element, figures_dir: Path, paper_name: str) -> List[Dict[str, Any]]:
        ns = {"tei": self._ns(root)}
        items: List[Dict[str, Any]] = []

        def text_content(el: Optional[ET.Element]) -> str:
            if el is None:
                return ""
            return re.sub(r"\s+", " ", " ".join(el.itertext())).strip()

        idx = 0
        for fig in root.findall(".//tei:figure", ns):
            idx += 1
            caption_el = fig.find("tei:figDesc", ns) or fig.find("tei:head", ns) or fig.find("tei:p", ns)
            caption = text_content(caption_el)
            graphic = fig.find(".//tei:graphic", ns)
            url = graphic.get("url") if graphic is not None else None

            # Save caption to text file for traceability
            cap_path = figures_dir / f"{paper_name}_figure_{idx}_caption.txt"
            with open(cap_path, "w", encoding="utf-8") as f:
                f.write(caption)

            items.append({
                "figure_number": idx,
                "caption": caption,
                "graphic_url": url,
                "caption_file": str(cap_path),
                "status": "metadata_only" if url is None else "referenced",
            })
        return items

    def _extract_tables_from_tei(self, root: ET.Element, tables_dir: Path, paper_name: str) -> List[Dict[str, Any]]:
        ns = {"tei": self._ns(root)}
        items: List[Dict[str, Any]] = []

        def text_content(el: Optional[ET.Element]) -> str:
            if el is None:
                return ""
            return re.sub(r"\s+", " ", " ".join(el.itertext())).strip()

        idx = 0
        # Tables are often encoded as <figure type="table"> wrappers containing a <table>.
        for fig in root.findall(".//tei:figure[@type='table']", ns):
            tbl = fig.find("tei:table", ns)
            if tbl is None:
                continue
            idx += 1
            caption_el = fig.find("tei:head", ns) or fig.find("tei:figDesc", ns)
            caption = text_content(caption_el)

            xml_path = tables_dir / f"{paper_name}_table_{idx}.tei.xml"
            with open(xml_path, "w", encoding="utf-8") as f:
                f.write(ET.tostring(tbl, encoding="unicode"))

            items.append({
                "table_number": idx,
                "caption": caption,
                "tei_file": str(xml_path),
                "status": "saved_xml",
            })

        # Fallback: any bare <table> not wrapped in a figure
        if idx == 0:
            for tbl in root.findall(".//tei:table", ns):
                idx += 1
                xml_path = tables_dir / f"{paper_name}_table_{idx}.tei.xml"
                with open(xml_path, "w", encoding="utf-8") as f:
                    f.write(ET.tostring(tbl, encoding="unicode"))
                items.append({
                    "table_number": idx,
                    "caption": "",
                    "tei_file": str(xml_path),
                    "status": "saved_xml",
                })
        return items

    def _ns(self, root: ET.Element) -> str:
        # get default namespace from TEI root tag like {http://www.tei-c.org/ns/1.0}TEI
        if root.tag.startswith("{"):
            return root.tag.split("}")[0].strip("{")
        return "http://www.tei-c.org/ns/1.0"
