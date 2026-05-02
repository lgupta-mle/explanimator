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
  const seg1Ready = !!jobState.segments?.[0]?.ready;
  const playerRef = useRef(null);
  const scrolledRef = useRef(false);

  useEffect(() => {
    if (seg1Ready && !scrolledRef.current && playerRef.current) {
      scrolledRef.current = true;
      // small timeout so layout settles before the scroll
      setTimeout(() => {
        playerRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 80);
    }
  }, [seg1Ready]);

  return (
    <div style={{ padding: "32px 48px", maxWidth: 1320, margin: "0 auto" }}>
      <ProgressHeader overallPct={overallPct} jobState={jobState} stageInfo={stageInfo} setView={setView} />
      <DiagramView stageInfo={stageInfo} />
      <SegmentTrack jobState={jobState} />
      {seg1Ready && (
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
                <circle cx={x} cy={y} r="58" fill="none" stroke="var(--accent)" strokeWidth="2.5"
                  strokeDasharray="365 365"
                  style={{ animation: "spin 2.4s linear infinite", transformOrigin: `${x}px ${y}px` }}
                />
              )}
              {s.status === "done" && (
                <circle cx={x} cy={y} r="58" fill="none" stroke="var(--good)" strokeWidth="2" />
              )}
              <text x={x} y={y - 6} textAnchor="middle" fontFamily="var(--mono)" fontSize="11" fill={color} letterSpacing="0.1em">
                0{i + 1}
              </text>
              <text x={x} y={y + 12} textAnchor="middle" fontFamily="var(--display-font, var(--serif))" fontSize="17" fill="var(--fg)" fontStyle="italic">
                {s.name}
              </text>
              <text x={x} y={y + 30} textAnchor="middle" fontFamily="var(--mono)" fontSize="9" fill="var(--fg-dim)" letterSpacing="0.06em">
                {s.status === "running" ? "RUNNING…" : s.status === "done" ? "DONE" : "QUEUED"}
              </text>
            </g>
          );
        })}
      </svg>
      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
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
          const isFirst = i === 0;
          const stageLabel = isFirst
            ? (seg.ready ? "ready to watch" : "wired to circles above")
            : _STAGE_LABEL[seg.current_stage || "queued"];
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
              {!isFirst && !seg.ready && (
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
  const [waiting, setWaiting] = useState(false);
  const videoRef = useRef(null);

  const currentSeg = segments[currentIdx];
  const nextSeg = segments[currentIdx + 1];

  // When video ends, advance to next ready segment.
  const onEnded = () => {
    const next = currentIdx + 1;
    if (next > Math.max(...orderedIdx)) return;  // last segment
    if (segments[next]?.ready) {
      setCurrentIdx(next);
      setWaiting(false);
    } else {
      setWaiting(true);
    }
  };

  // If we were waiting and the next segment becomes ready, advance.
  useEffect(() => {
    if (waiting && nextSeg?.ready) {
      setCurrentIdx((c) => c + 1);
      setWaiting(false);
    }
  }, [waiting, nextSeg?.ready]);

  if (!currentSeg) {
    return <div className="card" style={{ padding: 32 }}>Waiting for segment 1…</div>;
  }

  const src = window.api.segmentUrl(jobState.job_id, currentIdx);

  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      <div style={{ padding: "14px 18px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div className="label-mono" style={{ color: "var(--accent)", marginBottom: 4 }}>NOW PLAYING · SEGMENT {currentIdx + 1} / {orderedIdx.length}</div>
          <div className="display" style={{ fontSize: 18 }}>{currentSeg.title}</div>
        </div>
        <span className="pill pill-good"><span className="pill-dot" />streaming</span>
      </div>
      <div style={{ position: "relative", background: "#000" }}>
        <video
          ref={videoRef}
          key={currentIdx}
          src={src}
          controls
          autoPlay
          onEnded={onEnded}
          style={{ width: "100%", display: "block" }}
        />
        {waiting && (
          <div style={{
            position: "absolute", inset: 0,
            background: "rgba(0,0,0,0.65)", color: "var(--fg)",
            display: "grid", placeItems: "center",
            fontFamily: "var(--mono)", fontSize: 13, letterSpacing: "0.08em",
          }}>
            <div>
              <div className="dots" style={{ color: "var(--accent)" }}><span></span><span></span><span></span></div>
              <div style={{ marginTop: 12 }}>Preparing segment {currentIdx + 2}…</div>
            </div>
          </div>
        )}
      </div>
      <div style={{ padding: "12px 18px", display: "flex", gap: 8, flexWrap: "wrap" }}>
        {orderedIdx.map((i) => (
          <button
            key={i}
            disabled={!segments[i]?.ready}
            onClick={() => { if (segments[i]?.ready) setCurrentIdx(i); }}
            className="mono"
            style={{
              padding: "4px 10px", borderRadius: 6, fontSize: 11,
              border: `1px solid ${currentIdx === i ? "var(--accent)" : "var(--border)"}`,
              background: currentIdx === i ? "color-mix(in srgb, var(--accent) 12%, var(--surface))" : "var(--surface)",
              color: segments[i]?.ready ? "var(--fg)" : "var(--fg-dim)",
              cursor: segments[i]?.ready ? "pointer" : "not-allowed",
              fontFamily: "var(--mono)",
            }}
          >
            {i + 1}{segments[i]?.ready ? "" : "·"}
          </button>
        ))}
      </div>
    </div>
  );
};

window.Progress = Progress;
