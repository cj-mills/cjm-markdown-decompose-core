"""Extract markdown -> NoteNode and project notes -> MEMORY.md index (with idempotency)."""

from cjm_dev_graph_schema.identity import note_node_id
from cjm_markdown_decompose_core.extract import note_from_text
from cjm_markdown_decompose_core.project import note_index_line, render_memory_index

PROJECT_DOC = """---
name: self-hosting-graph-arc
description: The dogfood arc.
metadata:
  type: project
---
Links [[current-arc-status]].
"""

FEEDBACK_DOC = """---
name: refinement-discipline
description: One best fix.
metadata:
  type: feedback
---
Body.
"""

NO_NAME_DOC = """# A loose note

No frontmatter here, links [[somewhere]].
"""


def test_note_from_text_uses_frontmatter_name_as_slug():
    note = note_from_text("memory/project_self_hosting_graph_arc.md", PROJECT_DOC)
    assert note.slug == "self-hosting-graph-arc"
    assert note.id == note_node_id("self-hosting-graph-arc")
    assert note.note_type == "project"
    assert note.description == "The dogfood arc."
    assert note.references == ["current-arc-status"]


def test_slug_falls_back_to_relative_path_when_no_name():
    note = note_from_text("/corpus/sub/loose.md", NO_NAME_DOC, corpus_root="/corpus")
    assert note.slug == "sub/loose"
    assert note.title == "Sub/Loose"  # titleized from slug


def test_extraction_is_deterministic():
    a = note_from_text("memory/x.md", PROJECT_DOC)
    b = note_from_text("memory/x.md", PROJECT_DOC)
    assert a.id == b.id
    assert a.content_hash == b.content_hash
    assert a.to_graph_node() == b.to_graph_node()


def test_index_line():
    note = note_from_text("memory/project_self_hosting_graph_arc.md", PROJECT_DOC)
    assert note_index_line(note) == (
        "- [Self Hosting Graph Arc](project_self_hosting_graph_arc.md) — The dogfood arc."
    )


def test_render_groups_by_category_in_order():
    notes = [note_from_text("memory/refinement.md", FEEDBACK_DOC),
             note_from_text("memory/arc.md", PROJECT_DOC)]
    out = render_memory_index(notes)
    assert "## Project" in out and "## Feedback" in out
    # project section precedes feedback per DEFAULT_SECTION_ORDER
    assert out.index("## Project") < out.index("## Feedback")


def test_render_is_idempotent():
    notes = [note_from_text("memory/refinement.md", FEEDBACK_DOC),
             note_from_text("memory/arc.md", PROJECT_DOC)]
    assert render_memory_index(notes) == render_memory_index(notes)
