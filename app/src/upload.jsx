// Upload flow — drag/drop, settings, submit

const Upload = ({ setView, onSubmit }) => {
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [mode, setMode] = useState("technical");
  const [voice, setVoice] = useState("aria");
  const [series, setSeries] = useState("none");
  const [chapters, setChapters] = useState([
    { n: "1", title: "Introduction", pages: "1–2", include: true },
    { n: "2", title: "Background", pages: "2–3", include: true },
    { n: "3", title: "Model Architecture", pages: "3–7", include: true, primary: true },
    { n: "3.1", title: "Encoder and Decoder Stacks", pages: "3", include: true, sub: true },
    { n: "3.2", title: "Attention", pages: "3–5", include: true, sub: true },
    { n: "3.3", title: "Position-wise FFN", pages: "5", include: true, sub: true },
    { n: "4", title: "Why Self-Attention", pages: "6–7", include: true },
    { n: "5", title: "Training", pages: "7–8", include: false },
    { n: "6", title: "Results", pages: "8–10", include: false },
    { n: "Refs", title: "References", pages: "10–11", include: false, muted: true },
  ]);

  const handleFile = (f) => {
    if (!f) return;
    setFile(f);
  };

  return (
    <div style={{ padding: "32px 48px", maxWidth: 1280, margin: "0 auto" }}>
      <div style={{ marginBottom: 32 }}>
        <div className="label-mono" style={{ marginBottom: 10 }}>Step 1 of 1 · new lecture</div>
        <h1 className="display" style={{ fontSize: 44, margin: 0, lineHeight: 1.1 }}>What are we turning into a video?</h1>
      </div>

      {!file ? (
        <DropZone dragging={dragging} setDragging={setDragging} onFile={handleFile} />
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 24 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <FilePreview file={file} onClear={() => setFile(null)} />
            <ChapterPicker chapters={chapters} setChapters={setChapters} />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <ModeCard mode={mode} setMode={setMode} />
            <VoiceCard voice={voice} setVoice={setVoice} />
            <SeriesCard series={series} setSeries={setSeries} />
            <EstimateCard onSubmit={() => { onSubmit(file, mode); }} chapters={chapters} mode={mode} />
          </div>
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
      <div style={{ marginTop: 36, paddingTop: 24, borderTop: "1px solid var(--border)" }}>
        <div className="label-mono" style={{ marginBottom: 14 }}>Difficulty</div>
        <DifficultyChoice />
      </div>
    </div>
  </div>
  );
};

const DifficultyChoice = () => {
  const [d, setD] = useState("technical");
  const opts = [
    {
      value: "easy",
      label: "Easy",
      blurb: "Plain language, more analogies, gentler pacing. Equations are introduced step-by-step. Best if the topic is new to you.",
    },
    {
      value: "technical",
      label: "Technical",
      blurb: "Full notation, faster pace, derivations shown. Assumes you're comfortable with the math. Best if you're refreshing or studying the field.",
    },
  ];
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, textAlign: "left" }} onClick={(e) => e.stopPropagation()}>
      {opts.map((o) => {
        const active = d === o.value;
        return (
          <div
            key={o.value}
            onClick={() => setD(o.value)}
            style={{
              padding: 18,
              borderRadius: 14,
              border: `1px solid ${active ? "var(--accent)" : "var(--border)"}`,
              background: active ? "color-mix(in srgb, var(--accent) 8%, var(--surface))" : "var(--bg-2)",
              cursor: "pointer",
              transition: "all 150ms",
              position: "relative",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
              <div className="display" style={{ fontSize: 18, color: active ? "var(--accent)" : "var(--fg)" }}>{o.label}</div>
              <div style={{
                width: 16, height: 16, borderRadius: "50%",
                border: `1.5px solid ${active ? "var(--accent)" : "var(--border-strong)"}`,
                display: "grid", placeItems: "center",
              }}>
                {active && <div style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--accent)" }} />}
              </div>
            </div>
            <div style={{ fontSize: 12, lineHeight: 1.5, color: "var(--fg-muted)" }}>{o.blurb}</div>
          </div>
        );
      })}
    </div>
  );
};

const FilePreview = ({ file, onClear }) => (
  <div className="card" style={{ padding: 20, display: "flex", alignItems: "center", gap: 16 }}>
    <div style={{
      width: 56, height: 72,
      background: "var(--bg-2)", border: "1px solid var(--border)",
      borderRadius: 6, padding: 6,
      display: "flex", flexDirection: "column", justifyContent: "space-between",
      flex: "none",
    }}>
      <div className="mono" style={{ fontSize: 8, color: "var(--accent-warm)" }}>PDF</div>
      <div>
        {[1, 2, 3, 4].map((i) => <div key={i} style={{ height: 1.5, background: "var(--border-strong)", marginBottom: 2 }} />)}
      </div>
    </div>
    <div style={{ flex: 1 }}>
      <div className="display" style={{ fontSize: 20, marginBottom: 4 }}>{file?.name}</div>
      <div className="mono" style={{ fontSize: 12, color: "var(--fg-dim)", letterSpacing: "0.06em" }}>
        {(file?.size ? (file.size / (1024 * 1024)).toFixed(2) : "?")} MB · uploaded just now
      </div>
    </div>
    <button className="btn btn-ghost" onClick={onClear}><I.x size={16} /></button>
  </div>
);

const ChapterPicker = ({ chapters, setChapters }) => {
  const toggle = (i) => setChapters((cs) => cs.map((c, j) => j === i ? { ...c, include: !c.include } : c));
  return (
    <div className="card" style={{ padding: 0 }}>
      <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div className="display" style={{ fontSize: 18 }}>Detected chapters</div>
          <div className="mono" style={{ fontSize: 11, color: "var(--fg-dim)", marginTop: 2 }}>
            from PDF table of contents · auto-strips refs and exercises
          </div>
        </div>
        <span className="pill pill-good"><span className="pill-dot" />ToC found</span>
      </div>
      <div>
        {chapters.map((c, i) => (
          <div
            key={i}
            onClick={() => !c.muted && toggle(i)}
            style={{
              display: "flex", alignItems: "center", gap: 12,
              padding: "10px 20px",
              borderTop: i > 0 ? "1px solid var(--border)" : "none",
              cursor: c.muted ? "default" : "pointer",
              opacity: c.muted ? 0.4 : c.include ? 1 : 0.5,
              transition: "opacity 120ms",
            }}
          >
            <div style={{
              width: 18, height: 18, borderRadius: 5,
              border: `1.5px solid ${c.include ? "var(--accent)" : "var(--border-strong)"}`,
              background: c.include ? "var(--accent)" : "transparent",
              display: "grid", placeItems: "center",
              flex: "none",
            }}>
              {c.include && <I.check size={11} stroke="var(--bg)" />}
            </div>
            <div className="mono" style={{ fontSize: 12, color: "var(--fg-dim)", width: 36, paddingLeft: c.sub ? 14 : 0 }}>{c.n}</div>
            <div style={{ flex: 1, fontSize: 14, color: c.muted ? "var(--fg-dim)" : "var(--fg)" }}>
              {c.title}
              {c.primary && <span className="pill" style={{ marginLeft: 10, fontSize: 9, padding: "2px 8px" }}><span className="pill-dot" style={{ background: "var(--accent)" }} />primary</span>}
            </div>
            <div className="mono" style={{ fontSize: 11, color: "var(--fg-dim)" }}>p. {c.pages}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

const ModeCard = ({ mode, setMode }) => (
  <div className="card" style={{ padding: 20 }}>
    <div className="display" style={{ fontSize: 18, marginBottom: 4 }}>Difficulty</div>
    <div className="mono" style={{ fontSize: 11, color: "var(--fg-dim)", marginBottom: 16 }}>SAME PAPER · DIFFERENT LECTURE</div>
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
      {[
        { id: "easy", label: "Easy", desc: "Intuition, analogies. No math required.", accent: "var(--accent-warm)" },
        { id: "technical", label: "Technical", desc: "Equations, derivations, proofs.", accent: "var(--accent-2)" },
      ].map((m) => (
        <div
          key={m.id}
          onClick={() => setMode(m.id)}
          style={{
            padding: 14,
            borderRadius: 10,
            border: `1.5px solid ${mode === m.id ? m.accent : "var(--border)"}`,
            background: mode === m.id ? "color-mix(in srgb, var(--surface-2) 80%, transparent)" : "transparent",
            cursor: "pointer",
            transition: "all 140ms",
          }}
        >
          <div className="mono" style={{ fontSize: 10, color: m.accent, marginBottom: 6, letterSpacing: "0.12em", textTransform: "uppercase" }}>{m.label}</div>
          <div style={{ fontSize: 12, color: "var(--fg-muted)", lineHeight: 1.4 }}>{m.desc}</div>
        </div>
      ))}
    </div>
  </div>
);

const VoiceCard = ({ voice, setVoice }) => (
  <div className="card" style={{ padding: 20 }}>
    <div className="display" style={{ fontSize: 18, marginBottom: 16 }}>Narrator</div>
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {[
        { id: "aria", name: "Aria", desc: "Warm, curious. Default for Easy mode." },
        { id: "rohan", name: "Rohan", desc: "Crisp, lecture-hall confident." },
        { id: "june", name: "June", desc: "Lower register, even pace." },
      ].map((v) => (
        <div
          key={v.id}
          onClick={() => setVoice(v.id)}
          style={{
            display: "flex", alignItems: "center", gap: 12,
            padding: "8px 12px",
            borderRadius: 8,
            background: voice === v.id ? "var(--surface-2)" : "transparent",
            cursor: "pointer",
          }}
        >
          <div style={{
            width: 28, height: 28, borderRadius: "50%",
            background: `linear-gradient(135deg, var(--accent), var(--accent-pink))`,
            display: "grid", placeItems: "center",
            color: "white", fontSize: 11, fontWeight: 600,
            flex: "none",
          }}>{v.name[0]}</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13 }}>{v.name}</div>
            <div className="mono" style={{ fontSize: 10, color: "var(--fg-dim)" }}>{v.desc}</div>
          </div>
          <I.play size={12} stroke="var(--fg-muted)" />
        </div>
      ))}
    </div>
  </div>
);

const SeriesCard = ({ series, setSeries }) => (
  <div className="card" style={{ padding: 20 }}>
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
      <div className="display" style={{ fontSize: 18 }}>Series Bible</div>
      <span className="pill" style={{ fontSize: 9 }}>OPTIONAL</span>
    </div>
    <div className="mono" style={{ fontSize: 11, color: "var(--fg-dim)", marginBottom: 14 }}>LOCK NOTATION + STYLE ACROSS CHAPTERS</div>
    <select
      value={series}
      onChange={(e) => setSeries(e.target.value)}
      style={{
        width: "100%",
        padding: "10px 12px",
        background: "var(--bg-2)",
        border: "1px solid var(--border)",
        borderRadius: 8,
        color: "var(--fg)",
        fontSize: 13,
        fontFamily: "inherit",
      }}
    >
      <option value="none">— None (one-off lecture) —</option>
      <option value="transformers">Transformers, from First Principles · ep 1 of 6</option>
      <option value="calc">Calculus, Visualized · ep 13 of 17</option>
      <option value="new">+ Start a new series</option>
    </select>
  </div>
);

const EstimateCard = ({ onSubmit, chapters, mode }) => {
  const included = chapters.filter((c) => c.include && !c.sub).length;
  const minutes = mode === "technical" ? 11 : 8;
  const cost = (minutes * 0.42).toFixed(2);
  return (
    <div className="card" style={{
      padding: 20,
      background: "linear-gradient(180deg, var(--surface), var(--bg-2))",
      borderColor: "var(--border-strong)",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 14 }}>
        <span style={{ fontSize: 13, color: "var(--fg-muted)" }}>Estimated length</span>
        <span className="display" style={{ fontSize: 16 }}>~ {minutes} min</span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 14 }}>
        <span style={{ fontSize: 13, color: "var(--fg-muted)" }}>Estimated time</span>
        <span className="display" style={{ fontSize: 16 }}>6–9 min</span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 18 }}>
        <span style={{ fontSize: 13, color: "var(--fg-muted)" }}>Cost</span>
        <span className="display" style={{ fontSize: 16 }}>${cost} <span className="mono" style={{ fontSize: 11, color: "var(--fg-dim)" }}>/ 18 free</span></span>
      </div>
      <button
        className="btn btn-primary"
        style={{ width: "100%", justifyContent: "center", padding: "14px 16px" }}
        onClick={onSubmit}
      >
        Generate lecture <I.sparkle size={14} />
      </button>
      <div className="mono" style={{ marginTop: 12, fontSize: 10, color: "var(--fg-dim)", textAlign: "center" }}>
        {included} chapters · cached at every stage
      </div>
    </div>
  );
};

window.Upload = Upload;
