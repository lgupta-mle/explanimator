// Library — list of saved videos

const Library = ({ setView }) => {
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");

  const filtered = window.LIBRARY.filter((v) => {
    if (filter === "ready" && v.status !== "ready") return false;
    if (filter === "rendering" && v.status !== "rendering") return false;
    if (filter === "easy" && v.mode !== "Easy") return false;
    if (filter === "technical" && v.mode !== "Technical") return false;
    if (search && !v.title.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <div style={{ padding: "32px 48px", maxWidth: 1500, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 32 }}>
        <div>
          <div className="label-mono" style={{ marginBottom: 10 }}>Library</div>
      <h1 className="display" style={{ fontSize: 48, margin: 0, whiteSpace: "nowrap" }}>Your lectures.</h1>
        </div>
        <button className="btn btn-primary" onClick={() => setView("upload")}>
          <I.plus size={14} /> New lecture
        </button>
      </div>

      {/* Filters / search */}
      <div style={{ display: "flex", gap: 12, marginBottom: 28, alignItems: "center" }}>
        <div style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "8px 14px",
          background: "var(--surface)", border: "1px solid var(--border)",
          borderRadius: 10, flex: 1, maxWidth: 360,
        }}>
          <I.search size={14} stroke="var(--fg-dim)" />
          <input
            placeholder="Search lectures…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              flex: 1, background: "transparent", border: "none", outline: "none",
              color: "var(--fg)", fontFamily: "inherit", fontSize: 13,
            }}
          />
        </div>
        <div style={{ display: "flex", gap: 4, padding: 4, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10 }}>
          {[
            ["all", "All"],
            ["ready", "Ready"],
            ["rendering", "Rendering"],
            ["technical", "Technical"],
            ["easy", "Easy"],
          ].map(([id, label]) => (
            <div key={id} onClick={() => setFilter(id)} style={{
              padding: "6px 12px", borderRadius: 7, fontSize: 12,
              cursor: "pointer",
              color: filter === id ? "var(--fg)" : "var(--fg-muted)",
              background: filter === id ? "var(--surface-2)" : "transparent",
            }}>{label}</div>
          ))}
        </div>
      </div>

      {/* Group: rendering banner */}
      {filtered.some((v) => v.status === "rendering") && filter !== "ready" && (
        <div className="card fade-in" style={{
          padding: 20, marginBottom: 24,
          border: "1px solid var(--accent)",
          background: "color-mix(in srgb, var(--accent) 5%, var(--surface))",
        }}>
          <div className="label-mono" style={{ marginBottom: 12, color: "var(--accent)" }}>
            <span className="dots" style={{ color: "var(--accent)" }}><span></span><span></span><span></span></span>{" "}
            CURRENTLY GENERATING · 1
          </div>
          {filtered.filter((v) => v.status === "rendering").map((v) => (
            <div key={v.id} onClick={() => setView("progress")} style={{
              display: "flex", alignItems: "center", gap: 16, cursor: "pointer",
            }}>
              <div style={{ flex: 1 }}>
                <div className="display" style={{ fontSize: 19, lineHeight: 1.2, marginBottom: 4 }}>{v.title}</div>
                <div className="mono" style={{ fontSize: 11, color: "var(--fg-dim)" }}>
                  {v.created} · stage 5 of 5 · render & stitch
                </div>
              </div>
              <div style={{ width: 200, height: 4, background: "var(--border)", borderRadius: 2, overflow: "hidden" }}>
                <div style={{ height: "100%", width: `${v.progress}%`, background: "var(--accent)", transition: "width 400ms" }} />
              </div>
              <div className="display" style={{ fontSize: 18, color: "var(--accent)", minWidth: 60, textAlign: "right" }}>
                {v.progress}%
              </div>
              <I.arrow size={16} stroke="var(--fg-muted)" />
            </div>
          ))}
        </div>
      )}

      {/* Series row */}
      <SeriesStrip setView={setView} />

      <div className="label-mono" style={{ margin: "32px 0 16px" }}>All lectures · {filtered.length}</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(310px, 1fr))", gap: 16 }}>
        {filtered.filter((v) => v.status === "ready").map((v) => (
          <LibraryCard key={v.id} v={v} onClick={() => setView("player")} />
        ))}
      </div>
    </div>
  );
};

const SeriesStrip = ({ setView }) => (
  <div className="card" style={{ padding: 0, overflow: "hidden", marginBottom: 8 }}>
    <div style={{ padding: "16px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--border)" }}>
      <div>
        <div className="display" style={{ fontSize: 19, lineHeight: 1.15 }}>Transformers, from First Principles</div>
        <div className="mono" style={{ fontSize: 11, color: "var(--fg-dim)", marginTop: 4 }}>
          SERIES · 2 OF 6 EPISODES · CREATED 4 DAYS AGO
        </div>
      </div>
      <button className="btn">View series</button>
    </div>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 0 }}>
      {[1, 2, 3, 4, 5, 6].map((n) => {
        const ready = n <= 2;
        return (
          <div key={n} onClick={() => ready && setView("player")} style={{
            padding: "20px 18px",
            borderRight: n < 6 ? "1px solid var(--border)" : "none",
            cursor: ready ? "pointer" : "default",
            opacity: ready ? 1 : 0.45,
          }}>
            <div className="mono" style={{ fontSize: 10, color: "var(--fg-dim)", marginBottom: 8, letterSpacing: "0.12em" }}>
              EP {String(n).padStart(2, "0")}
            </div>
            <div style={{ fontSize: 13, lineHeight: 1.35, marginBottom: 10, color: ready ? "var(--fg)" : "var(--fg-muted)" }}>
              {[
                "Attention Is All You Need",
                "BERT: Bidirectional Pre-training",
                "GPT-2: Language Models Are Multitask Learners",
                "T5: Text-to-Text Transfer",
                "Switch Transformers",
                "Chinchilla Scaling Laws",
              ][n - 1]}
            </div>
            <div className="mono" style={{ fontSize: 10, color: ready ? "var(--accent)" : "var(--fg-dim)" }}>
              {ready ? <><I.check size={10} style={{ verticalAlign: "middle" }} /> READY</> : "QUEUED"}
            </div>
          </div>
        );
      })}
    </div>
  </div>
);

const LibraryCard = ({ v, onClick }) => (
  <div onClick={onClick} style={{
    background: "var(--surface)", border: "1px solid var(--border)",
    borderRadius: 14, overflow: "hidden", cursor: "pointer",
    transition: "all 160ms",
  }}
    onMouseEnter={(e) => e.currentTarget.style.borderColor = "var(--border-strong)"}
    onMouseLeave={(e) => e.currentTarget.style.borderColor = "var(--border)"}
  >
    <div style={{ aspectRatio: "16 / 9", background: "#000", borderBottom: "1px solid var(--border)", position: "relative", overflow: "hidden" }}>
      <LibraryThumb v={v} />
      <div className="mono" style={{
        position: "absolute", right: 10, bottom: 10,
        padding: "3px 8px", background: "rgba(0,0,0,0.7)",
        color: "white", fontSize: 11, borderRadius: 4,
      }}>{v.duration}</div>
      {v.series && (
        <div className="mono" style={{
          position: "absolute", left: 10, top: 10,
          padding: "3px 8px", background: "rgba(0,0,0,0.6)",
          color: "white", fontSize: 9, borderRadius: 4,
          letterSpacing: "0.1em",
        }}>EP {v.chapter?.split(" ")[0]}</div>
      )}
    </div>
    <div style={{ padding: 16 }}>
      <div className="display" style={{ fontSize: 17, lineHeight: 1.3, marginBottom: 6 }}>{v.title}</div>
      <div className="mono" style={{ fontSize: 11, color: "var(--fg-dim)", marginBottom: 10 }}>{v.author}</div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: 12 }}>
        <span style={{ color: "var(--fg-muted)" }}>{v.created}</span>
        <span style={{ display: "flex", alignItems: "center", gap: 6, color: v.accent }}>
          <span style={{ width: 6, height: 6, borderRadius: 3, background: v.accent }} />
          {v.mode}
        </span>
      </div>
    </div>
  </div>
);

const LibraryThumb = ({ v }) => {
  // unique mini-scene per video
  const seed = v.id.charCodeAt(0);
  return (
    <svg viewBox="0 0 320 180" width="100%" height="100%" style={{ display: "block" }}>
      <text x="14" y="22" fontSize="9" fill="#6B7280" fontFamily="var(--mono)" letterSpacing="0.1em">SCENE 01</text>
      {seed % 3 === 0 && <>
        <rect x="40" y="60" width="60" height="36" stroke="#FCD34D" strokeWidth="1.2" fill="rgba(252,211,77,0.06)" />
        <rect x="220" y="60" width="60" height="36" stroke="#7DD3FC" strokeWidth="1.2" fill="rgba(125,211,252,0.06)" />
        <line x1="100" y1="78" x2="220" y2="78" stroke="white" strokeWidth="1" markerEnd="url(#aw)" />
        <text x="160" y="74" textAnchor="middle" fontSize="11" fill="white" fontFamily="var(--serif)" fontStyle="italic">·</text>
        <defs><marker id="aw" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="white" /></marker></defs>
        <text x="160" y="130" textAnchor="middle" fontSize="14" fill="white" fontFamily="var(--serif)" fontStyle="italic">QK<tspan baselineShift="super" fontSize="9">T</tspan></text>
      </>}
      {seed % 3 === 1 && <>
        <circle cx="80" cy="90" r="32" stroke="#7DD3FC" strokeWidth="1.2" fill="rgba(125,211,252,0.06)" />
        <circle cx="160" cy="90" r="32" stroke="#3B82F6" strokeWidth="1.2" fill="rgba(59,130,246,0.06)" />
        <circle cx="240" cy="90" r="32" stroke="#F59E0B" strokeWidth="1.2" fill="rgba(245,158,11,0.06)" />
        <text x="160" y="160" textAnchor="middle" fontSize="11" fill="#9CA3AF" fontFamily="var(--mono)">multi-head</text>
      </>}
      {seed % 3 === 2 && <>
        {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
          <rect key={i} x={30 + i * 32} y={130 - i * 6} width="22" height={20 + i * 6} fill="#7DD3FC" opacity={0.3 + i * 0.08} />
        ))}
        <text x="160" y="22" fontSize="9" fill="#6B7280" fontFamily="var(--mono)" textAnchor="end">EXPONENTIAL</text>
      </>}
    </svg>
  );
};

window.Library = Library;
