"""Per-source-type relationship harvesters + profile dispatch + extract wiring."""

from cjm_markdown_decompose_core.extract import note_from_text
from cjm_markdown_decompose_core.parse import parse_markdown
from cjm_markdown_decompose_core.relations import (
    detect_profile, harvest_aliases, harvest_categories, harvest_cross_post_links,
    harvest_relations, harvest_series_links, normalize_permalink, slugify)

# A representative Quarto blog post (shape from christianjmills/posts).
QUARTO_POST = """---
title: "Training YOLOX Models"
date: 2023-8-21
categories: [pytorch, object-detection, "YOLOX", tutorial]
aliases:
- /posts/icevision-openvino-unity-tutorial/part-1/
description: "Train YOLOX."
---
This builds on [Colab setup](/posts/google-colab-getting-started-tutorial/#using-hardware-acceleration)
and [Mamba](../mamba-getting-started-tutorial-windows/). See my own
[loading section](/posts/pytorch-train-object-detector-yolox-tutorial/#loading-the-model).

::: {.callout-tip}
Part of the [Education series](/series/notes/education-notes.html).
:::

```python
link = "[skip](/posts/should-be-ignored/)"  # code is stripped
```
"""

MEMORY_DOC = """---
name: some-memory
description: A memory file.
metadata:
  type: project
---
Links [[other-memory]] only.
"""


def test_slugify_normalizes():
    assert slugify("YOLOX") == "yolox"
    assert slugify(" Object Detection ") == "object-detection"
    assert slugify("a__b") == "a-b"


def test_normalize_permalink_variants():
    assert normalize_permalink("/posts/x/#anchor") == "x"
    assert normalize_permalink("https://www.christianjmills.com/posts/x/") == "x"
    assert normalize_permalink("../../posts/nested/lecture-1/") == "nested/lecture-1"
    assert normalize_permalink("../sibling-post/") == "sibling-post"
    assert normalize_permalink("/posts/x/index.html") == "x"
    assert normalize_permalink("https://example.com/blog/y/") is None  # not a post link


def test_harvest_categories_normalized_deduped():
    fm = parse_markdown(QUARTO_POST).frontmatter
    assert harvest_categories(fm) == ["pytorch", "object-detection", "yolox", "tutorial"]


def test_harvest_aliases_to_permalinks():
    fm = parse_markdown(QUARTO_POST).frontmatter
    assert harvest_aliases(fm) == ["icevision-openvino-unity-tutorial/part-1"]


def test_harvest_cross_post_links_with_anchors_and_code_stripped():
    body = parse_markdown(QUARTO_POST).body
    refs = harvest_cross_post_links(body)
    assert ("google-colab-getting-started-tutorial", "using-hardware-acceleration") in refs
    assert ("mamba-getting-started-tutorial-windows", "") in refs
    # The self-link is still harvested here (extract filters it); the CODE link is NOT.
    assert ("pytorch-train-object-detector-yolox-tutorial", "loading-the-model") in refs
    assert all(p != "should-be-ignored" for p, _ in refs)


def test_harvest_series_links():
    body = parse_markdown(QUARTO_POST).body
    assert harvest_series_links(body) == ["education-notes"]


def test_detect_profile():
    assert detect_profile(parse_markdown(QUARTO_POST).frontmatter) == "quarto_post"
    assert detect_profile(parse_markdown(MEMORY_DOC).frontmatter) == "memory"
    assert detect_profile({}) == "memory"  # no-frontmatter-safe


def test_harvest_relations_dispatches_by_profile():
    rel = harvest_relations(parse_markdown(QUARTO_POST))
    assert rel.categories and rel.series_refs and rel.aliases and rel.cross_post_refs
    mem = harvest_relations(parse_markdown(MEMORY_DOC))
    assert mem == type(mem)()  # memory profile harvests nothing extra (wiki-links via parse)


def test_extract_drops_self_reference_cross_post_link():
    note = note_from_text(
        "/corpus/posts/pytorch-train-object-detector-yolox-tutorial/index.md",
        QUARTO_POST, corpus_root="/corpus/posts")
    assert note.slug == "pytorch-train-object-detector-yolox-tutorial"
    targets = {p for p, _ in note.cross_post_refs}
    # own-section self-link dropped; real cross-post links kept
    assert "pytorch-train-object-detector-yolox-tutorial" not in targets
    assert "google-colab-getting-started-tutorial" in targets
    assert note.categories == ["pytorch", "object-detection", "yolox", "tutorial"]
    assert note.series_refs == ["education-notes"]


def test_memory_corpus_unaffected():
    note = note_from_text("memory/some.md", MEMORY_DOC)
    assert note.categories == [] and note.series_refs == [] and note.cross_post_refs == []
    assert note.references == ["other-memory"]  # wiki-links still work
