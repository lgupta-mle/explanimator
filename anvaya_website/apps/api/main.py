"""
FastAPI Backend for Anvaya — PDF to Animated Video Pipeline
"""

import os
import re
import sys
import uuid
import json
import threading
import traceback
from pathlib import Path
from typing import Dict, Any, Optional

import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from dotenv import load_dotenv

# Allow importing from the src/ tree
# File lives at anvaya/apps/api/main.py
# research-paper-graphviz root is 3 levels up from here
ROOT_DIR = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "src"))

# Load .env from multiple candidate locations
for _env_candidate in [
    ROOT_DIR / ".env",
    ROOT_DIR / "src" / "research_viz" / ".env",
    Path(__file__).parent.parent.parent.parent.parent / ".env",  # workspace root
]:
    if _env_candidate.exists():
        load_dotenv(_env_candidate)
        break

app = FastAPI(title="Anvaya Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory job store ─────────────────────────────────────────────────────
jobs: Dict[str, Dict[str, Any]] = {}

JOBS_DIR = Path(__file__).parent / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _clean_narration(text: str) -> str:
    """Strip stage directions and markdown from narration for display."""
    # Remove bracketed stage directions: [VISUAL: ...], [PAUSE 2s], etc.
    text = re.sub(r"\[[^\]]*\]", "", text)
    # Remove markdown bold/italic markers
    text = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}(.*?)_{1,3}", r"\1", text)
    # Remove markdown headers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove horizontal rules
    text = re.sub(r"^---+$", "", text, flags=re.MULTILINE)
    # Collapse extra whitespace/blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _seconds_to_timestamp(total_seconds: float) -> str:
    """Convert a float seconds value to M:SS display string."""
    total_seconds = max(0, int(total_seconds))
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def _estimate_duration(narration: str) -> int:
    """Estimate duration in seconds from narration word count (150 wpm)."""
    word_count = len(narration.split())
    return max(10, int(word_count / 2.5))


def _build_segment_list(explanation: dict, audio_timeline: Optional[dict] = None) -> list:
    """Build segment list with computed timestamps for the Player UI.

    If audio_timeline (beat_timeline.json contents) is provided, uses the actual
    rendered audio total_duration per segment for accurate start times.
    Falls back to word-count estimation when not available.
    """
    segments_raw = explanation.get("segments", [])
    segments_raw = sorted(segments_raw, key=lambda s: s.get("order", 0))

    audio_segments = (audio_timeline or {}).get("segments", {})

    result = []
    current_time = 0.0
    for seg in segments_raw:
        segment_id = seg.get("segment_id", "")
        if segment_id and segment_id in audio_segments:
            duration = audio_segments[segment_id].get("total_duration") or _estimate_duration(
                seg.get("narration_script", "")
            )
        else:
            duration = seg.get("estimated_duration_seconds") or _estimate_duration(
                seg.get("narration_script", "")
            )
        raw_narration = seg.get("narration_script", "")
        result.append({
            "title": seg.get("title", "Untitled"),
            "order": seg.get("order", 0),
            "narration_script": raw_narration,
            "narration_clean": _clean_narration(raw_narration),
            "start_time": current_time,
            "timestamp": _seconds_to_timestamp(current_time),
            "duration": duration,
        })
        current_time += duration
    return result


# ── Background pipeline runner ───────────────────────────────────────────────

def run_pipeline(job_id: str, pdf_path: str):
    job = jobs[job_id]
    output_dir = str(JOBS_DIR / job_id / "output")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Model configuration
    explanation_model = "google/gemini-3.1-pro-preview"
    manim_model = "google/gemini-3.1-pro-preview"
    tts_voice = "nova"

    try:
        # ── Step 0: Extract concepts ──────────────────────────────────────
        job.update(status="extracting", step=0,
                   message="Extracting concepts from paper…")

        from research_viz.manim_generator.pdf_explanation_generator import (
            generate_explanation_from_pdf,
        )

        print(f"\n{'='*70}")
        print(f"STEP 0: EXPLANATION GENERATION")
        print(f"{'='*70}")
        print(f"Model: {explanation_model}")
        print(f"PDF: {pdf_path}")
        print(f"{'='*70}\n")

        explanation_path = f"{output_dir}/explanation.json"
        explanation = generate_explanation_from_pdf(
            pdf_path=pdf_path,
            output_path=explanation_path,
            model_name=explanation_model,
            max_judge_attempts=2,
        )

        if not explanation:
            job.update(status="failed", error="Failed to generate explanation from PDF.")
            return

        # ── Step 1: Build animation code ──────────────────────────────────
        job.update(status="building", step=1,
                   message="Building animation structure…")

        from research_viz.manim_generator.pdf_to_manim_pipeline import (
            generate_all_scenes,
            assemble_complete_code,
        )

        print(f"\n{'='*70}")
        print(f"STEP 1: MANIM CODE GENERATION")
        print(f"{'='*70}")
        print(f"Model: {manim_model}")
        print(f"Segments: {len(explanation.get('segments', []))}")
        print(f"{'='*70}\n")

        scene_codes = generate_all_scenes(
            explanation=explanation,
            model_name=manim_model,
            max_retries=3,
        )

        if not scene_codes:
            job.update(status="failed", error="Failed to generate animation code.")
            return

        paper_title = explanation.get("paper_title", "paper")
        complete_code = assemble_complete_code(scene_codes, paper_title)
        with open(f"{output_dir}/animation.py", "w") as f:
            f.write(complete_code)

        # Save scene metadata
        scene_meta_path = f"{output_dir}/scene_metadata.json"
        with open(scene_meta_path, "w") as f:
            json.dump([sc.model_dump() for sc in scene_codes], f, indent=2)

        # ── Step 2: Render animation ──────────────────────────────────────
        job.update(status="rendering", step=2,
                   message="Rendering animation…")

        audio_dir = f"{output_dir}/audio_beats"
        audio_timeline_path = f"{audio_dir}/beat_timeline.json"

        from research_viz.audio_generator.beat_sync_tts import generate_beat_timeline

        print(f"\n{'='*70}")
        print(f"STEP 2: AUDIO & VIDEO RENDERING")
        print(f"{'='*70}")
        print(f"TTS Voice: {tts_voice}")
        print(f"{'='*70}\n")

        generate_beat_timeline(
            explanation_path=explanation_path,
            output_dir=audio_dir,
            voice=tts_voice,
        )

        from research_viz.manim_generator.pdf_to_manim_pipeline import (
            render_and_sync_all_scenes,
        )

        final_video = render_and_sync_all_scenes(
            scene_codes=scene_codes,
            explanation=explanation,
            audio_timeline_path=audio_timeline_path,
            output_dir=output_dir,
            quality="l",
            sync_mode="segment",
            max_speed_change=0.3,
        )

        if not final_video:
            job.update(status="failed", error="Failed to render final video.")
            return

        # ── Done ──────────────────────────────────────────────────────────
        # Load beat timeline for accurate segment durations
        audio_timeline_data = None
        if os.path.exists(audio_timeline_path):
            with open(audio_timeline_path, "r") as f:
                audio_timeline_data = json.load(f)

        segments = _build_segment_list(explanation, audio_timeline=audio_timeline_data)
        full_transcript = "\n\n".join(
            s["narration_script"] for s in segments if s["narration_script"]
        )

        job.update(
            status="completed",
            step=3,
            message="Done!",
            video_path=final_video,
            paper_title=paper_title,
            segments=segments,
            transcript=full_transcript,
            models={
                "explanation": explanation_model,
                "manim_code": manim_model,
                "tts_voice": tts_voice,
            },
        )

    except Exception as e:
        job.update(
            status="failed",
            error=str(e),
            traceback=traceback.format_exc(),
        )


# ── API Routes ───────────────────────────────────────────────────────────────

@app.post("/api/generate")
async def generate_video(file: UploadFile = File(...)):
    """Accept a PDF and kick off the generation pipeline."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    job_id = str(uuid.uuid4())
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = str(job_dir / file.filename)
    with open(pdf_path, "wb") as f:
        f.write(await file.read())

    jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "step": 0,
        "message": "Job queued…",
        "filename": file.filename,
        "pdf_path": pdf_path,
        "error": None,
        "video_path": None,
        "segments": [],
        "transcript": "",
        "paper_title": "",
    }

    thread = threading.Thread(target=run_pipeline, args=(job_id, pdf_path), daemon=True)
    thread.start()

    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    """Poll the current status of a generation job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found.")
    job = jobs[job_id]
    return {
        "job_id": job_id,
        "status": job["status"],
        "step": job.get("step", 0),
        "message": job.get("message", ""),
        "error": job.get("error"),
        "filename": job.get("filename", ""),
    }


@app.get("/api/result/{job_id}")
async def get_result(job_id: str):
    """Get the full result (segments, transcript, video URL) for a completed job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found.")
    job = jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Job not completed (status: {job['status']}).")
    return {
        "job_id": job_id,
        "paper_title": job.get("paper_title", "Untitled"),
        "video_url": f"/api/video/{job_id}",
        "segments": job.get("segments", []),
        "transcript": job.get("transcript", ""),
        "models": job.get("models", {}),
    }


@app.get("/api/video/{job_id}")
async def serve_video(job_id: str):
    """Stream the generated video file."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found.")
    video_path = jobs[job_id].get("video_path")
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found.")
    return FileResponse(video_path, media_type="video/mp4")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
