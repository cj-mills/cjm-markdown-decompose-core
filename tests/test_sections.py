"""Body -> ordered Section nodes: anchors, hierarchy, verbatim text, disambiguation."""

from cjm_dev_graph_schema.identity import note_node_id, section_node_id
from cjm_dev_graph_schema.vocab import DevNodeKinds, DevRelations
from cjm_markdown_decompose_core.extract import note_from_text
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
