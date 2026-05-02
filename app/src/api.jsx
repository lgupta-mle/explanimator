// Backend API helpers — POST upload, SSE subscribe, segment URL builder.
// Loaded before any view component so window.api is always available.

const BACKEND_URL = window.ANVYA_BACKEND_URL || "http://localhost:8000";

const _DIFFICULTY_MAP = {
  easy: "easy",
  technical: "medium",
  scholar: "medium",
  initiate: "easy",
};

async function uploadPdf(file, mode) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("difficulty", _DIFFICULTY_MAP[mode] || "medium");
  const res = await fetch(`${BACKEND_URL}/api/generate`, { method: "POST", body: fd });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Upload failed (${res.status}): ${body}`);
  }
  return await res.json();
}

function subscribeEvents(jobId, onEvent, onError) {
  const url = `${BACKEND_URL}/api/events/${jobId}`;
  const es = new EventSource(url);
  // sse-starlette names events by `event:` field; we listen via `message`
  // catch-all by binding addEventListener to each known type AND a default.
  const types = [
    "pipeline_started",
    "explanation_started",
    "explanation_done",
    "audio_segment_ready",
    "codegen_segment_started",
    "codegen_segment_done",
    "codegen_segment_failed",
    "render_segment_started",
    "render_segment_done",
    "render_segment_failed",
    "sync_segment_started",
    "sync_segment_done",
    "pipeline_done",
    "pipeline_error",
  ];
  const handler = (e) => {
    try {
      const data = JSON.parse(e.data);
      onEvent(data);
    } catch (err) {
      console.error("SSE parse error", err, e.data);
    }
  };
  types.forEach((t) => es.addEventListener(t, handler));
  es.onerror = (err) => {
    if (onError) onError(err);
  };
  return () => es.close();
}

function segmentUrl(jobId, idx) {
  return `${BACKEND_URL}/api/segment/${jobId}/${idx}`;
}

async function fetchSegments(jobId) {
  const res = await fetch(`${BACKEND_URL}/api/segments/${jobId}`);
  if (!res.ok) throw new Error(`Failed to fetch segments: ${res.status}`);
  return await res.json();
}

window.api = { BACKEND_URL, uploadPdf, subscribeEvents, segmentUrl, fetchSegments };
