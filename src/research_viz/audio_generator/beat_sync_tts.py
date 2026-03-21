"""
Beat-synchronized TTS Generation

Splits narration into beats (sentences/phrases), generates TTS per beat,
and tracks timing for precise animation sync.
"""

import logging
import re
import json
import wave
import time
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict

from research_viz.config.pipeline_config import get_config

logger = logging.getLogger(__name__)

OPENAI_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]


@dataclass
class NarrationBeat:
    """A single narration beat (sentence or phrase)."""
    beat_id: int
    text: str
    audio_file: Optional[str] = None
    duration: Optional[float] = None
    start_time: float = 0.0  # Cumulative start time in scene


def split_into_beats(narration: str, min_words: int = 8, max_words: int = 25) -> List[str]:
    """
    Split narration into beats (sentences or natural phrase breaks).

    Args:
        narration: Full narration text
        min_words: Minimum words per beat
        max_words: Maximum words per beat

    Returns:
        List of beat texts
    """
    sentences = re.split(r'(?<=[.!?])\s+', narration.strip())

    beats = []
    current_beat = []
    current_word_count = 0

    for sentence in sentences:
        words = sentence.split()
        word_count = len(words)

        if current_word_count + word_count <= max_words:
            current_beat.append(sentence)
            current_word_count += word_count
        else:
            if current_word_count >= min_words:
                beats.append(' '.join(current_beat))
                current_beat = [sentence]
                current_word_count = word_count
            else:
                current_beat.append(sentence)
                beats.append(' '.join(current_beat))
                current_beat = []
                current_word_count = 0

    if current_beat:
        beats.append(' '.join(current_beat))

    return beats


class BeatSyncTTS:
    """Generate beat-synchronized TTS using OpenAI."""

    def __init__(
        self,
        voice: Optional[str] = None,
        sample_rate: Optional[int] = None
    ):
        cfg = get_config()
        self.voice = voice if voice is not None else cfg.audio.voice
        self.sample_rate = sample_rate if sample_rate is not None else cfg.audio.sample_rate
        self.tts_model = cfg.audio.tts_model
        self.client = None

    def _load_client(self):
        """Lazy load OpenAI client."""
        if self.client is None:
            from openai import OpenAI
            self.client = OpenAI()

    def generate_beat_audio(self, text: str, output_path: str) -> float:
        """
        Generate audio for a single beat.

        Returns:
            Audio duration in seconds
        """
        self._load_client()

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        response = self.client.audio.speech.create(
            model=self.tts_model,
            voice=self.voice,
            input=text,
            response_format="wav"
        )
        response.write_to_file(str(output_path))

        with wave.open(str(output_path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()

            # OpenAI TTS sometimes has invalid frame count in header
            # Calculate from file size if frame count seems wrong
            if frames > 2000000000:  # Suspiciously large (>23 hours at 24kHz)
                import os
                file_size = os.path.getsize(str(output_path))
                # WAV header is typically 44 bytes
                data_size = file_size - 44
                frames = data_size // (channels * sampwidth)

            duration = frames / rate

        return duration

    def generate_segment_beats(
        self,
        segment: dict,
        output_dir: str,
        min_words: Optional[int] = None,
        max_words: Optional[int] = None
    ) -> List[NarrationBeat]:
        """
        Generate beat-synced audio for an entire segment.

        Returns:
            List of NarrationBeat objects with timing
        """
        cfg = get_config()
        if min_words is None:
            min_words = cfg.audio.min_words_per_beat
        if max_words is None:
            max_words = cfg.audio.max_words_per_beat

        narration = segment.get('narration_script', '').strip()
        if not narration:
            return []

        segment_id = segment.get('segment_id', 'unknown')
        title = segment.get('title', 'Untitled')

        logger.info("=" * 70)
        logger.info(f"Segment: {segment_id} - {title}")
        logger.info("=" * 70)

        beat_texts = split_into_beats(narration, min_words, max_words)
        logger.info(f"Split into {len(beat_texts)} beats")

        beats = []
        cumulative_time = 0.0

        for i, text in enumerate(beat_texts, 1):
            beat_id = i
            safe_segment_id = segment_id.replace('/', '_').replace(' ', '_')
            audio_file = Path(output_dir) / f"{safe_segment_id}_beat_{beat_id}.wav"

            logger.info(f"Beat {beat_id}/{len(beat_texts)}:")
            logger.info(f"  Text: {text[:60]}{'...' if len(text) > 60 else ''}")

            # Partial resume: skip beats with existing valid audio files
            if audio_file.exists() and audio_file.stat().st_size > 44:
                import wave
                try:
                    with wave.open(str(audio_file), 'rb') as wf:
                        frames = wf.getnframes()
                        rate = wf.getframerate()
                        duration = frames / rate
                    logger.info(f"  Skipped (existing audio: {duration:.2f}s)")
                    beat = NarrationBeat(
                        beat_id=beat_id, text=text, audio_file=str(audio_file),
                        duration=duration, start_time=cumulative_time,
                    )
                    beats.append(beat)
                    cumulative_time += duration
                    continue
                except Exception:
                    pass  # Regenerate if file is corrupted

            start_time = time.monotonic()
            duration = self.generate_beat_audio(text, str(audio_file))
            gen_time = time.monotonic() - start_time

            beat = NarrationBeat(
                beat_id=beat_id,
                text=text,
                audio_file=str(audio_file),
                duration=duration,
                start_time=cumulative_time
            )
            beats.append(beat)
            cumulative_time += duration

            logger.info(f"  Duration: {duration:.2f}s (generated in {gen_time:.2f}s)")
            logger.debug(f"  File: {audio_file.name}")

        total_duration = cumulative_time
        logger.info(f"Total segment duration: {total_duration:.2f}s")
        logger.info(f"Average beat length: {total_duration/len(beats):.2f}s")

        return beats


def generate_beat_timeline(
    explanation_path: str,
    output_dir: str = "src/research_viz/manim_generator/output/audio_beats",
    voice: Optional[str] = None,
    min_words: Optional[int] = None,
    max_words: Optional[int] = None
) -> Dict[str, List[NarrationBeat]]:
    """
    Generate complete beat timeline for all segments.

    Returns:
        Dict mapping segment_id to list of beats
    """
    cfg = get_config()
    if voice is None:
        voice = cfg.audio.voice
    if min_words is None:
        min_words = cfg.audio.min_words_per_beat
    if max_words is None:
        max_words = cfg.audio.max_words_per_beat

    with open(explanation_path, 'r') as f:
        explanation = json.load(f)

    segments = explanation.get('segments', [])
    logger.info(f"Generating beat timeline for {len(segments)} segments")
    logger.info(f"Voice: {voice}")
    logger.info(f"Beat length: {min_words}-{max_words} words")

    tts = BeatSyncTTS(voice=voice)

    timeline = {}

    for segment in segments:
        segment_id = segment.get('segment_id', 'unknown')
        beats = tts.generate_segment_beats(
            segment=segment,
            output_dir=output_dir,
            min_words=min_words,
            max_words=max_words
        )
        timeline[segment_id] = beats

    # Save timeline metadata
    timeline_data = {
        'explanation_source': explanation_path,
        'voice': voice,
        'total_segments': len(segments),
        'segments': {}
    }

    for seg_id, beats in timeline.items():
        timeline_data['segments'][seg_id] = {
            'beat_count': len(beats),
            'total_duration': sum(b.duration for b in beats),
            'beats': [asdict(b) for b in beats]
        }

    metadata_path = Path(output_dir) / "beat_timeline.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    with open(metadata_path, 'w') as f:
        json.dump(timeline_data, f, indent=2)

    logger.info(f"Beat timeline saved to {metadata_path}")

    total_beats = sum(len(beats) for beats in timeline.values())
    total_duration = sum(
        sum(b.duration for b in beats)
        for beats in timeline.values()
    )
    logger.info(f"Total beats: {total_beats}")
    logger.info(f"Total duration: {total_duration:.1f}s")

    return timeline


def main():
    """CLI for beat timeline generation."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate beat-synced TTS timeline")
    parser.add_argument(
        "--explanation-path",
        required=True,
        help="Path to educational explanation JSON"
    )
    parser.add_argument(
        "--output-dir",
        default="src/research_viz/manim_generator/output/audio_beats",
        help="Output directory for audio files"
    )
    parser.add_argument(
        "--voice",
        default="nova",
        choices=OPENAI_VOICES,
        help="TTS voice"
    )
    parser.add_argument(
        "--min-words",
        type=int,
        default=8,
        help="Minimum words per beat"
    )
    parser.add_argument(
        "--max-words",
        type=int,
        default=25,
        help="Maximum words per beat"
    )

    args = parser.parse_args()

    generate_beat_timeline(
        explanation_path=args.explanation_path,
        output_dir=args.output_dir,
        voice=args.voice,
        min_words=args.min_words,
        max_words=args.max_words
    )


if __name__ == "__main__":
    main()
