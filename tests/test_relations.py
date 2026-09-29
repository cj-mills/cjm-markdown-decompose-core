"""Per-source-type relationship harvesters + profile dispatch + extract wiring."""

from cjm_markdown_decompose_core.extract import note_from_text
from cjm_markdown_decompose_core.parse import parse_markdown
from cjm_markdown_decompose_core.relations import (
    detect_profile, harvest_aliases, harvest_categories, harvest_relations, harvest_site_links,
    is_page_target, is_site_link, normalize_permalink, quarto_site_url, slugify)

# A representative Quarto blog post (shape from christianjmills/posts).
QUARTO_POST = """---
title: "Training YOLOX Models"
date: 2023-08-21
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


def test_harvest_site_links_keeps_every_page_target_verbatim():
    # ONE harvest for every in-body site link (ruling d31e9ba7): posts, series pages, relative
    # and anchored targets, kept VERBATIM for the post-replay resolver; code is stripped, and
    # the self-link is kept here (the resolver drops a link to the note's own page).
    body = parse_markdown(QUARTO_POST).body
    assert harvest_site_links(body) == [
        "/posts/google-colab-getting-started-tutorial/#using-hardware-acceleration",
        "../mamba-getting-started-tutorial-windows/",
        "/posts/pytorch-train-object-detector-yolox-tutorial/#loading-the-model",
        "/series/notes/education-notes.html"]
    twice = "[a](/series/notes/x.html) [b](/series/notes/x.html) [c](/series/notes/x.html#part)"
    assert harvest_site_links(twice) == ["/series/notes/x.html", "/series/notes/x.html#part"]


def test_only_page_targets_are_site_links():
    # an image, a video or a download beside a post is a file, never a cross-reference; a bare
    # #anchor names a place on the linking page itself
    for page in ("../x/", "/posts/x", "part-2/index.html", "/series/notes/x.htm#a", "../../y/z/#b"):
        assert is_page_target(page), page
    for other in ("./images/a.png", "../b/c.MP4", "#anchor", "/files/x.zip", ""):
        assert not is_page_target(other), other
    body = "![img](./images/a.png) [same page](#here) [prev](../part-1/) [vid](./v.mp4)"
    assert harvest_site_links(body) == ["../part-1/"]


def test_only_site_links_are_harvested():
    # Another site's /series/ or /posts/ path is not a site relation (finding 0fadbbbd); the
    # site's own absolute URL is (www. included), and relative/rooted links always are.
    body = ("[hnsw](https://www.pinecone.io/learn/series/faiss/hnsw/) "
            "[evals](https://hamel.dev/blog/posts/evals/) "
            "[own](https://www.christianjmills.com/posts/x/#a) "
            "[own series](https://christianjmills.com/series/notes/education-notes.html) "
            "[rooted](/posts/y/) [mail](mailto:me@example.com)")
    site = "https://christianjmills.com"
    assert harvest_site_links(body, site) == [
        "https://www.christianjmills.com/posts/x/#a",
        "https://christianjmills.com/series/notes/education-notes.html", "/posts/y/"]
    # With no known site URL every absolute URL is external; rooted links still count.
    assert harvest_site_links(body) == ["/posts/y/"]
    assert is_site_link("../z/") and is_site_link("#anchor")
    assert not is_site_link("https://christianjmills.com/posts/x/")


def test_quarto_site_url_from_the_nearest_project(tmp_path):
    # The site URL is the post's Quarto project's website.site-url (ruling 260119bf), found
    # the way Quarto finds a file's project; the harvest reads it through the post's path.
    site, bare = tmp_path / "site", tmp_path / "bare"
    (site / "posts" / "p").mkdir(parents=True)
    (bare / "posts" / "q").mkdir(parents=True)
    (site / "_quarto.yml").write_text('website:\n  site-url: "https://christianjmills.com"\n')
    (bare / "_quarto.yml").write_text("project:\n  type: website\n")
    post = str(site / "posts" / "p" / "index.md")
    assert quarto_site_url(post) == "https://christianjmills.com"
    assert quarto_site_url(str(bare / "posts" / "q" / "index.md")) is None
    assert quarto_site_url(str(tmp_path / "loose.md")) is None
    assert quarto_site_url(None) is None

    doc = ("---\ntitle: P\ndate: 2024-1-1\n---\n"
           "[own](https://christianjmills.com/series/notes/education-notes.html) "
           "[other](https://www.pinecone.io/learn/series/faiss/hnsw/)\n")
    assert note_from_text(post, doc, corpus_root=str(site / "posts")).site_refs == [
        "https://christianjmills.com/series/notes/education-notes.html"]


def test_detect_profile():
    assert detect_profile(parse_markdown(QUARTO_POST).frontmatter) == "quarto_post"
    assert detect_profile(parse_markdown(MEMORY_DOC).frontmatter) == "memory"
    assert detect_profile({}) == "memory"  # no-frontmatter-safe


def test_harvest_relations_dispatches_by_profile():
    rel = harvest_relations(parse_markdown(QUARTO_POST))
    assert rel.categories and rel.site_refs and rel.aliases
    mem = harvest_relations(parse_markdown(MEMORY_DOC))
    assert mem == type(mem)()  # memory profile harvests nothing extra (wiki-links via parse)


def test_extract_keeps_every_site_link_for_the_resolver():
    note = note_from_text(
        "/corpus/posts/pytorch-train-object-detector-yolox-tutorial/index.md",
        QUARTO_POST, corpus_root="/corpus/posts")
    assert note.slug == "pytorch-train-object-detector-yolox-tutorial"
    assert note.categories == ["pytorch", "object-detection", "yolox", "tutorial"]
    # the self-link rides along: the resolver drops a link to the note's own page
    assert note.site_refs[-1] == "/series/notes/education-notes.html" and len(note.site_refs) == 4
    assert not hasattr(note, "cross_post_refs")


def test_memory_corpus_unaffected():
    note = note_from_text("memory/some.md", MEMORY_DOC)
    assert note.categories == [] and note.site_refs == []
    assert note.references == ["other-memory"]  # wiki-links still work


def test_yaml_date_frontmatter_is_json_safe():
    import json
    # PyYAML parses `date:` into a datetime.date; the wire dict must stay JSON-safe.
    note = note_from_text("/c/posts/x/index.md", QUARTO_POST, corpus_root="/c/posts")
    assert note.metadata["date"] == "2023-08-21"  # coerced to an ISO string
    json.dumps(note.to_graph_node())  # the graph-store boundary: must not raise
