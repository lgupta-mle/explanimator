// Sign-in / sign-up page — single centered form

const Auth = ({ setView }) => {
  const [mode, setMode] = useState("signup");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");

  return (
    <div style={{
      minHeight: "100vh",
      display: "flex",
      flexDirection: "column",
      background: "var(--bg)",
      position: "relative",
      overflow: "hidden",
    }}>
    <div className="noise" />

      {/* Top bar */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "24px 48px",
        position: "relative", zIndex: 2,
      }}>
        <div onClick={() => setView("landing")} style={{ cursor: "pointer" }}>
          <Brand size={26} />
        </div>
        <div style={{ fontSize: 13, color: "var(--fg-muted)" }}>
          {mode === "signup" ? "Have an account?" : "New here?"}{" "}
          <span
            onClick={() => setMode(mode === "signup" ? "signin" : "signup")}
            style={{ color: "var(--accent)", cursor: "pointer", fontWeight: 500 }}
          >
            {mode === "signup" ? "Sign in" : "Create one"}
          </span>
        </div>
      </div>

      {/* Centered form */}
      <div style={{ flex: 1, display: "grid", placeItems: "center", padding: "24px 48px", position: "relative", zIndex: 2 }}>
        <div style={{ width: "100%", maxWidth: 420 }}>
          <div className="label-mono" style={{ marginBottom: 14, textAlign: "center" }}>
            {mode === "signup" ? "Get started" : "Welcome back"}
          </div>
          <h1 className="display" style={{ fontSize: 48, margin: 0, marginBottom: 12, lineHeight: 1.05, textAlign: "center" }}>
            {mode === "signup" ? (
              <>Make a paper <em style={{ color: "var(--accent)" }}>watchable</em>.</>
            ) : (
              <>Pick up where you left off.</>
            )}
          </h1>
          <p style={{ color: "var(--fg-muted)", marginBottom: 32, fontSize: 15, textAlign: "center" }}>
            {mode === "signup"
              ? "First three lectures free. No card required."
              : "Sign in to continue your library."}
          </p>

          <button className="btn" style={{ width: "100%", justifyContent: "center", padding: "12px 16px", marginBottom: 24 }}>
            <I.google size={16} stroke="var(--fg)" /> Continue with Google
          </button>

          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24, color: "var(--fg-dim)", fontSize: 11 }}>
            <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
            <div className="mono">OR</div>
            <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
          </div>

          {mode === "signup" && (
            <Field label="Name" value={name} onChange={setName} placeholder="Sasha Grant" />
          )}
          <Field label="Email" value={email} onChange={setEmail} placeholder="you@university.edu" type="email" />
          <Field label="Password" value={password} onChange={setPassword} placeholder="••••••••" type="password" />

          <button className="btn btn-primary" style={{ width: "100%", justifyContent: "center", padding: "12px 16px", marginTop: 12 }} onClick={() => setView("upload")}>
            {mode === "signup" ? "Create account" : "Sign in"} <I.arrow size={14} />
          </button>

          {mode === "signup" && (
            <p style={{ fontSize: 11, color: "var(--fg-dim)", marginTop: 18, lineHeight: 1.5, textAlign: "center" }}>
              By creating an account you agree to our <span style={{ color: "var(--fg-muted)", textDecoration: "underline" }}>Terms</span> and <span style={{ color: "var(--fg-muted)", textDecoration: "underline" }}>Privacy Policy</span>. We'll never train on your uploaded PDFs.
            </p>
          )}
        </div>
      </div>

      {/* Footer */}
      <div style={{ padding: "20px 48px", fontSize: 12, color: "var(--fg-dim)", display: "flex", justifyContent: "space-between", position: "relative", zIndex: 2 }}>
        <span>© 2026 Anvya, Inc.</span>
        <span>Trouble signing in?</span>
      </div>
    </div>
  );
};

const Field = ({ label, value, onChange, placeholder, type = "text" }) => (
  <div style={{ marginBottom: 14 }}>
    <div className="label-mono" style={{ marginBottom: 6, fontSize: 10 }}>{label}</div>
    <input
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      style={{
        width: "100%",
        padding: "12px 14px",
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 10,
        color: "var(--fg)",
        fontSize: 14,
        fontFamily: "inherit",
        outline: "none",
      }}
      onFocus={(e) => (e.target.style.borderColor = "var(--accent)")}
      onBlur={(e) => (e.target.style.borderColor = "var(--border)")}
    />
  </div>
);

window.Auth = Auth;
