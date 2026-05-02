// Shared shell — sidebar nav, brand mark, top bar

const { useState, useEffect, useRef, useCallback, useMemo } = React;

const Brand = ({ size = 28 }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
    <div style={{
      width: size, height: size, borderRadius: size * 0.28,
      background: "linear-gradient(135deg, var(--accent), var(--accent-2))",
      position: "relative", flex: "none",
    }}>
      <div style={{
        position: "absolute", inset: size * 0.22,
        border: "1.5px solid var(--bg)",
        borderRadius: 3,
      }} />
    </div>
    <div className="display" style={{ fontSize: size * 0.78, lineHeight: 1 }}>
      anvya<span style={{ color: "var(--accent)", fontStyle: "italic" }}>.ai</span>
    </div>
  </div>
);

const NavLink = ({ icon, label, active, onClick, badge }) => (
  <div className="nav-link" data-active={active} onClick={onClick}>
    {icon}
    <span style={{ flex: 1 }}>{label}</span>
    {badge ? (
      <span className="mono" style={{
        fontSize: 10, padding: "2px 6px", borderRadius: 4,
        background: "var(--accent-2)", color: "white",
      }}>{badge}</span>
    ) : null}
  </div>
);

const Sidebar = ({ view, setView, jobsRunning }) => (
  <nav className="nav">
    <div className="nav-brand">
      <Brand size={28} />
    </div>
    <div className="nav-section">Workspace</div>
    <NavLink icon={<I.upload />} label="New lecture" active={view === "upload"} onClick={() => setView("upload")} />
    <NavLink icon={<I.pulse />} label="In progress" badge={jobsRunning} active={view === "progress"} onClick={() => setView("progress")} />
    <NavLink icon={<I.library />} label="Library" active={view === "library"} onClick={() => setView("library")} />

    <div className="nav-section">Series</div>
    <div style={{ padding: "4px 10px", fontSize: 13, color: "var(--fg-muted)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 0" }}>
        <span style={{ width: 4, height: 4, borderRadius: 2, background: "var(--accent-2)" }} />
        Transformers, from First Principles
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 0" }}>
        <span style={{ width: 4, height: 4, borderRadius: 2, background: "var(--accent-warm)" }} />
        Calculus, Visualized
      </div>
      <div style={{ padding: "6px 0", color: "var(--fg-dim)", display: "flex", alignItems: "center", gap: 8 }}>
        <I.plus size={12} /> New series
      </div>
    </div>

    <div className="nav-foot">
      <div className="nav-avatar">SG</div>
      <div style={{ flex: 1, fontSize: 13 }}>
        <div style={{ color: "var(--fg)" }}>Sasha Grant</div>
        <div className="mono" style={{ fontSize: 10, color: "var(--fg-dim)" }}>PRO · 18 / 50</div>
      </div>
      <I.settings size={14} stroke="var(--fg-dim)" />
    </div>
  </nav>
);

window.Brand = Brand;
window.Sidebar = Sidebar;
window.NavLink = NavLink;
