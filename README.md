# Research Paper PDF Parser

A hybrid PDF parsing system that extracts structured content from research papers, including methodology sections, figures, tables, and metadata.

## Overview

This project provides two hybrid PDF parsers:

1. **pdf_parser1.py** (GROBID + Marker): Best for text-based PDFs with complex layouts
2. **pdf_parser2.py** (GROBID + PyMuPDF): Faster alternative with comprehensive image extraction

Both parsers combine:
- **GROBID**: Extracts text, sections, methodology, and metadata with captions
- **Marker/PyMuPDF**: Extracts actual images and tables from PDFs

## Features

- ✅ **Methodology Extraction**: Automatically finds and extracts methodology sections with nested subsections
- ✅ **Figure Extraction**: Extracts images with GROBID captions
- ✅ **Table Extraction**: Extracts tables in markdown format with captions
- ✅ **Hierarchical Structure**: Correctly handles nested subsections using section numbering
- ✅ **Smart Section Matching**: Prioritizes exact matches for "Methodology" sections

## Quick Start

```bash
# 1. Clone and setup
git clone https://github.com/your-repo/research-paper-graphviz.git
cd research-paper-graphviz
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start GROBID (in separate terminal)
docker run --rm -p 8070:8070 lfoppiano/grobid:0.8.0

# 4. Add PDFs to resources/ folder
mkdir -p resources
cp /path/to/your/paper.pdf resources/

# 5. Run parser
python run_parser1.py  # or run_parser2.py
```

## Prerequisites

### System Requirements

- **Python**: 3.10 or higher (required)
- **Java**: JDK 21 or higher (required for GROBID)
- **Operating System**: macOS, Linux, or Windows

### Required Software

1. **Git**: For cloning repositories
2. **Gradle**: For building GROBID (or use pre-built Docker image)

## Installation

### Step 1: Clone This Repository

```bash
git clone https://github.com/your-repo/research-paper-graphviz.git
cd research-paper-graphviz
```

### Step 2: Set Up Python Environment

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate  # On Windows
```

### Step 3: Install Python Dependencies

Install all dependencies using the requirements file:

```bash
pip install -r requirements.txt
```

This will install:
- **Core dependencies**: `requests`, `Pillow` (required for both parsers)
- **marker-pdf**: For pdf_parser1.py
- **pymupdf**: For pdf_parser2.py (version 1.23.0+ for table extraction)

**Note**: Python 3.10+ is required for all parsers.

#### Alternative: Install for Specific Parser Only

**For pdf_parser1.py only** (GROBID + Marker):
```bash
pip install requests Pillow marker-pdf
```

**For pdf_parser2.py only** (GROBID + PyMuPDF):
```bash
pip install requests Pillow pymupdf>=1.23.0
```

### Step 4: Install and Run GROBID

GROBID is a machine learning library for extracting structured information from scholarly documents.

#### Option A: Using Docker (Recommended - Easiest)

```bash
# Pull the GROBID Docker image
docker pull lfoppiano/grobid:0.8.0

# Run GROBID server
docker run --rm -p 8070:8070 lfoppiano/grobid:0.8.0
```

GROBID will be available at `http://localhost:8070`

#### Option B: Building from Source

1. **Clone GROBID repository**:
```bash
cd ..  # Go to parent directory
git clone https://github.com/kermitt2/grobid.git
cd grobid
```

2. **Build GROBID** (requires Gradle):
```bash
./gradlew clean install
```

3. **Run GROBID server**:
```bash
./gradlew run
```

GROBID will start on `http://localhost:8070`

**Verify GROBID is running**:
```bash
curl http://localhost:8070/api/isalive
```
Should return `true`

### Step 5: Prepare Input PDFs

Place your research paper PDFs in the `resources/` directory:

```bash
mkdir -p resources
# Copy your PDFs to resources/
cp /path/to/your/paper.pdf resources/
```

## Usage

### Running pdf_parser1.py (GROBID + Marker)

```bash
python run_parser1.py
```

**Output**: `./output_grobid_marker/`

**Best for**:
- Text-based PDFs with complex layouts
- Papers with equations and mathematical notation
- High-quality text extraction

### Running pdf_parser2.py (GROBID + PyMuPDF)

```bash
python run_parser2.py
```

**Output**: `./output_grobid_pymupdf/`

**Best for**:
- Faster processing
- Comprehensive image extraction
- Works with Python 3.12+

## Output Structure

Each parser creates the following structure:

```
output_*/
├── paper_name/
│   ├── paper_name.tei.xml              # GROBID TEI XML output
│   ├── paper_name_extraction_results.json  # Structured extraction results
│   ├── images/
│   │   ├── paper_name_image_1.png
│   │   ├── paper_name_image_2.png
│   │   └── ...
│   └── tables/
│       ├── paper_name_table_1.md
│       ├── paper_name_table_2.md
│       └── ...
└── extraction_summary.json             # Summary of all processed papers
```

### JSON Output Format

```json
{
  "paper_name": "attention_is_all_you_need",
  "methodology": {
    "found": true,
    "title": "Model Architecture",
    "section_number": "3",
    "text": "Direct text from section...",
    "subsections": [
      {
        "title": "Encoder and Decoder Stacks",
        "section_number": "3.1",
        "text": "...",
        "level": 1,
        "subsections": []
      }
    ],
    "full_text": "Complete text including all subsections..."
  },
  "figures": {
    "count": 5,
    "items": [
      {
        "figure_number": 1,
        "image_file": "path/to/image.png",
        "caption": "Figure caption from GROBID",
        "width": 800,
        "height": 600
      }
    ]
  },
  "tables": {
    "count": 3,
    "items": [
      {
        "table_number": 1,
        "file": "path/to/table.md",
        "caption": "Table caption from GROBID",
        "rows": 10,
        "columns": 5,
        "has_content": true
      }
    ]
  }
}
```

## Configuration

### Changing GROBID URL

If GROBID is running on a different host/port:

```python
# In run_parser1.py or run_parser2.py
parser = HybridResearchPaperParser(
    grobid_url="http://your-server:8070",
    output_base_dir="./output",
    timeout=180
)
```

### Customizing Methodology Keywords

Edit the `methodology_keywords` list in the parser files:

```python
methodology_keywords = [
    'method', 'methods', 'methodology',
    'approach', 'implementation',
    # Add your custom keywords here
]
```

## Troubleshooting

### GROBID Connection Error

**Error**: `Connection refused` or `GROBID error 503`

**Solution**:
1. Verify GROBID is running: `curl http://localhost:8070/api/isalive`
2. Check Docker container: `docker ps`
3. Restart GROBID server

### Marker Installation Issues

**Error**: `marker-pdf` installation fails

**Solution**: 
1. Ensure you have Python 3.10+ installed
2. Try upgrading pip: `pip install --upgrade pip`
3. If issues persist, use `pdf_parser2.py` instead

### PyMuPDF Table Extraction Not Working

**Error**: Tables show `status: "metadata_only"`

**Solution**: Upgrade PyMuPDF:
```bash
pip install --upgrade pymupdf
```

Verify version:
```bash
python -c "import fitz; print(fitz.__version__)"
```
Should be 1.23.0 or higher.

### Empty Subsections

**Issue**: Methodology section found but `subsections: []`

**Cause**: GROBID outputs flat structure; hierarchy is built from section numbers

**Solution**: This is now fixed in the latest version. Ensure you have the updated parsers.

## Development

### Project Structure

```
research-paper-graphviz/
├── src/
│   └── research_viz/
│       └── preprocessing/
│           ├── pdf_parser1.py    # GROBID + Marker
│           └── pdf_parser2.py    # GROBID + PyMuPDF
├── run_parser1.py                # Runner for parser1
├── run_parser2.py                # Runner for parser2
├── resources/                    # Input PDFs
├── output_grobid_marker/         # Parser1 output
├── output_grobid_pymupdf/        # Parser2 output
└── README.md
```

### Running Tests

To test methodology extraction on existing TEI XML files:

```bash
# Test files should be in output directories
python -c "from src.research_viz.preprocessing.pdf_parser1 import HybridResearchPaperParser; \
           parser = HybridResearchPaperParser(); \
           parser.parse_pdf('resources/your_paper.pdf')"
```

## Key Implementation Details

### Methodology Extraction Algorithm

1. **Flat Structure Handling**: GROBID outputs sections as siblings, not nested children
2. **Section Number Parsing**: Extracts numbers like "3", "3.1", "3.2.1" from `<head n="...">` attributes
3. **Hierarchy Building**: Reconstructs nested structure by analyzing section number patterns
4. **Smart Matching**: Scores section titles to find the best methodology match:
   - Exact match "methodology" = score 100
   - Contains "method" as word = score 80
   - Secondary keywords = score 50

### Table Extraction

- **Parser1 (Marker)**: Extracts markdown tables using regex pattern `r'((?:\|.+\|\n)+)'`
- **Parser2 (PyMuPDF)**: Uses `page.find_tables()` API to detect and extract tables

Both save tables as `.md` files and merge with GROBID captions.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

[Add your license here]

## Acknowledgments

- **GROBID**: Machine learning library for extracting structured information from scholarly documents
- **Marker**: PDF to Markdown converter with excellent layout preservation
- **PyMuPDF**: Fast PDF processing library with comprehensive extraction capabilities

## Support

For issues, questions, or contributions, please open an issue on GitHub.
