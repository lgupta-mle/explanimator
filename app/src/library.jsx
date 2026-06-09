// Library — lists completed jobs from /api/jobs

const Library = ({ setView }) => {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${window.api.BACKEND_URL}/api/jobs`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!cancelled) setJobs(data);
      } catch (e) {
        if (!cancelled) setErr(e.message || String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const formatDuration = (s) => {
    if (!s) return "—";
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${String(sec).padStart(2, "0")}`;
  };

  return (
    <div style={{ padding: "32px 48px", maxWidth: 1100, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 28 }}>
        <div>
          <div className="label-mono" style={{ marginBottom: 8 }}>Library</div>
          <h1 className="display" style={{ fontSize: 36, margin: 0 }}>Generated lectures</h1>
        </div>
        <button className="btn btn-primary" onClick={() => setView("upload")}>
          <I.upload size={14} /> New lecture
        </button>
      </div>

      {loading && (
        <div className="card" style={{ padding: 32, textAlign: "center", color: "var(--fg-muted)" }}>
          Loading…
        </div>
      )}

      {err && !loading && (
        <div className="card" style={{ padding: 24, borderColor: "var(--bad, #ff6b6b)" }}>
          <div className="label-mono" style={{ color: "var(--bad, #ff6b6b)", marginBottom: 6 }}>Can't reach backend</div>
          <div style={{ color: "var(--fg-muted)", fontSize: 14 }}>{err}</div>
        </div>
      )}

      {!loading && !err && jobs.length === 0 && (
        <div className="card" style={{ padding: 48, textAlign: "center" }}>
          <div className="display" style={{ fontSize: 22, marginBottom: 8 }}>No lectures yet</div>
          <div style={{ color: "var(--fg-muted)", marginBottom: 20 }}>
            Upload a research paper to generate your first lecture.
          </div>
          <button className="btn btn-primary" onClick={() => setView("upload")}>
            <I.upload size={14} /> Upload a PDF
          </button>
        </div>
      )}

      {!loading && !err && jobs.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 16 }}>
          {jobs.map((job) => (
            <a
              key={job.job_id}
              href={`${window.api.BACKEND_URL}/api/video/${job.job_id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="card"
              style={{ padding: 18, textDecoration: "none", color: "inherit", display: "block" }}
            >
              <div className="label-mono" style={{ color: "var(--fg-dim)", marginBottom: 8 }}>
                {(job.difficulty || "medium").toUpperCase()} · {job.segments_count} SEGMENTS
              </div>
              <div className="display" style={{ fontSize: 16, lineHeight: 1.3, marginBottom: 10, minHeight: 42 }}>
                {job.paper_title || "Untitled"}
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12, color: "var(--fg-muted)" }}>
                <span className="mono">{formatDuration(job.duration_seconds)}</span>
                <span style={{ color: "var(--accent)" }}>Watch →</span>
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
};

window.Library = Library;
