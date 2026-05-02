// App entry — view router + tweaks panel + SSE subscription lifecycle

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "palette": "manim",
  "font": "lora-inter",
  "heroVariant": "equation",
  "progressVariant": "diagram",
  "startView": "landing"
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

  // apply theme attrs
  useEffect(() => {
    document.documentElement.setAttribute("data-palette", T.palette);
    document.documentElement.setAttribute("data-font", T.font);
  }, [T.palette, T.font]);

  // close any open SSE stream when the app unmounts
  useEffect(() => () => { if (closeStreamRef.current) closeStreamRef.current(); }, []);

  const startJob = async (file, mode) => {
    if (!file) {
      console.error("No file selected");
      return;
    }
    try {
      const { job_id } = await window.api.uploadPdf(file, mode);
      setJobState({
        ...INITIAL_JOB_STATE,
        job_id,
        filename: file.name,
      });
      // close any prior stream
      if (closeStreamRef.current) closeStreamRef.current();
      closeStreamRef.current = window.api.subscribeEvents(
        job_id,
        (event) => setJobState((s) => reduceJobState(s, event)),
        (err) => console.error("SSE error", err),
      );
      setView("progress");
    } catch (e) {
      setJobState((s) => ({ ...s, error: e.message || String(e) }));
      console.error(e);
    }
  };

  const showSidebar = view !== "landing" && view !== "auth";
  const jobsRunning = jobState.job_id && !jobState.done && !jobState.error ? 1 : null;

  return (
    <>
      <div className="app" data-view={view}>
        {showSidebar && (
          <Sidebar
            view={view}
            setView={(v) => { setView(v); window.scrollTo(0, 0); }}
            jobsRunning={jobsRunning}
          />
        )}
        <div className="view" data-screen-label={`view-${view}`}>
          {view === "landing" && <Landing heroVariant={T.heroVariant} setView={setView} />}
          {view === "auth" && <Auth setView={setView} />}
          {view === "upload" && <Upload setView={setView} onSubmit={startJob} />}
          {view === "progress" && <Progress progressVariant={T.progressVariant} jobState={jobState} setJobState={setJobState} setView={setView} />}
          {view === "player" && <Player setView={setView} jobState={jobState} />}
          {view === "library" && <Library setView={setView} />}
        </div>
      </div>

      {window.TweaksPanel && (
        <window.TweaksPanel title="Tweaks">
          <window.TweakSection title="Quick jump">
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
              {[
                ["landing", "Landing"],
                ["auth", "Sign-in"],
                ["upload", "Upload"],
                ["progress", "Progress"],
                ["player", "Player"],
                ["library", "Library"],
              ].map(([id, label]) => (
                <button
                  key={id}
                  onClick={() => setView(id)}
                  className="tweak-btn"
                  style={{
                    padding: "6px 10px", borderRadius: 6, fontSize: 11,
                    border: "1px solid var(--border)",
                    background: view === id ? "var(--accent)" : "var(--surface)",
                    color: view === id ? "var(--bg)" : "var(--fg-muted)",
                    cursor: "pointer",
                    fontFamily: "var(--mono)",
                  }}
                >{label}</button>
              ))}
            </div>
          </window.TweakSection>
          <window.TweakSection title="Theme">
            <window.TweakRadio
              label="Palette"
              value={T.palette}
              onChange={(v) => setTweak("palette", v)}
              options={[
                { value: "manim", label: "Manim Midnight" },
                { value: "chalk", label: "Chalkboard Slate" },
                { value: "paper", label: "Paper & Ink (light)" },
              ]}
            />
            <window.TweakRadio
              label="Type"
              value={T.font}
              onChange={(v) => setTweak("font", v)}
              options={[
                { value: "lora-inter", label: "Lora × Inter" },
                { value: "lora-grotesk", label: "Lora × Space Grotesk" },
                { value: "grotesk-code", label: "Space Grotesk × Source Code Pro" },
                { value: "code-grotesk", label: "Source Code Pro display × Space Grotesk" },
                { value: "serif-sans", label: "Instrument Serif × Inter" },
                { value: "fraunces", label: "Fraunces × Inter" },
                { value: "sans-mono", label: "Geometric sans only" },
              ]}
            />
          </window.TweakSection>
          <window.TweakSection title="Job state (demo)">
            <button
              onClick={() => setJobState(INITIAL_JOB_STATE)}
              style={{
                padding: "8px 12px", borderRadius: 6, fontSize: 12,
                background: "var(--surface)", border: "1px solid var(--border)",
                color: "var(--fg)", cursor: "pointer", width: "100%",
                fontFamily: "inherit",
              }}
            >Reset job state</button>
          </window.TweakSection>
        </window.TweaksPanel>
      )}
    </>
  );
};

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
