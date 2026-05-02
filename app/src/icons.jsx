// Lightweight stroke icons (Lucide-style)
const Icon = ({ d, size = 16, stroke = "currentColor", fill = "none", children, ...rest }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill={fill}
    stroke={stroke}
    strokeWidth="1.6"
    strokeLinecap="round"
    strokeLinejoin="round"
    {...rest}
  >
    {d ? <path d={d} /> : children}
  </svg>
);

const I = {
  home: (p) => <Icon {...p}><path d="M3 10.5L12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/></Icon>,
  upload: (p) => <Icon {...p}><path d="M12 3v13"/><path d="M7 8l5-5 5 5"/><path d="M5 21h14"/></Icon>,
  pulse: (p) => <Icon {...p}><path d="M3 12h4l2-7 4 14 2-7h6"/></Icon>,
  play: (p) => <Icon {...p}><path d="M6 4l14 8-14 8z" fill="currentColor"/></Icon>,
  library: (p) => <Icon {...p}><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></Icon>,
  settings: (p) => <Icon {...p}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06A1.65 1.65 0 0 0 15 19.4a1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9c.16.39.5.7.93.85.16.06.34.09.51.09H21a2 2 0 1 1 0 4h-.09c-.43 0-.84.16-1.15.45z"/></Icon>,
  arrow: (p) => <Icon {...p}><path d="M5 12h14"/><path d="M13 5l7 7-7 7"/></Icon>,
  arrowDown: (p) => <Icon {...p}><path d="M12 5v14"/><path d="M19 12l-7 7-7-7"/></Icon>,
  check: (p) => <Icon {...p}><path d="M4 12l5 5L20 6"/></Icon>,
  pdf: (p) => <Icon {...p}><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><text x="7.5" y="17" fontSize="5" fontFamily="monospace" fontWeight="700" fill="currentColor" stroke="none">PDF</text></Icon>,
  sparkle: (p) => <Icon {...p}><path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5z"/><path d="M19 17l.7 2.1L22 20l-2.3.9L19 23l-.7-2.1L16 20l2.3-.9z"/></Icon>,
  film: (p) => <Icon {...p}><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 3v18"/><path d="M17 3v18"/><path d="M3 8h4"/><path d="M3 16h4"/><path d="M17 8h4"/><path d="M17 16h4"/><path d="M7 12h10"/></Icon>,
  pause: (p) => <Icon {...p}><rect x="6" y="4" width="4" height="16" rx="1" fill="currentColor"/><rect x="14" y="4" width="4" height="16" rx="1" fill="currentColor"/></Icon>,
  bookmark: (p) => <Icon {...p}><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></Icon>,
  cc: (p) => <Icon {...p}><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M8 11a2 2 0 0 0-2 2 2 2 0 0 0 2 2"/><path d="M16 11a2 2 0 0 0-2 2 2 2 0 0 0 2 2"/></Icon>,
  speed: (p) => <Icon {...p}><circle cx="12" cy="13" r="8"/><path d="M12 13l4-4"/><path d="M9 3h6"/></Icon>,
  share: (p) => <Icon {...p}><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.6 13.5l6.8 4"/><path d="M15.4 6.5l-6.8 4"/></Icon>,
  search: (p) => <Icon {...p}><circle cx="11" cy="11" r="7"/><path d="M16 16l5 5"/></Icon>,
  filter: (p) => <Icon {...p}><path d="M3 5h18"/><path d="M6 12h12"/><path d="M10 19h4"/></Icon>,
  arrowLeft: (p) => <Icon {...p}><path d="M19 12H5"/><path d="M11 19l-7-7 7-7"/></Icon>,
  x: (p) => <Icon {...p}><path d="M6 6l12 12"/><path d="M18 6l-12 12"/></Icon>,
  more: (p) => <Icon {...p}><circle cx="5" cy="12" r="1.5" fill="currentColor"/><circle cx="12" cy="12" r="1.5" fill="currentColor"/><circle cx="19" cy="12" r="1.5" fill="currentColor"/></Icon>,
  plus: (p) => <Icon {...p}><path d="M12 5v14"/><path d="M5 12h14"/></Icon>,
  clock: (p) => <Icon {...p}><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></Icon>,
  doc: (p) => <Icon {...p}><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6"/><path d="M9 17h6"/></Icon>,
  brain: (p) => <Icon {...p}><path d="M12 5a3 3 0 0 0-3 3v0a3 3 0 0 0-3 3 3 3 0 0 0 1 2.2A3 3 0 0 0 9 19h0a3 3 0 0 0 3-3"/><path d="M12 5a3 3 0 0 1 3 3v0a3 3 0 0 1 3 3 3 3 0 0 1-1 2.2A3 3 0 0 1 15 19h0a3 3 0 0 1-3-3"/><path d="M12 5v14"/></Icon>,
  code: (p) => <Icon {...p}><path d="M16 18l6-6-6-6"/><path d="M8 6l-6 6 6 6"/></Icon>,
  layers: (p) => <Icon {...p}><path d="M12 2L2 7l10 5 10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></Icon>,
  globe: (p) => <Icon {...p}><circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3a14 14 0 0 1 0 18a14 14 0 0 1 0-18"/></Icon>,
  google: (p) => <Icon {...p}><path d="M21 12a9 9 0 1 1-2.6-6.4"/><path d="M21 4v5h-5"/></Icon>,
};

window.I = I;
window.Icon = Icon;
