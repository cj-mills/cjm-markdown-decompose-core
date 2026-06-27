"""Projections from the decomposed content back out to files.

The first projection is the `MEMORY.md` index: one line per note, grouped by
category, with each line derived from the note's own frontmatter (title +
description). This is the self-hosting payoff in miniature — the index becomes a
PROJECTION of a single source of truth (each note) rather than a file edited by
hand. Operates on `NoteNode`s, whether they come straight from `extract` or from
a graph query.
"""

import os
from typing import Any, Dict, Iterable, List, Optional, Tuple

from cjm_dev_graph_schema.nodes import NoteNode, SectionNode

# Default category section order + display headings for the memory index.
DEFAULT_SECTION_ORDER = ("project", "feedback", "reference", "user")
_SECTION_HEADINGS = {
    "project": "Project",
    "feedback": "Feedback",
    "reference": "Reference",
    "user": "User",
}
_UNCATEGORIZED = "Other"


def note_index_line(
    note: NoteNode,  # The note to render
) -> str:  # One Markdown index line: "- [Title](file.md) — description"
    """Render one index line from a note's frontmatter-derived fields."""
    link = os.path.basename(note.path)
    line = f"- [{note.title}]({link})"
    if note.description:
        line += f" — {note.description}"
    return line


def _node_field(
    node: Any,        # A queried graph node (typed GraphNode or wire dict)
    key: str,         # Property name
    default: Any = None,
) -> Any:  # The property value
    """Read one property from a queried node, tolerating GraphNode or wire dict."""
    props = node.properties if hasattr(node, "properties") else node.get("properties", {})
    return props.get(key, default)


def note_view_from_graph_node(
    node: Any,  # A queried `Note` graph node (typed GraphNode or wire dict)
) -> NoteNode:  # An index-relevant NoteNode reconstructed from the graph
    """Reconstruct an index-relevant `NoteNode` from a queried graph node.

    Carries the fields the index needs (title / description / path / note_type);
    `references` are an edge query, not needed for the index, so they are left
    empty. This is what closes the self-hosting loop — the projection reads the
    GRAPH, not the in-memory extraction."""
    return NoteNode(
        slug=_node_field(node, "slug", "") or "",
        title=_node_field(node, "title", "") or "",
        path=_node_field(node, "path", "") or "",
        content_hash="",
        description=_node_field(node, "description", "") or "",
        note_type=_node_field(node, "note_type"),
    )


def render_memory_index_from_graph_nodes(
    nodes: Iterable[Any],  # Queried `Note` graph nodes (typed GraphNode or wire dicts)
    **kwargs: Any,         # Forwarded to render_memory_index (title / section_order / preamble)
) -> str:  # The rendered MEMORY.md text
    """Render the memory index FROM queried graph nodes (the self-hosting path)."""
    return render_memory_index((note_view_from_graph_node(n) for n in nodes), **kwargs)


def render_memory_index(
    notes: Iterable[NoteNode],                 # The notes to index
    title: str = "# Project Memory",           # Top-level document title
    section_order: Iterable[str] = DEFAULT_SECTION_ORDER,  # Category order for sections
    preamble: Optional[str] = None,            # Optional prose inserted under the title
) -> str:  # The rendered MEMORY.md text
    """Render a `MEMORY.md` index: notes grouped by category, one line each.

    Deterministic: notes are bucketed by `note_type`, sections emitted in
    `section_order` (any leftover categories appended alphabetically, then an
    `Other` bucket for notes without a category), and lines within a section
    sorted by title. Same notes in -> same text out (so a regenerate is a clean
    idempotent overwrite)."""
    buckets: Dict[str, List[NoteNode]] = {}
    for n in notes:
        buckets.setdefault(n.note_type or _UNCATEGORIZED, []).append(n)

    ordered = list(section_order)
    leftovers = sorted(k for k in buckets if k not in ordered and k != _UNCATEGORIZED)
    section_keys = [k for k in ordered if k in buckets] + leftovers
    if _UNCATEGORIZED in buckets:
        section_keys.append(_UNCATEGORIZED)

    parts: List[str] = [title]
    if preamble:
        parts.append(preamble.strip())
    for key in section_keys:
        heading = _SECTION_HEADINGS.get(key, key.title())
        lines = [note_index_line(n) for n in sorted(buckets[key], key=lambda n: n.title.lower())]
        parts.append(f"## {heading}\n" + "\n".join(lines))

    return "\n\n".join(parts) + "\n"


# --- Onboarding surface (the MEMORY.md-as-projection reframe) -----------------
#
# A different projection from `render_memory_index`: instead of ENUMERATING every
# note (which pays session budget for mostly task-conditional content), emit a
# radically-minimal resident core + a MAP of how to pull the rest from the graph
# on demand. Domain-neutral: the graph-specific prose (how to query THIS graph,
# the guardrails) is injected by the driver; the core only assembles the structure
# + the coverage map + the terse push-core lines.

_DEFAULT_INTRO = (
    "> Project knowledge lives in a **context graph**, not this file. This is your MAP "
    "+ the few things to know *before* querying. Pull the rest on demand — don't expect "
    "it enumerated here."
)
_DEFAULT_HOW_TO_QUERY = (
    "## How to query\n"
    "Use your read-only graph query tool: `relevant \"<your task>\"` ranks nearby nodes; "
    "`show <id>` drills into one node + its neighbours; `state` is an overview."
)
_DEFAULT_HOW_TO_PULL = (
    "## How to pull\n"
    "1. At task start, run `relevant \"<task>\"` — it ranks by structural nearness "
    "(decisions, notes, code, cross-links), richer than any static list.\n"
    "2. `show <id>` to read a node in full + its neighbours.\n"
    "3. If a landmark above names your area, use its query hint as a starting point.\n"
    "4. Treat what you pull as the live source of truth; this surface is only the map."
)


def first_sentence(
    text: str,         # The full description text
    limit: int = 220,  # Hard character cap when no sentence boundary is found
) -> str:  # A terse one-line hook
    """A deterministic terse hook: the description's first sentence, capped.

    The frontmatter `description` is a full recall-abstract (it feeds relevance, so we
    keep it whole there); the onboarding surface needs a terse navigational hook, so
    take the first sentence (else hard-cap with an ellipsis). Same text in -> same hook."""
    t = " ".join((text or "").split())
    if not t:
        return ""
    best = -1
    for sep in (". ", "; "):
        i = t.find(sep)
        if 0 < i <= limit and (best < 0 or i < best):
            best = i
    if best > 0:
        return t[:best + 1].rstrip()
    return (t[:limit].rstrip() + "…") if len(t) > limit else t


def render_onboarding_surface(
    notes: Iterable[NoteNode],              # All Note nodes (the coverage map + push-core lookup)
    push_slugs: Iterable[str],              # Allowlist of slugs rendered inline as the resident PUSH core
    landmarks: Iterable[Tuple[str, str]],   # (label, query-hint) coverage pointers (NOT an enumeration)
    arc_lead: str,                          # The live arc-lead anchor (one line)
    *,
    title: str = "# Project Memory — Onboarding Surface",  # Document title
    intro: str = _DEFAULT_INTRO,                # Orientation prose under the title
    how_to_query: str = _DEFAULT_HOW_TO_QUERY,  # Graph-specific "how to query" section (driver overrides)
    how_to_pull: str = _DEFAULT_HOW_TO_PULL,    # The pull-discipline section
    push_hooks: Optional[Dict[str, str]] = None,  # slug -> terse COMPLETE hook (else first_sentence fallback)
) -> str:  # The rendered onboarding-surface markdown
    """Render the onboarding surface: orientation + how-to-query + resident PUSH core + landmark map + how-to-pull.

    The push core renders one line per allowlisted slug (title + an explicit terse hook
    — else the description's first sentence — + a `show <id>` pull-hint for the full node,
    the exact-node analogue of a landmark's `relevant` cluster hint); the landmark map
    lists coverage pointers + per-category counts (the territory, not its contents).
    Deterministic for a given (notes, seeds) — a regenerate is a clean idempotent overwrite.
    Graph-specific prose is injected via `how_to_query` so the core stays domain-neutral.

    A push node's `description` is a full recall-abstract that often BURIES the actionable
    point, so truncating it can mislead (e.g. severing "NEVER delete the journal"); the
    explicit `push_hooks` hook is a terse COMPLETE statement — `show <id>` fetches the rest."""
    notes = list(notes)
    by_slug = {n.slug: n for n in notes}
    counts: Dict[str, int] = {}
    for n in notes:
        counts[n.note_type or "other"] = counts.get(n.note_type or "other", 0) + 1
    total = sum(counts.values())

    parts: List[str] = [f"{title}\n\n{intro}", how_to_query]
    hooks = push_hooks or {}
    push_lines: List[str] = []
    for s in push_slugs:
        if s not in by_slug:
            push_lines.append(f"- _(push node not found on-graph: {s})_")
            continue
        n = by_slug[s]
        push_lines.append(f"- **{n.title}** — {hooks.get(s) or first_sentence(n.description)}  ↳ `show {n.id}`")
    parts.append("## Resident core (read me)\n- " + arc_lead + "\n" + "\n".join(push_lines))
    cov = ", ".join(f"{k}:{v}" for k, v in sorted(counts.items()))
    lm = "\n".join(f"- **{label}** → `relevant \"{hint}\"`" for label, hint in landmarks)
    parts.append("## Landmark map — what's on-graph (coverage, not enumeration)\n"
                 f"_~{total} notes ({cov}); query a landmark to pull its cluster:_\n" + lm)
    parts.append(how_to_pull)
    return "\n\n".join(parts) + "\n"


# --- Lossless note round-trip (M1: memory bodies on-graph) --------------------
#
# The inverse of `lossless` decomposition: reassemble a note's exact file text
# from its verbatim parts — the Note's `frontmatter_raw` plus every Section's
# heading-inclusive `raw` span in document order. PURE concatenation, no
# canonical-seam emission (prose derives nothing, unlike code's imports/ordering),
# so the result is byte-for-byte the original file when the note was decomposed
# `lossless=True`. This is M1's content-fidelity gate (file -> graph -> file ==
# file) and the read leg of authoring memory on-graph (M2).

def render_note_text(
    frontmatter_raw: str,             # The note's verbatim frontmatter prefix ("" when none)
    sections: Iterable[SectionNode],  # The note's Section nodes (any order; sorted by `order` here)
) -> str:  # The reconstructed file text
    """Reassemble a note's exact file text from its verbatim parts (lossless mode).

    `frontmatter_raw + ''.join(s.raw for s in sorted-by-order)`. Requires sections
    decomposed `lossless=True` (each carries its heading-inclusive `raw` span, with
    a level-0 preamble at order 0); a Scope-A section set has empty `raw` and will
    NOT round-trip — that is the mode boundary, not a bug."""
    ordered = sorted(sections, key=lambda s: s.order)
    return frontmatter_raw + "".join(s.raw for s in ordered)


def note_text_from_graph_nodes(
    note_node: Any,                # The queried `Note` graph node (typed GraphNode or wire dict)
    section_nodes: Iterable[Any],  # The note's queried `Section` graph nodes
) -> str:  # The reconstructed file text (the self-hosting round-trip path)
    """Reconstruct a note's file text FROM the graph (frontmatter_raw + ordered raw spans).

    Reads `frontmatter_raw` off the Note and each Section's `raw`/`order` off the
    queried nodes — the projection reads the GRAPH, not the in-memory extraction
    (the same loop-closing move as `render_memory_index_from_graph_nodes`)."""
    frontmatter_raw = _node_field(note_node, "frontmatter_raw", "") or ""
    spans = sorted(
        ((int(_node_field(s, "order", 0) or 0), _node_field(s, "raw", "") or "")
         for s in section_nodes),
        key=lambda t: t[0],
    )
    return frontmatter_raw + "".join(raw for _, raw in spans)
