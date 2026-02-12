# Audio Generation for Research Paper Videos

This module generates TTS audio synchronized with Manim animations for research paper explainer videos.

## Overview

The audio generator uses OpenAI's TTS API to create narration audio that syncs with Manim animations:

1. **Beat Splitting**: Splits narration into beats (sentences/phrases, ~8-25 words each)
2. **TTS Generation**: Generates audio per beat using OpenAI TTS
3. **Duration Tracking**: Measures exact audio duration for each beat
4. **Video Syncing**: Extends or syncs video animations to match audio length

## Requirements

- **OpenAI API Key**: Set `OPENAI_API_KEY` environment variable
- **ffmpeg**: For audio/video processing

```bash
# Set up OpenAI API key
export OPENAI_API_KEY="your-api-key-here"

# Install ffmpeg (macOS)
brew install ffmpeg
```

## Quick Start

The easiest way to use this module is through the complete pipeline in `pdf_to_manim_pipeline.py`:

```bash
python -m research_viz.manim_generator.pdf_to_manim_pipeline \
  --explanation-path path/to/explanation.json \
  --output-dir output/test_run \
  --generate-audio \
  --render-video \
  --video-quality l \
  --tts-voice nova
```

This will:
1. Generate Manim code for all segments
2. Generate TTS audio for each segment
3. Render each Manim scene to video
4. Sync audio with each video (extending video if needed)
5. Stitch all videos into one final video with synchronized narration

## Available Voices

OpenAI TTS provides six voices:
- `alloy` - Neutral, balanced
- `echo` - Clear, warm
- `fable` - Expressive, storytelling
- `onyx` - Deep, authoritative
- `nova` - Natural, clear (default)
- `shimmer` - Bright, energetic

## Module Architecture

```
audio_generator/
├── __init__.py                    # Module exports
├── beat_sync_tts.py              # TTS generation using OpenAI
├── beat_duration_allocator.py    # Duration allocation (legacy)
├── beat_synced_manim_generator.py # Placeholder animation generator
├── workflow.py                    # Standalone workflow
└── README.md                      # This file
```

## Usage Examples

### Standalone Audio Generation

Generate audio without video rendering:

```bash
python -m research_viz.audio_generator.beat_sync_tts \
  --explanation-path output/explanation.json \
  --output-dir output/audio_beats \
  --voice nova \
  --min-words 8 \
  --max-words 25
```

Output:
- `output/audio_beats/seg_01_beat_1.wav`, `seg_01_beat_2.wav`, ...
- `output/audio_beats/beat_timeline.json` (metadata with durations)

### Complete Workflow (Standalone)

```bash
python -m research_viz.audio_generator.workflow \
  --explanation-path output/explanation.json \
  --voice nova \
  --min-words 8 \
  --max-words 25
```

This generates beat timeline, allocations, and placeholder Manim code (not integrated with LLM code generation).

### API Usage

```python
from research_viz.audio_generator import generate_beat_timeline, OPENAI_VOICES

# Generate audio beats
timeline = generate_beat_timeline(
    explanation_path="output/explanation.json",
    output_dir="output/audio_beats",
    voice="nova",
    min_words=8,
    max_words=25
)

# Available voices
print(OPENAI_VOICES)  # ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']
```

## Output Structure

```
output/
├── audio_beats/
│   ├── seg_01_beat_1.wav          # Audio for segment 1, beat 1
│   ├── seg_01_beat_2.wav
│   ├── seg_02_beat_1.wav
│   ├── ...
│   └── beat_timeline.json         # Beat metadata with durations
└── synced_scene_1.mp4             # Video synced with audio
└── synced_scene_2.mp4
└── final_video.mp4                # All scenes stitched together
```

### beat_timeline.json Structure

```json
{
  "explanation_source": "path/to/explanation.json",
  "voice": "nova",
  "total_segments": 5,
  "segments": {
    "seg_01": {
      "beat_count": 8,
      "total_duration": 49.1,
      "beats": [
        {
          "beat_id": 1,
          "text": "Let's ask a simple question: How do you read?",
          "audio_file": "output/audio_beats/seg_01_beat_1.wav",
          "duration": 2.67,
          "start_time": 0.0
        }
      ]
    }
  }
}
```

## Configuration

### Beat Length

Control how narration is split into beats:

```bash
--min-words 8 --max-words 15   # Fine-grained (shorter beats, more files)
--min-words 15 --max-words 30  # Coarser (longer beats, fewer files)
```

### Voice Selection

```bash
--voice nova     # Default: natural and clear
--voice onyx     # Deeper, more authoritative
--voice shimmer  # Brighter, more energetic
```

### Video Quality

When using the full pipeline:

```bash
--video-quality l  # Low (480p15) - fast
--video-quality m  # Medium (720p30)
--video-quality h  # High (1080p60)
```

## How Video Syncing Works

1. **Audio First**: TTS generates audio with exact duration (e.g., 48.98s)
2. **Render Video**: Manim renders animation (e.g., 48.47s)
3. **Compare Durations**:
   - If audio > video: Extend video by freezing last frame
   - If video > audio: Trim video to match audio
4. **Merge**: Combine video and audio into synced output

This ensures narration always matches visuals perfectly!

## Performance

- **TTS Generation**: ~2-3s per beat (OpenAI API latency)
- **Beat Splitting**: Instant (<1s)
- **Video Syncing**: ~5-10s per scene (ffmpeg processing)

Total pipeline time for 5 segments: ~10-15 minutes (depends on Manim code generation retries and video rendering quality).

## Troubleshooting

### "OpenAI API key not set"

```bash
export OPENAI_API_KEY="your-api-key-here"
# Add to ~/.bashrc or ~/.zshrc for persistence
```

### "ffmpeg not found"

```bash
brew install ffmpeg  # macOS
sudo apt install ffmpeg  # Linux
```

### Invalid WAV duration calculation

The module automatically handles OpenAI TTS WAV files that have invalid frame counts in headers by calculating duration from file size.

### Audio out of sync

- Check that beat splitting isn't too aggressive (increase `--max-words`)
- Ensure video rendering completed without errors
- Verify audio files weren't corrupted during generation

## Migration from Orpheus-TTS

This module previously used Orpheus-TTS which required GPU/CUDA. It now uses OpenAI TTS API which:
- Works on macOS (no GPU required)
- Produces high-quality natural speech
- Requires API key but no local model setup
- Processes audio ~2-3x faster than real-time

Old voice names (dan, tara, leo, etc.) are replaced with OpenAI voices (nova, alloy, etc.).

## Integration with Pipeline

This module is fully integrated with `pdf_to_manim_pipeline.py`:

```bash
# Full pipeline: PDF → Explanation → Code → Audio → Video
python -m research_viz.manim_generator.pdf_to_manim_pipeline \
  --explanation-path explanation.json \
  --generate-audio \
  --render-video
```

The pipeline automatically:
- Skips audio generation if `beat_timeline.json` exists
- Skips video rendering if videos already exist
- Re-syncs and stitches on subsequent runs

---

**OpenAI TTS + Manim = Perfect sync between narration and visuals!** 🎙️🎬
