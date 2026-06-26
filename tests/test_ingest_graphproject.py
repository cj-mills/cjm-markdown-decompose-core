"""Corpus -> graph elements, and projecting the index back from graph nodes."""

from cjm_dev_graph_schema.identity import (note_node_id, series_node_id,
                                           topic_node_id)
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


def test_alias_map_heals_a_drifted_reference():
    # alpha links [[beta]] (real) and [[gamma]] (dangling). Confirming gamma->beta
    # resolves the once-dangling edge onto beta's real id, file left untouched.
    nodes, edges = corpus_graph_elements(_notes(), aliases={"gamma": "beta"})
    targets = {e["target_id"] for e in edges}
    assert targets == {note_node_id("beta")}  # both refs now land on beta
    assert note_node_id("gamma") not in targets  # the drifted id is gone
    # Without the alias the drifted edge points at the (absent) gamma id.
    _, plain = corpus_graph_elements(_notes())
    assert note_node_id("gamma") in {e["target_id"] for e in plain}


# --- Increment 2: post-corpus facet/relationship dedup (the Gatto-cluster shape) ---

BOOK_A = """---
title: "The Learning Game"
date: 2024-1-1
categories: [education, history]
---
Part of the [Education series](/series/notes/education-notes.html).
See [Dumbing Us Down](/posts/dumbing-us-down-book-notes/).
"""

BOOK_B = """---
title: "Dumbing Us Down"
date: 2024-1-2
categories: [education, history]
---
Part of the [Education series](/series/notes/education-notes.html).
"""


def _books():
    return [note_from_text("/c/posts/the-learning-game-book-notes/index.md", BOOK_A, corpus_root="/c/posts"),
            note_from_text("/c/posts/dumbing-us-down-book-notes/index.md", BOOK_B, corpus_root="/c/posts")]


def test_topic_and_series_nodes_are_deduped_across_notes():
    nodes, edges = corpus_graph_elements(_books())
    labels = [n["label"] for n in nodes]
    # 2 Notes + 2 shared Topics (education, history) + 1 shared Series (deduped).
    assert labels.count(DevNodeKinds.NOTE) == 2
    assert labels.count(DevNodeKinds.TOPIC) == 2
    assert labels.count(DevNodeKinds.SERIES) == 1
    topic_ids = {n["id"] for n in nodes if n["label"] == DevNodeKinds.TOPIC}
    assert topic_ids == {topic_node_id("education"), topic_node_id("history")}


def test_both_books_converge_on_shared_facets():
    _, edges = corpus_graph_elements(_books())
    tagged = [e for e in edges if e["relation_type"] == DevRelations.TAGGED]
    in_series = [e for e in edges if e["relation_type"] == DevRelations.IN_SERIES]
    # Both books TAGGED education+history (4 edges) and IN_SERIES the one series (2 edges).
    assert len(tagged) == 4 and len(in_series) == 2
    assert {e["target_id"] for e in in_series} == {series_node_id("education-notes")}
    # The cross-post link (learning-game -> dumbing-us-down) is a REFERENCES edge.
    refs = [e for e in edges if e["relation_type"] == DevRelations.REFERENCES]
    assert any(e["target_id"] == note_node_id("dumbing-us-down-book-notes")
               and e["properties"].get("cross_post") for e in refs)


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
