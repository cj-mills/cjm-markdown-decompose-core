#!/usr/bin/env python
"""Inc 1 round-trip: memory corpus -> graph (extend_graph) -> MEMORY.md projection.

The self-hosting loop closed through the REAL storage path: decompose the memory
files into Note nodes + REFERENCES edges, `extend_graph` them into a scratch
cjm-capability-graph-sqlite store via the JobQueue, then regenerate the MEMORY.md
index by QUERYING the graph (not the in-memory extraction). Asserts:

  1. ingest counts: every Note node + REFERENCES edge added.
  2. graph-projected index == directly-rendered index (the projection reads the
     graph faithfully).
  3. idempotency: a second extend_graph adds nothing (verify-collide) and the
     re-projected index is byte-identical (the "re-extraction idempotent" DoD).

Needs the substrate runtime + the graph capability manifest, so run in a core
env that has both (host imports: substrate + layer + primitives + the two new
libs installed editable):

    conda run -n cjm-transcript-correction-core --no-capture-output python \
        cjm-markdown-decompose-core/tests_manual/memory_roundtrip.py

A SCRATCH db is used; no real corpus/graph is touched.
"""
import argparse
import asyncio
import sys
import tempfile
from pathlib import Path

from cjm_substrate.core.manager import CapabilityManager
from cjm_substrate.core.queue import JobQueue
from cjm_context_graph_layer.ops import extend_graph, graph_task
from cjm_context_graph_primitives.query import NodeQuery

from cjm_markdown_decompose_core.extract import note_from_file
from cjm_markdown_decompose_core.ingest import corpus_graph_elements
from cjm_markdown_decompose_core.project import (
    render_memory_index, render_memory_index_from_graph_nodes,
)

GRAPH_ID = "cjm-capability-graph-sqlite"
DEFAULT_MEMORY = ("/home/innom-dt/.claude/projects/"
                  "-mnt-SN850X-8TB-EXT4-Projects-GitHub-cj-mills-cjm-substrate/memory")
DEFAULT_MANIFESTS = ("/mnt/SN850X_8TB_EXT4/Projects/GitHub/cj-mills/"
                     "cjm-transcript-correction-core/.cjm/manifests")


def check(name, cond):
    print(("  PASS " if cond else "  FAIL ") + name)
    return bool(cond)


async def run(memory_dir: str, manifests_dir: str) -> bool:
    mem = Path(memory_dir)
    files = sorted(p for p in mem.glob("*.md") if p.name != "MEMORY.md")
    notes = [note_from_file(str(p), corpus_root=str(mem)) for p in files]
    nodes, edges = corpus_graph_elements(notes)
    # A REFERENCES edge resolves only if its target slug names a known note.
    # Dangling targets (archived/unwritten memories, or [[link]]-vs-frontmatter-name
    # slug drift) point at absent nodes, and the store drops those edges — a real
    # corpus-health finding the graph makes visible, not a failure here.
    node_ids = {n["id"] for n in nodes}
    resolved = sum(1 for e in edges if e["target_id"] in node_ids)
    dangling = len(edges) - resolved

    scratch = Path(tempfile.mkdtemp(prefix="memory_roundtrip_")) / "scratch_graph.db"
    manager = CapabilityManager(search_paths=[Path(manifests_dir)])
    manager.discover_manifests()
    meta = {m.name: m for m in manager.discovered}[GRAPH_ID]
    assert manager.load_capability(meta, config={"db_path": str(scratch)}), "graph load failed"
    queue = JobQueue(deps=manager)
    await queue.start()
    ok = True
    try:
        # 1. Ingest the whole corpus.
        r1 = await extend_graph(queue, GRAPH_ID, nodes, edges)
        ok &= check(f"1a: all {len(nodes)} Note nodes added", r1.nodes_added == len(nodes))
        ok &= check(f"1b: all {resolved} resolved REFERENCES edges added "
                    f"({dangling} dangling-target edges dropped — corpus-health finding)",
                    r1.edges_added == resolved)

        # 2. Project the index FROM the graph; compare to the direct render.
        res = await graph_task(queue, GRAPH_ID, "query_nodes",
                               query=NodeQuery(label="Note").to_dict())
        queried = res.nodes or []
        ok &= check(f"2a: queried back {len(nodes)} Note nodes", len(queried) == len(nodes))
        from_graph = render_memory_index_from_graph_nodes(queried)
        direct = render_memory_index(notes)
        ok &= check("2b: graph-projected index == directly-rendered index", from_graph == direct)

        # 3. Idempotency: re-ingest adds nothing; re-projection is byte-identical.
        r2 = await extend_graph(queue, GRAPH_ID, nodes, edges)
        ok &= check("3a: re-ingest adds 0 nodes (verify-collide)",
                    r2.nodes_added == 0 and r2.nodes_verified == len(nodes))
        ok &= check("3b: re-ingest adds 0 edges", r2.edges_added == 0)
        res2 = await graph_task(queue, GRAPH_ID, "query_nodes",
                                query=NodeQuery(label="Note").to_dict())
        ok &= check("3c: re-projection byte-identical",
                    render_memory_index_from_graph_nodes(res2.nodes or []) == from_graph)
    finally:
        await queue.stop()
        manager.unload_capability(GRAPH_ID)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--memory-dir", default=DEFAULT_MEMORY)
    ap.add_argument("--manifests-dir", default=DEFAULT_MANIFESTS)
    args = ap.parse_args()
    ok = asyncio.run(run(args.memory_dir, args.manifests_dir))
    print("MEMORY ROUND-TRIP", "ALL CHECKS PASSED" if ok else "FAILURES")
    return 0 if ok else 1


sys.exit(main())
