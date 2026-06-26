"""Runtime harness: decompose a real christianjmills/posts slice through the full
increment-2 pipeline (permalink identity + relationship harvesters + dedup) and
report the relationship graph that lights up — the Gatto cluster convergence."""
import collections, glob, os
from cjm_markdown_decompose_core.extract import note_from_file
from cjm_markdown_decompose_core.ingest import corpus_graph_elements
from cjm_dev_graph_schema.identity import series_node_id, topic_node_id

ROOT = "/mnt/990_PRO_4TB/Projects/GitHub/cj-mills/christianjmills/posts"
SLICE = ["pytorch-train-object-detector-yolox-tutorial", "tfjs-yolox-unity-tutorial",
         "the-learning-game-book-notes", "dumbing-us-down-book-notes",
         "weapons-of-mass-instruction-book-notes"]

notes = [note_from_file(f"{ROOT}/{s}/index.md", corpus_root=ROOT) for s in SLICE
         if glob.glob(f"{ROOT}/{s}/index.md")]
nodes, edges = corpus_graph_elements(notes)

nl = collections.Counter(n["label"] for n in nodes)
el = collections.Counter(e["relation_type"] for e in edges)
print("NODES:", dict(nl)); print("EDGES:", dict(el))

print("\n-- per note --")
for n in notes:
    print(f"  {n.slug:<46} cats={n.categories} series={n.series_refs} xpost={len(n.cross_post_refs)}")

# The cluster test: who TAGGED 'education' and who is IN the education-notes series?
edu_topic = topic_node_id("education")
edu_series = series_node_id("education-notes")
tagged_edu = [e["source_id"] for e in edges
              if e["relation_type"] == "TAGGED" and e["target_id"] == edu_topic]
in_edu = [e["source_id"] for e in edges
          if e["relation_type"] == "IN_SERIES" and e["target_id"] == edu_series]
id2slug = {n.id: n.slug for n in notes}
print(f"\nTAGGED 'education' ({len(tagged_edu)}): {[id2slug.get(i,'?') for i in tagged_edu]}")
print(f"IN education-notes series ({len(in_edu)}): {[id2slug.get(i,'?') for i in in_edu]}")
print(f"\n=> the 3 Gatto books converge: {sorted(set(id2slug.get(i) for i in in_edu))}")
