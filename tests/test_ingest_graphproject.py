"""Corpus -> graph elements, and projecting the index back from graph nodes."""

from cjm_dev_graph_schema.vocab import DevNodeKinds, DevRelations
from cjm_markdown_decompose_core.extract import note_from_text
from cjm_markdown_decompose_core.ingest import corpus_graph_elements
from cjm_markdown_decompose_core.project import (
    note_view_from_graph_node, render_memory_index, render_memory_index_from_graph_nodes,
)

PROJECT_DOC = """---
name: alpha
description: Alpha note.
metadata:
  type: project
---
Links [[beta]] and [[gamma]].
"""

FEEDBACK_DOC = """---
name: beta
description: Beta note.
metadata:
  type: feedback
---
No links.
"""


def _notes():
    return [note_from_text("memory/alpha.md", PROJECT_DOC),
            note_from_text("memory/beta.md", FEEDBACK_DOC)]


def test_corpus_graph_elements_counts():
    nodes, edges = corpus_graph_elements(_notes())
    assert len(nodes) == 2
    assert all(n["label"] == DevNodeKinds.NOTE for n in nodes)
    # alpha has two [[links]] -> two REFERENCES edges; beta has none.
    assert len(edges) == 2
    assert all(e["relation_type"] == DevRelations.REFERENCES for e in edges)


def test_note_view_from_graph_node_dict():
    node = note_from_text("memory/alpha.md", PROJECT_DOC).to_graph_node()
    view = note_view_from_graph_node(node)
    assert view.title == "Alpha"
    assert view.description == "Alpha note."
    assert view.note_type == "project"
    assert view.path == "memory/alpha.md"


def test_render_from_graph_nodes_matches_direct_render():
    notes = _notes()
    nodes, _ = corpus_graph_elements(notes)
    # Projecting from the (id-bearing) node wire dicts equals rendering the notes.
    assert render_memory_index_from_graph_nodes(nodes) == render_memory_index(notes)
