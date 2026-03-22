"""
Beat-synchronized TTS Generation

Splits narration into beats (sentences/phrases), generates TTS per beat,
and tracks timing for precise animation sync.

Beat audio generation is parallelized across all segments via ThreadPoolExecutor.
"""

import re
import json
import wave
import time
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

OPENAI_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

MAX_TTS_WORKERS = 6  # Max parallel OpenAI TTS requests


@dataclass
class NarrationBeat:
    """A single narration beat (sentence or phrase)."""
    beat_id: int
    text: str
    audio_file: Optional[str] = None
    duration: Optional[float] = None
    start_time: float = 0.0  # Cumulative start time in scene


CJK_LANGUAGES = {"ja", "zh", "ko"}
CJK_CHAR_PER_WORD = 3  # ~3 CJK characters ≈ 1 English word for pacing purposes


def _count_units(text: str, language: str) -> int:
    """Count words (Latin/Cyrillic) or character-equivalent units (CJK)."""
    if language in CJK_LANGUAGES:
        # Count non-whitespace characters, divide by CJK_CHAR_PER_WORD
        char_count = len(re.sub(r'\s+', '', text))
        return max(1, char_count // CJK_CHAR_PER_WORD)
    return len(text.split())


def split_into_beats(narration: str, min_words: int = 8, max_words: int = 25, language: str = "en") -> List[str]:
    """
    Split narration into beats (sentences or natural phrase breaks).

    Args:
        narration: Full narration text
        min_words: Minimum words (or CJK char-equivalent units) per beat
        max_words: Maximum words (or CJK char-equivalent units) per beat
        language: ISO 639-1 language code

    Returns:
        List of beat texts
    """
    # Sentence splitting works for all languages (CJK/Arabic also use .!? or equivalents)
    sentences = re.split(r'(?<=[.!?\u3002\uff01\uff1f\u061f])\s*', narration.strip())
    sentences = [s for s in sentences if s.strip()]

    beats = []
    current_beat = []
    current_count = 0

    for sentence in sentences:
        unit_count = _count_units(sentence, language)

        if current_count + unit_count <= max_words:
            current_beat.append(sentence)
            current_count += unit_count
        else:
            if current_count >= min_words:
                beats.append(' '.join(current_beat) if language not in CJK_LANGUAGES else ''.join(current_beat))
                current_beat = [sentence]
                current_count = unit_count
            else:
                current_beat.append(sentence)
                joiner = '' if language in CJK_LANGUAGES else ' '
                beats.append(joiner.join(current_beat))
                current_beat = []
                current_count = 0

    if current_beat:
        joiner = '' if language in CJK_LANGUAGES else ' '
        beats.append(joiner.join(current_beat))

    return beats


class BeatSyncTTS:
    """Generate beat-synchronized TTS using OpenAI."""

    def __init__(
        self,
        voice: str = "nova",
        sample_rate: int = 24000
    ):
        self.voice = voice
        self.sample_rate = sample_rate
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
            model="tts-1",
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
        min_words: int = 8,
        max_words: int = 25,
        language: str = "en"
    ) -> List[NarrationBeat]:
        """
        Generate beat-synced audio for an entire segment.

        Returns:
            List of NarrationBeat objects with timing
        """
        narration = segment.get('narration_script', '').strip()
        if not narration:
            return []

        segment_id = segment.get('segment_id', 'unknown')
        title = segment.get('title', 'Untitled')

        print(f"\n{'='*70}")
        print(f"Segment: {segment_id} - {title}")
        print(f"{'='*70}")

        beat_texts = split_into_beats(narration, min_words, max_words, language)
        print(f"Split into {len(beat_texts)} beats")

        beats = []
        cumulative_time = 0.0

        for i, text in enumerate(beat_texts, 1):
            beat_id = i
            safe_segment_id = segment_id.replace('/', '_').replace(' ', '_')
            audio_file = Path(output_dir) / f"{safe_segment_id}_beat_{beat_id}.wav"

            print(f"\nBeat {beat_id}/{len(beat_texts)}:")
            print(f"  Text: {text[:60]}{'...' if len(text) > 60 else ''}")

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

            print(f"  Duration: {duration:.2f}s (generated in {gen_time:.2f}s)")
            print(f"  File: {audio_file.name}")

        total_duration = cumulative_time
        print(f"\nTotal segment duration: {total_duration:.2f}s")
        print(f"Average beat length: {total_duration/len(beats):.2f}s")

        return beats


@dataclass
class _BeatJob:
    """Internal: describes a single TTS job for parallel execution."""
    segment_id: str
    beat_id: int
    text: str
    audio_file: str


def generate_beat_timeline(
    explanation_path: str,
    output_dir: str = "src/research_viz/manim_generator/output/audio_beats",
    voice: str = "nova",
    min_words: int = 8,
    max_words: int = 25,
    language: str = "en",
    max_workers: int = MAX_TTS_WORKERS
) -> Dict[str, List[NarrationBeat]]:
    """
    Generate complete beat timeline for all segments.

    All TTS calls across all segments are parallelized via ThreadPoolExecutor.
    Cumulative timing is computed after all audio durations are known.

    Returns:
        Dict mapping segment_id to list of beats
    """
    with open(explanation_path, 'r') as f:
        explanation = json.load(f)

    segments = explanation.get('segments', [])
    print(f"\nGenerating beat timeline for {len(segments)} segments")
    print(f"Voice: {voice}, Language: {language}")
    print(f"Beat length: {min_words}-{max_words} words")
    print(f"Max parallel TTS workers: {max_workers}\n")

    # Phase 1: Split all segments into beats (CPU-only, fast)
    jobs: List[_BeatJob] = []
    segment_beat_counts: Dict[str, int] = {}  # segment_id -> number of beats

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    for segment in segments:
        segment_id = segment.get('segment_id', 'unknown')
        narration = segment.get('narration_script', '').strip()
        if not narration:
            segment_beat_counts[segment_id] = 0
            continue

        beat_texts = split_into_beats(narration, min_words, max_words, language)
        segment_beat_counts[segment_id] = len(beat_texts)
        safe_segment_id = segment_id.replace('/', '_').replace(' ', '_')

        print(f"Segment {segment_id} ({segment.get('title', 'Untitled')}): {len(beat_texts)} beats")

        for i, text in enumerate(beat_texts, 1):
            audio_file = str(Path(output_dir) / f"{safe_segment_id}_beat_{i}.wav")
            jobs.append(_BeatJob(
                segment_id=segment_id,
                beat_id=i,
                text=text,
                audio_file=audio_file
            ))

    print(f"\nTotal beats to generate: {len(jobs)}")

    if not jobs:
        # Still write an empty timeline so downstream steps find the file
        timeline_data = {
            'explanation_source': explanation_path,
            'voice': voice,
            'total_segments': len(segments),
            'segments': {
                seg.get('segment_id', 'unknown'): {
                    'beat_count': 0,
                    'total_duration': 0.0,
                    'beats': []
                }
                for seg in segments
            }
        }
        metadata_path = Path(output_dir) / "beat_timeline.json"
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with open(metadata_path, 'w') as f:
            json.dump(timeline_data, f, indent=2)
        print(f"\nBeat timeline saved to {metadata_path} (no beats)")
        return {}

    # Phase 2: Generate all beat audio in parallel
    tts = BeatSyncTTS(voice=voice)
    # Eagerly load the client so all threads share the same connection pool
    tts._load_client()

    # Map (segment_id, beat_id) -> duration
    durations: Dict[tuple, float] = {}
    gen_start = time.monotonic()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_job = {
            executor.submit(tts.generate_beat_audio, job.text, job.audio_file): job
            for job in jobs
        }

        for future in as_completed(future_to_job):
            job = future_to_job[future]
            try:
                duration = future.result()
                durations[(job.segment_id, job.beat_id)] = duration
                print(f"  [{len(durations)}/{len(jobs)}] {job.segment_id} beat {job.beat_id}: "
                      f"{duration:.2f}s  \"{job.text[:50]}{'...' if len(job.text) > 50 else ''}\"")
            except Exception as e:
                print(f"  ERROR: {job.segment_id} beat {job.beat_id}: {e}")
                # Estimate duration from word count (~2.5 words/sec) so downstream
                # sync doesn't break.  A zero duration causes divide-by-zero or
                # missing audio segments in the final video.
                word_count = len(job.text.split())
                estimated = max(1.0, word_count / 2.5)
                durations[(job.segment_id, job.beat_id)] = estimated
                print(f"         Using estimated duration: {estimated:.1f}s ({word_count} words)")

    gen_elapsed = time.monotonic() - gen_start
    print(f"\nAll {len(jobs)} beats generated in {gen_elapsed:.1f}s "
          f"(avg {gen_elapsed/len(jobs):.2f}s/beat, {len(jobs)/gen_elapsed:.1f} beats/s)")

    # Phase 3: Assemble timeline with cumulative timing per segment
    timeline: Dict[str, List[NarrationBeat]] = {}

    for job in jobs:
        if job.segment_id not in timeline:
            timeline[job.segment_id] = []

    for job in jobs:
        duration = durations.get((job.segment_id, job.beat_id), 0.0)
        beat = NarrationBeat(
            beat_id=job.beat_id,
            text=job.text,
            audio_file=job.audio_file,
            duration=duration,
            start_time=0.0  # computed below
        )
        timeline[job.segment_id].append(beat)

    # Sort beats within each segment and compute cumulative start_time
    for seg_id in timeline:
        timeline[seg_id].sort(key=lambda b: b.beat_id)
        cumulative = 0.0
        for beat in timeline[seg_id]:
            beat.start_time = cumulative
            cumulative += beat.duration

    # Include segments with no narration as empty lists
    for segment in segments:
        seg_id = segment.get('segment_id', 'unknown')
        if seg_id not in timeline:
            timeline[seg_id] = []

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

    print(f"\nBeat timeline saved to {metadata_path}")

    total_beats = sum(len(beats) for beats in timeline.values())
    total_duration = sum(
        sum(b.duration for b in beats)
        for beats in timeline.values()
    )
    print(f"Total beats: {total_beats}")
    print(f"Total duration: {total_duration:.1f}s")

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
    parser.add_argument(
        "--language",
        default="en",
        help="ISO 639-1 language code (default: en)"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=MAX_TTS_WORKERS,
        help=f"Max parallel TTS workers (default: {MAX_TTS_WORKERS})"
    )

    args = parser.parse_args()

    generate_beat_timeline(
        explanation_path=args.explanation_path,
        output_dir=args.output_dir,
        voice=args.voice,
        min_words=args.min_words,
        max_words=args.max_words,
        language=args.language,
        max_workers=args.max_workers
    )


if __name__ == "__main__":
    main()
