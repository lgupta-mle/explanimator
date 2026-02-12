"""
Beat-Synced Manim Code Generator

Generates Manim code that synchronizes with beat-level audio timing.
"""

import json
from pathlib import Path
from typing import List, Dict, Optional


def generate_beat_synced_scene(
    segment: dict,
    beats_data: List[dict],
    class_name: str,
    segment_id: str
) -> str:
    """
    Generate Manim scene code synchronized with beat audio.
    
    Args:
        segment: Segment data from explanation
        beats_data: List of beat allocation dicts
        class_name: Scene class name
        segment_id: Segment identifier
        
    Returns:
        Complete Manim scene code with beat sync
    """
    title = segment.get('title', 'Untitled')
    
    # Build beat-synced construct method
    beat_code_blocks = []
    
    for beat in beats_data:
        beat_id = beat['beat_id']
        beat_text = beat['beat_text']
        audio_file = beat['audio_file']
        audio_duration = beat['audio_duration']
        animations = beat['animations']
        filler_wait = beat['filler_wait']
        
        # Create comment block for beat
        beat_block = f"""
        # ============================================================
        # Beat {beat_id}: {beat_text[:50]}{'...' if len(beat_text) > 50 else ''}
        # Audio duration: {audio_duration:.2f}s
        # ============================================================
        
        # Start beat audio
        self.add_sound("{audio_file}")
        
"""
        
        # Generate animations for this beat
        for i, anim in enumerate(animations):
            anim_type = anim['animation_type']
            description = anim['description']
            run_time = anim['allocated_time']
            
            # Generate placeholder animation based on type
            if anim_type == 'Write':
                anim_code = f'        text_{beat_id}_{i} = Text("{description}", font_size=36)\n'
                anim_code += f'        self.play(Write(text_{beat_id}_{i}), run_time={run_time:.2f})\n'
            elif anim_type == 'MathTex':
                anim_code = f'        eq_{beat_id}_{i} = Text("Equation placeholder", font_size=32)  # Use Text instead of MathTex\n'
                anim_code += f'        self.play(FadeIn(eq_{beat_id}_{i}), run_time={run_time:.2f})\n'
            elif anim_type == 'Create':
                anim_code = f'        shape_{beat_id}_{i} = Circle(radius=1.0, color=BLUE)\n'
                anim_code += f'        self.play(Create(shape_{beat_id}_{i}), run_time={run_time:.2f})\n'
            elif anim_type == 'Transform' or anim_type == 'ReplacementTransform':
                if i > 0:
                    anim_code = f'        # Transform from previous element\n'
                    anim_code += f'        self.play(Indicate(text_{beat_id}_{i-1}), run_time={run_time:.2f})\n'
                else:
                    anim_code = f'        # First animation, skip transform\n'
                    anim_code += f'        self.wait({run_time:.2f})\n'
            elif anim_type == 'FadeIn':
                anim_code = f'        elem_{beat_id}_{i} = Text("{description}", font_size=28).shift(DOWN)\n'
                anim_code += f'        self.play(FadeIn(elem_{beat_id}_{i}), run_time={run_time:.2f})\n'
            elif anim_type == 'FadeOut':
                if i > 0:
                    anim_code = f'        self.play(FadeOut(elem_{beat_id}_{i-1}), run_time={run_time:.2f})\n'
                else:
                    anim_code = f'        self.wait({run_time:.2f})\n'
            else:
                # Generic animation
                anim_code = f'        # {anim_type}: {description}\n'
                anim_code += f'        self.wait({run_time:.2f})\n'
            
            beat_block += anim_code + '\n'
        
        # Add filler wait to complete the beat
        if filler_wait > 0.05:
            beat_block += f'        # End-of-beat pause for reading\n'
            beat_block += f'        self.wait({filler_wait:.2f})\n'
        
        beat_code_blocks.append(beat_block)
    
    # Assemble complete scene
    full_code = f'''"""
{title}

Auto-generated Manim scene with beat-synchronized audio.
Segment: {segment_id}
"""

from manim import *


class {class_name}(Scene):
    """Beat-synced scene for: {title}"""
    
    def construct(self):
        # Scene title
        title = Text("{title}", font_size=48)
        self.play(Write(title), run_time=1.5)
        self.play(FadeOut(title), run_time=0.8)
        self.wait(0.5)
        
{"".join(beat_code_blocks)}
        # Scene complete
        self.wait(1.0)
'''
    
    return full_code


def generate_all_beat_synced_scenes(
    explanation_path: str,
    beat_timeline_path: str,
    output_dir: str = "src/research_viz/manim_generator/output/beat_synced_scenes"
) -> List[str]:
    """
    Generate beat-synced Manim scenes for all segments.
    
    Args:
        explanation_path: Path to educational explanation JSON
        beat_timeline_path: Path to beat_timeline.json
        output_dir: Output directory for scene files
        
    Returns:
        List of generated scene file paths
    """
    # Load data
    with open(explanation_path, 'r') as f:
        explanation = json.load(f)
    
    with open(beat_timeline_path, 'r') as f:
        timeline = json.load(f)
    
    segments = explanation.get('segments', [])
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    generated_files = []
    
    print(f"\nGenerating beat-synced Manim scenes")
    print(f"Output: {output_dir}\n")
    
    for segment in segments:
        segment_id = segment.get('segment_id', 'unknown')
        title = segment.get('title', 'Untitled')
        
        if segment_id not in timeline['segments']:
            print(f"⚠️  No beat data for segment {segment_id}, skipping")
            continue
        
        beats_data = timeline['segments'][segment_id]['beats']
        
        # Generate class name
        class_name = ''.join(word.capitalize() for word in title.split()[:5])
        class_name = ''.join(c for c in class_name if c.isalnum())
        if not class_name:
            class_name = f"Segment{segment_id.upper()}"
        
        print(f"[{segment_id}] {title}")
        print(f"  Class: {class_name}")
        print(f"  Beats: {len(beats_data)}")
        
        # Generate code
        scene_code = generate_beat_synced_scene(
            segment=segment,
            beats_data=beats_data,
            class_name=class_name,
            segment_id=segment_id
        )
        
        # Save to file
        safe_id = segment_id.replace('/', '_').replace(' ', '_')
        output_file = output_dir / f"{safe_id}_beat_synced.py"
        
        with open(output_file, 'w') as f:
            f.write(scene_code)
        
        generated_files.append(str(output_file))
        print(f"  ✓ Generated: {output_file.name}\n")
    
    print(f"{'='*70}")
    print(f"✓ Generated {len(generated_files)} beat-synced scenes")
    print(f"  Output: {output_dir}")
    print(f"{'='*70}")
    
    return generated_files


def main():
    """CLI for beat-synced scene generation."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate beat-synced Manim scenes")
    parser.add_argument(
        "--explanation-path",
        required=True,
        help="Path to educational explanation JSON"
    )
    parser.add_argument(
        "--beat-timeline-path",
        required=True,
        help="Path to beat_timeline.json"
    )
    parser.add_argument(
        "--output-dir",
        default="src/research_viz/manim_generator/output/beat_synced_scenes",
        help="Output directory for scene files"
    )
    
    args = parser.parse_args()
    
    generate_all_beat_synced_scenes(
        explanation_path=args.explanation_path,
        beat_timeline_path=args.beat_timeline_path,
        output_dir=args.output_dir
    )


if __name__ == "__main__":
    main()
