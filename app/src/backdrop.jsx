// MagicalBackdrop — a minimal 3D parallaxed glyph field rendered behind the landing
// hero. Mathematical sigils drift through perspective space; cursor tilts the
// field. Pure CSS 3D transforms, no canvas, no deps.

const MAGIC_GLYPHS = ["∑", "∂", "∫", "∮", "π", "𝛁", "ℏ", "∞", "Φ", "Ψ", "λ", "ε", "α", "β", "θ", "ƒ", "≈", "ℒ", "ℂ", "∇"];

// Deterministic pseudo-random so layout is stable across mounts
const seededRand = (seed) => {
  let s = seed;
  return () => {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
};

const MagicalBackdrop = () => {
  const wrapRef = React.useRef(null);
  const fieldRef = React.useRef(null);
  const targetRef = React.useRef({ x: 0, y: 0 });
  const currentRef = React.useRef({ x: 0, y: 0 });
  const rafRef = React.useRef(0);

  // Generate the glyph field once
  const glyphs = React.useMemo(() => {
    const r = seededRand(7);
    const items = [];
    // 3 depth layers — back (small/dim), mid, front (large/translucent)
    const layers = [
      { count: 28, zMin: -800, zMax: -500, sizeMin: 14, sizeMax: 22, opacityMin: 0.08, opacityMax: 0.18 },
      { count: 18, zMin: -400, zMax: -150, sizeMin: 22, sizeMax: 38, opacityMin: 0.14, opacityMax: 0.26 },
      { count: 6,  zMin: -100, zMax:  100, sizeMin: 60, sizeMax: 110, opacityMin: 0.06, opacityMax: 0.12 }
    ];
    layers.forEach((L, li) => {
      for (let i = 0; i < L.count; i++) {
        items.push({
          id: `${li}-${i}`,
          glyph: MAGIC_GLYPHS[Math.floor(r() * MAGIC_GLYPHS.length)],
          x: r() * 100,        // vw %
          y: r() * 110 - 5,    // vh % (slight overflow top/bot)
          z: L.zMin + r() * (L.zMax - L.zMin),
          size: L.sizeMin + r() * (L.sizeMax - L.sizeMin),
          opacity: L.opacityMin + r() * (L.opacityMax - L.opacityMin),
          rotX: (r() - 0.5) * 50,
          rotY: (r() - 0.5) * 50,
          rotZ: (r() - 0.5) * 30,
          driftDur: 22 + r() * 28,    // s
          driftDelay: -r() * 30,      // s (negative so they're already in motion)
          spinDur: 30 + r() * 40,
          spinDelay: -r() * 30,
          driftDx: (r() - 0.5) * 60,  // px
          driftDy: (r() - 0.5) * 60,
          layer: li
        });
      }
    });
    return items;
  }, []);

  React.useEffect(() => {
    const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) return;

    const onMove = (e) => {
      const w = window.innerWidth;
      const h = window.innerHeight;
      // -1..1 normalized
      targetRef.current.x = (e.clientX / w - 0.5) * 2;
      targetRef.current.y = (e.clientY / h - 0.5) * 2;
    };
    window.addEventListener("pointermove", onMove, { passive: true });

    const tick = () => {
      const t = targetRef.current;
      const c = currentRef.current;
      // Eased lerp — feels physical
      c.x += (t.x - c.x) * 0.05;
      c.y += (t.y - c.y) * 0.05;
      const f = fieldRef.current;
      if (f) {
        const rotY = c.x * 6;   // deg — subtle
        const rotX = -c.y * 4;
        const tx = c.x * -18;   // px counter-parallax
        const ty = c.y * -12;
        f.style.transform = `translate3d(${tx}px, ${ty}px, 0) rotateX(${rotX}deg) rotateY(${rotY}deg)`;
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      window.removeEventListener("pointermove", onMove);
      cancelAnimationFrame(rafRef.current);
    };
  }, []);

  return (
    <React.Fragment>
      <style>{`
        @keyframes mb-drift-0 {
          0%, 100% { transform: translate3d(0, 0, 0); }
          50% { transform: translate3d(var(--mb-dx, 0), var(--mb-dy, 0), 0); }
        }
        @keyframes mb-spin {
          from { transform: rotateX(var(--mb-rx, 0deg)) rotateY(var(--mb-ry, 0deg)) rotateZ(var(--mb-rz, 0deg)); }
          to   { transform: rotateX(calc(var(--mb-rx, 0deg) + 360deg)) rotateY(calc(var(--mb-ry, 0deg) + 240deg)) rotateZ(calc(var(--mb-rz, 0deg) + 180deg)); }
        }
        @keyframes mb-pulse {
          0%, 100% { opacity: var(--mb-op-base, 0.15); }
          50% { opacity: calc(var(--mb-op-base, 0.15) * 1.7); }
        }
        .mb-wrap {
          position: absolute; inset: 0;
          pointer-events: none;
          overflow: hidden;
          z-index: 0;
          perspective: 1100px;
          perspective-origin: 50% 50%;
        }
        .mb-field {
          position: absolute; inset: 0;
          transform-style: preserve-3d;
          will-change: transform;
          transition: transform 60ms linear;
        }
        .mb-glyph {
          position: absolute;
          font-family: 'Fraunces', 'Lora', Georgia, serif;
          font-weight: 400;
          color: var(--accent);
          mix-blend-mode: screen;
          will-change: transform, opacity;
          transform-style: preserve-3d;
          user-select: none;
          text-shadow: 0 0 18px color-mix(in srgb, var(--accent) 40%, transparent);
        }
        /* Chalk palette: vibrant chalk strokes — multicolored, screen-blend, italic Lora */
        :root[data-palette="chalk"] .mb-glyph {
          mix-blend-mode: screen;
          font-family: 'Lora', 'Fraunces', Georgia, serif;
          font-style: italic;
          text-shadow:
            0 0 16px color-mix(in srgb, currentColor 50%, transparent),
            0 0 4px color-mix(in srgb, currentColor 70%, transparent);
        }
        :root[data-palette="chalk"] .mb-aura {
          background: radial-gradient(circle at center,
            color-mix(in srgb, var(--accent) 14%, transparent) 0%,
            color-mix(in srgb, var(--accent-pink) 8%, transparent) 30%,
            color-mix(in srgb, var(--accent-2) 5%, transparent) 50%,
            transparent 70%);
        }
        /* Paper palette: ink on parchment */
        :root[data-palette="paper"] .mb-glyph {
          mix-blend-mode: multiply;
          text-shadow: none;
        }
        .mb-glyph-inner {
          display: inline-block;
          will-change: transform;
        }
        .mb-aura {
          position: absolute;
          width: 60vmax; height: 60vmax;
          border-radius: 50%;
          left: 50%; top: 30%;
          transform: translate(-50%, -50%);
          background: radial-gradient(circle at center,
            color-mix(in srgb, var(--accent) 8%, transparent) 0%,
            color-mix(in srgb, var(--accent-2) 4%, transparent) 35%,
            transparent 65%);
          filter: blur(40px);
          pointer-events: none;
          animation: mb-aura-breathe 14s ease-in-out infinite;
        }
        @keyframes mb-aura-breathe {
          0%, 100% { transform: translate(-50%, -50%) scale(1); opacity: 0.7; }
          50% { transform: translate(-50%, -50%) scale(1.12); opacity: 1; }
        }
        @media (prefers-reduced-motion: reduce) {
          .mb-glyph-inner, .mb-aura { animation: none !important; }
        }
      `}</style>
      <div ref={wrapRef} className="mb-wrap" aria-hidden="true">
        <div className="mb-aura" />
        <div ref={fieldRef} className="mb-field">
          {glyphs.map((g) => {
            // Color: layer 0 (back) → muted plum/pink; layer 1 → amber; layer 2 (front) → soft accent
            const colorVar = g.layer === 0 ? "var(--accent-pink)" : (g.layer === 1 ? "var(--accent)" : "var(--accent-warm)");
            return (
              <div
                key={g.id}
                className="mb-glyph"
                style={{
                  left: `${g.x}%`,
                  top: `${g.y}%`,
                  fontSize: `${g.size}px`,
                  color: colorVar,
                  transform: `translate3d(-50%, -50%, ${g.z}px)`,
                  "--mb-op-base": g.opacity,
                  opacity: g.opacity
                }}>
                <div
                  className="mb-glyph-inner"
                  style={{
                    "--mb-rx": `${g.rotX}deg`,
                    "--mb-ry": `${g.rotY}deg`,
                    "--mb-rz": `${g.rotZ}deg`,
                    "--mb-dx": `${g.driftDx}px`,
                    "--mb-dy": `${g.driftDy}px`,
                    animation: `mb-spin ${g.spinDur}s linear ${g.spinDelay}s infinite, mb-drift-0 ${g.driftDur}s ease-in-out ${g.driftDelay}s infinite, mb-pulse ${g.driftDur * 0.8}s ease-in-out ${g.driftDelay}s infinite`
                  }}>
                  {g.glyph}
                </div>
              </div>);
          })}
        </div>
      </div>
    </React.Fragment>);
};

window.MagicalBackdrop = MagicalBackdrop;
