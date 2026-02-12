"""
Beat Duration Allocator

Allocates beat audio durations to animation sequences,
ensuring animations match narration timing.
"""

import json
from typing import List, Dict, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AnimationAllocation:
    """Allocation of time for a single animation."""
    animation_type: str  # Write, Create, FadeIn, Transform, etc.
    description: str
    allocated_time: float
    weight: float  # Complexity weight


@dataclass
class BeatAllocation:
    """Complete allocation for a beat."""
    beat_id: int
    beat_text: str
    audio_file: str
    audio_duration: float
    animations: List[AnimationAllocation]
    total_allocated: float
    filler_wait: float  # Time to wait at end


# Animation complexity weights
ANIMATION_WEIGHTS = {
    'Write': 1.4,
    'MathTex': 1.3,
    'Create': 1.1,
    'Transform': 1.2,
    'ReplacementTransform': 1.2,
    'FadeIn': 0.6,
    'FadeOut': 0.5,
    'Indicate': 0.7,
    'ShowCreation': 1.1,
    'Shift': 0.4,
    'Scale': 0.4,
    'Rotate': 0.5,
    'default': 0.8
}

# Minimum reading pause at end of beat (seconds)
MIN_READING_PAUSE = 0.3


def estimate_animation_count_for_beat(beat_text: str) -> int:
    """
    Estimate number of animations needed for a beat based on its content.
    
    Args:
        beat_text: The narration text
        
    Returns:
        Estimated animation count
    """
    # Heuristic: more words = more visuals
    word_count = len(beat_text.split())
    
    if word_count < 10:
        return 2  # Simple: intro + one visual
    elif word_count < 20:
        return 4  # Medium: intro + 2-3 visuals
    else:
        return 6  # Complex: intro + multiple visuals
    

def allocate_beat_duration(
    beat_duration: float,
    animation_specs: List[Dict],
    min_pause: float = MIN_READING_PAUSE
) -> BeatAllocation:
    """
    Allocate beat duration across animations.
    
    Args:
        beat_duration: Total time available (audio duration)
        animation_specs: List of dicts with 'type' and 'description'
        min_pause: Minimum pause at end for reading
        
    Returns:
        BeatAllocation with time allocations
    """
    if not animation_specs:
        # No animations, just pause
        return BeatAllocation(
            beat_id=0,
            beat_text="",
            audio_file="",
            audio_duration=beat_duration,
            animations=[],
            total_allocated=0.0,
            filler_wait=beat_duration
        )
    
    # Reserve time for reading pause
    available_time = max(beat_duration - min_pause, beat_duration * 0.7)
    
    # Get weights for each animation
    animation_weights = []
    for spec in animation_specs:
        anim_type = spec.get('type', 'default')
        weight = ANIMATION_WEIGHTS.get(anim_type, ANIMATION_WEIGHTS['default'])
        animation_weights.append(weight)
    
    total_weight = sum(animation_weights)
    
    # Allocate time proportionally to weights
    allocations = []
    total_allocated = 0.0
    
    for i, (spec, weight) in enumerate(zip(animation_specs, animation_weights)):
        # Proportional allocation
        if i < len(animation_specs) - 1:
            allocated = (weight / total_weight) * available_time
        else:
            # Last animation gets remainder
            allocated = available_time - total_allocated
        
        # Enforce minimum (0.3s) and maximum (beat_duration * 0.6) per animation
        allocated = max(0.3, min(allocated, beat_duration * 0.6))
        
        allocations.append(AnimationAllocation(
            animation_type=spec.get('type', 'Unknown'),
            description=spec.get('description', ''),
            allocated_time=allocated,
            weight=weight
        ))
        total_allocated += allocated
    
    # Calculate filler wait
    filler_wait = max(0.0, beat_duration - total_allocated)
    
    return BeatAllocation(
        beat_id=0,
        beat_text="",
        audio_file="",
        audio_duration=beat_duration,
        animations=allocations,
        total_allocated=total_allocated,
        filler_wait=filler_wait
    )


def create_animation_specs_for_beat(beat_text: str, beat_id: int) -> List[Dict]:
    """
    Create default animation specifications for a beat.
    This is a placeholder - in practice, these would come from the LLM code generator.
    
    Args:
        beat_text: Narration text
        beat_id: Beat number
        
    Returns:
        List of animation spec dicts
    """
    count = estimate_animation_count_for_beat(beat_text)
    
    specs = []
    
    # First animation is usually text/title
    if beat_id == 1:
        specs.append({'type': 'Write', 'description': 'Title or intro text'})
    else:
        specs.append({'type': 'FadeIn', 'description': 'Beat intro'})
    
    # Middle animations based on content hints
    if 'equation' in beat_text.lower() or 'formula' in beat_text.lower():
        specs.append({'type': 'MathTex', 'description': 'Mathematical formula'})
        specs.append({'type': 'Transform', 'description': 'Equation transformation'})
    
    if any(word in beat_text.lower() for word in ['show', 'visualize', 'see', 'watch']):
        specs.append({'type': 'Create', 'description': 'Visual element'})
    
    if 'transform' in beat_text.lower() or 'becomes' in beat_text.lower():
        specs.append({'type': 'ReplacementTransform', 'description': 'Transform element'})
    
    # Fill to target count
    while len(specs) < count:
        specs.append({'type': 'FadeIn', 'description': 'Supporting visual'})
    
    return specs[:count]


def build_beat_allocations(timeline_path: str) -> Dict[str, List[BeatAllocation]]:
    """
    Build complete beat allocations from timeline.
    
    Args:
        timeline_path: Path to beat_timeline.json
        
    Returns:
        Dict mapping segment_id to list of BeatAllocations
    """
    with open(timeline_path, 'r') as f:
        timeline = json.load(f)
    
    allocations = {}
    
    for seg_id, seg_data in timeline['segments'].items():
        seg_allocations = []
        
        for beat_data in seg_data['beats']:
            beat_id = beat_data['beat_id']
            beat_text = beat_data['text']
            duration = beat_data['duration']
            audio_file = beat_data['audio_file']
            
            # Create placeholder animation specs
            # In practice, these come from the Manim code generator
            anim_specs = create_animation_specs_for_beat(beat_text, beat_id)
            
            # Allocate duration
            allocation = allocate_beat_duration(duration, anim_specs)
            
            # Fill in metadata
            allocation.beat_id = beat_id
            allocation.beat_text = beat_text
            allocation.audio_file = audio_file
            
            seg_allocations.append(allocation)
        
        allocations[seg_id] = seg_allocations
    
    return allocations


def save_allocations(
    allocations: Dict[str, List[BeatAllocation]],
    output_path: str
):
    """Save beat allocations to JSON."""
    output_data = {'segments': {}}
    
    for seg_id, beat_allocs in allocations.items():
        output_data['segments'][seg_id] = {
            'beat_count': len(beat_allocs),
            'beats': [
                {
                    'beat_id': alloc.beat_id,
                    'beat_text': alloc.beat_text,
                    'audio_file': alloc.audio_file,
                    'audio_duration': alloc.audio_duration,
                    'total_allocated': alloc.total_allocated,
                    'filler_wait': alloc.filler_wait,
                    'animations': [
                        {
                            'type': anim.animation_type,
                            'description': anim.description,
                            'allocated_time': anim.allocated_time,
                            'weight': anim.weight
                        }
                        for anim in alloc.animations
                    ]
                }
                for alloc in beat_allocs
            ]
        }
    
    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"✓ Saved beat allocations: {output_path}")


def main():
    """CLI for allocation generation."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Allocate beat durations to animations")
    parser.add_argument(
        "--timeline-path",
        required=True,
        help="Path to beat_timeline.json"
    )
    parser.add_argument(
        "--output-path",
        default="src/research_viz/manim_generator/output/audio_beats/beat_allocations.json",
        help="Output path for allocations"
    )
    
    args = parser.parse_args()
    
    print("Building beat allocations...")
    allocations = build_beat_allocations(args.timeline_path)
    
    save_allocations(allocations, args.output_path)
    
    # Summary
    total_beats = sum(len(allocs) for allocs in allocations.values())
    print(f"\nProcessed {total_beats} beats across {len(allocations)} segments")


if __name__ == "__main__":
    main()
