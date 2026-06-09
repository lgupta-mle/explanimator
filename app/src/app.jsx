// App entry — view router + tweaks panel + SSE subscription lifecycle

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "palette": "manim",
  "font": "lora-inter",
  "heroVariant": "equation",
  "progressVariant": "diagram",
  "startView": "upload"
}/*EDITMODE-END*/;

const INITIAL_JOB_STATE = {
  job_id: null,
  paper_title: "",
  filename: "",
  total_segments: null,
  segment_1_stages: {
    explanation: "pending",
    audio: "pending",
    codegen: "pending",
    render: "pending",
    sync: "pending",
  },
  segments: {}, // idx -> { idx, title, ready, url, current_stage, duration_seconds }
  done: false,
  error: null,
};

function _setStage(stages, id, status) {
  if (stages[id] === status) return stages;
  return { ...stages, [id]: status };
}

function _seg(segments, idx, patch) {
  return {
    ...segments,
    [idx]: { idx, title: "", ready: false, url: null, current_stage: null, duration_seconds: 0, ...(segments[idx] || {}), ...patch },
  };
}

// Reconstruct a jobState shape from a /api/segments + /api/status snapshot.
// Used when re-hydrating across page reload — we may have missed SSE events
// that already drained from the backend queue.
function snapshotToJobState(segmentsResp, statusResp) {
  const list = segmentsResp.segments || [];
  const segments = {};
  list.forEach((s) => {
    segments[s.idx] = {
      idx: s.idx,
      title: s.title || `Segment ${s.idx + 1}`,
      ready: !!s.ready,
      url: s.url || null,
      current_stage: s.ready ? "ready" : (s.duration_seconds > 0 ? "codegen" : "queued"),
      duration_seconds: s.duration_seconds || 0,
    };
  });

  const status = statusResp.status || "queued";
  const done = status === "completed";
  const error = status === "failed" ? (statusResp.error || "Pipeline failed") : null;

  // Derive segment_1_stages from snapshot. Without an event log we assume
  // the natural ordering (explanation -> audio -> codegen -> render -> sync).
  const seg0 = segments[0];
  const stages = {
    explanation: "pending",
    audio: "pending",
    codegen: "pending",
    render: "pending",
    sync: "pending",
  };
  if (list.length > 0 || done) {
    stages.explanation = "done";
    // audio kicks off as soon as explanation completes; treat as running once
    // there are segments and assume done if any segment has duration.
    stages.audio = (seg0 && seg0.duration_seconds > 0) ? "done" : "running";
    stages.codegen = "running";
  }
  if (seg0) {
    if (seg0.ready) {
      stages.codegen = "done";
      stages.render = "done";
      stages.sync = "done";
    } else if (seg0.current_stage === "render" || seg0.current_stage === "sync") {
      stages.codegen = "done";
      stages.render = seg0.current_stage === "sync" ? "done" : "running";
      stages.sync = seg0.current_stage === "sync" ? "running" : "pending";
    }
  }
  if (done) {
    Object.keys(stages).forEach((k) => { stages[k] = "done"; });
  }

  return {
    job_id: segmentsResp.job_id,
    paper_title: segmentsResp.paper_title || "",
    filename: statusResp.filename || "",
    total_segments: segmentsResp.total_segments || list.length || null,
    segment_1_stages: stages,
    segments,
    done,
    error,
  };
}

function reduceJobState(state, event) {
  const t = event.type;
  const idx = event.segment_idx;
  const isFirst = idx === 0;

  if (t === "pipeline_started") {
    return { ...state, total_segments: event.payload?.total_segments ?? null };
  }
  if (t === "explanation_started") {
    return { ...state, segment_1_stages: _setStage(state.segment_1_stages, "explanation", "running") };
  }
  if (t === "explanation_done") {
    const segs = {};
    (event.payload?.segments || []).forEach((s) => {
      segs[s.idx] = { idx: s.idx, title: s.title, ready: false, url: null, current_stage: "queued", duration_seconds: 0 };
    });
    return {
      ...state,
      paper_title: event.payload?.paper_title || state.paper_title,
      total_segments: event.payload?.total_segments ?? state.total_segments,
      segments: segs,
      segment_1_stages: {
        ..._setStage(state.segment_1_stages, "explanation", "done"),
        audio: "running",  // audio for all segments starts in parallel with codegen
        codegen: "running",
      },
    };
  }
  if (t === "audio_segment_ready") {
    const newSegs = _seg(state.segments, idx, {
      title: state.segments[idx]?.title || event.segment_id,
      duration_seconds: event.payload?.duration_seconds || 0,
    });
    return {
      ...state,
      segments: newSegs,
      segment_1_stages: isFirst
        ? _setStage(state.segment_1_stages, "audio", "done")
        : state.segment_1_stages,
    };
  }
  if (t === "codegen_segment_started") {
    return {
      ...state,
      segments: _seg(state.segments, idx, { current_stage: "codegen" }),
    };
  }
  if (t === "codegen_segment_done") {
    return {
      ...state,
      segments: _seg(state.segments, idx, { current_stage: "render" }),
      segment_1_stages: isFirst
        ? { ..._setStage(state.segment_1_stages, "codegen", "done"), render: "running" }
        : state.segment_1_stages,
    };
  }
  if (t === "render_segment_done") {
    return {
      ...state,
      segments: _seg(state.segments, idx, { current_stage: "sync" }),
      segment_1_stages: isFirst
        ? { ..._setStage(state.segment_1_stages, "render", "done"), sync: "running" }
        : state.segment_1_stages,
    };
  }
  if (t === "sync_segment_done") {
    return {
      ...state,
      segments: _seg(state.segments, idx, {
        current_stage: "ready",
        ready: true,
        url: event.payload?.url || null,
      }),
      segment_1_stages: isFirst
        ? _setStage(state.segment_1_stages, "sync", "done")
        : state.segment_1_stages,
    };
  }
  if (t === "pipeline_done") {
    return { ...state, done: true };
  }
  if (t === "pipeline_error") {
    return { ...state, error: event.payload?.message || "Pipeline error" };
  }
  return state;
}

const App = () => {
  const tweakResult = window.useTweaks ? window.useTweaks(TWEAK_DEFAULTS) : [TWEAK_DEFAULTS, () => {}];
  const T = tweakResult[0];
  const setTweak = tweakResult[1];

  const [view, setView] = useState(T.startView || "landing");
  const [jobState, setJobState] = useState(INITIAL_JOB_STATE);
  const closeStreamRef = useRef(null);
  const subscribedJobRef = useRef(null);

  const subscribe = (jobId) => {
    if (subscribedJobRef.current === jobId) return;
    if (closeStreamRef.current) closeStreamRef.current();
    subscribedJobRef.current = jobId;
    closeStreamRef.current = window.api.subscribeEvents(
      jobId,
      (event) => {
        setJobState((s) => reduceJobState(s, event));
        if (event.type === "pipeline_done" || event.type === "pipeline_error") {
          window.api.clearActiveJobId();
        }
      },
      (err) => console.error("SSE error", err),
    );
  };

  // apply theme attrs
  useEffect(() => {
    document.documentElement.setAttribute("data-palette", T.palette);
    document.documentElement.setAttribute("data-font", T.font);
  }, [T.palette, T.font]);

  // Re-hydrate any active job on mount: pull a snapshot from the backend,
  // then resume the SSE stream for live events.
  useEffect(() => {
    const jobId = window.api.loadActiveJobId();
    if (!jobId) return;
    let cancelled = false;
    (async () => {
      try {
        const [segs, status] = await Promise.all([
          window.api.fetchSegments(jobId),
          window.api.fetchStatus(jobId),
        ]);
        if (cancelled) return;
        const restored = snapshotToJobState(segs, status);
        setJobState(restored);
        if (status.status !== "completed" && status.status !== "failed") {
          subscribe(jobId);
        } else {
          window.api.clearActiveJobId();
        }
        // Drop the user back into the progress view so they can see the run.
        setView("progress");
      } catch (e) {
        // job_id stale (server restarted, job purged, etc.) — clear and move on.
        window.api.clearActiveJobId();
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line
  }, []);

  // close any open SSE stream when the app unmounts
  useEffect(() => () => { if (closeStreamRef.current) closeStreamRef.current(); }, []);

  const startJob = async (file, mode) => {
    if (!file) {
      console.error("No file selected");
      return;
    }
    try {
      const { job_id } = await window.api.uploadPdf(file, mode);
      window.api.saveActiveJobId(job_id);
      setJobState({
        ...INITIAL_JOB_STATE,
        job_id,
        filename: file.name,
      });
      subscribe(job_id);
      setView("progress");
    } catch (e) {
      setJobState((s) => ({ ...s, error: e.message || String(e) }));
      console.error(e);
    }
  };

  const jobsRunning = jobState.job_id && !jobState.done && !jobState.error ? 1 : null;

  return (
    <div className="app" data-view={view}>
      <Sidebar
        view={view}
        setView={(v) => { setView(v); window.scrollTo(0, 0); }}
        jobsRunning={jobsRunning}
      />
      <div className="view" data-screen-label={`view-${view}`}>
        {view === "upload" && <Upload setView={setView} onSubmit={startJob} />}
        {view === "progress" && <Progress progressVariant={T.progressVariant} jobState={jobState} setJobState={setJobState} setView={setView} />}
        {view === "player" && <Player setView={setView} jobState={jobState} />}
        {view === "library" && <Library setView={setView} />}
      </div>
    </div>
  );
};

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
