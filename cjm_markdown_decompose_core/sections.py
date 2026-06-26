"""Decompose a Markdown body into ordered Section nodes (the navigable unit).

The coarse Note stores only frontmatter/relationships; this is the first time
body CONTENT comes on-graph (increment-4 Scope A). Each ATX heading opens a
Section carrying its VERBATIM immediate prose (the text up to the next heading of
ANY level — subsections are their own nodes, so no text is duplicated up the
hierarchy). Identity = (note, anchor slug); the anchor mirrors the Pandoc/Quarto
auto-identifier so a cross-post `#anchor` link resolves onto the section BY
CONSTRUCTION (the increment-2 Fork-C close). Scope A is faithful at the SECTION
grain — it does not yet promise whole-file byte-exact round-trip.
"""

import re
from typing import List

from cjm_context_graph_primitives.provenance import SourceRef
from cjm_dev_graph_schema.nodes import SectionNode

# An ATX heading line: 1-6 `#`, the text, optional trailing `#`s (captured with
# positions so the section body can be sliced between consecutive headings).
_HEADING_LINE_RE = re.compile(r"(?m)^(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$")


def heading_anchor(
    text: str,  # The heading text
) -> str:  # The slug anchor (Pandoc/Quarto auto-identifier, pre-disambiguation)
    """Slugify a heading to its anchor — the Pandoc/Quarto auto-identifier shape.

    Lowercase; drop everything except word chars / whitespace / `.` / `-`; spaces
    to hyphens; collapse repeats. `## Loading the YOLOX-Tiny Model` ->
    `loading-the-yolox-tiny-model` — the SAME slug the corpus's cross-post
    `#anchor` links carry, so anchored references resolve by construction. (Leading
    digits are kept — modern SSGs don't strip them; if a corpus disagrees the
    resolution rate is the signal to tune this one function.)"""
    s = text.strip().lower()
    s = re.sub(r"[^\w\s.-]", "", s)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "section"


def decompose_sections(
    body: str,            # The document body (frontmatter already stripped)
    note_id: str,         # The enclosing Note node id
    path: str = "",       # Source file path (provenance locator)
) -> List[SectionNode]:  # Ordered Section nodes (document order)
    """Decompose a body into ordered `SectionNode`s (heading-delimited).

    Each heading opens a section whose text runs to the next heading of ANY level
    (immediate prose only; subsections are separate nodes). Duplicate anchors are
    disambiguated `-1/-2` in document order (Pandoc's rule). The parent is the
    nearest preceding heading of a SHALLOWER level (the `PART_OF` hierarchy);
    preamble before the first heading is not a section in v1 (the Note's
    description already carries the lede)."""
    matches = list(_HEADING_LINE_RE.finditer(body))
    sections: List[SectionNode] = []
    seen = {}                 # base anchor -> occurrence count (for -1/-2 disambiguation)
    stack: List = []          # (level, anchor) of open ancestors, for parent resolution
    for i, m in enumerate(matches):
        level = len(m.group(1))
        title = m.group(2).strip()
        base = heading_anchor(title)
        n = seen.get(base, 0)
        seen[base] = n + 1
        anchor = base if n == 0 else f"{base}-{n}"
        text = body[m.end():matches[i + 1].start() if i + 1 < len(matches) else len(body)]
        while stack and stack[-1][0] >= level:
            stack.pop()
        parent_anchor = stack[-1][1] if stack else None
        stack.append((level, anchor))
        sections.append(SectionNode(
            note_id=note_id, anchor=anchor, level=level, title=title, text=text,
            order=i, parent_anchor=parent_anchor, path=path,
            content_hash=SourceRef.compute_hash(text.encode("utf-8"))))
    return sections
