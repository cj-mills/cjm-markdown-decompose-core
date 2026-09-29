"""Per-source-type relationship harvesting from parsed Markdown.

The `[[wiki-link]]` model (`parse.extract_wiki_links`) fits the memory corpus but
finds ~noise on richer corpora: a Quarto blog post encodes its real relationships
through frontmatter `categories`, `/series/...` page links, `/posts/...`
cross-post links (with section anchors), and `aliases` — none of which are
`[[wiki-links]]`. This module adds COMPOSABLE harvesters for those signals plus a
PROFILE dispatch that selects which harvesters run for a given source type.

Design (Fork A, user-endorsed): keep `parse` schema-free and general; add the
harvesters here as small composable functions, and select them per source type so
new formats (e.g. the frontmatter-less session scratchpads) slot in as a new
profile rather than a rewrite. `extract` binds the harvested `NoteRelations` onto
the `NoteNode` fields; this module returns plain data and carries no graph schema.
"""

import posixpath
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlsplit

import yaml

from .blocks import derived_blocks, DerivedBlock, mask_blocks
from .parse import ParsedMarkdown, strip_code

# A markdown inline-link target: the `(...)` of `[text](url)`, up to whitespace
# (a `"title"`) or the closing paren; an optional `<...>` autolink wrapper trimmed.
_MD_LINK_RE = re.compile(r"\]\(\s*<?([^)>\s]+)>?")
# `/posts/<permalink>` segment in a link target (absolute, relative, or full URL).
_POSTS_RE = re.compile(r"(?:^|/)posts/(.+)$")


def slugify(
    value: str,  # A raw category/tag string
) -> str:  # Normalized kebab-case key
    """Normalize a category/tag to a stable key (lowercased, separators collapsed).

    The Topic node id keys off this, so `PyTorch` and `pytorch` and `Py Torch`
    converge on one Topic. Identity normalization lives in the harvester (the
    schema's `topic_node_id` just keys off the result)."""
    s = re.sub(r"[\s_]+", "-", value.strip().lower())
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s


def _as_str_list(
    value: Any,  # A frontmatter value that may be a list, a scalar, or a comma string
) -> List[str]:  # Flattened list of non-empty trimmed strings
    """Coerce a frontmatter field to a list of strings (list | scalar | "a, b" )."""
    if value is None:
        return []
    if isinstance(value, str):
        return [p.strip() for p in value.split(",") if p.strip()]
    if isinstance(value, (list, tuple)):
        out: List[str] = []
        for v in value:
            if isinstance(v, str) and v.strip():
                out.append(v.strip())
        return out
    return []


def normalize_permalink(
    target: str,  # A link target pointing at a post (absolute/relative/full URL)
) -> Optional[str]:  # Bare permalink (path after `posts/`), or None when not a post link
    """Reduce a post link to its bare permalink — the path AFTER `posts/`.

    `/posts/x/`, `../x/`, `../../posts/x/`, and `https://…/posts/x/#a` all reduce to
    `x` (anchors are dropped by the caller first; `index.html`/trailing `/` removed).
    This is the SAME namespace as a post's slug when the corpus is ingested with
    `corpus_root` = the posts dir (bare permalinks), so a `REFERENCES` edge resolves
    onto the real Note. Returns None for links that are not post links."""
    m = _POSTS_RE.search(target)
    if not m:
        # A bare relative `../<slug>/` sibling link (no explicit `posts/` segment).
        if target.startswith("../") and "://" not in target:
            tail = target.lstrip("./")
        else:
            return None
    else:
        tail = m.group(1)
    tail = tail.split("#", 1)[0].strip("/")
    tail = re.sub(r"/?index\.html?$", "", tail)
    tail = re.sub(r"\.html?$", "", tail)
    return tail or None


def _bare_host(
    host: Optional[str],  # A URL host (any case, maybe `www.`-prefixed)
) -> str:  # The host lowercased, a leading `www.` dropped ('' when None)
    """Normalize a host for same-site comparison: `www.christianjmills.com` IS the site."""
    h = (host or "").lower()
    return h[4:] if h.startswith("www.") else h


def is_site_link(
    target: str,                     # A markdown link target
    site_url: Optional[str] = None,  # The site's own URL (its _quarto.yml site-url); None = unknown
) -> bool:  # True when the target points into the site itself
    """A link into the site: relative or rooted, or an absolute URL on the site's own host.

    A path segment never decides it alone: `pinecone.io/learn/series/faiss/hnsw/` carries a
    `/series/` segment and is another site (finding 0fadbbbd). A site links itself by
    absolute URL too, so a scheme alone does not make a link external; with no known site
    URL, every absolute URL is."""
    parts = urlsplit(target)
    if not parts.scheme and not parts.netloc:
        return True
    return bool(site_url) and _bare_host(parts.hostname) == _bare_host(urlsplit(site_url).hostname)


def quarto_site_url(
    path: Optional[str],  # A source file inside a Quarto project (None = unknown)
) -> Optional[str]:  # The project's `website.site-url`, or None
    """The site URL of the Quarto project a file belongs to (ruling 260119bf).

    Read from the nearest `_quarto.yml` above the file, the way Quarto finds a file's
    project, so every harvest (ingest, born notes, harvest-on-edit, replay) sees the value
    Quarto itself renders with and no second copy exists to drift. None when no project is
    found or it names no site-url."""
    if not path:
        return None
    for d in Path(path).absolute().parents:
        cfg = d / "_quarto.yml"
        if cfg.is_file():
            site = ((yaml.safe_load(cfg.read_text()) or {}).get("website") or {}).get("site-url")
            return site.strip() if isinstance(site, str) and site.strip() else None
    return None


def harvest_categories(
    frontmatter: Dict[str, Any],  # Parsed frontmatter
) -> List[str]:  # Normalized category keys (de-duplicated, order-preserved)
    """Harvest `categories` -> normalized Topic keys (the thematic-clustering facet)."""
    seen: Dict[str, None] = {}
    for c in _as_str_list(frontmatter.get("categories")):
        key = slugify(c)
        if key:
            seen.setdefault(key, None)
    return list(seen)


def harvest_aliases(
    frontmatter: Dict[str, Any],  # Parsed frontmatter
) -> List[str]:  # Alternate-identity permalinks (de-duplicated, order-preserved)
    """Harvest `aliases` (old URLs) -> bare permalinks (alternate identities).

    Normalized into the same permalink namespace as cross-post links so they can
    later seed an alias map (a cross-post link to an OLD url resolves to this note)."""
    seen: Dict[str, None] = {}
    for a in _as_str_list(frontmatter.get("aliases")):
        key = normalize_permalink(a) or a.split("#", 1)[0].strip("/")
        if key:
            seen.setdefault(key, None)
    return list(seen)


def is_page_target(
    target: str,  # A site link target (rooted, relative, or an own-site URL)
) -> bool:  # True when it names a PAGE (a directory, an .html page, or an extension-less path)
    """A link to a page, not to a file: an image, video or download beside a post is never a
    cross-reference. A bare `#anchor` names a place on the linking page itself, so it is none."""
    path = urlsplit(target).path
    if not path:
        return False
    ext = posixpath.splitext(path.rstrip("/"))[1].lower()
    return path.endswith("/") or ext in ("", ".html", ".htm")


def harvest_site_links(
    body: str,                       # Document body
    site_url: Optional[str] = None,  # The site's own URL (quarto_site_url); None = every absolute URL is external
) -> List[str]:  # Verbatim link targets, anchors kept (de-duplicated, order-preserved)
    """Harvest every in-body link to a site PAGE -> its VERBATIM target (ruling d31e9ba7).

    ONE harvest for every site link — a post (`/posts/x/`, `../x/`, `../../y/z/#anchor`), a
    series or topic page, a site page — kept verbatim: what the target IS lives in the
    `site_path` facts the journal replays after ingest, and a relative target resolves only
    against the linking page's own path, so the post-replay resolve pass maps it (DEC
    72d669c5) and reports what it cannot place. A link to a series page is a
    CROSS-REFERENCE, never membership (ruling 0f9ee9a8 (2)). Code spans are stripped first;
    only site links count (`is_site_link`: another site's `/series/` or `/posts/` path is not
    one, finding 0fadbbbd), and only page targets (`is_page_target`)."""
    seen: Dict[str, None] = {}
    for m in _MD_LINK_RE.finditer(strip_code(body)):
        target = m.group(1)
        if is_site_link(target, site_url) and is_page_target(target):
            seen.setdefault(target, None)
    return list(seen)


@dataclass
class NoteRelations:
    """The harvested relationship signals for one note (beyond `[[wiki-links]]`)."""
    categories: List[str] = field(default_factory=list)       # Normalized Topic keys
    site_refs: List[str] = field(default_factory=list)        # Verbatim site-link targets the resolve pass maps (every page link into the site)
    aliases: List[str] = field(default_factory=list)          # Alternate-identity permalinks


# A profile = the harvester for a source type: it takes (frontmatter, body, source path)
# and returns the NoteRelations it found; the path lets a profile find its project (the
# Quarto profile reads its site URL there).
_Harvester = Callable[[Dict[str, Any], str, Optional[str]], NoteRelations]


def _quarto_harvest(fm: Dict[str, Any], body: str, source_path: Optional[str] = None) -> NoteRelations:
    """The Quarto blog-post profile: categories + site links + aliases.

    Site links count only when they point into the post's own site, whose URL the post's
    Quarto project names (`quarto_site_url`, ruling 260119bf); every one of them, a post, a
    series page or any other page, is kept verbatim for the one resolver (ruling d31e9ba7)."""
    site_url = quarto_site_url(source_path)
    return NoteRelations(
        categories=harvest_categories(fm),
        site_refs=harvest_site_links(body, site_url),
        aliases=harvest_aliases(fm),
    )


def _memory_harvest(fm: Dict[str, Any], body: str, source_path: Optional[str] = None) -> NoteRelations:
    """The memory profile: relationships ride `[[wiki-links]]` (parse), nothing here."""
    return NoteRelations()


# Source-type profiles. Add a new format (e.g. "scratchpad") as a new entry.
PROFILES: Dict[str, _Harvester] = {
    "quarto_post": _quarto_harvest,
    "memory": _memory_harvest,
}


def detect_profile(
    frontmatter: Dict[str, Any],  # Parsed frontmatter ({} when none — no-frontmatter-safe)
) -> str:  # A key into PROFILES
    """Detect the source-type profile from the frontmatter shape.

    Quarto blog posts carry `categories` / `listing` / `date`; the memory corpus
    uses `metadata.type` + `[[wiki-links]]`. Frontmatter-less sources (the session
    scratchpads) fall through to `memory` until they earn their own profile — so
    detection must never assume frontmatter exists."""
    if any(k in frontmatter for k in ("categories", "listing", "date")):
        return "quarto_post"
    return "memory"


def harvest_relations(
    parsed: ParsedMarkdown,           # The parsed document
    profile: Optional[str] = None,    # Explicit profile key, or None to auto-detect
    source_path: Optional[str] = None,  # The document's file path (a profile may find its project from it)
    blocks: Optional[List[DerivedBlock]] = None,  # The body's derived blocks when the caller already classified them (None = classify here)
) -> NoteRelations:  # The harvested relationships
    """Harvest a note's relationships using its (detected or given) source profile.

    `profile=None` auto-detects from the frontmatter; pass an explicit profile to
    override (e.g. force `quarto_post` for a corpus the detector can't sniff). An
    unknown profile key falls back to `memory` (wiki-links only). `source_path` is
    handed to the profile: the Quarto profile reads its site URL from the post's
    project, so site links are told from other sites' links.

    The harvest reads the body with its DERIVED blocks blanked (`blocks.mask_blocks`,
    design 253ac996 (4)): a series callout's link restates the journaled membership, so
    a block is never a source of edges."""
    name = profile or detect_profile(parsed.frontmatter)
    harvest = PROFILES.get(name, _memory_harvest)
    if blocks is None:
        blocks = derived_blocks(parsed.body, name)
    return harvest(parsed.frontmatter, mask_blocks(parsed.body, blocks), source_path)
