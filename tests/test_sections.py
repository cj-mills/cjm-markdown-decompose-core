"""Body -> ordered Section nodes: anchors, hierarchy, verbatim text, disambiguation."""

from cjm_dev_graph_schema.identity import note_node_id, section_node_id
from cjm_dev_graph_schema.vocab import DevNodeKinds, DevRelations
from cjm_markdown_decompose_core.extract import note_from_text
from cjm_markdown_decompose_core.project import render_note_text
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
