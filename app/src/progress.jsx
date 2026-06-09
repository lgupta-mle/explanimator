// Progress page — 5-circle status for segment 1, "Preparing segment X" cards
// for the rest, inline streaming player below, auto-scroll on first segment ready.

const Progress = ({ progressVariant, jobState, setJobState, setView }) => {
  const stages = jobState.segment_1_stages || {};
  const stageInfo = window.PIPELINE_STAGES.map((s, i) => ({
    ...s,
    idx: i,
    status: stages[s.id] || "pending",
  }));
  const totalStagesDone = stageInfo.filter((s) => s.status === "done").length;
  const overallPct = Math.min(100, Math.round((totalStagesDone / stageInfo.length) * 100));
  const anyReady = Object.values(jobState.segments || {}).some((s) => s && s.ready);
  const playerRef = useRef(null);
  const scrolledRef = useRef(false);

  useEffect(() => {
    if (anyReady && !scrolledRef.current && playerRef.current) {
      scrolledRef.current = true;
      // small timeout so layout settles before the scroll
      setTimeout(() => {
        playerRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 80);
    }
  }, [anyReady]);

  return (
    <div style={{ padding: "32px 48px", maxWidth: 1320, margin: "0 auto" }}>
      <ProgressHeader overallPct={overallPct} jobState={jobState} stageInfo={stageInfo} setView={setView} />
      <DiagramView stageInfo={stageInfo} />
      <SegmentTrack jobState={jobState} />
      {anyReady && (
        <div ref={playerRef} style={{ marginTop: 40 }}>
          <InlinePlayer jobState={jobState} />
        </div>
      )}
      {jobState.error && (
        <div style={{ marginTop: 24, padding: 16, borderRadius: 12, border: "1px solid var(--bad, #ff6b6b)", background: "color-mix(in srgb, var(--bad, #ff6b6b) 8%, var(--surface))", color: "var(--fg)" }}>
          <div className="label-mono" style={{ marginBottom: 6, color: "var(--bad, #ff6b6b)" }}>ERROR</div>
          <div>{jobState.error}</div>
        </div>
      )}
    </div>
  );
};

const ProgressHeader = ({ overallPct, jobState, stageInfo, setView }) => {
  const current = stageInfo.find((s) => s.status === "running") || stageInfo.find((s) => s.status === "done");
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 32, gap: 32 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
          <span className="pill pill-good"><span className="pill-dot" />{jobState.done ? "READY" : "GENERATING"}</span>
          <span className="mono" style={{ fontSize: 11, color: "var(--fg-dim)", letterSpacing: "0.08em" }}>
            JOB · {jobState.job_id ? jobState.job_id.slice(0, 8).toUpperCase() : "—"}
          </span>
        </div>
        <h1 className="display" style={{ fontSize: 40, margin: 0, marginBottom: 6, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {jobState.paper_title || jobState.filename || "Generating lecture…"}
        </h1>
        <div style={{ color: "var(--fg-muted)", fontSize: 14 }}>
          {jobState.total_segments ? `${jobState.total_segments} segments planned` : "Reading paper…"}
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 8 }}>
        <div className="display" style={{ fontSize: 56, lineHeight: 1, color: jobState.done ? "var(--good)" : "var(--accent)" }}>
          {overallPct}<span style={{ fontSize: 24, color: "var(--fg-dim)" }}>%</span>
        </div>
        <div className="mono" style={{ fontSize: 11, color: "var(--fg-dim)", letterSpacing: "0.08em" }}>
          {jobState.done ? "DONE" : `STAGE ${(current?.idx ?? 0) + 1} / ${stageInfo.length} · ${(current?.name || "—").toUpperCase()}`}
        </div>
        {jobState.done && (
          <button className="btn btn-primary" onClick={() => setView("player")} style={{ marginTop: 4 }}>
            Watch full lecture <I.play size={12} />
          </button>
        )}
      </div>
    </div>
  );
};

const DiagramView = ({ stageInfo }) => {
  return (
    <div className="card" style={{ padding: "48px 32px", position: "relative", marginBottom: 24, overflow: "hidden" }}>
      <div className="label-mono" style={{ marginBottom: 18, color: "var(--fg-dim)" }}>SEGMENT 1 PIPELINE</div>
      <svg viewBox="0 0 1200 200" style={{ width: "100%", display: "block", position: "relative" }}>
        {stageInfo.map((s, i) => {
          const x = 80 + i * 220;
          const y = 100;
          const next = stageInfo[i + 1];
          const color = s.status === "done" ? "var(--good)" : s.status === "running" ? "var(--accent)" : "var(--fg-dim)";
          return (
            <g key={s.id}>
              {next && (
                <line
                  x1={x + 62} y1={y}
                  x2={x + 220 - 62} y2={y}
                  stroke={s.status === "done" ? "var(--good)" : "var(--border-strong)"}
                  strokeWidth="2"
                  strokeDasharray={s.status === "done" ? "none" : "4 4"}
                />
              )}
              <circle cx={x} cy={y} r="58" fill="var(--surface)" stroke="var(--border)" strokeWidth="1" />
              {s.status === "running" && (
                <>
                  <circle cx={x} cy={y} r="58" fill="none" stroke="var(--border-strong)" strokeWidth="2" />
                  <g style={{ transformOrigin: `${x}px ${y}px`, animation: "spin 1.6s linear infinite" }}>
                    <circle cx={x} cy={y} r="58" fill="none" stroke="var(--accent)" strokeWidth="3"
                      strokeDasharray="90 365" strokeLinecap="round"
                    />
                  </g>
                  <circle cx={x} cy={y} r="6" fill="var(--accent)">
                    <animate attributeName="opacity" values="0.4;1;0.4" dur="1.4s" repeatCount="indefinite" />
                  </circle>
                </>
              )}
              {s.status === "done" && (
                <circle cx={x} cy={y} r="58" fill="none" stroke="var(--good)" strokeWidth="2" />
              )}
              <text x={x} y={y - 18} textAnchor="middle" fontFamily="var(--mono)" fontSize="11" fill={color} letterSpacing="0.1em"
                style={s.status === "running" ? { animation: "pulse-glow 1.4s ease-in-out infinite" } : undefined}>
                0{i + 1}
              </text>
              <text x={x} y={y + 4} textAnchor="middle" fontFamily="var(--display-font, var(--serif))" fontSize="17" fill="var(--fg)" fontStyle="italic">
                {s.name}
              </text>
              <text x={x} y={y + 22} textAnchor="middle" fontFamily="var(--mono)" fontSize="9" fill={color} letterSpacing="0.08em"
                style={s.status === "running" ? { animation: "pulse-glow 1.4s ease-in-out infinite" } : undefined}>
                {s.status === "running" ? "RUNNING…" : s.status === "done" ? "DONE" : "QUEUED"}
              </text>
            </g>
          );
        })}
      </svg>
      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes pulse-glow { 0%, 100% { opacity: 0.55; } 50% { opacity: 1; } }
      `}</style>
    </div>
  );
};

const _STAGE_LABEL = {
  queued: "queued",
  codegen: "writing animation code",
  render: "rendering frames",
  sync: "matching audio",
  ready: "ready to watch",
};

const SegmentTrack = ({ jobState }) => {
  const segments = jobState.segments || {};
  const indices = Object.keys(segments).map((k) => parseInt(k, 10)).sort((a, b) => a - b);
  const tail = indices.filter((i) => i >= 1);

  if (!indices.length) return null;

  return (
    <div style={{ marginTop: 24 }}>
      <div className="label-mono" style={{ marginBottom: 12, color: "var(--fg-dim)" }}>SEGMENTS</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 12 }}>
        {indices.map((i) => {
          const seg = segments[i];
          const stageLabel = seg.ready
            ? "ready to watch"
            : _STAGE_LABEL[seg.current_stage || "queued"];
          const isFirst = i === 0;
          const accent = seg.ready ? "var(--good)" : "var(--accent)";
          return (
            <div
              key={i}
              className="card"
              style={{
                padding: 14,
                borderColor: seg.ready ? "var(--good)" : "var(--border)",
                opacity: seg.ready ? 1 : 0.92,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <span className="mono" style={{ fontSize: 11, color: "var(--fg-dim)", letterSpacing: "0.08em" }}>
                  SEGMENT {i + 1}
                </span>
                <span className="mono" style={{ fontSize: 10, color: accent, letterSpacing: "0.08em" }}>
                  {seg.ready ? "✓ READY" : (stageLabel || "queued").toUpperCase()}
                </span>
              </div>
              <div className="display" style={{ fontSize: 14, lineHeight: 1.25 }}>
                {seg.title || `Segment ${i + 1}`}
              </div>
              {!seg.ready && (
                <div className="mono" style={{ fontSize: 11, marginTop: 8, color: "var(--fg-muted)" }}>
                  Preparing… <span className="dots" style={{ color: accent }}><span></span><span></span><span></span></span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

const InlinePlayer = ({ jobState }) => {
  const segments = jobState.segments || {};
  const orderedIdx = Object.keys(segments).map((k) => parseInt(k, 10)).sort((a, b) => a - b);
  const [currentIdx, setCurrentIdx] = useState(0);
  const videoRef = useRef(null);

  const currentSeg = segments[currentIdx];
  const currentReady = !!currentSeg?.ready;

  // Whenever the current segment flips ready, the <video key={currentIdx}>
  // remounts with a real src and autoplays.
  // When the current ends, advance to the next index (whether ready or not);
  // if not ready yet, the overlay below will show "preparing" and the
  // segment will auto-load + play once segments[next].ready becomes true.
  const onEnded = () => {
    const lastIdx = orderedIdx.length ? orderedIdx[orderedIdx.length - 1] : 0;
    if (currentIdx >= lastIdx) return;
    setCurrentIdx(currentIdx + 1);
  };

  const lastIdx = orderedIdx.length ? orderedIdx[orderedIdx.length - 1] : 0;
  const totalSegments = jobState.total_segments || orderedIdx.length || 1;

  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      <div style={{ padding: "14px 18px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div className="label-mono" style={{ color: "var(--accent)", marginBottom: 4 }}>
            {currentReady ? "NOW PLAYING" : "QUEUED"} · SEGMENT {currentIdx + 1} / {totalSegments}
          </div>
          <div className="display" style={{ fontSize: 18 }}>{currentSeg?.title || `Segment ${currentIdx + 1}`}</div>
        </div>
        <span className="pill pill-good"><span className="pill-dot" />streaming</span>
      </div>
      <div style={{ position: "relative", background: "#000", aspectRatio: "16 / 9" }}>
        {currentReady ? (
          <video
            ref={videoRef}
            key={currentIdx}
            src={window.api.segmentUrl(jobState.job_id, currentIdx)}
            controls
            autoPlay
            onEnded={onEnded}
            style={{ width: "100%", height: "100%", display: "block" }}
          />
        ) : (
          <div style={{
            position: "absolute", inset: 0,
            color: "var(--fg)",
            display: "grid", placeItems: "center",
            fontFamily: "var(--mono)", fontSize: 13, letterSpacing: "0.08em",
            textAlign: "center", padding: 24,
          }}>
            <div>
              <div className="dots" style={{ color: "var(--accent)", fontSize: 20 }}><span></span><span></span><span></span></div>
              <div style={{ marginTop: 14, color: "var(--fg-muted)" }}>
                Preparing segment {currentIdx + 1}…
              </div>
              <div style={{ marginTop: 4, fontSize: 11, color: "var(--fg-dim)" }}>
                It will auto-play as soon as it's rendered.
              </div>
            </div>
          </div>
        )}
      </div>
      <div style={{ padding: "12px 18px", display: "flex", gap: 8, flexWrap: "wrap" }}>
        {orderedIdx.map((i) => {
          const seg = segments[i];
          const isCur = currentIdx === i;
          return (
            <button
              key={i}
              disabled={!seg?.ready}
              onClick={() => { if (seg?.ready) setCurrentIdx(i); }}
              className="mono"
              style={{
                padding: "4px 10px", borderRadius: 6, fontSize: 11,
                border: `1px solid ${isCur ? "var(--accent)" : "var(--border)"}`,
                background: isCur ? "color-mix(in srgb, var(--accent) 12%, var(--surface))" : "var(--surface)",
                color: seg?.ready ? "var(--fg)" : "var(--fg-dim)",
                cursor: seg?.ready ? "pointer" : "not-allowed",
                fontFamily: "var(--mono)",
              }}
              title={seg?.title || `Segment ${i + 1}`}
            >
              {i + 1}{seg?.ready ? "" : "·"}
            </button>
          );
        })}
      </div>
    </div>
  );
};

window.Progress = Progress;
