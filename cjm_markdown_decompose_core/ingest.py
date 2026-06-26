"""Flatten decomposed notes into graph elements for idempotent extension.

The pure (queue-free) half of putting a corpus on the graph: turn `NoteNode`s
into the `(nodes, edges)` wire-dict lists that `cjm_context_graph_layer.ops.
extend_graph` commits. The queue/capability wiring itself is the projection-CLI
driver's concern (it owns the JobQueue + graph-storage capability); keeping the
flattening here makes it reusable and unit-testable without a running graph.
"""

from typing import Any, Dict, Iterable, List, Optional, Tuple

from cjm_dev_graph_schema.nodes import NoteNode, SeriesNode, TopicNode


def corpus_graph_elements(
    notes: Iterable[NoteNode],  # Decomposed notes
    aliases: Optional[Dict[str, str]] = None,  # Confirmed {drifted-slug: canonical-slug} link aliases
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:  # (node wire dicts, edge wire dicts)
    """Collect notes into the node + edge wire-dict lists `extend_graph` expects.

    One `Note` node per file plus its relationship edges — `REFERENCES`
    (`[[wiki-links]]` + cross-post links), `TAGGED` (categories), `IN_SERIES`
    (series membership) — and, when the note was decomposed `with_sections`, its
    `Section` nodes + `HAS_SECTION`/`PART_OF` edges (the body content + hierarchy).
    The shared facet nodes (`Topic` per category, `Series` per series) are emitted
    ONCE, deduped across the corpus, so independent notes sharing a category/series
    converge on one node. Deterministic ids make the result idempotent under
    `extend_graph` — re-ingesting collides into verified no-ops rather than
    duplicating.

    A confirmed `aliases` map resolves drifted link slugs to their canonical note
    before the edge is built, so a once-dangling `[[wiki-link]]` (or cross-post
    link) lands on the real note (slug-drift rot healed on-graph, file untouched)."""
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    topics: Dict[str, None] = {}   # distinct category keys (first-seen order)
    series: Dict[str, None] = {}   # distinct series keys (first-seen order)
    for n in notes:
        nodes.append(n.to_graph_node())
        edges.extend(n.reference_edges(aliases))
        edges.extend(n.cross_post_edges(aliases))
        edges.extend(n.tagged_edges())
        edges.extend(n.series_edges())
        for sec in n.sections:
            nodes.append(sec.to_graph_node())
            edges.extend(sec.structural_edges())
        for c in n.categories:
            topics.setdefault(c, None)
        for s in n.series_refs:
            series.setdefault(s, None)
    nodes.extend(TopicNode(key=k).to_graph_node() for k in topics)
    nodes.extend(SeriesNode(key=k).to_graph_node() for k in series)
    return nodes, edges
