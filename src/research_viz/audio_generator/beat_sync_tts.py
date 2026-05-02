"""
Beat-synchronized TTS Generation

Splits narration into beats (sentences/phrases), generates TTS per beat,
and tracks timing for precise animation sync.

Beat audio generation is parallelized across all segments via ThreadPoolExecutor.
"""

import logging
import re
import json
import wave
import time
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from research_viz.config.pipeline_config import get_config

logger = logging.getLogger(__name__)

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
    """Generate beat-synchronized TTS using OpenRouter or OpenAI."""

    def __init__(
        self,
        voice: Optional[str] = None,
        sample_rate: Optional[int] = None
    ):
        cfg = get_config()
        self.voice = voice if voice is not None else cfg.audio.voice
        self.sample_rate = sample_rate if sample_rate is not None else cfg.audio.sample_rate
        self.tts_model = cfg.audio.tts_model
        self.provider = getattr(cfg.audio, 'provider', 'openai')
        self.client = None

    def _load_client(self):
        """Lazy load OpenAI-compatible client (OpenRouter or OpenAI)."""
        if self.client is None:
            import os
            from openai import OpenAI
            if self.provider == "openrouter":
                self.client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=os.getenv("OPENROUTER_API_KEY"),
                )
            else:
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

        # OpenRouter's Gemini TTS rejects response_format="wav"; only mp3/pcm
        # are supported. We request pcm (raw 16-bit mono samples) and wrap
        # with a WAV header so the rest of the pipeline keeps working with
        # standard .wav files.
        use_pcm = self.provider == "openrouter"
        response = self.client.audio.speech.create(
            model=self.tts_model,
            voice=self.voice,
            input=text,
            response_format="pcm" if use_pcm else "wav",
        )
        if use_pcm:
            pcm_bytes = response.read()
            with wave.open(str(output_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(pcm_bytes)
        else:
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
        max_words: Optional[int] = None,
        language: str = "en",
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

        beat_texts = split_into_beats(narration, min_words, max_words, language)
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


class StreamingBeatGenerator:
    """Generates TTS beats and signals per-segment completion via threading.Event.

    Pipeline-parallel callers (e.g. pipelined_codegen_render_sync) can wait
    on `event_for(segment_id)` to gate the sync stage on per-segment audio
    readiness, instead of waiting for the whole batch.
    """

    def __init__(
        self,
        explanation: dict,
        output_dir: str,
        voice: Optional[str] = None,
        min_words: Optional[int] = None,
        max_words: Optional[int] = None,
        language: str = "en",
        max_workers: int = MAX_TTS_WORKERS,
        on_segment_ready: Optional[callable] = None,
    ):
        import threading
        cfg = get_config()
        self.voice = voice or cfg.audio.voice
        self.min_words = min_words if min_words is not None else cfg.audio.min_words_per_beat
        self.max_words = max_words if max_words is not None else cfg.audio.max_words_per_beat
        self.language = language
        self.max_workers = max_workers
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.explanation = explanation
        self._on_segment_ready = on_segment_ready

        self._lock = threading.Lock()
        self._segment_events: Dict[str, threading.Event] = {}
        self._segment_data: Dict[str, dict] = {}
        self._segment_remaining: Dict[str, int] = {}
        self._beat_durations: Dict[tuple, float] = {}
        self._beat_texts: Dict[tuple, str] = {}
        self._beat_files: Dict[tuple, str] = {}
        self._beat_order: Dict[str, list[int]] = {}
        self._executor: Optional[ThreadPoolExecutor] = None
        self._tts: Optional[BeatSyncTTS] = None
        self._jobs_total = 0
        self._gen_start: Optional[float] = None

        for seg in explanation.get('segments', []):
            seg_id = seg.get('segment_id')
            if seg_id:
                self._segment_events[seg_id] = threading.Event()

    def event_for(self, segment_id: str):
        return self._segment_events.get(segment_id)

    def get_segment_audio(self, segment_id: str) -> Optional[dict]:
        with self._lock:
            return self._segment_data.get(segment_id)

    def start(self):
        """Submit all TTS jobs to a background thread pool and return immediately."""
        segments = self.explanation.get('segments', [])
        jobs: list[_BeatJob] = []

        for segment in segments:
            seg_id = segment.get('segment_id', 'unknown')
            narration = segment.get('narration_script', '').strip()
            if not narration:
                self._segment_remaining[seg_id] = 0
                self._beat_order[seg_id] = []
                self._segment_data[seg_id] = {'beat_count': 0, 'total_duration': 0.0, 'beats': []}
                self._segment_events[seg_id].set()
                continue

            beat_texts = split_into_beats(narration, self.min_words, self.max_words, self.language)
            self._segment_remaining[seg_id] = len(beat_texts)
            self._beat_order[seg_id] = list(range(1, len(beat_texts) + 1))
            safe_id = seg_id.replace('/', '_').replace(' ', '_')
            for i, text in enumerate(beat_texts, 1):
                audio_file = str(self.output_dir / f"{safe_id}_beat_{i}.wav")
                self._beat_texts[(seg_id, i)] = text
                self._beat_files[(seg_id, i)] = audio_file
                jobs.append(_BeatJob(seg_id, i, text, audio_file))

        self._jobs_total = len(jobs)
        logger.info(f"StreamingBeatGenerator: {len(jobs)} beats across {len(segments)} segments")

        if not jobs:
            return

        self._tts = BeatSyncTTS(voice=self.voice)
        self._tts._load_client()
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix='tts')
        self._gen_start = time.monotonic()

        for job in jobs:
            self._executor.submit(self._run_beat, job)

    def _run_beat(self, job: '_BeatJob'):
        try:
            duration = self._tts.generate_beat_audio(job.text, job.audio_file)
        except Exception as exc:
            wc = len(job.text.split())
            duration = max(1.0, wc / 2.5)
            logger.error(
                f"  TTS error {job.segment_id} beat {job.beat_id}: {exc}; "
                f"using estimated duration {duration:.1f}s"
            )
        with self._lock:
            self._beat_durations[(job.segment_id, job.beat_id)] = duration
            self._segment_remaining[job.segment_id] -= 1
            done = self._segment_remaining[job.segment_id] == 0
        if done:
            self._finalize_segment(job.segment_id)

    def _finalize_segment(self, seg_id: str):
        beat_ids = sorted(self._beat_order.get(seg_id, []))
        beats: list[dict] = []
        cumulative = 0.0
        for bi in beat_ids:
            d = self._beat_durations.get((seg_id, bi), 0.0)
            beats.append({
                'beat_id': bi,
                'text': self._beat_texts[(seg_id, bi)],
                'audio_file': self._beat_files[(seg_id, bi)],
                'duration': d,
                'start_time': cumulative,
            })
            cumulative += d
        seg_data = {
            'beat_count': len(beats),
            'total_duration': cumulative,
            'beats': beats,
        }
        with self._lock:
            self._segment_data[seg_id] = seg_data
        evt = self._segment_events.get(seg_id)
        if evt:
            evt.set()
        logger.info(f"  audio READY for {seg_id}: {len(beats)} beats, {cumulative:.1f}s")
        if self._on_segment_ready is not None:
            try:
                self._on_segment_ready(seg_id, seg_data)
            except Exception as exc:
                logger.warning(f"on_segment_ready raised for {seg_id}: {exc}")

    def shutdown_and_write_timeline(self) -> Optional[str]:
        """Wait for all jobs, write the consolidated beat_timeline.json."""
        if self._executor:
            self._executor.shutdown(wait=True)
            elapsed = time.monotonic() - (self._gen_start or time.monotonic())
            logger.info(
                f"StreamingBeatGenerator: all {self._jobs_total} beats done in {elapsed:.1f}s"
            )
        timeline_path = self.output_dir / "beat_timeline.json"
        with self._lock:
            data = {
                'voice': self.voice,
                'total_segments': len(self._segment_data),
                'segments': dict(self._segment_data),
            }
        with open(timeline_path, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Beat timeline saved to {timeline_path}")
        return str(timeline_path)


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
    voice: Optional[str] = None,
    min_words: Optional[int] = None,
    max_words: Optional[int] = None,
    language: str = "en",
    max_workers: int = MAX_TTS_WORKERS,
) -> Dict[str, List[NarrationBeat]]:
    """
    Generate complete beat timeline for all segments.

    All TTS calls across all segments are parallelized via ThreadPoolExecutor.
    Cumulative timing is computed after all audio durations are known.

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
    logger.info(f"Voice: {voice}, Language: {language}")
    logger.info(f"Beat length: {min_words}-{max_words} words")
    logger.info(f"Max parallel TTS workers: {max_workers}")

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
