// Landing page with 3 selectable hero variants

const Landing = ({ heroVariant, setView }) => {
  return (
    <div style={{ background: "var(--bg)", minHeight: "100vh", overflow: "hidden", backgroundColor: "rgb(14, 13, 27)", position: "relative" }}>
      <div style={{ position: "relative", zIndex: 1 }}>
      <LandingTopBar setView={setView} />
      {heroVariant === "morph" && <HeroMorph setView={setView} />}
      {heroVariant === "split" && <HeroSplit setView={setView} />}
      {heroVariant === "equation" && <HeroEquation setView={setView} />}

      <SamplesSection setView={setView} />
      <Footer />
      </div>
    </div>);

};

const LandingTopBar = ({ setView }) =>
<div style={{
  display: "flex", alignItems: "center", justifyContent: "space-between",
  padding: "20px 48px",
  position: "sticky", top: 0, zIndex: 50,
  background: "color-mix(in srgb, var(--bg) 80%, transparent)",
  backdropFilter: "blur(12px)",
  borderBottom: "1px solid var(--border)"
}}>
    <Brand size={26} />
    <div style={{ display: "flex", alignItems: "center", gap: 28, fontSize: 14, color: "var(--fg-muted)" }}>
    </div>
    <div style={{ display: "flex", gap: 10 }}>
      <button className="btn btn-ghost" onClick={() => setView("auth")}>Sign in</button>
      <button className="btn btn-ghost" onClick={() => setView("library")}>Library</button>
      <button className="btn btn-primary" onClick={() => setView("upload")}>Try it free</button>
    </div>
  </div>;


/* -------------------- HERO 1: Morph -------------------- */
const HeroMorph = ({ setView }) => {
  const [phase, setPhase] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setPhase((p) => (p + 1) % 4), 2500);
    return () => clearInterval(id);
  }, []);

  return (
    <section style={{ position: "relative", padding: "80px 48px 120px", maxWidth: 1400, margin: "0 auto" }}>
      <div style={{ position: "relative", display: "grid", gridTemplateColumns: "1.05fr 1fr", gap: 80, alignItems: "center" }}>
        <div>
          <div className="pill" style={{ marginBottom: 28 }}>
            <span className="pill-dot" style={{ background: "var(--accent-warm)" }} />
            New · Series mode
          </div>
          <h1 className="display" style={{ fontSize: "clamp(56px, 7vw, 96px)", margin: 0, marginBottom: 24 }}>
            Read the paper.<br />
            <span style={{ fontStyle: "italic", color: "var(--accent)" }}>Watch the lecture.</span>
          </h1>
          <p style={{ fontSize: 19, color: "var(--fg-muted)", maxWidth: 520, lineHeight: 1.5, marginBottom: 36 }}>
            Anvya turns research papers and textbook chapters into fully animated, narrated video lectures.
            Manim-style visuals, scripted from first principles, no human in the loop.
          </p>
          <div style={{ display: "flex", gap: 12, marginBottom: 40 }}>
            <button className="btn btn-primary btn-lg" onClick={() => setView("upload")}>
              Upload a PDF <I.arrow size={14} />
            </button>
            <button className="btn btn-lg" onClick={() => setView("library")}>
              <I.play size={12} /> Open library
            </button>
          </div>
          <div style={{ display: "flex", gap: 32, fontSize: 13, color: "var(--fg-muted)" }}>
            <Stat n="48k+" label="lectures generated" />
            <Stat n="11 min" label="average length" />
            <Stat n="$0.42" label="per minute, avg" />
          </div>
        </div>

        <MorphCanvas phase={phase} />
      </div>
    </section>);

};

const Stat = ({ n, label }) =>
<div>
    <div className="display" style={{ fontSize: 22, color: "var(--fg)" }}>{n}</div>
    <div className="mono" style={{ fontSize: 10, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--fg-dim)" }}>{label}</div>
  </div>;


const MorphCanvas = ({ phase }) => {
  // 0: PDF page, 1: extracted concepts, 2: manim scene, 3: video frame
  return (
    <div style={{ position: "relative", aspectRatio: "1 / 1", maxWidth: 540, marginLeft: "auto" }}>
      <div style={{
        position: "absolute", inset: 0,
        borderRadius: 24,
        background: "var(--surface)",
        border: "1px solid var(--border)",
        overflow: "hidden"
      }}>
        {/* phase 0: PDF */}
        <div style={{ position: "absolute", inset: 0, opacity: phase === 0 ? 1 : 0, transition: "opacity 800ms" }}>
          <PdfPagePreview />
        </div>
        {/* phase 1: concept map */}
        <div style={{ position: "absolute", inset: 0, opacity: phase === 1 ? 1 : 0, transition: "opacity 800ms" }}>
          <ConceptMap />
        </div>
        {/* phase 2: manim scene */}
        <div style={{ position: "absolute", inset: 0, opacity: phase === 2 ? 1 : 0, transition: "opacity 800ms" }}>
          <ManimScene />
        </div>
        {/* phase 3: video */}
        <div style={{ position: "absolute", inset: 0, opacity: phase === 3 ? 1 : 0, transition: "opacity 800ms" }}>
          <FinalVideoFrame />
        </div>
      </div>

      {/* Phase labels */}
      <div style={{ position: "absolute", bottom: -36, left: 0, right: 0, display: "flex", justifyContent: "space-between" }}>
        {["PDF", "Digest", "Manim", "Video"].map((label, i) =>
        <div key={label} className="mono" style={{
          fontSize: 10, letterSpacing: "0.14em", textTransform: "uppercase",
          color: phase === i ? "var(--accent)" : "var(--fg-dim)",
          transition: "color 400ms",
          display: "flex", alignItems: "center", gap: 6
        }}>
            <span style={{
            width: 6, height: 6, borderRadius: 3,
            background: phase === i ? "var(--accent)" : "var(--border-strong)",
            transition: "background 400ms"
          }} />
            0{i + 1} {label}
          </div>
        )}
      </div>
    </div>);

};

const PdfPagePreview = () =>
<div style={{ padding: 28, height: "100%", background: "linear-gradient(180deg, #f5f1e8, #ECE6D6)", color: "#1A140A" }}>
    <div className="mono" style={{ fontSize: 9, color: "#948672", marginBottom: 12 }}>Vaswani et al. · arXiv:1706.03762 · p. 4</div>
    <div className="display" style={{ fontFamily: "'Fraunces', serif", fontSize: 18, fontWeight: 600, marginBottom: 14 }}>
      3.2.1 Scaled Dot-Product Attention
    </div>
    {[
  "We call our particular attention 'Scaled Dot-Product",
  "Attention'. The input consists of queries and keys",
  "of dimension d_k, and values of dimension d_v.",
  "We compute the dot products of the query with all keys,",
  "divide each by √d_k, and apply a softmax function to",
  "obtain the weights on the values."].
  map((line, i) =>
  <div key={i} style={{ fontSize: 11, lineHeight: 1.6, opacity: 0.85, fontFamily: "Georgia, serif" }}>{line}</div>
  )}
    <div style={{
    marginTop: 16, padding: "10px 14px",
    border: "1px solid rgba(20,14,5,0.15)",
    borderRadius: 4,
    fontFamily: "'Fraunces', serif", fontStyle: "italic", fontSize: 14,
    textAlign: "center"
  }}>
      Attention(Q, K, V) = softmax(QK<sup>T</sup>/√d<sub>k</sub>) V
    </div>
  </div>;


const ConceptMap = () =>
<div style={{ height: "100%", padding: 28, position: "relative" }}>
    <div className="label-mono" style={{ marginBottom: 14 }}>Knowledge Digest</div>
    <svg viewBox="0 0 400 380" style={{ width: "100%", height: "calc(100% - 28px)" }}>
      <defs>
        <marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M0,0 L10,5 L0,10 z" fill="var(--fg-dim)" />
        </marker>
      </defs>
      {[
    ["self-attention", 200, 60, "var(--accent)"],
    ["query, key, value", 90, 160, "var(--accent-2)"],
    ["dot product", 200, 200, "var(--fg)"],
    ["scaling √d_k", 320, 160, "var(--accent-warm)"],
    ["softmax", 130, 290, "var(--fg)"],
    ["multi-head", 290, 290, "var(--accent-pink)"]].
    map(([t, x, y, c], i) =>
    <g key={i}>
          <circle cx={x} cy={y} r="42" fill="var(--surface-2)" stroke={c} strokeWidth="1.5" />
          <text x={x} y={y + 4} textAnchor="middle" fontSize="11" fill="var(--fg)" fontFamily="var(--mono)">{t}</text>
        </g>
    )}
      {[[200, 60, 90, 160], [200, 60, 320, 160], [200, 60, 200, 200], [200, 200, 130, 290], [200, 60, 290, 290]].map(([x1, y1, x2, y2], i) =>
    <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--fg-dim)" strokeWidth="1" strokeDasharray="3 3" markerEnd="url(#ar)" opacity="0.6" />
    )}
    </svg>
  </div>;


const ManimScene = () =>
<div style={{ height: "100%", background: "#000", padding: 32, position: "relative", color: "white" }}>
    <div className="label-mono" style={{ marginBottom: 14, color: "#9CA3AF" }}>Scene 03 · QKV intro</div>
    <svg viewBox="0 0 400 360" style={{ width: "100%", height: "calc(100% - 28px)" }}>
      {/* Q vector */}
      <g>
        <text x="40" y="80" fontSize="22" fill="#FCD34D" fontFamily="var(--serif)" fontStyle="italic">Q</text>
        <rect x="60" y="60" width="100" height="28" fill="none" stroke="#FCD34D" strokeWidth="1.5" />
        {[0, 1, 2, 3].map((i) =>
      <line key={i} x1={60 + i * 25} y1="60" x2={60 + i * 25} y2="88" stroke="#FCD34D" strokeWidth="1" opacity="0.5" />
      )}
      </g>
      {/* K vectors stack */}
      <g>
        <text x="40" y="180" fontSize="22" fill="#7DD3FC" fontFamily="var(--serif)" fontStyle="italic">K</text>
        {[0, 1, 2].map((i) =>
      <rect key={i} x="60" y={150 + i * 18} width="100" height="14" fill="none" stroke="#7DD3FC" strokeWidth="1.2" opacity={1 - i * 0.2} />
      )}
      </g>
      {/* multiplication arrow */}
      <text x="200" y="160" fontSize="32" fill="white" fontFamily="var(--serif)" fontStyle="italic">·</text>
      <line x1="220" y1="155" x2="280" y2="155" stroke="white" strokeWidth="1.5" markerEnd="url(#ar2)" />
      <defs>
        <marker id="ar2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M0,0 L10,5 L0,10 z" fill="white" />
        </marker>
      </defs>
      {/* attention weights output */}
      <g>
        <text x="290" y="160" fontSize="14" fill="#34D399" fontFamily="var(--serif)" fontStyle="italic">α</text>
        {[0.6, 0.25, 0.15].map((a, i) =>
      <rect key={i} x="305" y={140 + i * 14} width={60 * a} height="10" fill="#34D399" opacity={0.4 + a} />
      )}
      </g>
      {/* equation */}
      <text x="200" y="290" textAnchor="middle" fontSize="18" fill="white" fontFamily="var(--serif)" fontStyle="italic">
        α = softmax( QK<tspan baselineShift="super" fontSize="11">T</tspan> / √d<tspan baselineShift="sub" fontSize="11">k</tspan> )
      </text>
      {/* baseline */}
      <line x1="40" y1="320" x2="360" y2="320" stroke="#374151" strokeWidth="1" />
    </svg>
  </div>;


const FinalVideoFrame = () =>
<div style={{ height: "100%", background: "#000", position: "relative" }}>
    <ManimScene />
    <div style={{
    position: "absolute", left: 16, right: 16, bottom: 16,
    display: "flex", alignItems: "center", gap: 12,
    padding: "10px 14px",
    background: "rgba(0,0,0,0.6)",
    backdropFilter: "blur(8px)",
    borderRadius: 10,
    border: "1px solid rgba(255,255,255,0.1)"
  }}>
      <I.play size={14} stroke="white" />
      <div style={{ flex: 1, height: 3, background: "rgba(255,255,255,0.2)", borderRadius: 2, position: "relative" }}>
        <div style={{ position: "absolute", left: 0, top: 0, height: "100%", width: "38%", background: "var(--accent)", borderRadius: 2 }} />
      </div>
      <div className="mono" style={{ fontSize: 10, color: "white", opacity: 0.7 }}>4:18 / 11:18</div>
    </div>
  </div>;


/* -------------------- HERO 2: Split before/after -------------------- */
const HeroSplit = ({ setView }) =>
<section style={{ padding: "60px 48px 100px", maxWidth: 1400, margin: "0 auto" }}>
    <div style={{ textAlign: "center", marginBottom: 48 }}>
      <div className="pill" style={{ marginBottom: 24 }}>
        <span className="pill-dot" />
        Now generating in Easy mode and Technical mode
      </div>
      <h1 className="display" style={{ fontSize: "clamp(56px, 7vw, 104px)", margin: 0, marginBottom: 20 }}>
        Any paper. <span style={{ fontStyle: "italic", color: "var(--accent)" }}>A real lecture.</span>
      </h1>
      <p style={{ fontSize: 19, color: "var(--fg-muted)", maxWidth: 580, margin: "0 auto", lineHeight: 1.5 }}>
        Drop in a PDF. We extract, digest, script, animate, and narrate it — end to end.
        The output is a 3Blue1Brown-style video you can actually understand.
      </p>
    </div>
    <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", gap: 32, alignItems: "center" }}>
      <div style={{ aspectRatio: "4 / 5", borderRadius: 16, overflow: "hidden", border: "1px solid var(--border)" }}>
        <PdfPagePreview />
      </div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14 }}>
        <div className="label-mono" style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}>Anvya</div>
        <I.arrow size={28} stroke="var(--accent)" />
      </div>
      <div style={{ aspectRatio: "4 / 5", borderRadius: 16, overflow: "hidden", border: "1px solid var(--border)", background: "#000" }}>
        <FinalVideoFrame />
      </div>
    </div>
    <div style={{ display: "flex", justifyContent: "center", gap: 12, marginTop: 48 }}>
      <button className="btn btn-primary btn-lg" onClick={() => setView("upload")}>
        Upload a PDF <I.arrow size={14} />
      </button>
      <button className="btn btn-lg" onClick={() => setView("library")}>
        <I.play size={12} /> Open library
      </button>
    </div>
  </section>;


/* -------------------- HERO 3: Equation that teaches itself -------------------- */
const HeroEquation = ({ setView }) => {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setStep((s) => (s + 1) % 5), 1800);
    return () => clearInterval(id);
  }, []);

  return (
    <section style={{ padding: "100px 48px 120px", maxWidth: 1200, margin: "0 auto", textAlign: "center", position: "relative" }}>
      <div style={{ position: "relative" }}>
        <div className="pill" style={{ marginBottom: 32 }}>
          <span className="pill-dot" />
          From papers to perception
        </div>
        <h1 className="display" style={{ fontSize: "clamp(48px, 6vw, 88px)", margin: 0, marginBottom: 24 }}>
          What if every paper<br />
          <span style={{ fontStyle: "italic", color: "rgb(244, 241, 234)" }}>taught itself</span>?
        </h1>

        {/* Self-teaching equation */}
        <div style={{
          margin: "60px auto 24px",
          padding: "56px 48px 48px",
          maxWidth: 880,
          position: "relative"
        }}>
          {/* corner ornaments */}
          <div style={{ position: "absolute", top: 0, left: 0, width: 24, height: 24, borderTop: "1px solid var(--accent)", borderLeft: "1px solid var(--accent)", opacity: 0.6 }} />
          <div style={{ position: "absolute", top: 0, right: 0, width: 24, height: 24, borderTop: "1px solid var(--accent)", borderRight: "1px solid var(--accent)", opacity: 0.6 }} />
          <div style={{ position: "absolute", bottom: 0, left: 0, width: 24, height: 24, borderBottom: "1px solid var(--accent)", borderLeft: "1px solid var(--accent)", opacity: 0.6 }} />
          <div style={{ position: "absolute", bottom: 0, right: 0, width: 24, height: 24, borderBottom: "1px solid var(--accent)", borderRight: "1px solid var(--accent)", opacity: 0.6 }} />

          {/* tag floating on top edge */}
          <div className="label-mono" style={{ position: "absolute", top: -8, left: "50%", transform: "translateX(-50%)", padding: "0 14px", background: "var(--bg)", color: "var(--accent)", letterSpacing: "0.22em" }}>
            scaled dot-product attention
          </div>

          <div className="display" style={{ fontSize: 52, fontStyle: "italic", letterSpacing: 0, textAlign: "center" }}>
            <span style={{ color: step >= 0 ? "var(--fg)" : "var(--fg-dim)", transition: "color 600ms" }}>α</span>
            <span style={{ color: "var(--fg-muted)", margin: "0 14px" }}>=</span>
            <span style={{ color: step >= 1 ? "var(--accent)" : "var(--fg-dim)", transition: "color 600ms" }}>softmax</span>
            <span style={{ color: "var(--fg-muted)" }}>(</span>
            <span style={{ color: step >= 2 ? "var(--accent-2)" : "var(--fg-dim)", transition: "color 600ms" }}>QK<sup>T</sup></span>
            <span style={{ color: step >= 3 ? "var(--accent-warm)" : "var(--fg-dim)", margin: "0 6px", transition: "color 600ms" }}>/ √d<sub>k</sub></span>
            <span style={{ color: "var(--fg-muted)" }}>)</span>
            <span style={{ color: step >= 4 ? "var(--accent-pink)" : "var(--fg-dim)", marginLeft: 10, transition: "color 600ms" }}>V</span>
          </div>
          {/* ornamental rule under equation */}
          <div style={{ height: 28, color: "var(--fg-muted)", fontSize: 17, textAlign: "center", fontStyle: "italic" }}>
            {step === 0 && <span>α — the attention weight we're solving for</span>}
            {step === 1 && <span>softmax — turn raw scores into probabilities</span>}
            {step === 2 && <span>QK<sup>T</sup> — query asks each key "how aligned are we?"</span>}
            {step === 3 && <span>/ √d<sub>k</sub> — scale, so dimensions don't dominate</span>}
            {step === 4 && <span>V — multiply by values to read out the answer</span>}
          </div>
        </div>

        <p style={{ fontSize: 18, color: "var(--fg-muted)", maxWidth: 560, margin: "32px auto 36px" }}>
          Drop a PDF. We script the lesson, generate the animations, narrate it,
          and ship a video — in about ten minutes.
        </p>

        <div style={{ display: "flex", justifyContent: "center", gap: 12 }}>
          <button className="btn btn-primary btn-lg" onClick={() => setView("upload")}>
            Upload a PDF <I.arrow size={14} />
          </button>
          <button className="btn btn-lg" onClick={() => setView("library")}><I.play size={12} /> Open library</button>
        </div>
      </div>
    </section>);

};

/* -------------------- Pipeline section -------------------- */
const PipelineSection = () =>
<section style={{ padding: "100px 48px", maxWidth: 1400, margin: "0 auto" }}>
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 48 }}>
      <div>
        <div className="label-mono" style={{ marginBottom: 12 }}>Pipeline · 6 stages</div>
        <h2 className="display" style={{ fontSize: 56, margin: 0, maxWidth: 720 }}>
          The same pipeline a great<br />
          teacher would <em style={{ color: "var(--accent)" }}>actually use</em>.
        </h2>
      </div>
      <p style={{ color: "var(--fg-muted)", maxWidth: 320, fontSize: 15 }}>
        Each stage is cached. Re-runs are fast and cheap — change the difficulty mode, get a new lecture in under a minute.
      </p>
    </div>

    <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 16 }}>
      {[
    { n: "01", t: "PDF Upload", d: "Drop a textbook chapter or research paper. We accept up to 200 pages." },
    { n: "02", t: "Smart Extraction", d: "Parse ToC, strip exercises, footnotes, and front matter. Find the real chapters." },
    { n: "03", t: "Knowledge Digest", d: "Map every concept, equation, derivation, and worked example into a structured graph." },
    { n: "04", t: "Explanation", d: "Write the lesson — narration, math derivations, scene-by-scene plan. Series Bible enforces consistency." },
    { n: "05", t: "Manim Code", d: "Generate Python animation code. Validator auto-fixes overlap and bounds issues." },
    { n: "06", t: "Render", d: "TTS narration per beat, Manim scenes rendered, ffmpeg muxes a final MP4." }].
    map((s) =>
    <div key={s.n} className="card" style={{ padding: 20 }}>
          <div className="mono" style={{ fontSize: 11, color: "var(--accent)", marginBottom: 28 }}>{s.n}</div>
          <div className="display" style={{ fontSize: 19, lineHeight: 1.15, marginBottom: 8 }}>{s.t}</div>
          <div style={{ fontSize: 13, color: "var(--fg-muted)", lineHeight: 1.5 }}>{s.d}</div>
        </div>
    )}
    </div>
  </section>;


/* -------------------- Features -------------------- */
const FeaturesSection = () =>
<section style={{ padding: "100px 48px", maxWidth: 1400, margin: "0 auto" }}>
    <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr 1fr", gap: 16 }}>
      <div className="card" style={{ padding: 32, gridRow: "span 2", display: "flex", flexDirection: "column" }}>
        <div className="label-mono" style={{ marginBottom: 16 }}>Easy ↔ Technical</div>
        <div className="display" style={{ fontSize: 36, marginBottom: 12 }}>
          Two modes. Same paper. Different lecture.
        </div>
        <p style={{ color: "var(--fg-muted)", marginBottom: 24 }}>
          Easy mode leans on intuition and analogies. Technical mode keeps the equations,
          shows the derivations, and assumes you've seen calculus.
        </p>
        <div style={{ marginTop: "auto", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <ModePreview mode="Easy" desc="Library analogy. No math." accent="var(--accent-warm)" />
          <ModePreview mode="Technical" desc="Derivation of √d_k." accent="var(--accent-2)" />
        </div>
      </div>

      <FeatureCard
      title="Series Bible"
      desc="Lock the running example, notation, and visual style across an entire chapter set. Episode 7 still calls them Q, K, V."
      icon={<I.layers size={22} stroke="var(--accent)" />} />
    
      <FeatureCard
      title="Cached at every stage"
      desc="Tweaking copy doesn't re-render the video. Tweaking the script doesn't re-extract the PDF. Iteration is cheap."
      icon={<I.layers size={22} stroke="var(--accent-2)" />} />
    
      <FeatureCard
      title="Live progress"
      desc="A long pipeline. So we tell you exactly where you are — extraction, digest, render — every step streamed live."
      icon={<I.pulse size={22} stroke="var(--accent-warm)" />} />
    
      <FeatureCard
      title="Saved forever"
      desc="Every video lives in your library. Share by link, embed, or download as MP4 + transcript JSON."
      icon={<I.bookmark size={22} stroke="var(--accent-pink)" />} />
    
    </div>
  </section>;


const FeatureCard = ({ title, desc, icon }) =>
<div className="card" style={{ padding: 28 }}>
    <div style={{ marginBottom: 20 }}>{icon}</div>
    <div className="display" style={{ fontSize: 22, marginBottom: 8 }}>{title}</div>
    <div style={{ fontSize: 13, color: "var(--fg-muted)", lineHeight: 1.5 }}>{desc}</div>
  </div>;


const ModePreview = ({ mode, desc, accent }) =>
<div style={{
  padding: 16,
  border: "1px solid var(--border)",
  borderRadius: 10,
  background: "var(--bg-2)"
}}>
    <div className="mono" style={{ fontSize: 10, color: accent, marginBottom: 8, letterSpacing: "0.1em", textTransform: "uppercase" }}>{mode}</div>
    <div style={{ fontSize: 13, color: "var(--fg-muted)" }}>{desc}</div>
  </div>;


/* -------------------- Samples -------------------- */
const SamplesSection = ({ setView }) =>
<section style={{ padding: "100px 48px", maxWidth: 1400, margin: "0 auto" }}>
    <div style={{ marginBottom: 36 }}>
      <div className="label-mono" style={{ marginBottom: 12 }}>Recent generations</div>
      <h2 className="display" style={{ fontSize: 48, margin: 0 }}>From the community.</h2>
    </div>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
      {window.LIBRARY.slice(0, 3).map((v) =>
    <SampleCard key={v.id} v={v} onClick={() => setView("player")} />
    )}
    </div>
  </section>;


const SampleCard = ({ v, onClick }) =>
<div className="card" style={{ padding: 0, overflow: "hidden", cursor: "pointer" }} onClick={onClick}>
    <div style={{
    aspectRatio: "16 / 9",
    background: "#000",
    position: "relative",
    borderBottom: "1px solid var(--border)"
  }}>
      <ManimScene />
      <div style={{
      position: "absolute", inset: 0, display: "grid", placeItems: "center",
      background: "linear-gradient(180deg, transparent 50%, rgba(0,0,0,0.5))"
    }}>
        <div style={{
        width: 56, height: 56, borderRadius: "50%",
        background: "rgba(255,255,255,0.95)",
        display: "grid", placeItems: "center"
      }}>
          <I.play size={20} stroke="#000" />
        </div>
      </div>
      <div className="mono" style={{ position: "absolute", right: 10, bottom: 10, padding: "3px 8px", background: "rgba(0,0,0,0.7)", color: "white", fontSize: 11, borderRadius: 4 }}>{v.duration}</div>
    </div>
    <div style={{ padding: 20 }}>
      <div className="display" style={{ fontSize: 20, marginBottom: 6 }}>{v.title}</div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 12, color: "var(--fg-muted)" }}>
        <span>{v.author}</span>
        <span style={{ color: "var(--fg-dim)" }}>·</span>
        <span style={{ color: "rgb(125, 211, 252)" }}>{v.mode}</span>
      </div>
    </div>
  </div>;


/* -------------------- Footer / CTA -------------------- */
const Footer = () =>
<section style={{ padding: "100px 48px 60px", maxWidth: 1400, margin: "0 auto", textAlign: "center" }}>
    <h2 className="display" style={{ fontSize: 72, margin: 0, marginBottom: 18 }}>
      Stop reading.<br />
      <em style={{ color: "var(--accent)" }}>Start watching.</em>
    </h2>
    <p style={{ fontSize: 17, color: "var(--fg-muted)", maxWidth: 480, margin: "0 auto 32px" }}>
      Free for your first three lectures. No credit card.
    </p>
    <button className="btn btn-primary btn-lg">Upload a PDF <I.arrow size={14} /></button>
    <div style={{
    marginTop: 80, paddingTop: 32,
    borderTop: "1px solid var(--border)",
    display: "flex", justifyContent: "space-between",
    color: "var(--fg-dim)", fontSize: 13
  }}>
      <Brand size={20} />
      <div style={{ display: "flex", gap: 24 }}>
        <span>Pricing</span><span>Examples</span><span>Docs</span><span>Privacy</span><span>Terms</span>
      </div>
      <div className="mono">© 2026</div>
    </div>
  </section>;


window.Landing = Landing;
window.PdfPagePreview = PdfPagePreview;
window.ManimScene = ManimScene;
window.FinalVideoFrame = FinalVideoFrame;