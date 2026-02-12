"""
Inline Marker Parser for TTS

Parses inline markers from narration script:
- [pause:medium]
- [emphasis]text[/emphasis]
- [tone:enthusiastic]
- [anim:key]
etc.
"""

import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class MarkerType(str, Enum):
    """Types of inline markers."""
    PAUSE = "pause"
    EMPHASIS = "emphasis"
    TONE = "tone"
    SPEED = "speed"
    ANIMATION = "anim"
    EMOTIVE = "emotive"


@dataclass
class InlineMarker:
    """A parsed inline marker."""
    type: MarkerType
    value: str  # e.g., "medium" for pause, "enthusiastic" for tone
    position: int  # Character position in clean text
    end_position: Optional[int] = None  # For paired markers like [emphasis]...[/emphasis]


@dataclass
class MarkedText:
    """Text segment with optional marker."""
    text: str
    markers: List[InlineMarker]


def parse_inline_markers(narration: str) -> Tuple[str, List[InlineMarker]]:
    """
    Parse inline markers from narration script.
    
    Args:
        narration: Narration with inline markers
        
    Returns:
        Tuple of (clean_text, markers_list)
        
    Example:
        >>> text, markers = parse_inline_markers(
        ...     "Hello [pause:medium] [emphasis]world[/emphasis]!"
        ... )
        >>> text
        "Hello world!"
        >>> markers
        [InlineMarker(type='pause', value='medium', position=6),
         InlineMarker(type='emphasis', value='world', position=6, end_position=11)]
    """
    clean_text = ""
    markers = []
    position = 0
    
    # Pattern for markers: [type:value] or [type]text[/type]
    pattern = r'\[([^\]]+)\]'
    
    last_end = 0
    emphasis_stack = []  # Track open emphasis tags
    
    for match in re.finditer(pattern, narration):
        # Add text before marker
        clean_text += narration[last_end:match.start()]
        position = len(clean_text)
        
        marker_content = match.group(1)
        
        # Parse marker
        if ':' in marker_content:
            # Type:value format (e.g., pause:medium, tone:enthusiastic)
            marker_type, value = marker_content.split(':', 1)
            marker_type = marker_type.strip().lower()
            value = value.strip()
            
            # Map to MarkerType
            type_map = {
                'pause': MarkerType.PAUSE,
                'tone': MarkerType.TONE,
                'speed': MarkerType.SPEED,
                'anim': MarkerType.ANIMATION,
                'animation': MarkerType.ANIMATION
            }
            
            if marker_type in type_map:
                markers.append(InlineMarker(
                    type=type_map[marker_type],
                    value=value,
                    position=position
                ))
        
        elif marker_content.startswith('/'):
            # Closing tag (e.g., [/emphasis])
            tag = marker_content[1:].strip().lower()
            
            # Find matching opening tag
            for i in range(len(emphasis_stack) - 1, -1, -1):
                if emphasis_stack[i][0] == tag:
                    # Found match
                    start_pos = emphasis_stack[i][1]
                    text_content = clean_text[start_pos:position]
                    
                    # Add marker with span
                    type_map = {
                        'emphasis': MarkerType.EMPHASIS,
                        'strong': MarkerType.EMPHASIS,
                        'light': MarkerType.EMPHASIS
                    }
                    
                    if tag in type_map:
                        # Determine level
                        level = 'moderate' if tag == 'emphasis' else tag
                        
                        markers.append(InlineMarker(
                            type=type_map[tag],
                            value=f"{level}:{text_content}",
                            position=start_pos,
                            end_position=position
                        ))
                    
                    emphasis_stack.pop(i)
                    break
        
        else:
            # Opening tag (e.g., [emphasis], [strong])
            tag = marker_content.strip().lower()
            
            # Emotive tags (single, no closing)
            emotive_tags = ['laugh', 'sigh', 'gasp', 'chuckle', 'cough', 'sniffle', 'groan', 'yawn']
            if tag in emotive_tags:
                markers.append(InlineMarker(
                    type=MarkerType.EMOTIVE,
                    value=tag,
                    position=position
                ))
            else:
                # Opening emphasis tag
                emphasis_stack.append((tag, position))
        
        last_end = match.end()
    
    # Add remaining text
    clean_text += narration[last_end:]
    
    return clean_text, markers


def split_by_pauses(
    narration: str,
    pause_threshold: str = "medium"
) -> List[MarkedText]:
    """
    Split narration into beats based on pause markers.
    
    Args:
        narration: Narration with inline markers
        pause_threshold: Split on pauses >= this level (short, medium, long)
        
    Returns:
        List of MarkedText beats
    """
    clean_text, markers = parse_inline_markers(narration)
    
    # Pause hierarchy
    pause_levels = {'short': 1, 'medium': 2, 'long': 3}
    threshold_level = pause_levels.get(pause_threshold, 2)
    
    # Find split points (pause markers at or above threshold)
    split_positions = [0]
    
    for marker in markers:
        if marker.type == MarkerType.PAUSE:
            # Check pause level
            pause_value = marker.value.lower()
            
            # Handle exact duration (e.g., "1.5s")
            if pause_value.endswith('s'):
                try:
                    duration = float(pause_value[:-1])
                    level = 1 if duration < 0.35 else (2 if duration < 0.65 else 3)
                except:
                    level = 2
            else:
                level = pause_levels.get(pause_value, 2)
            
            if level >= threshold_level:
                split_positions.append(marker.position)
    
    split_positions.append(len(clean_text))
    
    # Create beats
    beats = []
    for i in range(len(split_positions) - 1):
        start = split_positions[i]
        end = split_positions[i + 1]
        
        beat_text = clean_text[start:end].strip()
        if not beat_text:
            continue
        
        # Find markers in this range
        beat_markers = [
            m for m in markers
            if start <= m.position < end
        ]
        
        # Adjust marker positions relative to beat
        for marker in beat_markers:
            marker.position -= start
            if marker.end_position:
                marker.end_position -= start
        
        beats.append(MarkedText(
            text=beat_text,
            markers=beat_markers
        ))
    
    return beats


def extract_emphasis_words(markers: List[InlineMarker]) -> List[Dict]:
    """
    Extract emphasis words from markers.
    
    Args:
        markers: List of markers
        
    Returns:
        List of emphasis dicts with text, level, position
    """
    emphasis = []
    
    for marker in markers:
        if marker.type == MarkerType.EMPHASIS:
            # Value format: "level:text"
            if ':' in marker.value:
                level, text = marker.value.split(':', 1)
            else:
                level = 'moderate'
                text = marker.value
            
            emphasis.append({
                'text': text.strip(),
                'level': level,
                'position': marker.position,
                'end_position': marker.end_position
            })
    
    return emphasis


def extract_animation_cues(markers: List[InlineMarker]) -> List[str]:
    """
    Extract animation trigger keys from markers.
    
    Args:
        markers: List of markers
        
    Returns:
        List of animation keys
    """
    return [
        marker.value
        for marker in markers
        if marker.type == MarkerType.ANIMATION
    ]


def get_prosody_hints(markers: List[InlineMarker]) -> Dict:
    """
    Extract prosody hints (tone, speed, pauses) from markers.
    
    Args:
        markers: List of markers
        
    Returns:
        Dict with tone, speed, pauses info
    """
    tone_markers = [m for m in markers if m.type == MarkerType.TONE]
    speed_markers = [m for m in markers if m.type == MarkerType.SPEED]
    pause_markers = [m for m in markers if m.type == MarkerType.PAUSE]
    
    return {
        'tone_shifts': [{'value': m.value, 'position': m.position} for m in tone_markers],
        'speed_changes': [{'value': m.value, 'position': m.position} for m in speed_markers],
        'pauses': [{'value': m.value, 'position': m.position} for m in pause_markers]
    }


def strip_markers(narration: str) -> str:
    """
    Remove all inline markers from narration (for backward compatibility).
    
    Args:
        narration: Narration with markers
        
    Returns:
        Clean text without markers
    """
    clean_text, _ = parse_inline_markers(narration)
    return clean_text


# Example usage and tests
if __name__ == "__main__":
    # Test narration
    test_narration = """Let's try a bold idea [pause:medium] [emphasis]what if translation[/emphasis] doesn't need to step through a sentence [pause:short] one token at a time? [pause:long] [tone:enthusiastic] Imagine placing every word as a vector on a circle. [pause:medium] [anim:circle_vectors] When the word [strong]sat[/strong] wants context [pause:short] it shines beams to every other word. [anim:beams] [pause:long]"""
    
    print("Original narration:")
    print(test_narration)
    print("\n" + "="*70 + "\n")
    
    # Parse markers
    clean_text, markers = parse_inline_markers(test_narration)
    
    print("Clean text:")
    print(clean_text)
    print("\n" + "="*70 + "\n")
    
    print("Markers:")
    for marker in markers:
        print(f"  {marker.type.value:12s} | {marker.value:20s} | pos={marker.position}")
    print("\n" + "="*70 + "\n")
    
    # Split into beats
    beats = split_by_pauses(test_narration, pause_threshold="medium")
    
    print(f"Beats ({len(beats)}):")
    for i, beat in enumerate(beats, 1):
        print(f"\nBeat {i}:")
        print(f"  Text: {beat.text[:60]}...")
        print(f"  Markers: {len(beat.markers)}")
        
        emphasis = extract_emphasis_words(beat.markers)
        if emphasis:
            print(f"  Emphasis: {[e['text'] for e in emphasis]}")
        
        anims = extract_animation_cues(beat.markers)
        if anims:
            print(f"  Animations: {anims}")
