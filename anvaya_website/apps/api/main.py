"""
FastAPI Backend for Anvaya — PDF to Animated Video Pipeline
"""

import asyncio
import os
import queue
import re
import sys
import uuid
import json
import threading
import time
import traceback
from pathlib import Path
from typing import Dict, Any, Optional

import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from sse_starlette.sse import EventSourceResponse

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

# Load existing job metadata on startup
def _load_existing_jobs():
    """Load job metadata from disk for any completed jobs."""
    for job_dir in JOBS_DIR.iterdir():
        if not job_dir.is_dir():
            continue
        metadata_file = job_dir / "job_metadata.json"
        if metadata_file.exists():
            try:
                with open(metadata_file, "r") as f:
                    job_data = json.load(f)
                    job_id = job_data.get("job_id")
                    if job_id:
                        jobs[job_id] = job_data
                        print(f"Loaded existing job: {job_id} - {job_data.get('paper_title', 'Untitled')}")
            except Exception as e:
                print(f"Failed to load job metadata from {metadata_file}: {e}")

_load_existing_jobs()


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

def _publish_event(job: Dict[str, Any], event: dict) -> None:
    """Push an event onto the job's queue (for SSE listeners) and update job state."""
    event = dict(event)
    event.setdefault("ts", time.time())
    q: Optional[queue.Queue] = job.get("events")
    if q is not None:
        q.put(event)
    # Mirror key transitions into the polling-friendly status field
    et = event.get("type")
    if et == "pipeline_started":
        job["status"] = "running"
        job["message"] = "Starting pipeline…"
    elif et == "explanation_started":
        job["status"] = "extracting"
        job["message"] = "Reading the paper…"
    elif et == "explanation_done":
        job["message"] = "Explanation ready"
    elif et == "audio_segment_ready":
        idx = event.get("segment_idx", -1)
        job["message"] = f"Audio ready for segment {idx + 1}"
    elif et == "codegen_segment_done":
        idx = event.get("segment_idx", -1)
        job["message"] = f"Codegen done for segment {idx + 1}"
    elif et == "render_segment_done":
        idx = event.get("segment_idx", -1)
        job["message"] = f"Render done for segment {idx + 1}"
    elif et == "sync_segment_done":
        idx = event.get("segment_idx", -1)
        job["message"] = f"Segment {idx + 1} ready to watch"
        # Track ready segments
        job.setdefault("ready_segments", set()).add(idx)
    elif et == "pipeline_done":
        job["status"] = "completed"
        job["step"] = 3
        job["message"] = "Done!"
        if event.get("payload", {}).get("final_video_path"):
            job["video_path"] = event["payload"]["final_video_path"]
    elif et == "pipeline_error":
        job["status"] = "failed"
        job["error"] = event.get("payload", {}).get("message", "Pipeline error")


def run_pipeline(job_id: str, pdf_path: str, difficulty: str = "medium"):
    job = jobs[job_id]
    output_dir = str(JOBS_DIR / job_id / "output")
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    base_dir = output_dir  # pipeline writes per-segment artifacts directly here

    from research_viz.config.difficulty import DIFFICULTY_CONFIGS
    difficulty_config = DIFFICULTY_CONFIGS.get(difficulty, DIFFICULTY_CONFIGS["medium"])

    def emit(event: dict):
        _publish_event(job, event)

    try:
        emit({"type": "pipeline_started", "payload": {"job_id": job_id, "difficulty": difficulty}})

        # ── Step 0: Explanation ──────────────────────────────────────────
        from research_viz.manim_generator.pdf_explanation_generator import (
            generate_explanation_from_pdf,
        )

        emit({"type": "explanation_started"})

        explanation_path = f"{output_dir}/explanation.json"
        explanation = generate_explanation_from_pdf(
            pdf_path=pdf_path,
            output_path=explanation_path,
            difficulty=difficulty,
            max_judge_attempts=3,
            difficulty_config=difficulty_config,
        )

        if not explanation:
            emit({"type": "pipeline_error", "payload": {"message": "Explanation generation failed"}})
            return

        segments_meta = explanation.get("segments", [])
        paper_title = explanation.get("paper_title", "paper")
        job["paper_title"] = paper_title
        # Pre-populate segment titles so the frontend can render placeholder cards
        job["segments"] = [
            {
                "idx": i,
                "segment_id": s.get("segment_id", f"seg_{i+1:02d}"),
                "title": s.get("title", f"Segment {i + 1}"),
                "narration_script": s.get("narration_script", ""),
                "narration_clean": _clean_narration(s.get("narration_script", "")),
                "duration_seconds": 0.0,  # filled in when audio_segment_ready arrives
                "ready": False,
                "url": None,
            }
            for i, s in enumerate(segments_meta)
        ]
        emit({
            "type": "explanation_done",
            "payload": {
                "paper_title": paper_title,
                "total_segments": len(segments_meta),
                "segments": [{"idx": i, "title": s["title"]} for i, s in enumerate(job["segments"])],
            },
        })

        # ── Step 1: Streaming audio + pipeline-parallel codegen → render → sync ──
        from research_viz.audio_generator.beat_sync_tts import StreamingBeatGenerator
        from research_viz.manim_generator.pdf_to_manim_pipeline import (
            pipelined_codegen_render_sync,
            assemble_complete_code,
        )

        # Map segment_id -> idx for the audio callback
        seg_id_to_idx = {s["segment_id"]: i for i, s in enumerate(job["segments"])}

        def on_audio_ready(seg_id: str, seg_data: dict):
            idx = seg_id_to_idx.get(seg_id, -1)
            if 0 <= idx < len(job["segments"]):
                job["segments"][idx]["duration_seconds"] = seg_data.get("total_duration", 0.0)
            emit({
                "type": "audio_segment_ready",
                "segment_idx": idx,
                "segment_id": seg_id,
                "payload": {
                    "duration_seconds": seg_data.get("total_duration", 0.0),
                    "beat_count": seg_data.get("beat_count", 0),
                },
            })

        def on_pipeline_event(event: dict):
            # Forward all pipelined events; enrich sync_segment_done with the
            # frontend-facing URL so it points at /api/segment/{job_id}/{idx}.
            if event.get("type") == "sync_segment_done":
                idx = event.get("segment_idx", -1)
                event = dict(event)
                event.setdefault("payload", {})
                event["payload"]["url"] = f"/api/segment/{job_id}/{idx}"
                if 0 <= idx < len(job["segments"]):
                    job["segments"][idx]["ready"] = True
                    job["segments"][idx]["url"] = event["payload"]["url"]
            emit(event)

        audio_dir = f"{output_dir}/audio_beats"
        audio_streamer = StreamingBeatGenerator(
            explanation=explanation,
            output_dir=audio_dir,
            voice=None,
            min_words=difficulty_config.beat_min_words,
            max_words=difficulty_config.beat_max_words,
            language="en",
            on_segment_ready=on_audio_ready,
        )
        audio_streamer.start()

        try:
            scene_codes, final_video = pipelined_codegen_render_sync(
                explanation=explanation,
                difficulty=difficulty,
                output_dir=base_dir,
                audio_streamer=audio_streamer,
                event_callback=on_pipeline_event,
            )
        finally:
            audio_streamer.shutdown_and_write_timeline()

        successful = [s for s in scene_codes if s is not None]
        if successful:
            complete_code = assemble_complete_code(successful, paper_title)
            with open(f"{output_dir}/animation.py", "w") as f:
                f.write(complete_code)
            with open(f"{output_dir}/scene_metadata.json", "w") as f:
                json.dump([sc.model_dump() for sc in successful], f, indent=2)

        if not final_video:
            emit({"type": "pipeline_error", "payload": {"message": "Final video stitching failed"}})
            return

        # ── Done — pipeline_done was already emitted by the pipelined function ──
        full_transcript = "\n\n".join(
            s["narration_clean"] for s in job["segments"] if s.get("narration_clean")
        )
        job["transcript"] = full_transcript
        job["models"] = {"difficulty": difficulty}

    except Exception as e:
        emit({"type": "pipeline_error", "payload": {"message": str(e)}})
        job["traceback"] = traceback.format_exc()
    finally:
        # Sentinel so the SSE generator knows to close cleanly
        if job.get("events") is not None:
            job["events"].put(None)


# ── API Routes ───────────────────────────────────────────────────────────────

# UI label → pipeline difficulty name
_DIFFICULTY_MAP = {
    "initiate": "easy",
    "scholar": "medium",
    "easy": "easy",
    "medium": "medium",
}


@app.post("/api/generate")
async def generate_video(
    file: UploadFile = File(...),
    difficulty: str = Form("scholar"),
):
    """Accept a PDF and kick off the generation pipeline."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    pipeline_difficulty = _DIFFICULTY_MAP.get(difficulty, "medium")

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
        "difficulty": pipeline_difficulty,
        "error": None,
        "video_path": None,
        "segments": [],
        "transcript": "",
        "paper_title": "",
        "events": queue.Queue(),
        "ready_segments": set(),
    }

    thread = threading.Thread(
        target=run_pipeline,
        args=(job_id, pdf_path, pipeline_difficulty),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id}


@app.get("/api/jobs")
async def list_jobs():
    """Return all completed jobs as a list for the My Videos page."""
    result = []
    for job_id, job in jobs.items():
        if job.get("status") != "completed":
            continue
        segments = job.get("segments", [])
        total_duration = sum(s.get("duration", 0) for s in segments)
        result.append({
            "job_id": job_id,
            "paper_title": job.get("paper_title", "Untitled"),
            "difficulty": job.get("difficulty", "medium"),
            "segments_count": len(segments),
            "duration_seconds": total_duration,
        })
    return result


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
        "difficulty": job.get("difficulty", "medium"),
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


@app.get("/api/events/{job_id}")
async def stream_events(job_id: str):
    """Server-Sent Events stream for real-time pipeline progress."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found.")
    job = jobs[job_id]
    q: Optional[queue.Queue] = job.get("events")
    if q is None:
        raise HTTPException(status_code=410, detail="Job has no event stream (cached/old job).")

    async def gen():
        loop = asyncio.get_event_loop()
        while True:
            event = await loop.run_in_executor(None, q.get)
            if event is None:  # sentinel — pipeline finished, close stream
                break
            yield {"event": event.get("type", "message"), "data": json.dumps(event)}

    return EventSourceResponse(gen())


@app.get("/api/segments/{job_id}")
async def list_segments(job_id: str):
    """List per-segment metadata for the player UI (titles, durations, ready state, urls)."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {
        "job_id": job_id,
        "paper_title": jobs[job_id].get("paper_title", ""),
        "total_segments": len(jobs[job_id].get("segments", [])),
        "segments": jobs[job_id].get("segments", []),
    }


@app.get("/api/segment/{job_id}/{idx}")
async def serve_segment(job_id: str, idx: int):
    """Stream a single per-segment .mp4 from debug_ready_segments/."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found.")
    debug_dir = JOBS_DIR / job_id / "output" / "debug_ready_segments"
    if not debug_dir.exists():
        raise HTTPException(status_code=404, detail="Segment not yet available.")
    prefix = f"order{idx + 1:02d}_"
    matches = sorted(debug_dir.glob(f"{prefix}*.mp4"))
    if not matches:
        raise HTTPException(status_code=404, detail="Segment not yet available.")
    return FileResponse(matches[0], media_type="video/mp4")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
