// Upload flow — PDF drop + difficulty pick + Generate

const Upload = ({ setView, onSubmit }) => {
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [mode, setMode] = useState("expert");

  const handleFile = (f) => {
    if (!f) return;
    setFile(f);
  };

  return (
    <div style={{ padding: "32px 48px", maxWidth: 920, margin: "0 auto" }}>
      <div style={{ marginBottom: 32 }}>
        <div className="label-mono" style={{ marginBottom: 10 }}>New lecture</div>
        <h1 className="display" style={{ fontSize: 44, margin: 0, lineHeight: 1.1 }}>What are we turning into a video?</h1>
      </div>

      {!file ? (
        <DropZone dragging={dragging} setDragging={setDragging} onFile={handleFile} />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <FilePreview file={file} onClear={() => setFile(null)} />
          <DifficultyCard mode={mode} setMode={setMode} />
          <button
            className="btn btn-primary"
            style={{
              padding: "16px 24px", fontSize: 16, justifyContent: "center",
              width: "100%", fontWeight: 600,
            }}
            onClick={() => onSubmit(file, mode)}
          >
            Generate lecture <I.sparkle size={14} />
          </button>
        </div>
      )}
    </div>
  );
};

const DropZone = ({ dragging, setDragging, onFile }) => {
  const inputRef = useRef(null);
  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => { e.preventDefault(); setDragging(false); onFile(e.dataTransfer.files?.[0]); }}
      onClick={() => inputRef.current && inputRef.current.click()}
      style={{
        padding: "80px 40px",
        borderRadius: 24,
        border: `2px dashed ${dragging ? "var(--accent)" : "var(--border-strong)"}`,
        background: dragging ? "color-mix(in srgb, var(--accent) 6%, var(--surface))" : "var(--surface)",
        textAlign: "center",
        cursor: "pointer",
        transition: "all 200ms",
        position: "relative", overflow: "hidden",
      }}
    >
      <div style={{ position: "relative" }}>
        <div style={{
          margin: "0 auto 24px",
          width: 80, height: 80,
          borderRadius: 20,
          background: "var(--bg-2)",
          border: "1px solid var(--border)",
          display: "grid", placeItems: "center",
        }}>
          <I.upload size={32} stroke="var(--accent)" />
        </div>
        <div className="display" style={{ fontSize: 32, marginBottom: 10 }}>
          Drop a PDF here
        </div>
        <p style={{ color: "var(--fg-muted)", marginBottom: 24, fontSize: 15 }}>
          Up to 200 pages. Research papers, textbook chapters, lecture notes — all welcome.
        </p>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          style={{ display: "none" }}
          onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ""; }}
        />
        <button className="btn btn-primary" onClick={(e) => { e.stopPropagation(); inputRef.current && inputRef.current.click(); }}>Browse files</button>
      </div>
    </div>
  );
};

const FilePreview = ({ file, onClear }) => (
  <div className="card" style={{ padding: 20, display: "flex", alignItems: "center", gap: 16 }}>
    <div style={{
      width: 56, height: 56, borderRadius: 12,
      background: "var(--bg-2)", border: "1px solid var(--border-strong)",
      display: "grid", placeItems: "center", flex: "none",
    }}>
      <I.doc size={24} stroke="var(--accent)" />
    </div>
    <div style={{ flex: 1, minWidth: 0 }}>
      <div className="display" style={{ fontSize: 20, marginBottom: 4 }}>{file?.name}</div>
      <div className="mono" style={{ fontSize: 11, color: "var(--fg-dim)" }}>
        {(file?.size ? (file.size / (1024 * 1024)).toFixed(2) : "?")} MB · ready to process
      </div>
    </div>
    <button
      onClick={onClear}
      className="btn btn-ghost"
      style={{ padding: "8px 10px" }}
      aria-label="Remove file"
    >
      <I.x size={14} />
    </button>
  </div>
);

const DifficultyCard = ({ mode, setMode }) => {
  const opts = [
    {
      id: "beginner",
      label: "Beginner",
      blurb: "Plain language, more analogies, gentler pacing. Prerequisites taught from scratch. Best if the topic is new to you.",
      accent: "var(--accent-warm)",
    },
    {
      id: "expert",
      label: "Expert",
      blurb: "Full notation, faster pace, derivations shown. Assumes you're comfortable with the math.",
      accent: "var(--accent-2)",
    },
  ];
  return (
    <div className="card" style={{ padding: 20 }}>
      <div className="label-mono" style={{ marginBottom: 12 }}>Difficulty</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        {opts.map((o) => {
          const active = mode === o.id;
          return (
            <div
              key={o.id}
              onClick={() => setMode(o.id)}
              style={{
                padding: 16,
                borderRadius: 12,
                border: `1.5px solid ${active ? o.accent : "var(--border)"}`,
                background: active ? "color-mix(in srgb, " + o.accent + " 6%, var(--surface-2))" : "var(--surface-2)",
                cursor: "pointer",
                transition: "all 150ms",
              }}
            >
              <div
                className="label-mono"
                style={{
                  color: active ? o.accent : "var(--fg-dim)",
                  marginBottom: 6,
                  letterSpacing: "0.14em",
                }}
              >
                {o.label}
              </div>
              <div style={{ fontSize: 13, color: "var(--fg-muted)", lineHeight: 1.45 }}>
                {o.blurb}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

window.Upload = Upload;
