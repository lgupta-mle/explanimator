# Research Paper GraphViz

A tool for generating visualizations and animations from research papers using Manim and AI-powered parsing.

## Features

- PDF parsing and text extraction
- Automated Manim animation generation
- Audio generation for video narration
- Graph visualization of research concepts

## Installation

```bash
pip install -e .
```

## Development Installation

```bash
pip install -e ".[dev]"
```

## Usage

```python
from research_viz import preprocessing, manim_generator

# Parse a research paper PDF
# Generate visualizations
# Create animations
```

## License

MIT
# Research Paper PDF Parser

A hybrid PDF parsing system that extracts structured content from research papers, including methodology sections, figures, tables, and metadata.

## Overview

This project provides two hybrid PDF parsers:

1. **pdf_parser1.py** (GROBID + Marker): Best for text-based PDFs with complex layouts
2. **pdf_parser2.py** (GROBID + PyMuPDF): Faster alternative with comprehensive image extraction

Both parsers combine:
- **GROBID**: Extracts text, sections, methodology, and metadata with captions
- **Marker/PyMuPDF**: Extracts actual images and tables from PDFs

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

### Running pdf_parser1.py in new terminal (keep gradle or docker running) (GROBID + Marker)

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