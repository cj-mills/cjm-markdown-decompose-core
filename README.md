# cjm-markdown-decompose-core

<!-- generated from the context graph by `cjm-context-graph readme` — do not edit by hand; edit the graph (the urge to hand-edit = move it on-graph) -->

A Markdown decomposition core for context graphs: parses Markdown content (frontmatter, structure, and [[wiki-links]]) into provenance-carrying graph nodes and edges. First source = the ecosystem's own memory/decision files; generalizes to any Markdown corpus.

## Modules

- **`cjm_markdown_decompose_core.__init__`**
- **`cjm_markdown_decompose_core.blocks`** — Embedded DERIVED blocks: spans of a body that are not the document's own content.
- **`cjm_markdown_decompose_core.extract`** — Map parsed Markdown onto dev-graph-schema nodes (coarse tier).
- **`cjm_markdown_decompose_core.ingest`** — Flatten decomposed notes into graph elements for idempotent extension.
- **`cjm_markdown_decompose_core.parse`** — Schema-free Markdown parsing (stdlib + PyYAML).
- **`cjm_markdown_decompose_core.project`** — Projections from the decomposed content back out to files.
- **`cjm_markdown_decompose_core.relations`** — Per-source-type relationship harvesting from parsed Markdown.
- **`cjm_markdown_decompose_core.sections`** — Decompose a Markdown body into ordered Section nodes (the navigable unit).

## API

### `cjm_markdown_decompose_core.blocks`

- `DerivedBlock` _class_ — One derived block: its role and its `[start, end)` span of the body.
- `block_link_targets` _function_ — A derived block's fingerprint for the render filter: its link targets as Pandoc hands
- `derived_blocks` _function_ — Classify a body's derived blocks under its source profile.
- `find_chrome_includes` _function_ — Site-chrome include lines: a line holding only `{{< include PATH >}}` whose PATH is one
- `find_hand_toc` _function_ — The hand table of contents: the FIRST run of two or more anchor-link list lines at
- `find_series_callouts` _function_ — The series callout(s): a top-level `::: {.callout-tip}` whose first line is a surveyed
- `find_series_nav_lines` _function_ — Hand series-navigation lines: a heading holding only `Previous:` / `Next:` and links.
- `include_target` _function_ — A chrome include's fingerprint for the render filter: the partial it includes (the
- `mask_blocks` _function_ — The body a relation harvest reads: derived blocks contribute no edges (253ac996 (4)).
- `quarto_derived_blocks` _function_ — The Quarto archive profile: series callouts, the hand TOC, hand series-nav lines, the

### `cjm_markdown_decompose_core.extract`

- `corpus_index_files` _function_ — Every `<dir>/index.md` or `<dir>/index.qmd` under the root, one per post directory.
- `note_from_file` _function_ — Read a Markdown file and map it to a coarse `NoteNode`.
- `note_from_parsed` _function_ — Build a coarse `NoteNode` from already-parsed Markdown.
- `note_from_text` _function_ — Parse + map in one step from in-memory text (hashes the UTF-8 bytes).
- `note_type_from` _function_ — Read the memory category from `metadata.type` (None when absent).
- `slug_from` _function_ — Derive the stable slug: frontmatter `name` if present, else the path.
- `title_from` _function_ — Derive a display title: explicit frontmatter `title`, else the slug titleized.

### `cjm_markdown_decompose_core.ingest`

- `corpus_graph_elements` _function_ — Collect notes into the node + edge wire-dict lists `extend_graph` expects.

### `cjm_markdown_decompose_core.parse`

- `ParsedMarkdown` _class_ — The structural decomposition of one Markdown document.
- `extract_headings` _function_ — Extract ATX headings (`#`..`######`) as (level, text) pairs.
- `extract_wiki_links` _function_ — Extract `[[wiki-link]]` targets from the body, de-duplicated, order-preserved.
- `fenced_code_spans` _function_ — Locate fenced code blocks (``` / ~~~) as character spans of the body.
- `find_headings` _function_ — The body's ATX heading matches, skipping every line inside a fenced code block.
- `parse_frontmatter` _function_ — Parse frontmatter YAML into a dict (empty dict when absent).
- `parse_markdown` _function_ — Parse a Markdown document into frontmatter + body + wiki-links + headings.
- `split_frontmatter` _function_ — Split a leading `---`-delimited YAML frontmatter block from the body.
- `strip_code` _function_ — Blank out fenced + inline code spans (replaced with a space, length-agnostic).

### `cjm_markdown_decompose_core.project`

- `first_sentence` _function_ — A deterministic terse hook: the description's first sentence, capped.
- `note_index_line` _function_ — Render one index line from a note's frontmatter-derived fields.
- `note_text_from_graph_nodes` _function_ — Reconstruct a note's file text FROM the graph (frontmatter_raw + ordered raw spans).
- `note_view_from_graph_node` _function_ — Reconstruct an index-relevant `NoteNode` from a queried graph node.
- `render_memory_index` _function_ — Render a `MEMORY.md` index: notes grouped by category, one line each.
- `render_memory_index_from_graph_nodes` _function_ — Render the memory index FROM queried graph nodes (the self-hosting path).
- `render_note_text` _function_ — Reassemble a note's exact file text from its verbatim parts (lossless mode).
- `render_onboarding_surface` _function_ — Render the onboarding surface: orientation + how-to-query + resident PUSH core + landmark map + how-to-pull.

### `cjm_markdown_decompose_core.relations`

- `NoteRelations` _class_ — The harvested relationship signals for one note (beyond `[[wiki-links]]`).
- `detect_profile` _function_ — Detect the source-type profile from the frontmatter shape.
- `harvest_aliases` _function_ — Harvest `aliases` (old URLs) -> bare permalinks (alternate identities).
- `harvest_categories` _function_ — Harvest `categories` -> normalized Topic keys (the thematic-clustering facet).
- `harvest_relations` _function_ — Harvest a note's relationships using its (detected or given) source profile.
- `harvest_site_links` _function_ — Harvest every in-body link to a site PAGE -> its VERBATIM target (ruling d31e9ba7).
- `is_page_target` _function_ — A link to a page, not to a file: an image, video or download beside a post is never a
- `is_site_link` _function_ — A link into the site: relative or rooted, or an absolute URL on the site's own host.
- `normalize_permalink` _function_ — Reduce a post link to its bare permalink — the path AFTER `posts/`.
- `quarto_site_url` _function_ — The site URL of the Quarto project a file belongs to (ruling 260119bf).
- `slugify` _function_ — Normalize a category/tag to a stable key (lowercased, separators collapsed).

### `cjm_markdown_decompose_core.sections`

- `decompose_sections` _function_ — Decompose a body into ordered `SectionNode`s (heading-delimited).
- `heading_anchor` _function_ — Slugify a heading to its anchor — the Pandoc/Quarto auto-identifier shape.

## Dependencies

**Depends on:** `cjm-context-graph-layer`, `cjm-context-graph-primitives`, `cjm-dev-graph-schema`, `pyyaml`
**Used by:** `cjm-context-graph-projection`, `cjm-notebook-decompose-core`
