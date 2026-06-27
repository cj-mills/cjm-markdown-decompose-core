"""Schema-free Markdown parsing (stdlib + PyYAML).

Splits YAML frontmatter from the body, extracts `[[wiki-links]]`, and reads
ATX headings. Carries NO graph-schema dependency on purpose — this is the
genuinely-general layer, reusable for any Markdown corpus (memory files today,
blog posts tomorrow). The dev-domain binding lives in `extract`.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import yaml

# A frontmatter block is a leading `---` line, YAML, and a closing `---` line.
_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?", re.DOTALL)
# `[[target]]` wiki-link; the target is the inner text (a slug), trimmed.
_WIKI_LINK_RE = re.compile(r"\[\[([^\[\]]+?)\]\]")
# ATX heading: 1-6 leading `#`, then the text.
_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$", re.MULTILINE)
# Code spans, stripped before wiki-link extraction so QUOTED example syntax
# (`[[wiki-link]]` in prose ABOUT links) is not mistaken for a real reference:
# fenced blocks first (multi-line), then inline backtick runs (single-line).
_FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"(`+)(?:.+?)\1")


@dataclass
class ParsedMarkdown:
    """The structural decomposition of one Markdown document."""
    frontmatter: Dict[str, Any] = field(default_factory=dict)  # Parsed YAML frontmatter ({} if none)
    body: str = ""                                             # Document body (frontmatter stripped)
    wiki_links: List[str] = field(default_factory=list)       # `[[link]]` targets, de-duplicated in first-seen order
    headings: List[Tuple[int, str]] = field(default_factory=list)  # (level, text) per ATX heading, in document order
    frontmatter_raw: str = ""                                 # The VERBATIM frontmatter prefix (fences + YAML + trailing newline); "" when none. `frontmatter_raw + body == original text`, so it is the lossless round-trip source for the frontmatter (the parsed `frontmatter` dict is a derived projection)


def split_frontmatter(
    text: str,  # Full document text
) -> Tuple[Optional[str], str]:  # (raw frontmatter YAML or None, body)
    """Split a leading `---`-delimited YAML frontmatter block from the body.

    Returns `(None, text)` when there is no frontmatter (the body is the whole
    document); the leading delimiter must be the very first thing in the file."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None, text
    return m.group(1), text[m.end():]


def parse_frontmatter(
    raw: Optional[str],  # Raw frontmatter YAML (from split_frontmatter), or None
) -> Dict[str, Any]:  # Parsed mapping ({} when absent or non-mapping)
    """Parse frontmatter YAML into a dict (empty dict when absent).

    Non-mapping frontmatter (a bare scalar/list) yields `{}` — frontmatter is a
    metadata mapping by convention; anything else is ignored rather than guessed."""
    if not raw or not raw.strip():
        return {}
    loaded = yaml.safe_load(raw)
    return loaded if isinstance(loaded, dict) else {}


def strip_code(
    body: str,  # Document body
) -> str:  # Body with fenced + inline code spans blanked
    """Blank out fenced + inline code spans (replaced with a space, length-agnostic).

    Wiki-link extraction runs on the result so that `[[link]]` written inside
    backticks — example syntax in notes that DISCUSS links, not a real reference —
    is never picked up as an edge (the corpus-findings extraction false positive)."""
    return _INLINE_CODE_RE.sub(" ", _FENCED_CODE_RE.sub(" ", body))


def extract_wiki_links(
    body: str,  # Document body
) -> List[str]:  # `[[link]]` targets, de-duplicated in first-seen order
    """Extract `[[wiki-link]]` targets from the body, de-duplicated, order-preserved.

    The target is the trimmed inner text (a note slug); code spans are stripped
    first so quoted example syntax is excluded. Order and de-duplication are stable
    so the resulting REFERENCES edge set is deterministic across re-extraction."""
    seen: Dict[str, None] = {}
    for m in _WIKI_LINK_RE.finditer(strip_code(body)):
        target = m.group(1).strip()
        if target:
            seen.setdefault(target, None)
    return list(seen)


def extract_headings(
    body: str,  # Document body
) -> List[Tuple[int, str]]:  # (level, text) per ATX heading, in document order
    """Extract ATX headings (`#`..`######`) as (level, text) pairs."""
    return [(len(m.group(1)), m.group(2).strip()) for m in _HEADING_RE.finditer(body)]


def parse_markdown(
    text: str,  # Full document text
) -> ParsedMarkdown:  # The structural decomposition
    """Parse a Markdown document into frontmatter + body + wiki-links + headings."""
    raw_fm, body = split_frontmatter(text)
    # The verbatim frontmatter prefix is everything `split_frontmatter` consumed
    # (the leading `---` fence, YAML, closing fence, trailing newline) — i.e. the
    # bytes before `body`. Reconstructed losslessly as `text[:len(text)-len(body)]`
    # so that `frontmatter_raw + body == text` holds by construction ("" when none).
    return ParsedMarkdown(
        frontmatter=parse_frontmatter(raw_fm),
        body=body,
        wiki_links=extract_wiki_links(body),
        headings=extract_headings(body),
        frontmatter_raw=text[:len(text) - len(body)],
    )
