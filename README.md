# Research Paper to Video Pipeline

Automatically generate educational explainer videos from research papers using AI-powered code generation, Manim animations, and synchronized TTS narration.

## Overview

This tool converts research papers (PDFs) into 3Blue1Brown-style animated explainer videos with synchronized narration:

```
PDF → Explanation → Audio Beats → Manim Code (with timing) → Rendered Videos → Synced & Stitched Video
```

### Pipeline Flow

1. **PDF → Explanation**
   - Extracts and structures paper content
   - LLM generates educational breakdown per segment

2. **Audio Generation FIRST** 
   - Splits narration into beats (sentences)
   - Generates TTS audio with precise timing
   - Creates a json file with exact durations

3. **Code Generation with Timing** 
   - Loads beat timeline for precise timing info
   - LLM generates Manim code per segment
   - Validates by executing code by using RAG to retrieve the manim documentation and store it as vector db, such that it can be referenced in case an error occurs.

4. **Video Rendering & Sync** 
   - Renders each segment with Manim
   - **Measures** actual video duration
   - **Adjusts** video speed to match audio exactly
   - Merges audio with speed-adjusted video

5. **Stitching** - Concatenates all synced segments → Final video

## Features

- **AI Explanation**: LLM (Gemini-3.1-Pro) generates 3Blue1Brown-style educational explanations from research paper PDF as input
- **Beat-Synchronized Audio**: OpenAI TTS with precise sentence-level timing
- **Manim Code Generation**: Executable animation code with automatic error fixing via RAG
- **Measured Duration Sync**: Mesures the duration of each segment and adjusts the video speed to match the audio
- **Configurable Speed Adjustment**: Segment-level or beat-level sync modes (Preferred and default: segment-level sync)
- **Auto-Stitching**: Seamlessly combines all segments

## Quick Start

### Prerequisites

```bash
# Python 3.10+
python --version

# Install dependencies
pip install -r requirements.txt

# Set up API keys
export OPENAI_API_KEY="your-openai-key"
export OPENROUTER_API_KEY="your-openrouter-key"  # For Claude/GPT access

# Install ffmpeg (for audio/video processing)
brew install ffmpeg  # macOS
```

### Run the Complete Pipeline

```bash
# From existing explanation JSON
python -m research_viz.manim_generator.pdf_to_manim_pipeline \
  --pdf-path resources/attention_is_all_you_need.pdf \
  --output-dir output/final \
  --generate-audio \
  --render-video \
  --video-quality l \
  --model-name google/gemini-3.1-pro-preview \
  --tts-voice nova
```

This will:
1. ✓ Load research paper PDF and create an intuitive explanation (stored in JSON)
2. ✓ Generate TTS audio with beat-level timing → `beat_timeline.json`
3. ✓ Generate Manim code (with beat timing info, validated by execution)
4. ✓ Render each segment to video using Manim
5. ✓ Measure video segment duration, adjust speed to match audio
6. ✓ Merge adjusted video with audio (segment-level sync)
7. ✓ Stitch all synced segments into final video

**Output**: `output/final/final_video.mp4`

## Pipeline Options

### Basic Usage (Code Generation Only)

```bash
python -m research_viz.manim_generator.pdf_to_manim_pipeline \
  --pdf-path research_paper.pdf \
  --output-dir output
```

Generates Manim code without rendering videos.

### With Audio Only

```bash
python -m research_viz.manim_generator.pdf_to_manim_pipeline \
  --pdf-path research_paper.pdf \
  --generate-audio \
  --tts-voice nova
```

Generates code and audio files (no video rendering).

### Full Pipeline (Recommended)

```bash
python -m research_viz.manim_generator.pdf_to_manim_pipeline \
  --pdf-path research_paper.pdf \
  --generate-audio \
  --render-video \
  --video-quality m \
  --tts-voice nova
```

Generates everything including final stitched video.

### Resume from Existing Files

The pipeline automatically skips completed steps:
- If code exists: skips generation
- If audio exists: skips TTS
- If videos exist: skips rendering

Just run the same command again - it will pick up where it left off!

## Configuration

### Video Quality

```bash
--video-quality l  # Low (480p15) - fast, good for testing
--video-quality m  # Medium (720p30) - balanced
--video-quality h  # High (1080p60) - best quality, slow
```

### TTS Voices

OpenAI TTS provides six natural voices:

```bash
--tts-voice nova     # Natural, clear (default)
--tts-voice alloy    # Neutral, balanced
--tts-voice echo     # Clear, warm
--tts-voice fable    # Expressive, storytelling
--tts-voice onyx     # Deep, authoritative
--tts-voice shimmer  # Bright, energetic
```

### Model Selection

```bash
--model-name google/gemini-3.1-pro-preview  # Preferred
--model-name openai/gpt-5.2-codex         # Alternative
```

### Code Generation Retries

```bash
--max-retries 3  # Number of attempts per scene (default: 3)
```

## Output Structure

```
output/
├── attention_is_all_you_need_animation.py    # Generated Manim code
├── attention_is_all_you_need_scene_metadata.json  # Scene metadata
├── audio_beats/
│   ├── seg_01_beat_1.wav                     # TTS audio files
│   ├── seg_01_beat_2.wav
│   └── beat_timeline.json                    # Audio timing metadata
├── synced_scene_1.mp4                        # Individual synced videos
├── synced_scene_2.mp4
└── final_video.mp4                           # Complete stitched video
```

## Advanced Usage

### Standalone Audio Generation

```bash
python -m research_viz.audio_generator.beat_sync_tts \
  --pdf-path research_paper.pdf \
  --output-dir audio_output \
  --voice nova
```

### Manual Rendering

```bash
# Render specific scene
manim -pqm output/animation.py SceneClassName

# Render all scenes
manim -pqm output/animation.py -a
```

## Project Structure

### Core Pipeline Files (Runtime)
```
src/research_viz/
├── manim_generator/
│   ├── pdf_to_manim_pipeline.py          # Main pipeline orchestrator
│   ├── pdf_explanation_generator.py      # PDF → Educational explanation
│   └── prompts/
│       └── manim_code_generation_prompt.txt  # LLM instructions for code
├── audio_generator/
│   └── beat_sync_tts.py                  # Beat-synchronized TTS (OpenAI)
├── preprocessing/
│   └── manim_db.py                       # RAG for Manim documentation
└── schemas/
    ├── explanation_schemas.py            # Data structures
    └── manim_docs_schemas.py             # RAG schemas
```

### Setup Files (One-Time)
```
src/research_viz/preprocessing/
├── manim_docs_scraper.py       # Scrape Manim docs
├── manim_docs_chunker.py       # Split into chunks
├── manim_docs_embedder.py      # Generate embeddings
└── build_manim_index.py        # Build ChromaDB index
```

**Setup**: Run once to create RAG database in `data/manim_docs/vector_db/chroma_db/`

See [PIPELINE_FILES.md](PIPELINE_FILES.md) for detailed dependency mapping.

## Audio-Video Synchronization

### Sync Modes

The pipeline supports configurable synchronization modes to ensure animations match narration timing:

#### **Segment-Level Sync** (Default, Recommended)

Adjusts entire segment video to match segment audio duration.

```bash
python -m research_viz.manim_generator.pdf_to_manim_pipeline \
  --explanation-path output/explanation.json \
  --generate-audio --render-video \
  --sync-mode segment \
  --max-speed-change 0.3
```

#### **Beat-Level Sync** (Experimental)

Adjusts each beat separately for frame-perfect synchronization.

```bash
python -m research_viz.manim_generator.pdf_to_manim_pipeline \
  --explanation-path output/explanation.json \
  --generate-audio --render-video \
  --sync-mode beat \
  --max-speed-change 0.2
```

**Transform research papers into engaging educational videos automatically!** 📄 → 🎬
