"""Extract markdown -> NoteNode and project notes -> MEMORY.md index (with idempotency)."""

from cjm_dev_graph_schema.identity import note_node_id
from cjm_dev_graph_schema.nodes import NoteNode
from cjm_markdown_decompose_core.extract import note_from_text
from cjm_markdown_decompose_core.project import (
    first_sentence, note_index_line, render_memory_index, render_onboarding_surface,
)

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


def test_index_md_identified_by_directory_permalink():
    # SSG `posts/<slug>/index.md` → identity is the directory (the permalink),
    # not the literal `index` stem (the corpus identity-collision pinch).
    a = note_from_text("/corpus/posts/yolox-train/index.md", NO_NAME_DOC, corpus_root="/corpus")
    b = note_from_text("/corpus/posts/dumbing-us-down/index.md", NO_NAME_DOC, corpus_root="/corpus")
    assert a.slug == "posts/yolox-train"
    assert b.slug == "posts/dumbing-us-down"
    assert a.id != b.id  # no longer collapsed onto a single `index` node

    # Identity relative to the posts root itself yields the bare permalink.
    c = note_from_text("/corpus/posts/yolox-train/index.md", NO_NAME_DOC, corpus_root="/corpus/posts")
    assert c.slug == "yolox-train"


def test_root_level_index_falls_back_to_dir_name():
    note = note_from_text("/corpus/posts/index.md", NO_NAME_DOC, corpus_root="/corpus/posts")
    assert note.slug == "posts"  # relative-to-root "." guarded to the dir name


def test_non_index_and_frontmatter_name_unaffected_by_index_rule():
    # The memory corpus is untouched: frontmatter `name` still wins outright,
    # and a non-`index` file keeps its stem-based fallback slug.
    named = note_from_text("/corpus/posts/x/index.md", PROJECT_DOC, corpus_root="/corpus")
    assert named.slug == "self-hosting-graph-arc"
    loose = note_from_text("/corpus/sub/loose.md", NO_NAME_DOC, corpus_root="/corpus")
    assert loose.slug == "sub/loose"


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


# --- Onboarding surface ------------------------------------------------------

def _note(slug, title, desc, ntype):
    return NoteNode(slug=slug, title=title, path=f"memory/{slug}.md",
                    content_hash="", description=desc, note_type=ntype)


def test_first_sentence_takes_boundary_else_caps():
    assert first_sentence("First sentence. Second one.") == "First sentence."
    assert first_sentence("clause one; clause two") == "clause one;"
    assert first_sentence("no boundary at all") == "no boundary at all"
    assert first_sentence("") == ""
    capped = first_sentence("x" * 300, limit=50)
    assert capped.endswith("…") and len(capped) <= 52


def test_render_onboarding_surface_structure_push_and_landmarks():
    notes = [
        _note("explicit-graph-db-path", "Explicit Graph Db Path", "Keep it explicit. Always.", "feedback"),
        _note("a-guardrail", "A Guardrail", "First point here. Buried critical bit.", "feedback"),
        _note("a-project", "A Project", "Some project note.", "project"),
    ]
    md = render_onboarding_surface(
        notes,
        push_slugs=["explicit-graph-db-path", "a-guardrail", "absent-slug"],
        landmarks=[("Design dialect", "design dialect")],
        arc_lead="ACTIVE LEAD: do the thing.",
        how_to_query="## How to query\nuse the tool.",
        push_hooks={"explicit-graph-db-path": "Always explicit — complete hook."},
    )
    assert "ACTIVE LEAD: do the thing." in md
    # explicit hook OVERRIDES the description truncation + carries a `show` pull-hint
    assert "- **Explicit Graph Db Path** — Always explicit — complete hook.  ↳ `show " in md
    # no hook -> first-sentence fallback (still a complete first sentence) + `show` pull-hint
    assert "- **A Guardrail** — First point here.  ↳ `show " in md
    # missing slug -> placeholder, no pull-hint
    assert "push node not found on-graph: absent-slug" in md
    # landmark map = coverage counts (NOT enumeration: the project note is counted, never listed) + injected prose
    assert 'relevant "design dialect"' in md
    assert "feedback:2, project:1" in md
    assert "A Project" not in md  # coverage, not enumeration
    assert "## How to query\nuse the tool." in md


def test_render_onboarding_surface_is_deterministic():
    notes = [_note("explicit-graph-db-path", "Explicit Graph Db Path", "Keep it explicit.", "feedback")]
    args = (notes, ["explicit-graph-db-path"], [("Dialect", "dialect")], "LEAD.")
    assert render_onboarding_surface(*args) == render_onboarding_surface(*args)


def test_render_onboarding_surface_coverage_augments_landmark_map():
    notes = [_note("a-project", "A Project", "x", "project")]
    cov = "### Graph at a glance (auto-derived)\n_By kind:_ Note×85 · Section×498"
    md = render_onboarding_surface(notes, ["a-project"], [("Dialect", "dialect")], "LEAD.",
                                   coverage=cov)
    # The auto coverage lands UNDER the curated landmark map and ABOVE 'How to pull'.
    assert cov in md
    assert md.index("Landmark map") < md.index("Graph at a glance") < md.index("How to pull")
    # Absent coverage -> unchanged (back-compat).
    assert "Graph at a glance" not in render_onboarding_surface(notes, ["a-project"],
                                                                [("Dialect", "dialect")], "LEAD.")
