"""
Scene Validator: post-generation code validator for Manim scenes.

Runs between LLM code generation and Manim execution.  Parses the
generated Python source, tracks visible objects, detects overlap /
cleanup violations, and auto-injects fixes.
"""

import re
from typing import List, Set, Tuple, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Phase boundary comment patterns the LLM typically generates
_PHASE_PATTERNS = [
    re.compile(r"^\s*#\s*={3,}\s*(PHASE|Phase|P\d|BEAT|Beat)", re.IGNORECASE),
    re.compile(r"^\s*#\s*-{3,}\s*(PHASE|Phase|P\d)", re.IGNORECASE),
    re.compile(r"^\s*#\s*(Phase|PHASE)\s+\d"),
]

# Manim mobject class names (common subset — enough for detection)
_MOBJECT_CLASSES = {
    "Text", "MathTex", "Tex", "Circle", "Square", "Rectangle", "Dot",
    "Arrow", "Line", "DashedLine", "CurvedArrow", "DoubleArrow",
    "VGroup", "Group", "Star", "Ellipse", "Polygon", "RegularPolygon",
    "Triangle", "Annulus", "Arc", "Sector", "NumberLine", "Axes",
    "BarChart", "Table", "SurroundingRectangle", "Brace", "BraceBetweenPoints",
    "RoundedRectangle", "Underline", "Cross", "Cutout",
    "DecimalNumber", "Integer", "BulletedList", "Title",
    "ImageMobject", "SVGMobject",
}

# Animations that make objects *visible*
_SHOW_ANIMATIONS = {
    "Create", "Write", "FadeIn", "GrowArrow", "DrawBorderThenFill",
    "GrowFromCenter", "GrowFromEdge", "GrowFromPoint", "SpinInFromNothing",
    "ShowCreation", "ShowPassingFlash", "AddTextLetterByLetter",
}

# Animations that *remove* objects
_HIDE_ANIMATIONS = {"FadeOut", "Uncreate", "ShrinkToCenter"}

# Safe frame boundaries (conservative)
_SAFE_X = 5.5
_SAFE_Y = 3.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_phase_boundaries(lines: List[str]) -> List[int]:
    """Return line indices where new phases begin."""
    boundaries: List[int] = []
    for i, line in enumerate(lines):
        for pat in _PHASE_PATTERNS:
            if pat.search(line):
                boundaries.append(i)
                break
    return boundaries


def _extract_var_name(line: str) -> Optional[str]:
    """Return the variable name from an assignment like `foo = Text(...)`, or None."""
    m = re.match(r"^\s+(\w+)\s*=\s*(\w+)\s*\(", line)
    if m and m.group(2) in _MOBJECT_CLASSES:
        return m.group(1)
    return None


def _extract_vgroup_members(line: str) -> Tuple[Optional[str], List[str]]:
    """Parse `grp = VGroup(a, b, c)` → ('grp', ['a','b','c'])."""
    m = re.match(r"^\s+(\w+)\s*=\s*VGroup\(([^)]*)\)", line)
    if m:
        name = m.group(1)
        inner = m.group(2).strip()
        members = [s.strip() for s in inner.split(",") if s.strip()] if inner else []
        return name, members
    return None, []


def _extract_shown_vars(line: str) -> Set[str]:
    """Extract variable names made visible in a self.play(...) call."""
    found: Set[str] = set()
    for anim in _SHOW_ANIMATIONS:
        for m in re.finditer(rf"{anim}\((\w+)", line):
            found.add(m.group(1))
    return found


def _extract_hidden_vars(line: str) -> Set[str]:
    """Extract variable names removed in a self.play(FadeOut(...)) call."""
    found: Set[str] = set()
    for anim in _HIDE_ANIMATIONS:
        for m in re.finditer(rf"{anim}\((\w+)", line):
            found.add(m.group(1))
    # Also catch: self.play(*[FadeOut(obj) for obj in VAR_LIST], ...)
    m = re.search(r"FadeOut\(\w+\)\s+for\s+\w+\s+in\s+(\w+)", line)
    if m:
        found.add(m.group(1))
    return found


def _line_has_fadeout(line: str) -> bool:
    """Check if a line contains any FadeOut animation."""
    return "FadeOut" in line


def _get_indent(line: str) -> str:
    """Return the leading whitespace of a line."""
    return re.match(r"^(\s*)", line).group(1)


# Inline tag and variable-name conventions marking a mobject as PERSISTENT across phases.
# Persistent objects — e.g. a header or an accumulating math/derivation panel in the
# 2-column zone layout — are excluded from Fix C's auto-FadeOut so they survive validation.
# The codegen prompt is expected to emit these names / the tag for things that must persist.
_PERSIST_TAG = "[persist]"


def _is_persistent_assignment(line: str, var: str) -> bool:
    """True if this assignment marks the object as persistent across phase boundaries."""
    if _PERSIST_TAG in line:
        return True
    v = var.lower()
    return (
        v == "header"
        or v.startswith("header")
        or v == "panel"
        or v.endswith("_panel")
        or "math_panel" in v
    )


# ---------------------------------------------------------------------------
# Core validator
# ---------------------------------------------------------------------------

def validate_and_fix_scene(code: str) -> Tuple[str, int]:
    """
    Validate and fix a generated Manim scene.

    Args:
        code: Raw Python source code string.

    Returns:
        (fixed_code, num_fixes) tuple.
    """
    lines = code.split("\n")
    fixes = 0

    # --- Fix A: Remove duplicate imports ---
    seen_imports: Set[str] = set()
    cleaned_lines: List[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("from manim import") or stripped.startswith("import manim"):
            if stripped in seen_imports:
                fixes += 1
                continue
            seen_imports.add(stripped)
        cleaned_lines.append(line)
    lines = cleaned_lines

    # --- Fix B: Cap excessive self.wait() durations ---
    MAX_WAIT = 25.0
    new_lines: List[str] = []
    for line in lines:
        m = re.match(r"^(\s+)self\.wait\((\d+\.?\d*)\)", line)
        if m:
            val = float(m.group(2))
            if val > MAX_WAIT:
                indent = m.group(1)
                new_lines.append(f"{indent}self.wait({MAX_WAIT})")
                fixes += 1
                continue
        new_lines.append(line)
    lines = new_lines

    # --- Fix C: Detect phase boundaries and inject missing FadeOut ---
    boundaries = _find_phase_boundaries(lines)

    if len(boundaries) >= 2:
        # Track objects through the code
        visible: Set[str] = set()
        persistent: Set[str] = set()  # vars excluded from auto-FadeOut (header, math panel, ...)
        groups: dict[str, Set[str]] = {}  # group_name -> member names
        insertions: List[Tuple[int, str]] = []  # (line_idx, code_to_insert)

        for i, line in enumerate(lines):
            # Track object creation
            var = _extract_var_name(line)
            if var and _is_persistent_assignment(line, var):
                persistent.add(var)

            # Track VGroup membership
            grp_name, members = _extract_vgroup_members(line)
            if grp_name:
                groups[grp_name] = set(members)
                if _is_persistent_assignment(line, grp_name):
                    persistent.add(grp_name)

            # Track .add() calls on groups
            add_m = re.match(r"^\s+(\w+)\.add\((\w+)\)", line)
            if add_m:
                grp = add_m.group(1)
                member = add_m.group(2)
                if grp in groups:
                    groups[grp].add(member)

            # Track visibility
            shown = _extract_shown_vars(line)
            visible.update(shown)

            # Track removal
            hidden = _extract_hidden_vars(line)
            for h in hidden:
                visible.discard(h)
                # If a group is hidden, remove all its members too
                if h in groups:
                    visible -= groups[h]

            # Check at phase boundaries
            if i in boundaries and i != boundaries[0]:
                # Look ahead: does the next 3 lines contain a FadeOut?
                lookahead = "\n".join(lines[i:min(i + 5, len(lines))])
                has_cleanup = _line_has_fadeout(lookahead)

                # Persistent objects (header / accumulating math panel) are never
                # auto-faded — only non-persistent "orphans" are eligible for cleanup.
                cleanable = visible - persistent

                if not has_cleanup and len(cleanable) > 1:
                    # There are orphaned visible objects and no upcoming cleanup
                    # Find the indent level from the phase comment or surrounding code
                    indent = "        "  # default 8 spaces (inside construct)
                    for j in range(max(0, i - 3), i):
                        if "self.play" in lines[j] or "self.wait" in lines[j]:
                            indent = _get_indent(lines[j])
                            break

                    # Build FadeOut injection — only the non-persistent orphans
                    orphans = sorted(cleanable)
                    if len(orphans) <= 6:
                        fadeout_args = ", ".join(orphans)
                        injection = f"{indent}self.play(FadeOut({fadeout_args}), run_time=1.5)  # [auto-cleanup]"
                    else:
                        # Too many to list inline — use *[FadeOut(m) for m in [...]]
                        orphan_list = ", ".join(orphans[:8])
                        injection = f"{indent}self.play(*[FadeOut(m) for m in [{orphan_list}]], run_time=1.5)  # [auto-cleanup]"

                    insertions.append((i, injection))
                    fixes += 1

                    # After injection, the cleaned orphans are gone; persistent objects stay.
                    visible = set(persistent)

        # Apply insertions in reverse order to preserve line numbers
        for idx, code_line in reversed(insertions):
            lines.insert(idx, code_line)

    # --- Fix D: Scale oversized MathTex ---
    new_lines = []
    for i, line in enumerate(lines):
        new_lines.append(line)
        # Check for MathTex with very long strings
        m = re.match(r'^(\s+)(\w+)\s*=\s*MathTex\((.+)\)', line)
        if m:
            indent = m.group(1)
            var_name = m.group(2)
            content = m.group(3)
            # Count the total LaTeX content length (rough heuristic)
            # Remove string delimiters and count
            clean = re.sub(r'["\']', '', content)
            clean = re.sub(r',\s*(font_size|color|tex_template)\s*=\s*\S+', '', clean)
            if len(clean) > 90:
                new_lines.append(f"{indent}if {var_name}.width > 11: {var_name}.scale(11.0 / {var_name}.width)  # [auto-scale]")
                fixes += 1
    lines = new_lines

    # --- Fix E: Validate spatial coordinates ---
    # Check .move_to(np.array([x, y, 0])) patterns
    new_lines = []
    for line in lines:
        fixed_line = line
        m = re.search(r'np\.array\(\[\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*0\s*\]\)', line)
        if m:
            x, y = float(m.group(1)), float(m.group(2))
            if abs(x) > _SAFE_X or abs(y) > _SAFE_Y:
                cx = max(-_SAFE_X, min(_SAFE_X, x))
                cy = max(-_SAFE_Y, min(_SAFE_Y, y))
                old = m.group(0)
                new = f"np.array([{cx}, {cy}, 0])"
                fixed_line = line.replace(old, new)
                fixes += 1
        new_lines.append(fixed_line)
    lines = new_lines

    # --- Fix F: Sector() takes radius=, not outer_radius= ---
    # Manim's Sector forwards outer_radius=radius to its AnnularSector parent,
    # so passing outer_radius= explicitly raises
    # "got multiple values for keyword argument 'outer_radius'".
    # AnnularSector legitimately accepts outer_radius=, so exclude it.
    new_lines = []
    for line in lines:
        if "outer_radius" in line and re.search(r"(?<![A-Za-z])Sector\s*\(", line):
            fixed_line = re.sub(r"\bouter_radius\s*=", "radius=", line)
            if fixed_line != line:
                fixes += 1
            new_lines.append(fixed_line)
        else:
            new_lines.append(line)
    lines = new_lines

    return "\n".join(lines), fixes
