"""Projections from the decomposed content back out to files.

The first projection is the `MEMORY.md` index: one line per note, grouped by
category, with each line derived from the note's own frontmatter (title +
description). This is the self-hosting payoff in miniature — the index becomes a
PROJECTION of a single source of truth (each note) rather than a file edited by
hand. Operates on `NoteNode`s, whether they come straight from `extract` or from
a graph query.
"""

import os
from typing import Dict, Iterable, List, Optional

from cjm_dev_graph_schema.nodes import NoteNode

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
