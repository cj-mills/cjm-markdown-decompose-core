"""Derived blocks (design 253ac996): classification, typed sections, harvest masking."""

from cjm_markdown_decompose_core.blocks import (
    HAND_TOC, SERIES_CALLOUT, SERIES_NAV_LINE, block_link_targets, derived_blocks,
    mask_blocks, quarto_derived_blocks)
from cjm_markdown_decompose_core.extract import note_from_text
from cjm_markdown_decompose_core.sections import CONTINUATION_SEP, PREAMBLE_ANCHOR

FM = "---\ntitle: T\ndate: 2024-01-01\ncategories: [x]\n---\n"

POST = """
::: {.callout-tip}
## This post is part of the following series:
* [**The Series**](/series/tutorials/the-series.html): My notes.
:::

* [Introduction](#introduction)
* [Setup](#setup)

-----

::: {.callout-note title="Resources"}
* [Slides](https://example.com/slides)
:::

## Introduction

Intro with a [cross-post](/posts/other-post/).

## Setup

Setup steps.

### Next: [Part 2](../part-2/)

{{< include /_about-author-cta.qmd >}}
"""


def _roles(body):
    return [(b.role, body[b.start:b.end]) for b in quarto_derived_blocks(body)]


def test_the_three_roles_and_their_spans():
    roles = _roles(POST)
    assert [r for r, _ in roles] == [SERIES_CALLOUT, HAND_TOC, SERIES_NAV_LINE]
    callout, toc, nav = (t for _, t in roles)
    assert callout.startswith("\n::: {.callout-tip}") and callout.endswith(":::\n\n")  # leading blank joins the first block
    assert toc.startswith("* [Introduction]") and "-----\n" in toc                      # the closing rule joins the TOC
    assert nav == "### Next: [Part 2](../part-2/)\n\n"


def test_collection_titles_and_bare_links():
    body = "::: {.callout-tip}\n## These notes are part of the following collection:\n[**Education**](/series/notes/education-notes.html)\n:::\n\nText.\n"
    assert [r for r, _ in _roles(body)] == [SERIES_CALLOUT]


def test_other_callout_tips_are_content():
    body = "::: {.callout-tip}\n## Tip\n* [a](#a)\n* [b](#b)\n:::\n\n## A\n"
    assert _roles(body) == []  # a tip callout with another title; the anchor list inside it is its own


def test_hand_toc_rules():
    # a single anchor line is not a TOC; blank lines between items are; a TOC after a
    # level-2 heading is content
    assert _roles("* [a](#a)\n\n## A\n") == []
    assert [r for r, _ in _roles("* [a](#a)\n\n* [b](#b)\n\n## A\n")] == [HAND_TOC]
    assert _roles("## A\n\n* [a](#a)\n* [b](#b)\n") == []
    # an anchor list inside a callout is skipped; the first depth-0 run is the TOC
    body = "::: {.callout-note}\n## Book Links:\n* [x](#x)\n* [y](#y)\n:::\n\n* [a](#a)\n* [b](#b)\n\n## A\n"
    (role, text), = _roles(body)
    assert role == HAND_TOC and text.startswith("* [a](#a)")
    # a fenced example is never a block
    assert _roles("```\n* [a](#a)\n* [b](#b)\n```\n") == []


def test_nav_lines_with_several_links():
    body = "## A\n\n### Previous: [Part 1](../part-1/) [Part 1.5](../part-1-5/)\n\nText.\n\n## Previous Work\n"
    (role, text), = _roles(body)
    assert role == SERIES_NAV_LINE and text.startswith("### Previous:")


def test_profiles_without_blocks():
    assert derived_blocks(POST, "memory") == []
    assert len(derived_blocks(POST, "quarto_post")) == 3


def test_mask_keeps_offsets_and_blanks_links():
    blocks = quarto_derived_blocks(POST)
    masked = mask_blocks(POST, blocks)
    assert len(masked) == len(POST) and masked.count("\n") == POST.count("\n")
    assert "/series/" not in masked and "../part-2/" not in masked and "/posts/other-post/" in masked


def test_link_targets_fingerprint():
    assert block_link_targets('* [**S**](/series/x.html): notes [y](/y "Title")') == ["/series/x.html", "/y"]
    assert block_link_targets("* [e](#)\n* [f](#Raw Text)") == ["#", "#Raw%20Text"]  # Pandoc escapes a spaced target


def test_typed_sections_round_trip_and_hierarchy():
    note = note_from_text("/c/p/index.md", FM + POST, profile="quarto_post", lossless=True)
    secs = note.sections
    assert note.frontmatter_raw + "".join(s.raw for s in secs) == FM + POST
    assert [(s.anchor, s.block_role, s.parent_anchor) for s in secs] == [
        ("_series_callout", SERIES_CALLOUT, None),
        ("_hand_toc", HAND_TOC, None),
        (PREAMBLE_ANCHOR, "", None),             # the resource callout: the pre-heading content
        ("introduction", "", None),
        ("setup", "", None),
        ("_series_nav_line", SERIES_NAV_LINE, "setup"),
        (f"setup{CONTINUATION_SEP}1", "", "setup"),  # the content the nav line interrupted
    ]
    assert [s.order for s in secs] == list(range(len(secs)))
    node = secs[0].to_graph_node()
    assert node["properties"]["block_role"] == SERIES_CALLOUT
    assert "block_role" not in secs[2].to_graph_node()["properties"]


def test_the_harvest_skips_derived_blocks():
    note = note_from_text("/c/p/index.md", FM + POST, profile="quarto_post", lossless=True)
    assert note.site_refs == ["/posts/other-post/"]  # the callout's and the nav line's links are gone


def test_scope_a_drops_pre_heading_content_but_types_blocks():
    note = note_from_text("/c/p/index.md", FM + POST, profile="quarto_post", with_sections=True)
    anchors = [s.anchor for s in note.sections]
    assert PREAMBLE_ANCHOR not in anchors and "_series_callout" in anchors
    assert f"setup{CONTINUATION_SEP}1" in anchors


def test_crlf_bodies_classify_and_round_trip():
    text = (FM + POST).replace("\n", "\r\n")
    note = note_from_text("/c/p/index.md", text, profile="quarto_post", lossless=True)
    assert note.frontmatter_raw + "".join(s.raw for s in note.sections) == text
    assert [s.block_role for s in note.sections if s.block_role] == [SERIES_CALLOUT, HAND_TOC, SERIES_NAV_LINE]
    assert "-----\r\n" in next(s.raw for s in note.sections if s.block_role == HAND_TOC)
