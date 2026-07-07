# cjm-markdown-decompose-core

<!-- generated from the context graph by `cjm-context-graph readme` — do not edit by hand; edit the graph (the urge to hand-edit = move it on-graph) -->

A Markdown decomposition core for context graphs: parses Markdown content (frontmatter, structure, and [[wiki-links]]) into provenance-carrying graph nodes and edges. First source = the ecosystem's own memory/decision files; generalizes to any Markdown corpus.

## Modules

- **`cjm_markdown_decompose_core.__init__`**
- **`cjm_markdown_decompose_core.extract`** — Map parsed Markdown onto dev-graph-schema nodes (coarse tier).
- **`cjm_markdown_decompose_core.ingest`** — Flatten decomposed notes into graph elements for idempotent extension.
- **`cjm_markdown_decompose_core.parse`** — Schema-free Markdown parsing (stdlib + PyYAML).
- **`cjm_markdown_decompose_core.project`** — Projections from the decomposed content back out to files.
- **`cjm_markdown_decompose_core.relations`** — Per-source-type relationship harvesting from parsed Markdown.
- **`cjm_markdown_decompose_core.sections`** — Decompose a Markdown body into ordered Section nodes (the navigable unit).
- **`tests.test_extract_project`** — Extract markdown -> NoteNode and project notes -> MEMORY.md index (with idempotency).
- **`tests.test_ingest_graphproject`** — Corpus -> graph elements, and projecting the index back from graph nodes.
- **`tests.test_parse`** — Schema-free Markdown parsing.
- **`tests.test_relations`** — Per-source-type relationship harvesters + profile dispatch + extract wiring.
- **`tests.test_sections`** — Body -> ordered Section nodes: anchors, hierarchy, verbatim text, disambiguation.
- **`tests_manual.memory_body_roundtrip`** — M1 round-trip: memory BODIES -> graph (extend_graph) -> byte-exact file text.
- **`tests_manual.memory_roundtrip`** — Inc 1 round-trip: memory corpus -> graph (extend_graph) -> MEMORY.md projection.
- **`tests_manual.notes_slice`** — Runtime harness: decompose a real christianjmills/posts slice through the full

## API

### `cjm_markdown_decompose_core.extract`

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
- `harvest_cross_post_links` _function_ — Harvest `/posts/...` markdown links -> (permalink, section anchor) pairs.
- `harvest_relations` _function_ — Harvest a note's relationships using its (detected or given) source profile.
- `harvest_series_links` _function_ — Harvest `/series/...` markdown links -> series keys (the membership signal).
- `normalize_permalink` _function_ — Reduce a post link to its bare permalink — the path AFTER `posts/`.
- `slugify` _function_ — Normalize a category/tag to a stable key (lowercased, separators collapsed).

### `cjm_markdown_decompose_core.sections`

- `decompose_sections` _function_ — Decompose a body into ordered `SectionNode`s (heading-delimited).
- `heading_anchor` _function_ — Slugify a heading to its anchor — the Pandoc/Quarto auto-identifier shape.

### `tests.test_extract_project`

- `test_extraction_is_deterministic` _function_
- `test_first_sentence_takes_boundary_else_caps` _function_
- `test_index_line` _function_
- `test_index_md_identified_by_directory_permalink` _function_
- `test_non_index_and_frontmatter_name_unaffected_by_index_rule` _function_
- `test_note_from_text_uses_frontmatter_name_as_slug` _function_
- `test_render_groups_by_category_in_order` _function_
- `test_render_is_idempotent` _function_
- `test_render_onboarding_surface_coverage_augments_landmark_map` _function_
- `test_render_onboarding_surface_is_deterministic` _function_
- `test_render_onboarding_surface_structure_push_and_landmarks` _function_
- `test_root_level_index_falls_back_to_dir_name` _function_
- `test_slug_falls_back_to_relative_path_when_no_name` _function_

### `tests.test_ingest_graphproject`

- `test_alias_map_heals_a_drifted_reference` _function_
- `test_both_books_converge_on_shared_facets` _function_
- `test_corpus_graph_elements_counts` _function_
- `test_note_view_from_graph_node_dict` _function_
- `test_render_from_graph_nodes_matches_direct_render` _function_
- `test_topic_and_series_nodes_are_deduped_across_notes` _function_

### `tests.test_parse`

- `test_extract_headings` _function_
- `test_extract_wiki_links_dedup_order_preserved` _function_
- `test_extract_wiki_links_ignores_code_spans` _function_
- `test_parse_frontmatter_empty` _function_
- `test_parse_frontmatter_handles_colons_and_nesting` _function_
- `test_parse_markdown_end_to_end` _function_
- `test_parse_markdown_frontmatter_raw_is_lossless_prefix` _function_
- `test_split_frontmatter_absent` _function_
- `test_split_frontmatter_separates_block` _function_

### `tests.test_relations`

- `test_detect_profile` _function_
- `test_extract_drops_self_reference_cross_post_link` _function_
- `test_harvest_aliases_to_permalinks` _function_
- `test_harvest_categories_normalized_deduped` _function_
- `test_harvest_cross_post_links_with_anchors_and_code_stripped` _function_
- `test_harvest_relations_dispatches_by_profile` _function_
- `test_harvest_series_links` _function_
- `test_memory_corpus_unaffected` _function_
- `test_normalize_permalink_variants` _function_
- `test_slugify_normalizes` _function_
- `test_yaml_date_frontmatter_is_json_safe` _function_

### `tests.test_sections`

- `test_decompose_sections_order_levels_hierarchy` _function_
- `test_duplicate_heading_anchor_disambiguated` _function_
- `test_heading_anchor_matches_quarto_slug` _function_
- `test_lossless_body_starting_with_heading_has_no_preamble_node` _function_
- `test_lossless_no_headings_is_one_preamble_node` _function_
- `test_lossless_preamble_is_level0_order0_node` _function_
- `test_lossless_raw_spans_reconstruct_body_byte_exact` _function_
- `test_note_from_text_lossless_round_trip_and_frontmatter_raw` _function_
- `test_note_from_text_with_sections_emits_section_nodes` _function_
- `test_scope_a_carries_no_raw` _function_
- `test_section_text_is_verbatim_immediate_prose` _function_
- `test_structural_edges_membership_and_hierarchy` _function_

### `tests_manual.memory_body_roundtrip`

- `check` _function_
- `main` _function_
- `run` _function_

### `tests_manual.memory_roundtrip`

- `check` _function_
- `main` _function_
- `run` _function_

## Dependencies

**Depends on:** `cjm-dev-graph-schema`, `cjm-substrate`
**Used by:** `cjm-context-graph-projection`, `cjm-notebook-decompose-core`
