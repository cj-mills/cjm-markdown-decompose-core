"""Per-source-type relationship harvesting from parsed Markdown.

The `[[wiki-link]]` model (`parse.extract_wiki_links`) fits the memory corpus but
finds ~noise on richer corpora: a Quarto blog post encodes its real relationships
through frontmatter `categories`, `/series/...` membership links, `/posts/...`
cross-post links (with section anchors), and `aliases` — none of which are
`[[wiki-links]]`. This module adds COMPOSABLE harvesters for those signals plus a
PROFILE dispatch that selects which harvesters run for a given source type.

Design (Fork A, user-endorsed): keep `parse` schema-free and general; add the
harvesters here as small composable functions, and select them per source type so
new formats (e.g. the frontmatter-less session scratchpads) slot in as a new
profile rather than a rewrite. `extract` binds the harvested `NoteRelations` onto
the `NoteNode` fields; this module returns plain data and carries no graph schema.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .parse import ParsedMarkdown, strip_code

# A markdown inline-link target: the `(...)` of `[text](url)`, up to whitespace
# (a `"title"`) or the closing paren; an optional `<...>` autolink wrapper trimmed.
_MD_LINK_RE = re.compile(r"\]\(\s*<?([^)>\s]+)>?")
# `/posts/<permalink>` segment in a link target (absolute, relative, or full URL).
_POSTS_RE = re.compile(r"(?:^|/)posts/(.+)$")
# `/series/<...>/<key>` segment in a link target.
_SERIES_RE = re.compile(r"(?:^|/)series/(.+)$")


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


def harvest_cross_post_links(
    body: str,  # Document body
) -> List[Tuple[str, str]]:  # (permalink, anchor) pairs, de-duplicated, order-preserved
    """Harvest `/posts/...` markdown links -> (permalink, section anchor) pairs.

    Code spans are stripped first (so URLs in example blocks are not mistaken for
    references — the same guard the wiki-link extractor uses). The anchor is kept
    (resolved to a section node later); de-duplication is on (permalink, anchor)."""
    seen: Dict[Tuple[str, str], None] = {}
    for m in _MD_LINK_RE.finditer(strip_code(body)):
        target = m.group(1)
        permalink = normalize_permalink(target)
        if not permalink:
            continue
        anchor = target.split("#", 1)[1] if "#" in target else ""
        seen.setdefault((permalink, anchor), None)
    return list(seen)


def harvest_series_links(
    body: str,  # Document body
) -> List[str]:  # Series keys (de-duplicated, order-preserved)
    """Harvest `/series/...` markdown links -> series keys (the membership signal).

    The series key is the link's final path segment without its extension
    (`/series/notes/education-notes.html` -> `education-notes`). These survive the
    callout flattening that drops the `:::`-fence structure (the link text is gone,
    but the link target — the real signal — is recovered here from the raw body)."""
    seen: Dict[str, None] = {}
    for m in _MD_LINK_RE.finditer(strip_code(body)):
        sm = _SERIES_RE.search(m.group(1))
        if not sm:
            continue
        last = sm.group(1).split("#", 1)[0].rstrip("/").split("/")[-1]
        key = re.sub(r"\.html?$", "", last)
        if key:
            seen.setdefault(key, None)
    return list(seen)


@dataclass
class NoteRelations:
    """The harvested relationship signals for one note (beyond `[[wiki-links]]`)."""
    categories: List[str] = field(default_factory=list)       # Normalized Topic keys
    series_refs: List[str] = field(default_factory=list)      # Series keys this note belongs to
    aliases: List[str] = field(default_factory=list)          # Alternate-identity permalinks
    cross_post_refs: List[Tuple[str, str]] = field(default_factory=list)  # (permalink, anchor) cross-post links


# A profile = the harvesters that apply to a source type. A harvester takes
# (frontmatter, body) and contributes to a NoteRelations via its target field.
_Harvester = Callable[[Dict[str, Any], str], None]


def _quarto_harvest(fm: Dict[str, Any], body: str) -> NoteRelations:
    """The Quarto blog-post profile: categories + series + cross-post + aliases."""
    return NoteRelations(
        categories=harvest_categories(fm),
        series_refs=harvest_series_links(body),
        aliases=harvest_aliases(fm),
        cross_post_refs=harvest_cross_post_links(body),
    )


def _memory_harvest(fm: Dict[str, Any], body: str) -> NoteRelations:
    """The memory profile: relationships ride `[[wiki-links]]` (parse), nothing here."""
    return NoteRelations()


# Source-type profiles. Add a new format (e.g. "scratchpad") as a new entry.
PROFILES: Dict[str, Callable[[Dict[str, Any], str], NoteRelations]] = {
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
    parsed: ParsedMarkdown,        # The parsed document
    profile: Optional[str] = None,  # Explicit profile key, or None to auto-detect
) -> NoteRelations:  # The harvested relationships
    """Harvest a note's relationships using its (detected or given) source profile.

    `profile=None` auto-detects from the frontmatter; pass an explicit profile to
    override (e.g. force `quarto_post` for a corpus the detector can't sniff). An
    unknown profile key falls back to `memory` (wiki-links only)."""
    name = profile or detect_profile(parsed.frontmatter)
    harvest = PROFILES.get(name, _memory_harvest)
    return harvest(parsed.frontmatter, parsed.body)
