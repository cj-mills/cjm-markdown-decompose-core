"""Body -> ordered Section nodes: anchors, hierarchy, verbatim text, disambiguation."""

import pytest

from cjm_dev_graph_schema.identity import note_node_id, section_node_id
from cjm_dev_graph_schema.vocab import DevNodeKinds, DevRelations
from cjm_markdown_decompose_core.extract import note_from_text

from cjm_markdown_decompose_core.project import compose_note_text, render_note_text, section_outline
from cjm_markdown_decompose_core.sections import decompose_sections, heading_anchor

DOC = """Preamble prose (not a section in v1).

# Setup

Intro to setup.

## Install

Install steps.

## Configure

Config steps.

# Setup

Duplicate top heading.

# Loading the YOLOX-Tiny Model

Body with a [link](/posts/x/).
"""


def test_heading_anchor_matches_quarto_slug():
    assert heading_anchor("Loading the YOLOX-Tiny Model") == "loading-the-yolox-tiny-model"
    assert heading_anchor("Using Hardware Acceleration") == "using-hardware-acceleration"
    assert heading_anchor("  Spaced  &  Punctuated!  ") == "spaced-punctuated"
    assert heading_anchor("###") == "section"  # empty -> fallback


def test_decompose_sections_order_levels_hierarchy():
    nid = note_node_id("p")
    secs = decompose_sections(DOC, nid)
    # 5 headings (preamble is not a section).
    assert [s.anchor for s in secs] == ["setup", "install", "configure", "setup-1",
                                        "loading-the-yolox-tiny-model"]
    assert [s.level for s in secs] == [1, 2, 2, 1, 1]
    assert [s.order for s in secs] == [0, 1, 2, 3, 4]
    # Hierarchy: install/configure nest under the first setup; top-level headings have no parent.
    by_anchor = {s.anchor: s for s in secs}
    assert by_anchor["install"].parent_anchor == "setup"
    assert by_anchor["configure"].parent_anchor == "setup"
    assert by_anchor["setup"].parent_anchor is None
    assert by_anchor["loading-the-yolox-tiny-model"].parent_anchor is None


def test_section_text_is_verbatim_immediate_prose():
    secs = decompose_sections(DOC, note_node_id("p"))
    by_anchor = {s.anchor: s for s in secs}
    # The first `setup` owns only its intro prose, NOT its subsections' text.
    assert "Intro to setup." in by_anchor["setup"].text
    assert "Install steps." not in by_anchor["setup"].text
    assert "Install steps." in by_anchor["install"].text


def test_fenced_code_comment_does_not_open_a_section():
    # c1b976d0: a `# comment` inside a ```python fence used to open a Section
    # mid-code, so the enclosing section's text ended with a stray opening fence
    # and the phantom section began with code and a stray closing fence.
    body = ("# Training\n\nDefine the loop.\n\n"
            "```python\n# Function to run a single training/validation epoch\n"
            "def run_epoch():\n    pass\n```\n\n"
            "# Evaluation\n\nEval prose.\n")
    secs = decompose_sections(body, note_node_id("p"))
    assert [s.anchor for s in secs] == ["training", "evaluation"]
    training = secs[0].text
    assert "```python\n# Function to run" in training and training.count("```") == 2
    # Lossless mode still round-trips byte-exact with the fence-aware boundaries.
    lossless = decompose_sections(body, note_node_id("p"), lossless=True)
    assert "".join(s.raw for s in lossless) == body
    assert [s.anchor for s in lossless] == ["training", "evaluation"]


def test_display_math_heading_is_source_faithful():
    # c1b976d0 part (2) is NOT a splitter defect: the transformers-book ch. 6 post
    # literally writes `### $$BR = ...$$` as its heading, so a math-bearing title is
    # the author's markdown, kept verbatim (the anchor slugs it like any heading).
    body = "### $$BR = min(1, e^{x})$$\n* bullet\n"
    secs = decompose_sections(body, note_node_id("p"))
    assert [s.title for s in secs] == ["$$BR = min(1, e^{x})$$"]
    assert secs[0].level == 3 and secs[0].text == "\n* bullet\n"


def test_duplicate_heading_anchor_disambiguated():
    secs = decompose_sections(DOC, note_node_id("p"))
    anchors = [s.anchor for s in secs]
    assert anchors.count("setup") == 1 and "setup-1" in anchors  # second `# Setup` -> setup-1


def test_note_from_text_with_sections_emits_section_nodes():
    note = note_from_text("/c/posts/p/index.md", "# A\n\nx\n\n## B\n\ny\n",
                          corpus_root="/c/posts", with_sections=True)
    assert [s.anchor for s in note.sections] == ["a", "b"]
    # Section id is deterministic from (note, anchor) — the anchor-resolution target.
    assert note.sections[0].id == section_node_id(note.id, "a")
    # Without the flag (the memory/dev default), no sections.
    assert note_from_text("/c/posts/p/index.md", "# A\n\nx\n").sections == []


def test_structural_edges_membership_and_hierarchy():
    note = note_from_text("/c/posts/p/index.md", "# A\n\nx\n\n## B\n\ny\n",
                          corpus_root="/c/posts", with_sections=True)
    b = note.sections[1]
    rels = {e["relation_type"] for e in b.structural_edges()}
    assert DevRelations.HAS_SECTION in rels and "PART_OF" in rels


# --- Lossless mode (M1: byte-exact memory body round-trip) --------------------

def test_scope_a_carries_no_raw():
    # Default (posts) mode leaves `raw` empty — the lossless source is opt-in.
    secs = decompose_sections(DOC, note_node_id("p"))
    assert all(s.raw == "" for s in secs)


def test_lossless_preamble_is_level0_order0_node():
    secs = decompose_sections(DOC, note_node_id("p"), lossless=True)
    # Preamble becomes a reserved level-0 section at order 0; headed sections shift to 1+.
    assert secs[0].anchor == "_preamble" and secs[0].level == 0 and secs[0].order == 0
    assert "Preamble prose" in secs[0].text
    assert [s.anchor for s in secs[1:]] == ["setup", "install", "configure", "setup-1",
                                            "loading-the-yolox-tiny-model"]
    assert [s.order for s in secs] == [0, 1, 2, 3, 4, 5]


def test_lossless_raw_spans_reconstruct_body_byte_exact():
    secs = decompose_sections(DOC, note_node_id("p"), lossless=True)
    # Concatenating every heading-inclusive `raw` span in order reproduces the body.
    assert "".join(s.raw for s in sorted(secs, key=lambda s: s.order)) == DOC
    # Each headed section's raw INCLUDES its heading line (unlike `text`).
    setup = next(s for s in secs if s.anchor == "setup")
    assert setup.raw.startswith("# Setup") and "# Setup" not in setup.text


def test_lossless_body_starting_with_heading_has_no_preamble_node():
    body = "# A\n\nx\n\n## B\n\ny\n"
    secs = decompose_sections(body, note_node_id("p"), lossless=True)
    assert [s.anchor for s in secs] == ["a", "b"]  # no preamble node when preamble is empty
    assert "".join(s.raw for s in secs) == body


def test_lossless_no_headings_is_one_preamble_node():
    body = "Just prose, no headings.\n"
    secs = decompose_sections(body, note_node_id("p"), lossless=True)
    assert len(secs) == 1 and secs[0].anchor == "_preamble" and secs[0].raw == body


def test_note_from_text_lossless_round_trip_and_frontmatter_raw():
    text = ("---\nname: m\ndescription: \"q: a, b\"\nmetadata:\n  type: project\n---\n\n"
            "Lede before any heading.\n\n# Plan\n\nDo the thing.\n")
    note = note_from_text("/mem/m.md", text, lossless=True)
    # The verbatim frontmatter prefix is captured (parsed fields are derived projections).
    # The FM regex consumes the closing fence + one newline; the blank line is body.
    assert note.frontmatter_raw.startswith("---\nname: m") and note.frontmatter_raw.endswith("---\n")
    assert render_note_text(note.frontmatter_raw, note.sections) == text
    # Lossless implies sectioning; Scope-A default still leaves frontmatter_raw empty.
    assert note_from_text("/mem/m.md", text).frontmatter_raw == ""


def test_sections_name_their_next_sibling_under_the_same_parent():
    secs = {s.anchor: s for s in decompose_sections(DOC, note_node_id("p"), lossless=True)}
    # Top-level siblings (the preamble included) chain in document order; children chain under their parent.
    assert [secs[a].next_anchor for a in ("_preamble", "setup", "setup-1")] == [
        "setup", "setup-1", "loading-the-yolox-tiny-model"]
    assert secs["install"].next_anchor == "configure" and secs["configure"].next_anchor is None
    assert secs["loading-the-yolox-tiny-model"].next_anchor is None
    # The NEXT edge rides structural_edges beside HAS_SECTION / PART_OF.
    nxt = [e for e in secs["install"].structural_edges() if e["relation_type"] == "NEXT"]
    assert [(e["source_id"], e["target_id"]) for e in nxt] == [
        (secs["install"].id, section_node_id(note_node_id("p"), "configure"))]


def test_composed_note_reproduces_a_canonical_post():
    # A canonical post: frontmatter, a preamble, a derived series callout, a tabset whose tab
    # headings stay inside their Section, nesting to H4 -- composed from state + relations.
    text = ("---\ntitle: P\n---\n\nLede.\n\n"
            "::: {.callout-tip}\n## This post is part of the following series:\n"
            "* [**The Series**](/series/tutorials/the-series.html): My notes.\n:::\n\n"
            "## Setup\n\nPick one.\n\n::: {.panel-tabset}\n### Mamba\n\nmamba x\n\n### Conda\n\nconda x\n:::\n\n"
            "### Install\n\nSteps.\n\n#### Detail\n\nMore.\n\n## Conclusion\n\nDone.\n")
    note = note_from_text("/c/posts/p/index.md", text, corpus_root="/c/posts",
                          profile="quarto_post", lossless=True)
    parent, following = section_outline(note.sections)
    assert compose_note_text(note.frontmatter_raw, note.sections, parent, following) == text


def test_composition_derives_heading_level_from_depth():
    # Level is presentation (design 56c9c332 (4)): a skipped level closes up, the top level
    # renders at H2, and heading-line whitespace takes the composed form.
    text = "### A  \n\nx\n\n#####  B\n\ny\n\n### C\n\nz\n"
    note = note_from_text("/c/posts/p/index.md", text, corpus_root="/c/posts",
                          profile="quarto_post", lossless=True)
    parent, following = section_outline(note.sections)
    assert compose_note_text("", note.sections, parent, following) == (
        "## A\n\nx\n\n### B\n\ny\n\n## C\n\nz\n")
    assert compose_note_text("", note.sections, parent, following, top_level=1).startswith("# A\n")


def test_composition_follows_the_relations_not_the_stored_order():
    note = note_from_text("/c/posts/p/index.md", "## A\n\na\n\n## B\n\nb\n\n## C\n\nc\n",
                          corpus_root="/c/posts", profile="quarto_post", lossless=True)
    a, b, c = (s.id for s in note.sections)
    # Reorder by re-pointing NEXT (C first), and re-parent B under C: one relation edit each.
    assert compose_note_text("", note.sections, {b: c}, {c: a}) == "## C\n\nc\n\n### B\n\nb\n\n## A\n\na\n"


def test_malformed_outline_refuses_rather_than_reordering():
    note = note_from_text("/c/posts/p/index.md", "## A\n\na\n\n## B\n\nb\n",
                          corpus_root="/c/posts", profile="quarto_post", lossless=True)
    a, b = (s.id for s in note.sections)
    for following in ({}, {a: b, b: a}):  # two first siblings; a cycle with no first
        with pytest.raises(ValueError, match="outline"):
            compose_note_text("", note.sections, {}, following)


def test_composition_reads_graph_wires_alike():
    # The projection composes from queried nodes: the Section wire's id + title / text / level.
    note = note_from_text("/c/posts/p/index.md", "Lede.\n\n## A\n\na\n\n### B\n\nb\n",
                          corpus_root="/c/posts", profile="quarto_post", lossless=True)
    parent, following = section_outline(note.sections)
    wires = [s.to_graph_node() for s in reversed(note.sections)]  # any input order
    assert compose_note_text("", wires, parent, following) == "Lede.\n\n## A\n\na\n\n### B\n\nb\n"


def test_composition_owns_the_separators_between_elements():
    # Blank-line runs and a heading glued to its body are layout, not content: the composed form
    # puts one blank line after the frontmatter and between elements. Whole blank lines only --
    # a last content line keeps its trailing spaces (an empty list item `* ` is not `*`).
    text = "---\ntitle: P\n---\nLede. \n\n\n\n## A\nx\n\n\n## B  \n\n\n* \n  \n\n"
    note = note_from_text("/c/posts/p/index.md", text, corpus_root="/c/posts",
                          profile="quarto_post", lossless=True)
    composed = compose_note_text(note.frontmatter_raw, note.sections, *section_outline(note.sections))
    assert composed == "---\ntitle: P\n---\n\nLede. \n\n## A\n\nx\n\n## B\n\n* \n"
    again = note_from_text("/c/posts/p/index.md", composed, corpus_root="/c/posts",
                           profile="quarto_post", lossless=True)
    assert compose_note_text(again.frontmatter_raw, again.sections,
                             *section_outline(again.sections)) == composed  # a fixpoint
    assert {s.id for s in again.sections} == {s.id for s in note.sections}


def test_a_heading_line_an_open_block_absorbs_is_no_section():
    # Pandoc's blank_before_header (Quarto keeps it on): an ATX line right after a line that leaves
    # a paragraph open is that paragraph's text, and right after an EMPTY list item it is the
    # item's content (`<li><h3>`). After a blank line, a heading or a fence it is a heading.
    body = ("## A\n\n* item text:\n### $$x = y$$\n\nprose\n#### Glued\n\n* \n### In the item\n\n"
            "::: {.callout-note}\n## Callout title\n:::\n\n## B\n### Under B\n")
    secs = decompose_sections(body, note_node_id("p"), lossless=True, blank_before_heading=True)
    assert [s.anchor for s in secs] == ["a", "callout-title", "b", "under-b"]
    assert all(h in secs[0].text for h in ("### $$x = y$$", "#### Glued", "### In the item"))
    # A corpus no Pandoc reader renders (the memory notes) keeps every ATX line a heading.
    plain = decompose_sections(body, note_node_id("p"), lossless=True)
    assert [s.anchor for s in plain] == ["a", "x-y", "glued", "in-the-item", "callout-title", "b", "under-b"]
    # A post's profile switches it on.
    post = note_from_text("/c/posts/p/index.md", body, corpus_root="/c/posts", profile="quarto_post", lossless=True)
    assert "glued" not in {s.anchor for s in post.sections}
