// Player view — for replaying a completed job's stitched final video.
// Live streaming during generation happens inside Progress (InlinePlayer).

const Player = ({ setView, jobState }) => {
  const hasJob = jobState && jobState.job_id;
  const finalUrl = hasJob ? `${window.api.BACKEND_URL}/api/video/${jobState.job_id}` : null;
  const orderedIdx = hasJob
    ? Object.keys(jobState.segments || {}).map((k) => parseInt(k, 10)).sort((a, b) => a - b)
    : [];

  const formatTime = (s) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${String(sec).padStart(2, "0")}`;
  };

  return (
    <div style={{ padding: "20px 32px 32px", maxWidth: 1280, margin: "0 auto" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 13, color: "var(--fg-muted)" }}>
          <span onClick={() => setView("library")} style={{ cursor: "pointer", display: "flex", alignItems: "center", gap: 6 }}>
            <I.arrowLeft size={14} /> Library
          </span>
          <span style={{ color: "var(--fg-dim)" }}>/</span>
          <span>{jobState?.paper_title || "Lecture"}</span>
        </div>
      </div>

      {!hasJob && (
        <div className="card" style={{ padding: 32 }}>
          No completed job loaded. Upload a PDF first.
        </div>
      )}

      {hasJob && (
        <>
          <h1 className="display" style={{ fontSize: 32, marginBottom: 16 }}>
            {jobState.paper_title || jobState.filename}
          </h1>
          <div style={{ aspectRatio: "16 / 9", background: "#000", borderRadius: 14, overflow: "hidden", border: "1px solid var(--border)" }}>
            <video src={finalUrl} controls style={{ width: "100%", height: "100%", display: "block" }} />
          </div>
          {orderedIdx.length > 0 && (
            <div className="card" style={{ marginTop: 16, padding: 0, overflow: "hidden" }}>
              <div style={{ padding: "12px 18px", borderBottom: "1px solid var(--border)" }}>
                <div className="label-mono" style={{ color: "var(--fg-dim)" }}>SEGMENTS</div>
              </div>
              <div style={{ padding: 12, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 8 }}>
                {orderedIdx.map((i) => {
                  const seg = jobState.segments[i];
                  return (
                    <div key={i} style={{
                      padding: 10, borderRadius: 8, border: "1px solid var(--border)",
                      background: "var(--surface)",
                    }}>
                      <div className="mono" style={{ fontSize: 10, color: "var(--fg-dim)", letterSpacing: "0.08em" }}>
                        SEGMENT {i + 1} · {formatTime(seg.duration_seconds || 0)}
                      </div>
                      <div className="display" style={{ fontSize: 13, lineHeight: 1.25, marginTop: 4 }}>
                        {seg.title || `Segment ${i + 1}`}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

window.Player = Player;
