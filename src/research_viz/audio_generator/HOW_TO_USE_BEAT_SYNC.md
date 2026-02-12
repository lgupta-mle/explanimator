# How to Use Beat-Sync (Simple Guide)

## What You Have Now

A complete system that:
- Splits narration into beats (sentences)
- Generates audio per beat with Orpheus-TTS
- Creates Manim code that stays perfectly in sync with audio

## Installation (One-Time)

```bash
pip install orpheus-speech
```

If you get errors:
```bash
pip install vllm==0.7.3
pip install orpheus-speech
```

## Usage (3 Commands)

### 1. Generate Everything

```bash
python -m research_viz.audio_generator.workflow \
    --explanation-path src/research_viz/manim_generator/output/educational_explanation_3.json \
    --voice dan
```

**What this does:**
- Reads your explanation JSON
- Splits each segment's narration into beats (~8-25 words each)
- Generates audio files (one per beat)
- Creates Manim code with perfect sync

**Time:** ~5-10 minutes

**Output:**
```
output/
├── audio_beats/
│   ├── s1_beat_1.wav
│   ├── s1_beat_2.wav
│   └── ...
└── beat_synced_scenes/
    ├── s1_beat_synced.py
    └── ...
```

### 2. Find the Class Name

```bash
grep "^class " src/research_viz/manim_generator/output/beat_synced_scenes/s1_beat_synced.py
```

Example output: `class TranslationByLookingNotMarching(Scene):`

### 3. Render the Scene

```bash
manim -pqh src/research_viz/manim_generator/output/beat_synced_scenes/s1_beat_synced.py TranslationByLookingNotMarching
```

**That's it!** The audio will play automatically during rendering.

## Customization

### Different Voice

```bash
--voice leo   # Warm, conversational
--voice tara  # Natural, expressive
--voice jess  # Energetic, engaging
```

### Shorter/Longer Beats

```bash
# Shorter beats (tighter sync, more files)
--min-words 8 --max-words 15

# Longer beats (looser sync, fewer files)
--min-words 15 --max-words 30
```

## How Sync Works

Each beat in the generated code looks like:

```python
# Beat 1: "Let's try a bold idea..." (6.2 seconds)
self.add_sound("output/audio_beats/s1_beat_1.wav")  # Start audio

# Animations for this beat (total 6.2s)
self.play(Write(title), run_time=1.8)     # 1.8s
self.play(Create(circle), run_time=2.4)   # 2.4s
self.wait(2.0)                            # 2.0s filler
# Total: 6.2s ✓ matches audio!

# Beat 2 starts immediately
self.add_sound("output/audio_beats/s1_beat_2.wav")
...
```

**Key**: Each beat's animations finish exactly when its audio ends. No drift!

## Troubleshooting

### Problem: "No module named 'orpheus_tts'"
**Solution**: 
```bash
pip install orpheus-speech
```

### Problem: Audio files not found during rendering
**Solution**: Run manim from the project root:
```bash
cd /Users/apopat/Desktop/GraphViz/research-paper-graphviz
manim -pqh output/beat_synced_scenes/s1_beat_synced.py <ClassName>
```

### Problem: Animations don't look right
**Explanation**: The current version uses placeholder animations. The timing is correct, but the visuals are generic. Next step is to integrate with the LLM code generator for content-specific animations.

## What's Next

1. **Test it**: Run the 3 commands above with your explanation
2. **Review**: Watch the rendered video to see the sync in action
3. **Integrate**: Connect with the LLM code generator to get real animations instead of placeholders
4. **Fine-tune**: Adjust voice, beat length, animation weights as needed

## Quick Reference

### Full Workflow
```bash
python -m research_viz.audio_generator.workflow \
    --explanation-path output/educational_explanation_3.json \
    --voice dan
```

### Render One Scene
```bash
manim -pqh output/beat_synced_scenes/s1_beat_synced.py <ClassName>
```

### Batch Render All Scenes
```bash
for file in output/beat_synced_scenes/*_beat_synced.py; do
    class=$(grep "^class " "$file" | awk '{print $2}' | cut -d'(' -f1)
    echo "Rendering $class..."
    manim -pqh "$file" "$class"
done
```

## Documentation

- **This file**: Quick how-to (you are here)
- **Quick start**: `BEAT_SYNC_QUICKSTART.md`
- **Full docs**: `src/research_viz/audio_generator/README.md`
- **Summary**: `LEVEL2_BEAT_SYNC_SUMMARY.md`
- **Complete**: `LEVEL2_IMPLEMENTATION_COMPLETE.md`

---

**That's everything you need to get started!** 🚀

Just run the workflow command, find the class name, and render. The audio will sync automatically.
