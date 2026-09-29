"""Embedded DERIVED blocks: spans of a body that are not the document's own content.

An archive post carries blocks another part of the site already states (design 253ac996,
work item 20b56bb7): the in-body series callout (membership is journaled on the Series,
38f1fd96), the hand-written table of contents (Quarto renders its own) and the hand
Previous / Next lines (the series order). Each is classified here, BEFORE heading
sectioning, so it becomes its own Section carrying a `block_role` and never counts as
content: the relation harvest skips it (`mask_blocks`), and the site build drops it from
the render and projects the replacement.

Classification is per source profile, like the relation harvest: a profile maps a body
to its derived blocks, and a profile with none (the memory corpus) returns nothing. The
rules are exact shapes, surveyed over the whole archive (zero false positives): a rule
that cannot tell a block from content leaves it content."""

import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Sequence, Tuple

from .parse import fenced_code_spans

SERIES_CALLOUT = "series_callout"    # the "part of the following series" callout
HAND_TOC = "hand_toc"                # the hand-written table of contents
SERIES_NAV_LINE = "series_nav_line"  # a hand "### Previous: [Part N](...)" / "Next:" line

# Every line-end anchor below allows a `\r`: some archive posts are CRLF files, and ingest
# decodes the bytes without newline translation (the lossless round trip).
# The series callout: a top-level callout-tip fence whose first line is one of the
# surveyed titles (113 posts), closed by the first bare `:::` line.
_CALLOUT_OPEN_RE = re.compile(r"^:::[ \t]*\{\.callout-tip\}[ \t]*\r?\n", re.M)
_CALLOUT_TITLES = (
    "## This post is part of the following series:",
    "## These notes are part of the following collection:",
    "## These notes are part of the following collections:",
)
_DIV_CLOSE_RE = re.compile(r"^:::[ \t]*\r?$\n?", re.M)
# A div fence line: an opener (`::: {.x}` / `::: name`) or a bare closer.
_DIV_LINE_RE = re.compile(r"^(:{3,})[ \t]*(.*?)[ \t]*\r?$")
# One hand-TOC item: a list line whose only content is a link to an in-page anchor.
_TOC_LINE_RE = re.compile(r"^[ \t]*[*-][ \t]+\[[^\]\n]*\]\(#[^)\n]*\)[ \t]*\r?$")
# A thematic break closing a hand TOC (the book-chapter posts' `-----`).
_RULE_LINE_RE = re.compile(r"^[ \t]*-{3,}[ \t]*\r?$")
# A hand series-navigation line: a heading holding only "Previous:" / "Next:" and links.
_NAV_LINE_RE = re.compile(
    r"^#{1,6}[ \t]+(?:Previous|Next):[ \t]*(?:\[[^\]\n]*\]\([^)\n]*\)[ \t]*)+\r?$\n?", re.M)
# The level-1/2 ATX heading that ends the region a hand TOC may sit in.
_TOP_HEADING_RE = re.compile(r"^#{1,2}[ \t]+\S")
# A markdown inline link's target (the `(...)` of `[text](url)`, an optional quoted title
# after it), for fingerprints. Pandoc accepts a spaced target (`(#Improving Our Model)`)
# and percent-escapes it, so the fingerprint applies the same escaping (`_pandoc_uri`).
_LINK_TARGET_RE = re.compile(r"\]\(\s*<?([^()\"<>]*?)>?(?:\s+\"[^\"]*\")?\s*\)")
# The characters Pandoc's escapeURI percent-escapes in a link target, besides whitespace.
_URI_ESCAPED = set('<>|"{}[]^`')


@dataclass(frozen=True)
class DerivedBlock:
    """One derived block: its role and its `[start, end)` span of the body."""
    role: str   # SERIES_CALLOUT | HAND_TOC | SERIES_NAV_LINE
    start: int  # Span start (character offset into the body)
    end: int    # Span end (exclusive), trailing blank lines included


def _in_spans(pos: int, spans: Sequence[Tuple[int, int]]) -> bool:
    return any(s <= pos < e for s, e in spans)


def _lines(body: str) -> List[Tuple[int, str]]:
    """(offset, line-with-newline) for every line of the body."""
    out, pos = [], 0
    for line in body.splitlines(keepends=True):
        out.append((pos, line))
        pos += len(line)
    return out


def _absorb_blank(body: str, end: int) -> int:
    """Extend a span end over the blank lines that follow it."""
    while end < len(body):
        nl = body.find("\n", end)
        line = body[end:] if nl < 0 else body[end:nl + 1]
        if line.strip():
            break
        end += len(line)
    return end


def find_series_callouts(
    body: str,  # Document body
) -> List[Tuple[int, int]]:  # [start, end) spans of the series callouts (blank lines after included)
    """The series callout(s): a top-level `::: {.callout-tip}` whose first line is a surveyed
    title, through its bare `:::` closer. Fenced code is skipped."""
    code = fenced_code_spans(body)
    out = []
    for m in _CALLOUT_OPEN_RE.finditer(body):
        if _in_spans(m.start(), code):
            continue
        first = body[m.end():].split("\n", 1)[0].rstrip()
        if first not in _CALLOUT_TITLES:
            continue
        close = _DIV_CLOSE_RE.search(body, m.end())
        if close is None:
            continue
        out.append((m.start(), _absorb_blank(body, close.end())))
    return out


def find_hand_toc(
    body: str,                             # Document body
    taken: Sequence[Tuple[int, int]] = (),  # Spans already classified (skipped)
) -> List[Tuple[int, int]]:  # The hand TOC's [start, end) span, or []
    """The hand table of contents: the FIRST run of two or more anchor-link list lines at
    div depth 0 (never inside a callout — an anchor list there is content), before the
    first level-1/2 heading, blank lines between items allowed. A thematic break right
    after the run belongs to the block (else the post would open on a bare rule)."""
    skip = list(fenced_code_spans(body)) + list(taken)
    lines = _lines(body)
    depth = 0
    i = 0
    while i < len(lines):
        off, line = lines[i]
        text = line.rstrip("\n")
        if _in_spans(off, skip):
            i += 1
            continue
        d = _DIV_LINE_RE.match(text)
        if d:
            depth = max(depth - 1, 0) if not d.group(2) else depth + 1
            i += 1
            continue
        if depth:   # inside a callout: its title heading and any anchor list are its own
            i += 1
            continue
        if _TOP_HEADING_RE.match(text):
            return []
        if not _TOC_LINE_RE.match(text):
            i += 1
            continue
        items, j, k = 0, i, i
        while k < len(lines) and not _in_spans(lines[k][0], skip):
            t = lines[k][1].rstrip("\n")
            if _TOC_LINE_RE.match(t):
                items, j = items + 1, k + 1
            elif not t.strip() and k + 1 < len(lines) and _TOC_LINE_RE.match(lines[k + 1][1].rstrip("\n")):
                pass
            else:
                break
            k += 1
        if items < 2:
            i = j
            continue
        end = lines[j][0] if j < len(lines) else len(body)
        end = _absorb_blank(body, end)
        nxt = body[end:].split("\n", 1)[0]
        if _RULE_LINE_RE.match(nxt):
            end = _absorb_blank(body, min(len(body), end + len(nxt) + 1))
        return [(off, end)]
    return []


def find_series_nav_lines(
    body: str,                             # Document body
    taken: Sequence[Tuple[int, int]] = (),  # Spans already classified (skipped)
) -> List[Tuple[int, int]]:  # [start, end) spans of the hand Previous / Next lines
    """Hand series-navigation lines: a heading holding only `Previous:` / `Next:` and links."""
    skip = list(fenced_code_spans(body)) + list(taken)
    return [(m.start(), _absorb_blank(body, m.end())) for m in _NAV_LINE_RE.finditer(body)
            if not _in_spans(m.start(), skip)]


def quarto_derived_blocks(
    body: str,  # A Quarto post body
) -> List[DerivedBlock]:  # Its derived blocks, in document order
    """The Quarto archive profile: series callouts, the hand TOC, hand series-nav lines.
    Blank lines between the body's start and its first block join that block, so no
    whitespace-only content section is left behind."""
    blocks = [DerivedBlock(SERIES_CALLOUT, s, e) for s, e in find_series_callouts(body)]
    taken = [(b.start, b.end) for b in blocks]
    blocks += [DerivedBlock(HAND_TOC, s, e) for s, e in find_hand_toc(body, taken)]
    taken = [(b.start, b.end) for b in blocks]
    blocks += [DerivedBlock(SERIES_NAV_LINE, s, e) for s, e in find_series_nav_lines(body, taken)]
    blocks.sort(key=lambda b: b.start)
    if blocks and blocks[0].start and not body[:blocks[0].start].strip():
        blocks[0] = DerivedBlock(blocks[0].role, 0, blocks[0].end)
    return blocks


# Source-type profiles (the keys of `relations.PROFILES`); a profile absent here has none.
DERIVED_BLOCK_PROFILES: Dict[str, Callable[[str], List[DerivedBlock]]] = {
    "quarto_post": quarto_derived_blocks,
}


def derived_blocks(
    body: str,     # Document body
    profile: str,  # The source profile key (already resolved, see `relations.detect_profile`)
) -> List[DerivedBlock]:  # The body's derived blocks, in document order ([] for a profile with none)
    """Classify a body's derived blocks under its source profile."""
    fn = DERIVED_BLOCK_PROFILES.get(profile)
    return fn(body) if fn else []


def mask_blocks(
    body: str,                         # Document body
    blocks: Sequence[DerivedBlock],   # Its derived blocks
) -> str:  # The body with every derived span blanked (newlines kept, so offsets hold)
    """The body a relation harvest reads: derived blocks contribute no edges (253ac996 (4))."""
    if not blocks:
        return body
    out, pos = [], 0
    for b in blocks:
        out.append(body[pos:b.start])
        out.append(re.sub(r"[^\n]", " ", body[b.start:b.end]))
        pos = b.end
    out.append(body[pos:])
    return "".join(out)


def block_link_targets(
    text: str,  # A derived block's verbatim text
) -> List[str]:  # Its inline-link targets, in order (duplicates kept)
    """A derived block's fingerprint for the render filter: its link targets as Pandoc hands
    them to a filter (text is typographically transformed, a target only URI-escaped)."""
    return [_pandoc_uri(m.group(1).strip()) for m in _LINK_TARGET_RE.finditer(text)]


def _pandoc_uri(
    target: str,  # A link target as written
) -> str:  # The target as Pandoc's reader stores it (whitespace and a few ASCII marks percent-escaped)
    return "".join("".join(f"%{b:02X}" for b in ch.encode("utf-8"))
                   if ch.isspace() or ch in _URI_ESCAPED else ch for ch in target)
