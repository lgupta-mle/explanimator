#!/usr/bin/env python3
"""
Script to register the pre-existing Unified Latents video into the backend job system.
"""
import json
import sys
from pathlib import Path

# Job ID we created
JOB_ID = "6e4688e0-92cc-49f0-8ba8-c5bf4c4d4d27"

# Paths
JOBS_DIR = Path(__file__).parent / "jobs"
job_dir = JOBS_DIR / JOB_ID / "output"
beat_timeline_path = job_dir / "audio_beats" / "beat_timeline.json"

# Load beat timeline to extract segments
with open(beat_timeline_path, "r") as f:
    audio_timeline = json.load(f)

# Build segments from beat timeline
segments = []
full_transcript = []
current_time = 0.0

for seg_key, seg_data in audio_timeline["segments"].items():
    beats = seg_data["beats"]
    
    # Extract title from first beat or segment key
    title = seg_key.replace("_", " ").title()
    
    # Combine all beat texts for this segment
    narration_parts = [beat["text"] for beat in beats]
    narration_script = " ".join(narration_parts)
    
    # Clean narration (remove stage directions)
    import re
    narration_clean = re.sub(r"\[[^\]]*\]", "", narration_script)
    narration_clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", narration_clean)
    narration_clean = re.sub(r"\*([^*]+)\*", r"\1", narration_clean)
    narration_clean = " ".join(narration_clean.split())
    
    duration = seg_data["total_duration"]
    
    segment = {
        "title": title,
        "order": len(segments),
        "narration_script": narration_script,
        "narration_clean": narration_clean,
        "start_time": current_time,
        "timestamp": f"{int(current_time // 60)}:{int(current_time % 60):02d}",
        "duration": duration,
    }
    
    segments.append(segment)
    full_transcript.append(narration_clean)
    current_time += duration

# Create job metadata JSON
job_metadata = {
    "job_id": JOB_ID,
    "status": "completed",
    "step": 3,
    "message": "Done!",
    "filename": "Unified_Latents.pdf",
    "pdf_path": str(job_dir.parent / "Unified_Latents.pdf"),
    "difficulty": "medium",
    "error": None,
    "video_path": str(job_dir / "final_video.mp4"),
    "paper_title": "Unified Latents (UL): How to train your latents",
    "segments": segments,
    "transcript": "\n\n".join(full_transcript),
    "models": {
        "explanation": "google/gemini-3.1-pro-preview",
        "manim_code": "google/gemini-3.1-pro-preview",
        "tts_voice": "fable",
        "difficulty": "medium",
    }
}

# Save to a JSON file that can be loaded
output_file = JOBS_DIR / JOB_ID / "job_metadata.json"
with open(output_file, "w") as f:
    json.dump(job_metadata, f, indent=2)

print(f"✓ Job metadata saved to: {output_file}")
print(f"✓ Job ID: {JOB_ID}")
print(f"✓ Paper: {job_metadata['paper_title']}")
print(f"✓ Segments: {len(segments)}")
print(f"✓ Total duration: {current_time:.1f}s")
print(f"\nTo use this video in the frontend:")
print(f"1. Navigate to: http://localhost:8080/player")
print(f"2. Use job_id: {JOB_ID}")
print(f"\nOr add this to localStorage manually in browser console:")
print(f'localStorage.setItem("anvaya_videos", JSON.stringify([{{')
print(f'  "job_id": "{JOB_ID}",')
print(f'  "paper_title": "Unified Latents (UL): How to train your latents (Scholar)",')
print(f'  "date": "{{"new Date().toLocaleDateString("en-US", {{"month": "short", "day": "numeric", "year": "numeric"}})}}",')
print(f'  "duration_seconds": {current_time:.1f},')
print(f'  "segments_count": {len(segments)},')
print(f'  "difficulty": "medium"')
print(f'}}]));')
