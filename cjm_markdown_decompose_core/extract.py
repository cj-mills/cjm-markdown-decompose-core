"""Map parsed Markdown onto dev-graph-schema nodes (coarse tier).

This is the dev-domain binding: it turns a `ParsedMarkdown` into a `NoteNode`
(one coarse node per file) carrying the frontmatter-derived identity/metadata,
with the body's `[[wiki-links]]` available as `REFERENCES` edges. The pure
parsing it builds on (`parse`) stays schema-free; this module is where the
markdown corpus meets the dev schema.
"""

import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from cjm_context_graph_primitives.provenance import SourceRef
from cjm_dev_graph_schema.nodes import NoteNode

from .parse import parse_markdown, ParsedMarkdown
from .relations import harvest_relations
from .sections import decompose_sections


def _json_safe(
    value: Any,  # A parsed-frontmatter value (PyYAML may produce date/datetime, nested)
) -> Any:  # The same value with date/datetime coerced to ISO strings (recursively)
    """Coerce frontmatter values to JSON-serializable forms for the graph wire dict.

    PyYAML parses `date: 2023-8-21` into a Python `datetime.date` (and timestamps
    into `datetime`), which the metadata passthrough carries verbatim and the graph
    store then can't JSON-encode. Dates are stable identity-irrelevant metadata, so
    ISO strings are the faithful wire form (the memory corpus never hit this — it has
    no date frontmatter; the blog posts do)."""
    if isinstance(value, datetime.date):  # also catches datetime.datetime (a subclass)
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def slug_from(
    path: str,                       # The file path
    frontmatter: Dict[str, Any],     # Parsed frontmatter
    corpus_root: Optional[str] = None,  # Root to make the fallback slug relative to
) -> str:  # Stable note slug
    """Derive the stable slug: frontmatter `name` if present, else the path.

    The fallback is the corpus-relative path without extension (or the bare stem
    when no root is given) — stable as long as the file does not move, which is
    why an explicit frontmatter `name` is preferred for content that outlives its
    location.

    SSG convention (Quarto/Hugo/…): a `<dir>/index.md` file is identified by its
    DIRECTORY — the permalink — not the literal `index` stem. Otherwise every
    post in a `posts/<slug>/index.md` tree collapses onto one `index` slug (the
    corpus-findings identity collision). The post's stable identity is its
    directory path relative to the corpus root."""
    name = frontmatter.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    p = Path(path)
    # `<dir>/index.md` → identify by the directory (permalink); else drop the suffix.
    ident = p.parent if p.stem.lower() == "index" else p.with_suffix("")
    if corpus_root:
        try:
            rel = ident.relative_to(corpus_root)
        except ValueError:
            rel = Path(ident.name)
        # A root-level `index.md` relativizes to "." — fall back to the dir name.
        return rel.as_posix() if rel != Path(".") else ident.name
    return ident.name


def title_from(
    slug: str,                    # The note slug
    frontmatter: Dict[str, Any],  # Parsed frontmatter
) -> str:  # Display title
    """Derive a display title: explicit frontmatter `title`, else the slug titleized."""
    title = frontmatter.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return slug.replace("-", " ").replace("_", " ").strip().title()


def note_type_from(
    frontmatter: Dict[str, Any],  # Parsed frontmatter
) -> Optional[str]:  # Memory category (user | feedback | project | reference) or None
    """Read the memory category from `metadata.type` (None when absent)."""
    meta = frontmatter.get("metadata")
    if isinstance(meta, dict):
        t = meta.get("type")
        if isinstance(t, str) and t.strip():
            return t.strip()
    return None


def note_from_parsed(
    path: str,                # The file path (provenance locator)
    content_hash: str,        # Content hash over the file bytes
    parsed: ParsedMarkdown,   # The parsed document
    corpus_root: Optional[str] = None,  # Root for the fallback slug
    profile: Optional[str] = None,      # Relationship-harvest profile (None = auto-detect)
    with_sections: bool = False,        # Also decompose the body into Section nodes (notes corpus; off for the memory/dev corpus)
    lossless: bool = False,             # Lossless body-on-graph mode (memory corpus): verbatim per-section `raw` spans + level-0 preamble + verbatim `frontmatter_raw`, so the file round-trips byte-for-byte (M1). Implies sectioning
) -> NoteNode:  # The coarse Note node
    """Build a coarse `NoteNode` from already-parsed Markdown.

    Beyond the coarse identity/metadata, the per-source-type relationship
    harvesters (`relations`) add the corpus's real relationship signals —
    categories, series membership, cross-post links, aliases — selected by the
    detected (or given) source profile. A cross-post link to THIS post's own
    section is dropped (a self-reference is not a cross-post edge).

    Body content comes on-graph in one of two opt-in modes. `with_sections`
    (Scope A, the notes corpus) decomposes the body into navigable `Section` nodes
    at the section grain. `lossless` (M1, the high-stakes memory corpus) is the
    stronger form: it sections too, but each section carries its heading-inclusive
    verbatim `raw` span and the Note carries the verbatim `frontmatter_raw`, so the
    file reconstructs byte-for-byte (`frontmatter_raw + ''.join(s.raw in order)`).
    Both are off for plain coarse ingestion."""
    fm = parsed.frontmatter
    slug = slug_from(path, fm, corpus_root)
    description = fm.get("description")
    rel = harvest_relations(parsed, profile)
    own = {slug, Path(path).parent.name}  # this post's own permalink (both namespaces)
    cross = [(p, a) for (p, a) in rel.cross_post_refs if p not in own]
    note = NoteNode(
        slug=slug,
        title=title_from(slug, fm),
        path=path,
        content_hash=content_hash,
        description=description.strip() if isinstance(description, str) else "",
        note_type=note_type_from(fm),
        references=list(parsed.wiki_links),
        metadata={k: _json_safe(v) for k, v in fm.items()
                  if k not in ("name", "title", "description", "metadata")},
        categories=rel.categories,
        series_refs=rel.series_refs,
        aliases=rel.aliases,
        cross_post_refs=cross,
        frontmatter_raw=parsed.frontmatter_raw if lossless else "",
    )
    if with_sections or lossless:
        note.sections = decompose_sections(parsed.body, note.id, path, lossless=lossless)
    return note


def note_from_text(
    path: str,                          # The file path (provenance locator)
    text: str,                          # The full document text
    corpus_root: Optional[str] = None,  # Root for the fallback slug
    profile: Optional[str] = None,      # Relationship-harvest profile (None = auto-detect)
    with_sections: bool = False,        # Also decompose the body into Section nodes
    lossless: bool = False,             # Lossless body-on-graph mode (memory corpus); see note_from_parsed
) -> NoteNode:  # The coarse Note node
    """Parse + map in one step from in-memory text (hashes the UTF-8 bytes)."""
    return note_from_parsed(path, SourceRef.compute_hash(text.encode("utf-8")),
                            parse_markdown(text), corpus_root, profile, with_sections, lossless)


def note_from_file(
    path: str,                          # Path to the Markdown file
    corpus_root: Optional[str] = None,  # Root for the fallback slug
    profile: Optional[str] = None,      # Relationship-harvest profile (None = auto-detect)
    with_sections: bool = False,        # Also decompose the body into Section nodes
    lossless: bool = False,             # Lossless body-on-graph mode (memory corpus); see note_from_parsed
) -> NoteNode:  # The coarse Note node
    """Read a Markdown file and map it to a coarse `NoteNode`.

    The content hash is computed over the raw file bytes (faithful to the file as
    stored); the text is decoded as UTF-8 for parsing."""
    raw = Path(path).read_bytes()
    return note_from_parsed(path, SourceRef.compute_hash(raw),
                            parse_markdown(raw.decode("utf-8")), corpus_root, profile, with_sections, lossless)
