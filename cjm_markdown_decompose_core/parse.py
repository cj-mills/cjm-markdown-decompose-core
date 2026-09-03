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
# A fenced-code delimiter line (CommonMark): up to 3 spaces of indent, then a run of
# 3+ backticks or 3+ tildes, then whatever follows (an opener's info string; a closer
# allows only whitespace). `fenced_code_spans` pairs openers with closers.
_FENCE_LINE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


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


def fenced_code_spans(
    body: str,  # Document body
) -> List[Tuple[int, int]]:  # [(start, end)] character spans of fenced code blocks, in document order
    """Locate fenced code blocks (``` / ~~~) as character spans of the body.

    CommonMark fence rules at the grain that matters here: an opener is a line of
    3+ backticks or 3+ tildes (up to 3 spaces of indent; a backtick opener's info
    string may not itself contain a backtick), the block runs to the first line
    holding a closer of the same character at least as long as the opener with
    nothing else on it, and an unclosed fence runs to the end of the body. These
    spans are what heading detection SKIPS: a `# comment` line inside a
    ```python block is code, not an ATX heading (finding c1b976d0 — 3,414 such
    phantom headings across 81 of 207 posts; the timm tutorial's `# Function to
    run ...` opened a Section mid-code, losing the fence)."""
    spans: List[Tuple[int, int]] = []
    open_char, open_len, open_start = "", 0, 0
    pos = 0
    for line in body.splitlines(keepends=True):
        m = _FENCE_LINE_RE.match(line)
        if m:
            run, rest = m.group(1), m.group(2)
            if not open_char:
                if not (run[0] == "`" and "`" in rest):
                    open_char, open_len, open_start = run[0], len(run), pos
            elif run[0] == open_char and len(run) >= open_len and not rest.strip():
                spans.append((open_start, pos + len(line)))
                open_char = ""
        pos += len(line)
    if open_char:
        spans.append((open_start, len(body)))
    return spans


def find_headings(
    body: str,  # Document body
) -> List["re.Match[str]"]:  # ATX heading matches (group 1 = hashes, group 2 = text), fenced code skipped
    """The body's ATX heading matches, skipping every line inside a fenced code block.

    The ONE heading detector both `extract_headings` and the section splitter
    (`sections.decompose_sections`) read, so a `#` line inside a fence is never a
    heading on either path. Matches carry positions (`start`/`end`) so the splitter
    can slice section bodies between consecutive headings."""
    spans = fenced_code_spans(body)
    return [m for m in _HEADING_RE.finditer(body)
            if not any(s <= m.start() < e for s, e in spans)]


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
    return [(len(m.group(1)), m.group(2).strip()) for m in find_headings(body)]


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
