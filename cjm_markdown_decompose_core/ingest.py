"""Flatten decomposed notes into graph elements for idempotent extension.

The pure (queue-free) half of putting a corpus on the graph: turn `NoteNode`s
into the `(nodes, edges)` wire-dict lists that `cjm_context_graph_layer.ops.
extend_graph` commits. The queue/capability wiring itself is the projection-CLI
driver's concern (it owns the JobQueue + graph-storage capability); keeping the
flattening here makes it reusable and unit-testable without a running graph.
"""

from typing import Any, Dict, Iterable, List, Optional, Tuple

from cjm_dev_graph_schema.nodes import NoteNode


def corpus_graph_elements(
    notes: Iterable[NoteNode],  # Decomposed notes
    aliases: Optional[Dict[str, str]] = None,  # Confirmed {drifted-slug: canonical-slug} link aliases
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:  # (node wire dicts, edge wire dicts)
    """Collect notes into the node + edge wire-dict lists `extend_graph` expects.

    One `Note` node per file plus its `REFERENCES` edges. Deterministic ids make
    the result idempotent under `extend_graph` — re-ingesting the same corpus
    collides into verified no-ops rather than duplicating.

    A confirmed `aliases` map resolves drifted link slugs to their canonical note
    before the edge is built, so a once-dangling `[[wiki-link]]` lands on the real
    note (slug-drift rot healed on-graph, the flat file left untouched)."""
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    for n in notes:
        nodes.append(n.to_graph_node())
        edges.extend(n.reference_edges(aliases))
    return nodes, edges
