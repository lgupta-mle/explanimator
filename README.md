# Research Paper to Video Pipeline

Automatically generate educational explainer videos from research papers using AI-powered code generation, Manim animations, and synchronized TTS narration.

## Overview

This tool converts research papers (PDFs) into 3Blue1Brown-style animated explainer videos with synchronized narration:

```
PDF → Explanation → Manim Code → Audio → Rendered Videos → Final Video
```

## Features

- **PDF Parsing**: Extracts structured content from research papers using GROBID
- **AI Explanation**: Generates educational explanations using LLMs (Claude/GPT)
- **Manim Code Generation**: Creates executable Manim animation code with retry logic
- **TTS Audio**: Generates natural speech using OpenAI TTS API
- **Video Syncing**: Synchronizes animations with narration (extends video if needed)
- **Auto-Stitching**: Combines all scenes into one final video

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
  --explanation-path src/research_viz/manim_generator/output/attention_is_all_you_need_explanation.json \
  --output-dir output/final \
  --generate-audio \
  --render-video \
  --video-quality l \
  --model-name openai/gpt-5.2-codex \
  --tts-voice nova
```

This will:
1. ✓ Load explanation (or generate from PDF with `--pdf-path`)
2. ✓ Generate Manim animation code for each segment (with execution validation)
3. ✓ Generate TTS audio for each segment's narration
4. ✓ Render each scene to video using Manim
5. ✓ Sync audio with video (extends video if audio is longer)
6. ✓ Stitch all scenes into final video

**Output**: `output/final/final_video.mp4`

## Pipeline Options

### Basic Usage (Code Generation Only)

```bash
python -m research_viz.manim_generator.pdf_to_manim_pipeline \
  --explanation-path explanation.json \
  --output-dir output
```

Generates Manim code without rendering videos.

### With Audio Only

```bash
python -m research_viz.manim_generator.pdf_to_manim_pipeline \
  --explanation-path explanation.json \
  --generate-audio \
  --tts-voice nova
```

Generates code and audio files (no video rendering).

### Full Pipeline (Recommended)

```bash
python -m research_viz.manim_generator.pdf_to_manim_pipeline \
  --explanation-path explanation.json \
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
--model-name anthropic/claude-sonnet-4.5  # Best for code generation
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

## How It Works

### 1. Explanation Generation

Converts PDF → structured educational explanation:
- Running example (concrete walkthrough)
- Segments (one per key concept)
- Narration scripts (what to say)
- Visual descriptions (what to show)

### 2. Manim Code Generation

Uses LLM to generate executable Manim code:
- Validates by actually running Manim
- Retries with RAG if errors occur
- Uses vector DB of Manim documentation

### 3. Audio Generation

Splits narration into beats and generates TTS:
- Beat = sentence or phrase (~8-25 words)
- OpenAI TTS generates natural speech
- Tracks exact duration per beat

### 4. Video Rendering & Syncing

Renders animations and syncs with audio:
- Manim renders each scene
- Compares video duration vs audio duration
- Extends video (freeze last frame) if audio is longer
- Merges audio with video using ffmpeg

### 5. Stitching

Concatenates all synced scenes into final video.

## Advanced Usage

### Generate Explanation from PDF

```bash
# Requires GROBID running on port 8070
docker run --rm -p 8070:8070 lfoppiano/grobid:0.8.0

# Generate explanation
python -m research_viz.manim_generator.pdf_explanation_generator \
  --pdf-path papers/attention.pdf \
  --output-path output/explanation.json
```

### Standalone Audio Generation

```bash
python -m research_viz.audio_generator.beat_sync_tts \
  --explanation-path explanation.json \
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

```
research-paper-graphviz/
├── src/research_viz/
│   ├── manim_generator/
│   │   ├── pdf_to_manim_pipeline.py      # Main pipeline
│   │   ├── pdf_explanation_generator.py  # PDF → Explanation
│   │   └── prompts/                      # LLM prompts
│   ├── audio_generator/
│   │   ├── beat_sync_tts.py             # OpenAI TTS integration
│   │   └── workflow.py                   # Audio workflow
│   └── preprocessing/
│       └── manim_db.py                   # RAG for Manim docs
├── requirements.txt
└── README.md
```

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

**How it works**:
1. Render segment animation (LLM creates code without worrying about exact timing)
2. Measure actual video duration (e.g., 53.4s)
3. Get exact audio duration (e.g., 47.8s)
4. Adjust video speed to match: 53.4s → 47.8s (11.7% faster)
5. Merge adjusted video with audio → perfect sync!

**Benefits**:
- ✅ Removes reliance on unreliable LLM timing calculations
- ✅ Guarantees duration matching (measured, not estimated)
- ✅ Smooth playback (typically < 20% speed change)
- ✅ Solves desynchronization at the root

#### **Beat-Level Sync** (Experimental)

Adjusts each beat separately for frame-perfect synchronization.

```bash
python -m research_viz.manim_generator.pdf_to_manim_pipeline \
  --explanation-path output/explanation.json \
  --generate-audio --render-video \
  --sync-mode beat \
  --max-speed-change 0.2
```

**Status**: Currently falls back to segment-level with warning (per-beat rendering not yet implemented).

### Configuration Parameters

- `--sync-mode`: `"segment"` (default) or `"beat"`
- `--max-speed-change`: Maximum video speed adjustment (default: `0.3` = 30%)

**Speed change perception**:
- 0-10%: Imperceptible
- 10-20%: Barely noticeable
- 20-30%: Acceptable for educational content
- >30%: Falls back to extend/trim to preserve naturalness

See [SYNC_MODES.md](SYNC_MODES.md) for detailed documentation.

## Troubleshooting

### "OpenAI API key not set"

```bash
export OPENAI_API_KEY="sk-..."
# Add to ~/.bashrc or ~/.zshrc for persistence
```

### "Manim render failed"

Check generated code in output directory:
```bash
cat output/animation.py
```

The pipeline retries with RAG if Manim execution fails.

### "ffmpeg not found"

```bash
brew install ffmpeg  # macOS
sudo apt install ffmpeg  # Ubuntu/Debian
```

### Videos have no audio

Ensure:
- `--generate-audio` flag is set
- `OPENAI_API_KEY` is configured
- Audio files exist in `audio_beats/` directory

### "Rendered video not found"

Check Manim output quality directory matches setting:
- `-ql` → `media/videos/temp_scene_X/480p15/`
- `-qm` → `media/videos/temp_scene_X/720p30/`
- `-qh` → `media/videos/temp_scene_X/1080p60/`

## Performance

Typical pipeline timing (5 segments):
- **Explanation generation**: 2-5 minutes (LLM calls)
- **Code generation**: 5-10 minutes (includes execution validation)
- **Audio generation**: 1-2 minutes (OpenAI TTS API)
- **Video rendering**: 5-15 minutes (Manim + ffmpeg, depends on quality)
- **Syncing & stitching**: 2-3 minutes (ffmpeg)

**Total**: ~15-35 minutes for complete pipeline

## Examples

Example output video from "Attention is All You Need" paper:
- 5 segments explaining Transformer architecture
- 4 minutes total duration
- Synchronized narration with animations
- Beat-level audio sync

## License

MIT

## Contributing

Contributions welcome! Key areas:
- Better Manim code generation prompts
- Improved error handling and retries
- Support for more TTS providers
- Enhanced video quality options

---

**Transform research papers into engaging educational videos automatically!** 📄 → 🎬
