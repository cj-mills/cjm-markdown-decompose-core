"""Schema-free Markdown parsing."""

from cjm_markdown_decompose_core.parse import (
    extract_headings, extract_wiki_links, fenced_code_spans, find_headings, parse_frontmatter,
    parse_markdown, split_frontmatter,
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


def test_fenced_code_spans_backtick_tilde_and_unclosed():
    body = ("intro\n"
            "```python\n# not a heading\nx = 1\n```\n"
            "mid\n"
            "~~~\n## also not a heading\n~~~\n"
            "  ````md\n```\n# nested fence stays open until a 4-run closer\n````\n"
            "tail\n"
            "```\n# unclosed fence runs to the end\n")
    spans = fenced_code_spans(body)
    assert len(spans) == 4
    starts = [body[s:s + 16] for s, _ in spans]
    assert starts[0].startswith("```python") and starts[1].startswith("~~~")
    assert starts[2].startswith("  ````md") and starts[3].startswith("```\n# unclosed")
    # A backtick opener whose info string carries a backtick is NOT a fence (CommonMark),
    # so the `# heading` after it stays a heading (the later ``` line opens a new fence).
    odd = "``` a`b\n# heading\n```\n"
    assert fenced_code_spans(odd) == [(18, 22)]
    assert [m.group(2) for m in find_headings(odd)] == ["heading"]
    # Closers must be at least as long as the opener: the inner ``` did not close ````.
    inner = body.index("# nested fence")
    assert any(s <= inner < e for s, e in spans)
    # Unclosed: the last span reaches the end of the body.
    assert spans[-1][1] == len(body)


def test_headings_inside_fenced_code_are_not_headings():
    body = ("# Real\n"
            "```python\n# Function to run a single epoch\ndef run_epoch():\n    pass\n```\n"
            "## Also real\n"
            "~~~\n### tilde-fenced\n~~~\n")
    assert extract_headings(body) == [(1, "Real"), (2, "Also real")]
    assert [m.group(2) for m in find_headings(body)] == ["Real", "Also real"]
    # The parse_markdown surface agrees (the finding's symptom: a mid-code Section).
    assert parse_markdown(body).headings == [(1, "Real"), (2, "Also real")]


def test_parse_markdown_end_to_end():
    parsed = parse_markdown(DOC)
    assert parsed.frontmatter["name"] == "self-hosting-graph-arc"
    assert parsed.wiki_links == ["current-arc-status", "self-hosting-graph-arc-first-slice-plan"]
    assert "[[current-arc-status]]" in parsed.body  # links stay in the body text
    assert (1, "Heading One") in parsed.headings
