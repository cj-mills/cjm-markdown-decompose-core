"""Decompose a Markdown body into ordered Section nodes (the navigable unit).

The coarse Note stores only frontmatter/relationships; this is the first time
body CONTENT comes on-graph (increment-4 Scope A). Each ATX heading opens a
Section carrying its VERBATIM immediate prose (the text up to the next heading of
ANY level — subsections are their own nodes, so no text is duplicated up the
hierarchy). Identity = (note, anchor slug); the anchor mirrors the Pandoc/Quarto
auto-identifier so a cross-post `#anchor` link resolves onto the section BY
CONSTRUCTION (the increment-2 Fork-C close). Scope A is faithful at the SECTION
grain — it does not promise whole-file byte-exact round-trip.

The `lossless=True` mode (M1, the high-stakes memory corpus) closes that gap: each
section also stores its heading-INCLUSIVE verbatim `raw` span and the pre-first-
heading text becomes a reserved level-0 preamble Section, so concatenating every
`raw` in order reproduces the body byte-for-byte (paired with the Note's verbatim
`frontmatter_raw`). The fine per-section verbatim regions are the lossless SOURCE;
`text`/`title`/`anchor` remain DERIVED projections (the arc's "verbatim content,
derived structure" principle), so the Scope-A posts path is untouched.
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


# The reserved anchor for the pre-first-heading region (lossless mode only). A
# real heading slugging to this is vanishingly unlikely (leading `_` is atypical);
# if a corpus ever collides, the round-trip harness's byte-exact check is the alarm.
PREAMBLE_ANCHOR = "_preamble"


def decompose_sections(
    body: str,            # The document body (frontmatter already stripped)
    note_id: str,         # The enclosing Note node id
    path: str = "",       # Source file path (provenance locator)
    lossless: bool = False,  # Lossless mode (memory): also store each section's heading-inclusive verbatim `raw` span + a level-0 preamble region, so concatenating every `raw` in order reproduces the body byte-for-byte
) -> List[SectionNode]:  # Ordered Section nodes (document order; preamble first in lossless mode)
    """Decompose a body into ordered `SectionNode`s (heading-delimited).

    Each heading opens a section whose text runs to the next heading of ANY level
    (immediate prose only; subsections are separate nodes). Duplicate anchors are
    disambiguated `-1/-2` in document order (Pandoc's rule). The parent is the
    nearest preceding heading of a SHALLOWER level (the `PART_OF` hierarchy).

    Two modes. **Scope A** (`lossless=False`, the posts corpus): faithful at the
    section grain only — `text` excludes the heading line and preamble before the
    first heading is dropped (the Note's description carries the lede); no
    whole-file round-trip promised. **Lossless** (`lossless=True`, the high-stakes
    memory corpus): additionally each section carries `raw` = its VERBATIM span
    INCLUDING the heading line (`heading.start` -> next `heading.start`), and the
    text before the first heading becomes a reserved level-0 preamble Section
    (order 0; headed sections shift to order 1+). Then `frontmatter_raw + ''.join(
    s.raw for s in order)` reproduces the file byte-for-byte (M1's content-fidelity
    gate). The `raw`-span slicing is exact regardless of whether a matched `#` is a
    "real" heading (e.g. inside a code fence), so round-trip never depends on the
    heading heuristic being perfect."""
    matches = list(_HEADING_LINE_RE.finditer(body))
    sections: List[SectionNode] = []
    base_order = 0            # headed sections start here (bumped to 1 when a preamble is emitted)
    if lossless:
        preamble_text = body[:matches[0].start()] if matches else body
        if preamble_text:    # an empty preamble (body starts with a heading) needs no node
            sections.append(SectionNode(
                note_id=note_id, anchor=PREAMBLE_ANCHOR, level=0, title="",
                text=preamble_text, raw=preamble_text, order=0, parent_anchor=None,
                path=path, content_hash=SourceRef.compute_hash(preamble_text.encode("utf-8"))))
            base_order = 1
    seen = {}                 # base anchor -> occurrence count (for -1/-2 disambiguation)
    stack: List = []          # (level, anchor) of open ancestors, for parent resolution
    for i, m in enumerate(matches):
        level = len(m.group(1))
        title = m.group(2).strip()
        base = heading_anchor(title)
        n = seen.get(base, 0)
        seen[base] = n + 1
        anchor = base if n == 0 else f"{base}-{n}"
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        text = body[m.end():end]
        raw = body[m.start():end] if lossless else ""
        while stack and stack[-1][0] >= level:
            stack.pop()
        parent_anchor = stack[-1][1] if stack else None
        stack.append((level, anchor))
        sections.append(SectionNode(
            note_id=note_id, anchor=anchor, level=level, title=title, text=text,
            order=base_order + i, parent_anchor=parent_anchor, path=path, raw=raw,
            content_hash=SourceRef.compute_hash((raw or text).encode("utf-8"))))
    return sections
