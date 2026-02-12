# Beat-Synchronized Audio Generation (Level 2)

This module implements **Level 2 beat-level synchronization** between TTS narration and Manim animations.

## How It Works

### The Problem
Without sync, narration and visuals drift apart:
- Narrator says "softmax" at 5s, but the softmax visual appears at 7s
- Animations finish before/after the narration
- Confusing for viewers

### The Solution: Beat-Level Sync
1. **Split narration** into beats (sentences/phrases, ~8-25 words each)
2. **Generate TTS audio** per beat and measure duration
3. **Allocate durations** to animations based on complexity weights
4. **Generate Manim code** with exact `run_time` and `wait()` to match audio

### Example
```
Beat 1: "Let's try a bold idea: what if translation doesn't need to step through a sentence?" (6.2s)
  ├─ Write(title): 1.8s
  ├─ FadeIn(example): 1.2s
  ├─ Create(diagram): 2.4s
  └─ wait(0.8s) for reading pause
  = 6.2s total ✓

Beat 2: "Imagine placing every word as a vector on a circle." (4.5s)
  ├─ Create(circle): 1.5s
  ├─ FadeIn(vectors): 1.8s
  └─ wait(1.2s)
  = 4.5s total ✓
```

## Architecture

### Module Files

```
audio_generator/
├── __init__.py                         # Module exports
├── beat_sync_tts.py                    # TTS generation per beat
├── beat_duration_allocator.py          # Duration allocation logic
├── beat_synced_manim_generator.py      # Manim code generation
├── workflow.py                         # Complete workflow orchestration
└── README.md                           # This file
```

### Data Flow

```
Explanation JSON
     ↓
┌─────────────────────────┐
│ 1. beat_sync_tts        │  Split into beats → Generate TTS
│    - split_into_beats() │  Output: beat_timeline.json + audio files
└─────────────────────────┘
     ↓ beat_timeline.json
┌─────────────────────────┐
│ 2. beat_allocator       │  Allocate durations to animations
│    - allocate_beat()    │  Output: beat_allocations.json
└─────────────────────────┘
     ↓ beat_allocations.json
┌─────────────────────────┐
│ 3. manim_generator      │  Generate Manim code with sync
│    - generate_scene()   │  Output: .py files with add_sound() + exact run_times
└─────────────────────────┘
```

## Usage

### Complete Workflow (Recommended)

```bash
python -m research_viz.audio_generator.workflow \
    --explanation-path output/educational_explanation_3.json \
    --voice dan \
    --min-words 8 \
    --max-words 25
```

This runs all steps:
1. Generates beat timeline + TTS audio
2. Builds duration allocations
3. Creates beat-synced Manim scenes

### Step-by-Step (Advanced)

#### Step 1: Generate Beat Timeline & TTS

```bash
python -m research_viz.audio_generator.beat_sync_tts \
    --explanation-path output/educational_explanation_3.json \
    --output-dir output/audio_beats \
    --voice dan
```

Output:
- `output/audio_beats/s1_beat_1.wav`, `s1_beat_2.wav`, ...
- `output/audio_beats/beat_timeline.json`

#### Step 2: Build Allocations

```bash
python -m research_viz.audio_generator.beat_duration_allocator \
    --timeline-path output/audio_beats/beat_timeline.json \
    --output-path output/audio_beats/beat_allocations.json
```

#### Step 3: Generate Manim Code

```bash
python -m research_viz.audio_generator.beat_synced_manim_generator \
    --explanation-path output/educational_explanation_3.json \
    --beat-timeline-path output/audio_beats/beat_timeline.json \
    --output-dir output/beat_synced_scenes
```

## Output Structure

```
output/
├── audio_beats/
│   ├── s1_beat_1.wav                  # Audio for segment 1, beat 1
│   ├── s1_beat_2.wav
│   ├── s2_beat_1.wav
│   ├── ...
│   ├── beat_timeline.json             # Beat metadata with durations
│   └── beat_allocations.json          # Animation time allocations
└── beat_synced_scenes/
    ├── s1_beat_synced.py              # Manim scene for segment 1
    ├── s2_beat_synced.py
    └── ...
```

### beat_timeline.json Structure

```json
{
  "segments": {
    "s1": {
      "beat_count": 4,
      "total_duration": 25.8,
      "beats": [
        {
          "beat_id": 1,
          "text": "Let's try a bold idea: what if translation...",
          "audio_file": "output/audio_beats/s1_beat_1.wav",
          "duration": 6.2,
          "start_time": 0.0
        },
        ...
      ]
    }
  }
}
```

## Rendering

### Render a Single Scene

```bash
manim -pqh output/beat_synced_scenes/s1_beat_synced.py <ClassName>
```

The audio will **automatically play** during rendering because the code includes `self.add_sound()` calls.

### Batch Render All Scenes

```bash
for file in output/beat_synced_scenes/*_beat_synced.py; do
    class_name=$(grep "^class " "$file" | head -1 | awk '{print $2}' | cut -d'(' -f1)
    manim -pqh "$file" "$class_name"
done
```

## Configuration

### Beat Length

Control beat granularity:
- **Short beats** (8-15 words): Fine-grained sync, more audio files
- **Long beats** (20-30 words): Coarser sync, fewer files

```bash
--min-words 8 --max-words 15  # Fine-grained
--min-words 15 --max-words 30 # Coarser
```

### Animation Weights

Defined in `beat_duration_allocator.py`:

```python
ANIMATION_WEIGHTS = {
    'Write': 1.4,        # Slower, more important
    'MathTex': 1.3,      # Complex equations
    'Create': 1.1,       # Shape creation
    'Transform': 1.2,    # Transformations
    'FadeIn': 0.6,       # Quick fades
    'FadeOut': 0.5,      # Quick exits
    'default': 0.8       # Fallback
}
```

Higher weight = more time allocated.

### Reading Pause

Minimum pause at end of each beat (default: 0.3s):

```python
MIN_READING_PAUSE = 0.3  # In beat_duration_allocator.py
```

## Sync Quality

### Validation

Each beat ensures:
```
sum(animation_run_times) + filler_wait ≈ audio_duration (±100ms)
```

### Drift Prevention

- Allocations are proportional to weights but capped to beat duration
- Filler waits absorb slack
- No accumulation of drift across beats

## Limitations & Future Work

### Current Limitations

1. **Placeholder animations**: Generated code uses generic animations; real code should come from LLM
2. **No word-level sync**: Syncs by sentence, not by individual words
3. **Fixed weights**: Animation complexity weights are hardcoded

### Planned Enhancements (Level 3)

1. **Forced alignment**: Use Aeneas/MFA for word-level timestamps
2. **LLM integration**: Let code generator use beat allocations to set exact run_times
3. **Dynamic weights**: Learn weights from actual animation complexity
4. **Drift correction**: Auto-scale groups if total drift exceeds threshold

## Troubleshooting

### Issue: "No module named 'orpheus_tts'"

```bash
pip install orpheus-speech
# If issues:
pip install vllm==0.7.3
pip install orpheus-speech
```

### Issue: Animations too fast/slow

Adjust animation weights in `ANIMATION_WEIGHTS` or beat length parameters.

### Issue: Audio files not found during rendering

Ensure paths in generated code are absolute or relative to where you run `manim`:

```python
# In beat_synced_manim_generator.py, use absolute paths:
audio_file = str(Path(audio_file).absolute())
```

## API Reference

### `generate_beat_timeline()`

```python
from research_viz.audio_generator import generate_beat_timeline

timeline = generate_beat_timeline(
    explanation_path="output/explanation.json",
    output_dir="output/audio_beats",
    voice="dan",
    min_words=8,
    max_words=25
)
```

Returns: `Dict[segment_id, List[NarrationBeat]]`

### `allocate_beat_duration()`

```python
from research_viz.audio_generator import allocate_beat_duration

allocation = allocate_beat_duration(
    beat_duration=6.2,
    animation_specs=[
        {'type': 'Write', 'description': 'Title'},
        {'type': 'FadeIn', 'description': 'Diagram'}
    ],
    min_pause=0.3
)
```

Returns: `BeatAllocation` with time allocations

## Example Output

### Generated Manim Code

```python
class TranslationByLookingNotMarching(Scene):
    def construct(self):
        # Beat 1
        self.add_sound("output/audio_beats/s1_beat_1.wav")
        text_1_0 = Text("Translation by Looking, Not Marching", font_size=36)
        self.play(Write(text_1_0), run_time=1.80)
        shape_1_1 = Circle(radius=1.0, color=BLUE)
        self.play(Create(shape_1_1), run_time=2.40)
        self.wait(2.00)  # Filler to match 6.2s beat
        
        # Beat 2
        self.add_sound("output/audio_beats/s1_beat_2.wav")
        ...
```

## Performance

- **TTS Generation**: ~2-3x real-time (10s audio in 3-5s)
- **Beat Splitting**: Instant (<1s for full explanation)
- **Allocation**: Instant (<1s)
- **Code Generation**: <1s per scene

Total workflow: ~5-10 minutes for a 7-segment explanation (depends on GPU for TTS).

---

**Level 2 beat-sync gives you 80-90% of perfect sync with minimal complexity!** 🎯🎙️
