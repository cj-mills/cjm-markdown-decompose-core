# cjm-markdown-decompose-core

A **Markdown decomposition core** for context graphs. It parses Markdown
content — frontmatter, document structure, and `[[wiki-links]]` — into
provenance-carrying graph nodes and edges, and projects views back out
(e.g. regenerating an index file from the graph).

Markdown is a *perennial* source type: the first corpus is the ecosystem's own
memory / decision files, but the same core applies to any Markdown — blog
posts, notes, docs. It is the markdown counterpart to the transcript
decomposition core, part of the **self-hosting graph arc**.

> **Born non-nbdev.** Plain `.py` modules, `pytest` tests, fine granularity
> (one concept per module). The Markdown parsing (`parse`) carries **no schema
> dependency** (stdlib + PyYAML only) so it is reusable for any corpus; the
> dev-domain binding lives in `extract`.

## Install

```bash
pip install -e .
```

Depends on
[`cjm-dev-graph-schema`](https://github.com/cj-mills/cjm-dev-graph-schema)
(the node/edge vocabulary it emits) plus
[`cjm-context-graph-layer`](https://github.com/cj-mills/cjm-context-graph-layer)
and
[`cjm-context-graph-primitives`](https://github.com/cj-mills/cjm-context-graph-primitives).

## What it provides

- **`parse`** — schema-free Markdown parsing (stdlib + PyYAML): split YAML
  frontmatter from the body, extract `[[wiki-links]]`, read headings. Reusable
  for any Markdown corpus.
- **`extract`** — map a parsed Markdown file onto dev-graph-schema nodes/edges
  (coarse tier: one `Note` node per file + `REFERENCES` edges for its links).
- **`project`** — regenerate views from the decomposed content; first projection
  is the `MEMORY.md` index (single source of truth = each note's frontmatter).

## Status

Early — built incrementally alongside the self-hosting graph arc. First
milestone: a generated `MEMORY.md` that approximates the hand-maintained one,
with idempotent re-extraction.
