"""Schema-free Markdown parsing."""

from cjm_markdown_decompose_core.parse import (
    extract_headings, extract_wiki_links, parse_frontmatter, parse_markdown, split_frontmatter,
)

DOC = """---
name: self-hosting-graph-arc
description: "The arc: with a colon, and quotes."
metadata:
  node_type: memory
  type: project
---
# Heading One

Body referencing [[current-arc-status]] and [[self-hosting-graph-arc-first-slice-plan]].
Again [[current-arc-status]] (a duplicate).

## Heading Two
"""


def test_split_frontmatter_separates_block():
    raw, body = split_frontmatter(DOC)
    assert raw is not None and "name: self-hosting-graph-arc" in raw
    assert body.lstrip().startswith("# Heading One")


def test_split_frontmatter_absent():
    raw, body = split_frontmatter("# Just a heading\n")
    assert raw is None
    assert body == "# Just a heading\n"


def test_parse_markdown_frontmatter_raw_is_lossless_prefix():
    p = parse_markdown(DOC)
    # The verbatim prefix + body reconstructs the document byte-for-byte (the M1 source).
    assert p.frontmatter_raw + p.body == DOC
    assert p.frontmatter_raw.startswith("---\nname:") and p.frontmatter_raw.endswith("---\n")
    # No frontmatter -> empty prefix, body is the whole document.
    assert parse_markdown("# Just a heading\n").frontmatter_raw == ""


def test_parse_frontmatter_handles_colons_and_nesting():
    fm = parse_frontmatter(split_frontmatter(DOC)[0])
    assert fm["name"] == "self-hosting-graph-arc"
    assert fm["description"] == "The arc: with a colon, and quotes."
    assert fm["metadata"]["type"] == "project"


def test_parse_frontmatter_empty():
    assert parse_frontmatter(None) == {}
    assert parse_frontmatter("   ") == {}


def test_extract_wiki_links_dedup_order_preserved():
    links = extract_wiki_links(DOC)
    assert links == ["current-arc-status", "self-hosting-graph-arc-first-slice-plan"]


def test_extract_wiki_links_ignores_code_spans():
    # Quoted example syntax (in notes ABOUT links) is NOT a real reference.
    body = (
        "A real ref to [[real-note]] here.\n"
        "Inline example: a dangling `[[wiki-link]]` marks a TODO, and `[[ref]]` too.\n"
        "```\nfenced [[not-a-ref]] block\n```\n"
        "Another real [[second-note]].\n"
    )
    assert extract_wiki_links(body) == ["real-note", "second-note"]


def test_extract_headings():
    assert extract_headings(DOC) == [(1, "Heading One"), (2, "Heading Two")]


def test_parse_markdown_end_to_end():
    parsed = parse_markdown(DOC)
    assert parsed.frontmatter["name"] == "self-hosting-graph-arc"
    assert parsed.wiki_links == ["current-arc-status", "self-hosting-graph-arc-first-slice-plan"]
    assert "[[current-arc-status]]" in parsed.body  # links stay in the body text
    assert (1, "Heading One") in parsed.headings
