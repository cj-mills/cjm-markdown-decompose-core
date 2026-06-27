#!/usr/bin/env python
"""M1 round-trip: memory BODIES -> graph (extend_graph) -> byte-exact file text.

The sibling `memory_roundtrip.py` closes the INDEX loop (frontmatter -> MEMORY.md);
this closes the CONTENT loop — the M1 content-fidelity gate. It decomposes the real
memory corpus in LOSSLESS mode (each note keeps its verbatim `frontmatter_raw`; each
section keeps its heading-inclusive `raw` span + a level-0 preamble), ingests Note +
Section nodes through the REAL storage path, then reconstructs every file FROM THE
GRAPH (`frontmatter_raw + concat(section.raw in order)`) and asserts it is byte-for-
byte the original file. Memory is the high-stakes corpus (the sole human-readable
planning record), so the bar is whole-file byte-exact, not the posts' Scope-A grain.

Asserts:
  1. ingest counts: every Note + Section node added; resolved REFERENCES edges added.
  2. round-trip: for EVERY file, graph-reconstructed text == original file (byte-exact)
     AND the recomputed content hash matches the Note's stored hash.
  3. idempotency: a second extend_graph adds nothing (verify-collide) and the
     re-reconstruction is still byte-identical.

Needs the substrate runtime + the graph capability manifest — run in a core env that
has both (substrate + layer + primitives + the two arc libs installed editable):

    conda run -n cjm-transcript-correction-core --no-capture-output python \
        cjm-markdown-decompose-core/tests_manual/memory_body_roundtrip.py

A SCRATCH db is used; no real corpus/graph is touched.
"""
import argparse
import asyncio
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from cjm_substrate.core.manager import CapabilityManager
from cjm_substrate.core.queue import JobQueue
from cjm_context_graph_layer.ops import extend_graph, graph_task
from cjm_context_graph_primitives.provenance import SourceRef
from cjm_context_graph_primitives.query import NodeQuery

from cjm_markdown_decompose_core.extract import note_from_file
from cjm_markdown_decompose_core.ingest import corpus_graph_elements
from cjm_markdown_decompose_core.project import note_text_from_graph_nodes

GRAPH_ID = "cjm-capability-graph-sqlite"
DEFAULT_MEMORY = ("/home/innom-dt/.claude/projects/"
                  "-mnt-SN850X-8TB-EXT4-Projects-GitHub-cj-mills-cjm-substrate/memory")
DEFAULT_MANIFESTS = ("/mnt/SN850X_8TB_EXT4/Projects/GitHub/cj-mills/"
                     "cjm-transcript-correction-core/.cjm/manifests")


def check(name, cond):
    print(("  PASS " if cond else "  FAIL ") + name)
    return bool(cond)


def _prop(node, key, default=None):
    props = node.properties if hasattr(node, "properties") else node.get("properties", {})
    return props.get(key, default)


async def run(memory_dir: str, manifests_dir: str) -> bool:
    mem = Path(memory_dir)
    files = sorted(p for p in mem.glob("*.md"))  # include MEMORY.md (itself a memory file)
    originals = {str(p): p.read_text() for p in files}
    notes = [note_from_file(str(p), corpus_root=str(mem), lossless=True) for p in files]
    n_sections = sum(len(n.sections) for n in notes)
    nodes, edges = corpus_graph_elements(notes)
    node_ids = {n["id"] for n in nodes}
    resolved = sum(1 for e in edges if e["target_id"] in node_ids)

    scratch = Path(tempfile.mkdtemp(prefix="memory_body_roundtrip_")) / "scratch_graph.db"
    manager = CapabilityManager(search_paths=[Path(manifests_dir)])
    manager.discover_manifests()
    meta = {m.name: m for m in manager.discovered}[GRAPH_ID]
    assert manager.load_capability(meta, config={"db_path": str(scratch)}), "graph load failed"
    queue = JobQueue(deps=manager)
    await queue.start()
    ok = True
    try:
        # 1. Ingest the whole corpus (Note + Section nodes).
        r1 = await extend_graph(queue, GRAPH_ID, nodes, edges)
        ok &= check(f"1a: all {len(notes)} Note nodes added", r1.nodes_added >= len(notes))
        ok &= check(f"1b: all {n_sections} Section nodes added "
                    f"(total {len(nodes)} nodes incl Topic/Series)",
                    r1.nodes_added == len(nodes))
        ok &= check(f"1c: all {resolved} resolved edges added "
                    f"({len(edges) - resolved} dangling-target dropped — corpus-health finding)",
                    r1.edges_added == resolved)

        # 2. Reconstruct EVERY file FROM THE GRAPH; assert byte-exact + hash match.
        note_res = await graph_task(queue, GRAPH_ID, "query_nodes",
                                    query=NodeQuery(label="Note").to_dict())
        sec_res = await graph_task(queue, GRAPH_ID, "query_nodes",
                                   query=NodeQuery(label="Section").to_dict())
        note_nodes = note_res.nodes or []
        sec_nodes = sec_res.nodes or []
        ok &= check(f"2a: queried back {len(notes)} Note nodes", len(note_nodes) == len(notes))
        ok &= check(f"2b: queried back {n_sections} Section nodes", len(sec_nodes) == n_sections)

        secs_by_note = defaultdict(list)
        for s in sec_nodes:
            secs_by_note[_prop(s, "note_id")].append(s)

        exact, hash_ok = 0, 0
        by_path = {str(p): nd for p, nd in zip(files, notes)}
        for gnode in note_nodes:
            path = _prop(gnode, "path")
            recon = note_text_from_graph_nodes(gnode, secs_by_note.get(_node_id(gnode), []))
            if recon == originals.get(path):
                exact += 1
            else:
                _report_diff(path, recon, originals.get(path, ""))
            stored_hash = by_path[path].content_hash
            if SourceRef.compute_hash(recon.encode("utf-8")) == stored_hash:
                hash_ok += 1
        ok &= check(f"2c: {exact}/{len(notes)} files reconstruct BYTE-EXACT from the graph",
                    exact == len(notes))
        ok &= check(f"2d: {hash_ok}/{len(notes)} reconstructed hashes match the stored file hash",
                    hash_ok == len(notes))

        # 3. Idempotency: re-ingest adds nothing; re-reconstruction is byte-identical.
        r2 = await extend_graph(queue, GRAPH_ID, nodes, edges)
        ok &= check("3a: re-ingest adds 0 nodes (verify-collide)",
                    r2.nodes_added == 0 and r2.nodes_verified == len(nodes))
        ok &= check("3b: re-ingest adds 0 edges", r2.edges_added == 0)
        sec_res2 = await graph_task(queue, GRAPH_ID, "query_nodes",
                                    query=NodeQuery(label="Section").to_dict())
        note_res2 = await graph_task(queue, GRAPH_ID, "query_nodes",
                                     query=NodeQuery(label="Note").to_dict())
        secs2 = defaultdict(list)
        for s in (sec_res2.nodes or []):
            secs2[_prop(s, "note_id")].append(s)
        stable = all(
            note_text_from_graph_nodes(g, secs2.get(_node_id(g), [])) == originals.get(_prop(g, "path"))
            for g in (note_res2.nodes or []))
        ok &= check("3c: re-reconstruction still byte-exact for every file", stable)
    finally:
        await queue.stop()
        manager.unload_capability(GRAPH_ID)
    return ok


def _node_id(node):
    return node.id if hasattr(node, "id") else node.get("id")


def _report_diff(path, recon, orig):
    if len(recon) != len(orig):
        print(f"    LEN DIFF {Path(path).name}: recon={len(recon)} orig={len(orig)}")
    for i, (a, b) in enumerate(zip(recon, orig)):
        if a != b:
            print(f"    DIFF {Path(path).name} @{i}: recon={a!r} orig={b!r} "
                  f"ctx={orig[max(0, i - 20):i + 20]!r}")
            return


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--memory-dir", default=DEFAULT_MEMORY)
    ap.add_argument("--manifests-dir", default=DEFAULT_MANIFESTS)
    args = ap.parse_args()
    ok = asyncio.run(run(args.memory_dir, args.manifests_dir))
    print("MEMORY BODY ROUND-TRIP", "ALL CHECKS PASSED" if ok else "FAILURES")
    return 0 if ok else 1


sys.exit(main())
