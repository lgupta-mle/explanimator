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

    <div className="nav-foot" style={{ fontSize: 11, color: "var(--fg-dim)", fontFamily: "var(--mono)" }}>
      <a
        href="https://github.com/lgupta-mle/explanimator"
        target="_blank"
        rel="noopener noreferrer"
        style={{ color: "var(--fg-muted)", textDecoration: "none" }}
      >
        github ↗
      </a>
    </div>
  </nav>
);

window.Brand = Brand;
window.Sidebar = Sidebar;
window.NavLink = NavLink;
