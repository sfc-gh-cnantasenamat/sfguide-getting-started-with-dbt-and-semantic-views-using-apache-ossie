"""Render workflow-diagram.png for the guide.

Run from the assets folder:  python3 workflow_diagram.py
"""

import math

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from matplotlib.transforms import Bbox

# Object type -> (fill, edge). Add types as needed; the legend shows only types used.
STYLE = {
    "Snowsight SQL Step":    ("#E1F5FE", "#0288D1"),
    "Local Setup Step":      ("#C8E6C9", "#388E3C"),
    "dbt CLI Step":          ("#F8BBD0", "#C2185B"),
    "Apache Ossie Artifact": ("#FFE0B2", "#F57C00"),
    "Snowflake Object":      ("#D1C4E9", "#5E35B1"),
}

PAD_PX = 28     # padding between text and box border, equal on all four sides
GAP_PX = 6      # gap between title and subtitle
LABEL_CLEAR_PX = 6  # minimum gap between an edge label and any box

# key: (x, y, type, title, subtitle)
NODES = {
    "step1":      (2.4, 6.2, "Snowsight SQL Step", "1. PREPARE SCHEMA", "CREATE DATABASE & SCHEMA\nANALYTICS.DEMO in Snowsight"),
    "step2":      (2.4, 2.4, "Local Setup Step", "2. SCAFFOLD & CONFIGURE", "Create dbt-ossie-demo files,\ninstall dbt 1.12 & export env vars"),
    "step3":      (8.2, 4.3, "dbt CLI Step", "3. RUN DBT BUILD", "dbt build --profiles-dir .\nBuilds models & parses semantics"),
    "out_tables": (14.2, 6.2, "Snowflake Object", "STAR SCHEMA TABLES", "4 staging views & 4 mart tables\nmaterialized in ANALYTICS.DEMO"),
    "out_ossie":  (14.2, 2.4, "Apache Ossie Artifact", "OSI_DOCUMENT.JSON", "Ossie 0.1.1 semantic document\nin target/osi_document.json"),
    "step4":      (20.0, 2.4, "dbt CLI Step", "4. PUBLISH SEMANTIC VIEW", "dbt run-operation publish_semantic_view\nStages JSON & calls Ossie loader"),
    "sv_obj":     (25.4, 2.4, "Snowflake Object", "SV_ORDERS", "Published Semantic View\nin ANALYTICS.DEMO"),
    "step5":      (25.4, 6.2, "Snowsight SQL Step", "5. QUERY WITH AGG()", "SELECT brand, AGG(total_revenue)...\nFROM analytics.demo.sv_orders"),
}

# (src, dst, label, color, dashed, rad)
EDGES = [
    ("step1", "step3", "Target schema\nready", "#0288D1", False, 0.0),
    ("step2", "step3", "Project & venv\nready", "#388E3C", False, 0.0),
    ("step3", "out_tables", "Materializes\n8 models", "#C2185B", False, 0.0),
    ("step3", "out_ossie", "Emits Ossie\n0.1.1 JSON", "#F57C00", False, 0.0),
    ("out_ossie", "step4", "Reads JSON", "#F57C00", False, 0.0),
    ("step4", "sv_obj", "CREATE\nSEMANTIC VIEW", "#C2185B", False, 0.0),
    ("sv_obj", "step5", "Exposes 4\nmetrics", "#5E35B1", False, 0.0),
    ("step5", "out_tables", "Resolves joins & metrics in SQL", "#0288D1", True, 0.0),
]

fig, ax = plt.subplots(figsize=(21.5, 6.8), dpi=160)
ax.set_xlim(0.1, 27.8)
ax.set_ylim(1.4, 7.2)
ax.axis("off")
renderer = fig.canvas.get_renderer()
to_data = ax.transData.inverted()


def px_to_data(dx, dy):
    """Convert a pixel offset to a data-coordinate offset."""
    (x0, y0), (x1, y1) = to_data.transform([(0, 0), (dx, dy)])
    return x1 - x0, y1 - y0


# Draw text first, then size each box to its text with equal pixel padding.
boxes = {}  # key -> Bbox in data coords
for key, (x, y, kind, title, sub) in NODES.items():
    t = ax.text(x, y, title, ha="center", va="bottom", fontsize=9,
                fontweight="bold", color="#212121", zorder=4)
    s = ax.text(x, y, sub, ha="center", va="top", fontsize=7.5,
                color="#424242", zorder=4, linespacing=1.15, multialignment="center")
    tb, sb = t.get_window_extent(renderer), s.get_window_extent(renderer)
    # Stack title above subtitle around (x, y), then re-centre the pair vertically.
    total = tb.height + GAP_PX + sb.height
    _, cy = ax.transData.transform((x, y))
    top = cy + total / 2
    t.set_position((x, to_data.transform((0, top - tb.height))[1]))
    s.set_position((x, to_data.transform((0, top - tb.height - GAP_PX))[1]))
    bb = Bbox.union([t.get_window_extent(renderer), s.get_window_extent(renderer)])
    bb = Bbox.from_extents(bb.x0 - PAD_PX, bb.y0 - PAD_PX, bb.x1 + PAD_PX, bb.y1 + PAD_PX)
    boxes[key] = Bbox(to_data.transform(bb.get_points()))
    fill, edge = STYLE[kind]
    b = boxes[key]
    ax.add_patch(FancyBboxPatch((b.x0, b.y0), b.width, b.height,
                                boxstyle="square,pad=0",
                                fc=fill, ec=edge, lw=2, zorder=3))


def border_point(key, toward):
    """Point on the box border of `key` in the direction of `toward`."""
    b = boxes[key]
    x, y = (b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2
    dx, dy = toward[0] - x, toward[1] - y
    sx = (b.width / 2) / abs(dx) if dx else float("inf")
    sy = (b.height / 2) / abs(dy) if dy else float("inf")
    s = min(sx, sy)
    return x + dx * s, y + dy * s


def center(key):
    b = boxes[key]
    return (b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2



LABEL_GAP_PX = 7  # gap between a label and its own arrow
LINE_CLEAR_PX = LABEL_GAP_PX  # same gap from every other line


def rect_poly(b, pad=0):
    """Display-space corners of a data Bbox, grown by `pad` pixels."""
    (x0, y0), (x1, y1) = ax.transData.transform(b.get_points())
    return [(x0 - pad, y0 - pad), (x1 + pad, y0 - pad), (x1 + pad, y1 + pad), (x0 - pad, y1 + pad)]


def polys_overlap(a, b):
    """Separating-axis test for two convex polygons."""
    for poly in (a, b):
        for i in range(len(poly)):
            (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
            nx, ny = y1 - y2, x2 - x1
            pa = [nx * x + ny * y for x, y in a]
            pb = [nx * x + ny * y for x, y in b]
            if max(pa) < min(pb) or max(pb) < min(pa):
                return False
    return True


box_polys = [rect_poly(b, LABEL_CLEAR_PX) for b in boxes.values()]
placed = []  # rotated outlines of labels already placed


def bezier(P0, P1, P2, t):
    """Point and tangent of a quadratic Bezier at t (display coords)."""
    pt = tuple((1 - t) ** 2 * a + 2 * (1 - t) * t * b + t ** 2 * c for a, b, c in zip(P0, P1, P2))
    tan = tuple(2 * (1 - t) * (b - a) + 2 * t * (c - b) for a, b, c in zip(P0, P1, P2))
    return pt, tan


# Pass 1: draw every arrow and record its path, so labels can avoid all lines.
paths = []  # (D1, C, D2, segments) in display coords
for src, dst, label, color, dashed, rad in EDGES:
    p1, p2 = border_point(src, center(dst)), border_point(dst, center(src))
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=14,
                                 color=color, lw=1.6, ls="--" if dashed else "-",
                                 connectionstyle=f"arc3,rad={rad}",
                                 shrinkA=4, shrinkB=4, zorder=2))
    # Same control point matplotlib's arc3 uses, so labels follow curved edges too.
    D1, D2 = ax.transData.transform(p1), ax.transData.transform(p2)
    dx, dy = D2[0] - D1[0], D2[1] - D1[1]
    C = ((D1[0] + D2[0]) / 2 + rad * dy, (D1[1] + D2[1]) / 2 - rad * dx)
    pts = [bezier(D1, C, D2, i / 30)[0] for i in range(31)]
    paths.append((D1, C, D2, list(zip(pts, pts[1:]))))

all_segments = [(i, seg) for i, (*_, segs) in enumerate(paths) for seg in segs]

# Pass 2: place each label clear of boxes, other labels, and every line.
for idx, ((src, dst, label, color, dashed, rad), (D1, C, D2, _)) in enumerate(zip(EDGES, paths)):
    txt = ax.text(0, 0, label, ha="center", va="bottom", fontsize=7.5, color=color,
                  zorder=5, linespacing=1.1, multialignment="center",
                  rotation_mode="anchor")
    ext = txt.get_window_extent(renderer)
    w, h = ext.width, ext.height
    # The text box includes room for descenders below the baseline, which reads as
    # extra gap when the label sits above its line. Add it to labels below so the
    # visible gap is the same on both sides.
    txt.set_va("baseline")
    descent = ext.y1 - txt.get_window_extent(renderer).y1
    txt.set_va("bottom")

    def outline_at(t, side, pad):
        """Rotated label outline beside the edge at t; side=+1 above, -1 below."""
        (px, py), (tx, ty) = bezier(D1, C, D2, t)
        ang = math.degrees(math.atan2(ty, tx))
        if ang > 90:
            ang -= 180
        elif ang <= -90:
            ang += 180
        a = math.radians(ang)
        ux, uy = math.cos(a), math.sin(a)
        nx, ny = -math.sin(a) * side, math.cos(a) * side
        gap = LABEL_GAP_PX + (descent if side < 0 else 0)
        bx, by = px + nx * gap, py + ny * gap
        poly = [(bx + ux * sx * (w / 2 + pad) + nx * (sy * (h + 2 * pad) - pad),
                 by + uy * sx * (w / 2 + pad) + ny * (sy * (h + 2 * pad) - pad))
                for sx, sy in ((-1, 0), (1, 0), (1, 1), (-1, 1))]
        return poly, (bx, by), ang

    candidates = sorted(((i / 40, side) for i in range(4, 37) for side in (1, -1)),
                        key=lambda c: (abs(c[0] - 0.5), -c[1]))
    for t, side in candidates:
        test, anchor, ang = outline_at(t, side, LINE_CLEAR_PX)
        if (not any(polys_overlap(test, p) for p in box_polys)
                and not any(polys_overlap(test, p) for p in placed)
                and not any(polys_overlap(test, list(s)) for i, s in all_segments if i != idx)):
            break
    else:
        print(f"warning: label {label!r} could not be placed cleanly")
    txt.set_position(to_data.transform(anchor))
    txt.set_rotation(ang)
    txt.set_va("bottom" if side > 0 else "top")
    # Store a grown outline so neighbouring labels keep a visible gap.
    placed.append(outline_at(t, side, LABEL_CLEAR_PX)[0])

handles = [Line2D([], [], marker="s", ls="", markersize=11, markerfacecolor=f,
                  markeredgecolor=e, markeredgewidth=1.8, label=k)
           for k, (f, e) in STYLE.items() if k in {n[2] for n in NODES.values()}]
ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.04), ncol=len(handles),
          frameon=False, fontsize=8.5, handletextpad=0.4, columnspacing=1.4)

fig.savefig("workflow-diagram.png", dpi=160, facecolor="white",
            bbox_inches="tight", pad_inches=0.2)
