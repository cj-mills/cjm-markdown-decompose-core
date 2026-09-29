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
from typing import List, Sequence

from cjm_context_graph_primitives.provenance import SourceRef
from cjm_dev_graph_schema.nodes import SectionNode

from .blocks import DerivedBlock
from .parse import find_headings


# Heading detection lives in `parse.find_headings` (fence-aware, positions kept so
# the section body can be sliced between consecutive headings).


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

# The separator of a CONTINUATION section's anchor, `<region anchor>~<n>`: content that
# resumes a region a derived block interrupted (design 253ac996). `heading_anchor` strips
# `~`, so no heading can collide with it.
CONTINUATION_SEP = "~"


def decompose_sections(
    body: str,            # The document body (frontmatter already stripped)
    note_id: str,         # The enclosing Note node id
    path: str = "",       # Source file path (provenance locator)
    lossless: bool = False,  # Lossless mode (memory): also store each section's heading-inclusive verbatim `raw` span + a level-0 preamble region, so concatenating every `raw` in order reproduces the body byte-for-byte
    blocks: Sequence[DerivedBlock] = (),  # The body's DERIVED blocks (`blocks.derived_blocks`): each becomes its own typed section, and a heading inside one opens nothing
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
    "real" heading, so round-trip never depends on the heading heuristic being
    perfect. Headings come from `parse.find_headings`, which SKIPS fenced code: a
    `# comment` inside a ```python block never opens a section (finding c1b976d0).

    DERIVED BLOCKS (design 253ac996): each block in `blocks` is cut out as its own
    level-0 section — anchor `_<role>` (`-1/-2` on a repeat), `block_role` set, parent the
    enclosing heading's section — and a heading inside it opens nothing (the series
    callout's `##` title). The first content after a block in the pre-heading region is
    the preamble; content RESUMING a region the block interrupted is a continuation
    section `<region anchor>~<n>` (level 0, parent the region's heading), so the `raw`
    spans still concatenate to the body byte-for-byte. A body with no blocks decomposes
    exactly as before."""
    spans = [(b.start, b.end) for b in blocks]
    matches = [m for m in find_headings(body) if not any(s <= m.start() < e for s, e in spans)]
    heads = {m.start(): m for m in matches}
    starts = {b.start: b for b in blocks}
    cuts = sorted({0, len(body)} | set(heads) | {p for s in spans for p in s})
    sections: List[SectionNode] = []
    seen = {}                 # base anchor -> occurrence count (for -1/-2 disambiguation)
    roles_seen = {}           # block role -> occurrence count
    stack: List = []          # (level, anchor) of open ancestors, for parent resolution
    region = None             # the current region's head anchor (None before any content)
    resumed = 0               # continuation count within the region

    def emit(anchor, level, title, text, span, parent, role=""):
        raw = span if lossless else ""
        sections.append(SectionNode(
            note_id=note_id, anchor=anchor, level=level, title=title, text=text,
            order=len(sections), parent_anchor=parent, path=path, raw=raw, block_role=role,
            content_hash=SourceRef.compute_hash((raw or text).encode("utf-8"))))

    for a, z in zip(cuts, cuts[1:]):
        if a == z:
            continue
        span = body[a:z]
        enclosing = stack[-1][1] if stack else None
        if a in starts:
            role = starts[a].role
            n = roles_seen.get(role, 0)
            roles_seen[role] = n + 1
            emit(f"_{role}" if n == 0 else f"_{role}-{n}", 0, "", span, span, enclosing, role)
        elif a in heads:
            m = heads[a]
            level = len(m.group(1))
            title = m.group(2).strip()
            base = heading_anchor(title)
            n = seen.get(base, 0)
            seen[base] = n + 1
            anchor = base if n == 0 else f"{base}-{n}"
            while stack and stack[-1][0] >= level:
                stack.pop()
            parent_anchor = stack[-1][1] if stack else None
            stack.append((level, anchor))
            emit(anchor, level, title, body[m.end():z], span, parent_anchor)
            region, resumed = anchor, 0
        elif region is None:  # the pre-heading region's first content: the preamble
            if lossless:
                emit(PREAMBLE_ANCHOR, 0, "", span, span, None)
            region, resumed = PREAMBLE_ANCHOR, 0
        elif region != PREAMBLE_ANCHOR or lossless:  # content resuming a region a block interrupted
            resumed += 1
            emit(f"{region}{CONTINUATION_SEP}{resumed}", 0, "", span, span, enclosing)
    return sections
