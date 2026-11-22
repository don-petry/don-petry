#!/usr/bin/env python3
"""Fail-closed source verification gate for household advisory teams (legal, tax, health).

No authority or quotation leaves `drafts/` unverified. This script is the deterministic
half of that rule: the model drafts; this script decides whether what the draft cites
exists and says what the draft claims.

What it checks, per paragraph of the draft (hard-wrapped lines and `>` blockquotes
are joined first):

  * every authority cited, through the SOURCE ADAPTERS active for the matter (below);
  * anything that LOOKS like a citation but no active adapter recognizes (``Section
    6-2-8`` without §, ``S.E.2d``, ``WL``, ``42 U.S.C. 1983``, another state's code,
    court rules) — FAIL, because the gate cannot check it;
  * every quotation of 20+ characters in straight or curly double quotes, curly
    single quotes, or a ``>`` blockquote — it must appear, word for word after
    whitespace, case and quote-mark normalization, in a source cited in the same
    paragraph (for a blockquote, the paragraph before, itself, or the one after). Ellipses split it
    into segments of at least three words each; a bracketed alteration may replace at
    most 25 characters; every piece must match on word boundaries;
  * a case name written before a citation must match the case CourtListener returns
    (a significant word from EACH side of the "v.");
  * strategy text must not appear: ``--forbid TEXT`` (literal), ``--forbid-regex RE``,
    and every ``forbid:`` list under any block of the matter's ``project.yaml``
    (``advisory:``, ``legal:``, ``tax_wealth:`` …), read automatically on every run.

It does NOT check figures or dates. Those follow their own rules (engine provenance for
tax figures; a quoted document or the deadline calculation for dates), checked by the
``source-verifier`` persona. Every report says so.

Statuses are PASS, FAIL and BLOCKED only. BLOCKED (quota, outage, empty page, no token
for opinion text) counts as failure. "Still good law" is never checked — there is no
free citator — and every report says so.

Every source is fetched fresh on every run; nothing on disk is trusted as a cache. The
fetched text is saved to the matter's ``authorities/`` folder with URL, date and SHA-256
as evidence, and every run appends to ``authorities/verification-log.jsonl``. Agents
never write either by hand.

SOURCE ADAPTERS
---------------
Always on (federal law and national sources apply in every U.S. matter):

  federal  U.S. Code (Cornell LII) and C.F.R. (eCFR, the official edition; LII if eCFR
           is down) — ``15 U.S.C. § 1681i``, ``26 C.F.R. § 1.152-4``
  irs      IRS publications, current edition on irs.gov — ``IRS Pub. 969``; a year,
           ``IRS Pub. 969 (2025)``, must match the live edition or the item FAILs
  cases    case law through CourtListener — federal reporters always; a state's
           regional reporter (``So. 2d``) only when that state's adapter is active
  local    a document in the repository, cited ``[src: relative/path]``

Jurisdiction (state) adapters are selected per matter, first match wins:

  1. ``--jurisdiction AL`` (repeatable, or comma-separated);
  2. the matter's ``project.yaml`` → ``advisory.jurisdiction`` (e.g. ``[AL, federal]``);
  3. the ``VERIFY_SOURCES_JURISDICTION`` environment variable.

``federal`` in that list is a no-op (always on). A code with no adapter is reported as a
note; its citations then FAIL as unsupported — fail-closed. With no state adapter, a bare
``§ 26-1-1`` FAILs rather than being guessed at. ``--list-adapters`` prints the registry.

Built in: ``AL`` — Code of Alabama via ALISON, the Legislature's GraphQL API. It is the
EXAMPLE of a state adapter; copy its shape for your own state.

Writing an adapter: subclass ``Adapter``, set ``name`` (a postal code for a state),
``label``, ``kinds`` and, for a state, ``reporters`` (regex alternation of its regional
reporters, e.g. ``r"S\\.E\\.\\s?2d|S\\.E\\."``); implement ``extract(par)`` → list of
``Hit`` and ``fetch(kind, key, fetcher)`` → ``Fetched``; decorate the class with
``@register``. ``fetch`` raises ``NotFound`` when the source answered and the authority
does not exist, ``Blocked`` when it could not be checked. Use ``fetcher.get(url)`` for
HTTP so tests can replace the network. Load it with ``--adapter-file my_state.py``
(repeatable) or ``VERIFY_SOURCES_ADAPTER_FILES`` (path-separated). Use ``foreign_marker()``
so another state's ``§`` citation is never checked against yours.

Usage:
    python3 verify_sources.py DRAFT.md [--authorities DIR] [--jurisdiction CODE ...]
                              [--adapter-file PY ...] [--forbid TEXT ...]
                              [--forbid-regex RE ...] [--promote]
    python3 verify_sources.py --list-adapters

    --promote  on a clean pass, copy the draft from drafts/ to the sibling outbound/
               folder. Nothing else should ever put a file in outbound/.

Exit status: 0 = every item PASS; 1 = any FAIL or BLOCKED; 2 = usage error.

Environment: COURTLISTENER_TOKEN (optional) enables opinion text, so quotations from
cases can be checked, and raises the rate limit. Without it, case citations are
checked for existence and name only, and quotations from cases are BLOCKED.

Tests: test_verify_sources.py — python3 -m pytest, or python3 -m unittest.
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import html
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

PASS, FAIL, BLOCKED = "PASS", "FAIL", "BLOCKED"
USER_AGENT = "verify-sources/2.0 (citation checker for household advisory drafts; low volume)"
MIN_QUOTE = 20
MIN_SOURCE_CHARS = 200
MAX_BRACKET = 25          # longest bracketed alteration allowed inside a quotation
MIN_SEGMENT_WORDS = 3     # every ellipsis-separated segment must be at least this long
MAX_GAP = 40              # chars allowed between pieces split by a bracket, in the source

# ── core patterns (adapter-independent) ───────────────────────────────────────

FEDERAL_REPORTERS = (
    r"F\.\s?(?:2d|3d|4th)|F\.\s?Supp\.(?:\s?[23]d)?|F\.\s?App'x|"
    r"U\.S\.|S\.\s?Ct\.|L\.\s?Ed\.\s?2d|B\.R\."
)
USC = re.compile(r"\b(\d{1,2})\s+U\.S\.C\.\s*§+\s*(\d+[a-z]?(?:-\d+)?)")
CFR = re.compile(r"\b(\d{1,2})\s+C\.F\.R\.\s*§+\s*(\d+\.\d+[a-z]?(?:-\d+[A-Za-z]?)?)")  # Treasury regs: 1.152-4
IRS_PUB = re.compile(r"\b(?:IRS\s+)?Pub(?:lication|\.)\s*(?:No\.\s*)?(\d{1,4}(?:-?[A-Z])?)\b(?:\s*\((\d{4})\))?")
SRC = re.compile(r"\[src:\s*([^\]]+?)\s*\]")
STATE_SECTION_SHAPE = re.compile(r"§+\s*\d{1,3}[A-Z]?-\d")

# Anything shaped like a citation. Whatever these match OUTSIDE a recognized citation
# is an unsupported form and fails.
LOOSE_CITES = [
    re.compile(r"§+\s*[\w.()-]+"),
    re.compile(r"\b[Ss]ec(?:tion|s?\.)\s+\d+[A-Z]?(?:-\d+[A-Z]?)+(?:\.\d+)?"),
    re.compile(r"\b\d+\s+U\.?\s?S\.?\s?C\.?\s*(?:A\.?\s*)?(?:§+\s*)?\d"),
    re.compile(r"\b\d+\s+C\.?\s?F\.?\s?R\.?\s*(?:§+\s*|[Pp]art\s+)?\d"),
    re.compile(r"\b\d{4}\s+WL\s+\d+"),
    re.compile(r"\b\d{1,4}\s+(?:[A-Z][A-Za-z']{0,5}\.\s?){1,4}(?:[23]d|4th)?\s?\d{1,5}\b"),
    re.compile(r"\b(?:[A-Z][a-z]{0,4}\.\s*)?R\.\s*(?:Civ|App|Evid|Crim)\.?"),   # court rules, any forum
    re.compile(r"\b[A-Z][a-z]{1,4}\.\s*Admin\.\s*Code"),                        # state administrative codes
]
REPORTER_LIKE = 5
NOT_A_REPORTER = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|No|Nos|Mr|Mrs|Ms|Dr|St|Ave|Rd|Blvd|Ste|Hwy|Pt|Pts|Vol|p|pp)\.",
)

QUOTE_PATTERNS = [
    re.compile(r"[“\"]([^“”\"]{%d,}?)[”\"]" % MIN_QUOTE),
    re.compile(r"‘(.{%d,}?)’(?![A-Za-z])" % MIN_QUOTE),
]
BRACKET = re.compile(r"\[([^\]]*)\]")
ELLIPSIS = re.compile(r"\s*(?:\.\s?\.\s?\.|…)\s*")
STOP_WORDS = {"see", "also", "cf", "cf.", "e.g.", "accord", "in", "under", "and", "the", "of", "a", "an", "but"}
GENERIC_NAME_WORDS = STOP_WORDS | {
    "co", "inc", "ins", "auto", "mut", "corp", "llc", "state", "united", "states", "county", "city",
    "company", "insurance", "ex", "parte", "re",
}

# U.S. jurisdictions: postal code → (name, citation abbreviations as regex). Used to keep a
# state adapter from checking another state's "§" citation against its own code.
JURISDICTIONS = {
    "AL": ("Alabama", r"Ala\."), "AK": ("Alaska", r"Alaska"), "AZ": ("Arizona", r"Ariz\."),
    "AR": ("Arkansas", r"Ark\."), "CA": ("California", r"Cal\."), "CO": ("Colorado", r"Colo\."),
    "CT": ("Connecticut", r"Conn\."), "DE": ("Delaware", r"Del\."), "DC": ("District of Columbia", r"D\.C\."),
    "FL": ("Florida", r"Fla\."), "GA": ("Georgia", r"Ga\.|O\.C\.G\.A\.?"), "HI": ("Hawaii", r"Haw\."),
    "ID": ("Idaho", r"Idaho"), "IL": ("Illinois", r"Ill\.|ILCS"), "IN": ("Indiana", r"Ind\."),
    "IA": ("Iowa", r"Iowa"), "KS": ("Kansas", r"Kan\."), "KY": ("Kentucky", r"Ky\."),
    "LA": ("Louisiana", r"La\."), "ME": ("Maine", r"Me\."), "MD": ("Maryland", r"Md\."),
    "MA": ("Massachusetts", r"Mass\."), "MI": ("Michigan", r"Mich\."), "MN": ("Minnesota", r"Minn\."),
    "MS": ("Mississippi", r"Miss\."), "MO": ("Missouri", r"Mo\."), "MT": ("Montana", r"Mont\."),
    "NE": ("Nebraska", r"Neb\."), "NV": ("Nevada", r"Nev\."), "NH": ("New Hampshire", r"N\.H\."),
    "NJ": ("New Jersey", r"N\.J\."), "NM": ("New Mexico", r"N\.M\."), "NY": ("New York", r"N\.Y\."),
    "NC": ("North Carolina", r"N\.C\."), "ND": ("North Dakota", r"N\.D\."), "OH": ("Ohio", r"Ohio"),
    "OK": ("Oklahoma", r"Okla\."), "OR": ("Oregon", r"Or\."), "PA": ("Pennsylvania", r"Pa\."),
    "RI": ("Rhode Island", r"R\.I\."), "SC": ("South Carolina", r"S\.C\."), "SD": ("South Dakota", r"S\.D\."),
    "TN": ("Tennessee", r"Tenn\."), "TX": ("Texas", r"Tex\."), "UT": ("Utah", r"Utah"),
    "VT": ("Vermont", r"Vt\."), "VA": ("Virginia", r"Va\."), "WA": ("Washington", r"Wash\."),
    "WV": ("West Virginia", r"W\.\s?Va\."), "WI": ("Wisconsin", r"Wis\."), "WY": ("Wyoming", r"Wyo\."),
}
FEDERAL_CODES = {"FEDERAL", "US", "USA", "FED"}


class NotFound(Exception):
    """The source answered and the authority does not exist there."""


class Blocked(Exception):
    """The source could not be checked (quota, outage, empty page, no token)."""


@dataclass
class Hit:
    """One citation an adapter found in a paragraph."""
    kind: str          # adapter-defined, e.g. "al-code", "usc"; core kinds: "other", "unrecognized"
    key: str           # canonical id, e.g. "26-1-1", "388 So. 2d 1207"
    display: str
    span: tuple
    name_hint: str = ""


@dataclass
class Fetched:
    url: str
    text: str | None   # None only when the source confirms existence but has no text (no token)
    name: str = ""     # case name, for cases


@dataclass
class Authority:
    kind: str          # e.g. al-code | case | usc | cfr | irs-pub | src | other | unrecognized
    key: str
    display: str
    paragraph: int
    name_hint: str = ""
    status: str = ""
    reason: str = ""
    url: str = ""
    snapshot: str = ""
    text: str | None = None


@dataclass
class Quote:
    text: str
    paragraphs: tuple
    status: str = ""
    reason: str = ""
    matched: str = ""


@dataclass
class Report:
    draft: str
    authorities: list = field(default_factory=list)
    quotes: list = field(default_factory=list)
    forbidden: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    adapters: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        items = self.authorities + self.quotes
        return all(i.status == PASS for i in items) and not self.forbidden and not self.errors


# ── text helpers ──────────────────────────────────────────────────────────────


def strip_html(s: str) -> str:
    s = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def norm(s: str) -> str:
    s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    s = s.replace(" ", " ").replace("—", "-").replace("–", "-")
    return re.sub(r"\s+", " ", s).strip().lower()


def norm_cite(s: str) -> str:
    return re.sub(r"\s+", "", s).lower()


def paragraphs(text: str) -> list[str]:
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


def flatten(par: str) -> str:
    """Join hard-wrapped lines and drop blockquote markers."""
    par = re.sub(r"(?m)^\s*>\s?", "", par)
    return re.sub(r"\s*\n\s*", " ", par).strip()


def blockquotes(par: str) -> list[str]:
    """Each run of consecutive `>` lines in a paragraph, joined into one string."""
    out, cur = [], []
    for ln in par.splitlines():
        if ln.lstrip().startswith(">"):
            cur.append(re.sub(r"^\s*>\s?", "", ln))
        elif cur:
            out.append(" ".join(cur)); cur = []
    if cur:
        out.append(" ".join(cur))
    return [re.sub(r"\s+", " ", b).strip() for b in out if b.strip()]


def _find_piece(hay: str, piece: str, start: int, open_left: bool, open_right: bool, limit: int | None):
    left = "" if open_left else r"(?<!\w)"
    right = "" if open_right else r"(?!\w)"
    m = re.compile(left + re.escape(piece) + right).search(hay, start)
    if not m or (limit is not None and m.start() > limit):
        return None
    return m


def check_quote(quote: str, source: str) -> tuple[bool, str]:
    """Every piece of the quotation appears in the source, in order, on word boundaries."""
    q = quote.strip().rstrip(".,;:").strip()
    for b in BRACKET.findall(q):
        if len(b) > MAX_BRACKET:
            return False, f"bracketed text '[{b[:30]}…]' is longer than an alteration ({MAX_BRACKET} chars)"
    segments = [s for s in ELLIPSIS.split(q) if s.strip()]
    if not segments:
        return False, "empty quotation"
    for s in segments:
        if len(BRACKET.sub(" ", s).split()) < MIN_SEGMENT_WORDS:
            return False, f"fragment '{s.strip()[:30]}' is too short to verify (under {MIN_SEGMENT_WORDS} words)"
    hay = norm(source)
    pos = 0
    for seg in segments:
        parts = re.split(r"(\[[^\]]*\])", seg)
        pieces = []  # (text, open_left, open_right)
        for idx, part in enumerate(parts):
            if part.startswith("[") or not part.strip():
                continue
            left_br = idx > 0 and parts[idx - 1].startswith("[") and not part[:1].isspace()
            right_br = idx + 1 < len(parts) and parts[idx + 1].startswith("[") and not part[-1:].isspace()
            pieces.append((norm(part), left_br, right_br))
        first = True
        for text, ol, orr in pieces:
            m = _find_piece(hay, text, pos, ol, orr, None if first else pos + MAX_GAP)
            if first:
                # retry from later matches if the rest of the segment doesn't follow
                while m:
                    p2, ok = m.end(), True
                    for t2, ol2, or2 in pieces[1:]:
                        m2 = _find_piece(hay, t2, p2, ol2, or2, p2 + MAX_GAP)
                        if not m2:
                            ok = False
                            break
                        p2 = m2.end()
                    if ok:
                        pos = p2
                        break
                    m = _find_piece(hay, text, m.start() + 1, ol, orr, None)
                if not m:
                    return False, "not found word-for-word"
                break
        if not pieces:
            return False, "no checkable text"
    return True, ""


def quote_found(quote: str, source: str) -> bool:
    return check_quote(quote, source)[0]


def _sig_words(side: str) -> set[str]:
    words = [w.lower().strip(".,'") for w in re.findall(r"[A-Za-z][A-Za-z'.&-]*", side)]
    words = [w for w in words if w and w not in STOP_WORDS]
    sig = {w for w in words if w not in GENERIC_NAME_WORDS and len(w) >= 3}
    return sig or set(words)


def case_name_before(par: str, start: int) -> tuple[set, set] | None:
    """Parties written just before a citation, as (left words, right words)."""
    before = par[max(0, start - 200):start]
    m = re.search(r"Ex parte\s+([A-Z][\w.'&-]*(?:\s+[A-Z][\w.'&-]*){0,4})\s*,?\s*$", before)
    if m:
        return _sig_words(m.group(1)), set()
    m = re.search(r"((?:[A-Z][\w.'&-]*\s+){0,6}[A-Z][\w.'&-]*)\s+v\.\s+([^,;()]+?)\s*,?\s*$", before)
    if not m:
        return None
    return _sig_words(m.group(1)), _sig_words(m.group(2))


def name_matches(parties: tuple[set, set], case_name: str) -> bool:
    name = case_name.lower()

    def has(words: set) -> bool:
        return any(re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", name) for w in words)

    left, right = parties
    return has(left) and (not right or has(right))


_FOREIGN_CACHE: dict[str, re.Pattern] = {}


def foreign_marker(window: str, own: str) -> str | None:
    """Another jurisdiction's name or code abbreviation just before a '§' (within 20 chars).

    `window` is the text preceding the citation; `own` is the adapter's postal code.
    Returns the marker found, or None.
    """
    rx = _FOREIGN_CACHE.get(own)
    if rx is None:
        alts = []
        for code, (name, abbr) in JURISDICTIONS.items():
            if code != own:
                alts += [re.escape(name), abbr, r"\b" + code + r"\b"]
        rx = re.compile(r"(?<![A-Za-z.])(" + "|".join(alts) + r")[^§\n]{0,20}$")
        _FOREIGN_CACHE[own] = rx
    m = rx.search(window)
    return m.group(1) if m else None


# ── fetching ──────────────────────────────────────────────────────────────────


def repo_root(start: pathlib.Path) -> pathlib.Path:
    """The git repository holding the draft; outside a repo, the matter folder."""
    for d in [start, *start.parents]:
        if (d / ".git").exists():
            return d
    return start.parent if start.name == "drafts" else start


class Fetcher:
    """Network and file access shared by every adapter. Tests replace `get`."""

    def __init__(self, token: str | None = None, base_dir: pathlib.Path | None = None,
                 draft: pathlib.Path | None = None):
        self.token = token
        self.base_dir = base_dir or pathlib.Path.cwd()
        self.draft = draft.resolve() if draft else None
        self._last_cl = 0.0

    def get(self, url: str, data: bytes | None = None, headers: dict | None = None) -> str:
        """HTTP GET (or POST with `data`). 404 → NotFound; any other failure → Blocked."""
        h = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip", **(headers or {})}
        req = urllib.request.Request(url, data=data, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                if r.status == 202:
                    raise Blocked(f"{url} answered 202 with a bot challenge")
                raw = r.read()
                if (r.headers.get("Content-Encoding") or "").lower() == "gzip":
                    raw = gzip.decompress(raw)
                return raw.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise NotFound(f"{url} returned 404")
            raise Blocked(f"{url} returned HTTP {e.code}")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise Blocked(f"{url} unreachable: {e}")

    def cl_json(self, url: str) -> dict:
        """CourtListener API call, with the token if set and the anonymous rate limit if not."""
        headers = {"Authorization": f"Token {self.token}"} if self.token else {}
        if not self.token:  # anonymous limit is 5/min
            wait = 13 - (time.time() - self._last_cl)
            if wait > 0 and self._last_cl:
                time.sleep(wait)
        self._last_cl = time.time()
        try:
            return json.loads(self.get(url, headers=headers))
        except json.JSONDecodeError:
            raise Blocked("CourtListener answered with non-JSON")

    def src(self, rel: str) -> tuple[str, str]:
        p = (self.base_dir / rel).resolve()
        root = repo_root(self.base_dir.resolve())
        if root != p and root not in p.parents:
            raise NotFound(f"local source {rel} is outside the repository")
        if self.draft and p == self.draft:
            raise NotFound("a draft cannot be its own source")
        if any(part in ("drafts", "outbound", "authorities") for part in p.relative_to(root).parts[:-1]):
            raise NotFound(f"local source {rel} is a draft or generated file, not an original document")
        if not p.is_file():
            raise NotFound(f"local source {rel} does not exist or is not a file")
        if p.suffix.lower() == ".pdf":
            if not shutil.which("pdftotext"):
                raise Blocked("pdftotext is not installed (poppler) — cannot read the PDF")
            out = subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, text=True, timeout=60)
            text = out.stdout
        else:
            text = p.read_text(encoding="utf-8", errors="replace")
            if p.suffix.lower() in (".html", ".htm"):
                text = strip_html(text)
        if len(text.strip()) < 40:
            raise Blocked(f"local source {rel} has no extractable text")
        return str(p), text


# ── adapters ──────────────────────────────────────────────────────────────────


class Adapter:
    """A source adapter: finds one family of citations and fetches their primary source.

    Subclass, set the class attributes, implement `extract` and `fetch`, and decorate with
    `@register` (state adapters) — see the module docstring.
    """
    name = ""          # registry key; a postal code ("AL") for a state adapter
    label = ""         # one line for reports and --list-adapters
    state = False      # True: selected per matter by jurisdiction
    example = False    # True: shipped as a worked example, not a claim of coverage
    kinds: tuple = ()  # Authority kinds this adapter fetches
    reporters = ""     # state adapters: regex alternation of regional case reporters

    def extract(self, par: str) -> list[Hit]:
        raise NotImplementedError

    def fetch(self, kind: str, key: str, fetcher: Fetcher) -> Fetched:
        raise NotImplementedError


STATE_ADAPTERS: dict[str, type[Adapter]] = {}


def register(cls: type[Adapter]) -> type[Adapter]:
    """Class decorator: make a state adapter selectable by its `name`."""
    if not cls.name:
        raise ValueError(f"{cls.__name__} has no name")
    STATE_ADAPTERS[cls.name.upper()] = cls
    return cls


@register
class AlabamaCode(Adapter):
    """EXAMPLE state adapter: Code of Alabama through ALISON, the Legislature's GraphQL API."""
    name = "AL"
    label = "Code of Alabama via ALISON GraphQL (the Legislature's official text) — example state adapter"
    state = True
    example = True
    kinds = ("al-code",)
    reporters = r"So\.\s?[23]d|So\."
    SEC = r"\d{1,2}[A-Z]?-\d{1,3}[A-Z]?-\d{1,4}(?:\.\d+)?"
    CITE = re.compile(r"§§?\s*(" + SEC + r"(?:\s*(?:,|and|&|to|through)\s*" + SEC + r")*)")
    SECTION = re.compile(SEC)

    def extract(self, par: str) -> list[Hit]:
        hits = []
        for m in self.CITE.finditer(par):
            other = foreign_marker(par[max(0, m.start() - 40):m.start()], self.name)
            if other:
                key = f"{other} § {m.group(1)}"
                hits.append(Hit("other", key, key, m.span()))
                continue
            for sec in self.SECTION.findall(m.group(1)):
                hits.append(Hit("al-code", sec, f"Ala. Code § {sec}", m.span()))
        return hits

    def fetch(self, kind: str, key: str, fetcher: Fetcher) -> Fetched:
        q = ("query($d:String){codesOfAlabama(where:{type:{eq:Section},displayId:{eq:$d}})"
             "{data{displayId catchLine content}}}")
        url = "https://alison.legislature.state.al.us/graphql"
        body = json.dumps({"query": q, "variables": {"d": key}}).encode()
        raw = fetcher.get(url, body, {"content-type": "application/json"})
        try:
            rows = json.loads(raw)["data"]["codesOfAlabama"]["data"]
        except (KeyError, TypeError, json.JSONDecodeError):
            raise Blocked("ALISON GraphQL answered in an unexpected shape")
        if not rows:
            raise NotFound(f"ALISON has no section {key}")
        row = rows[0]
        text = strip_html(f"{row.get('catchLine') or ''}. {row.get('content') or ''}")
        if len(text) < 40:
            raise Blocked(f"ALISON returned an empty section {key}")
        return Fetched(f"https://alison.legislature.state.al.us/code-of-alabama?section={key}", text)


class CaseLaw(Adapter):
    """Reported cases through CourtListener (national)."""
    name = "cases"
    label = "Case law via CourtListener v4 — federal reporters, plus regional reporters of active state adapters"
    kinds = ("case",)

    def __init__(self, state_reporters: list[str] = ()):
        alts = [r for r in state_reporters if r] + [FEDERAL_REPORTERS]
        self.cite = re.compile(r"\b(\d{1,4})\s+(" + "|".join(alts) + r")\s+(\d{1,5})\b")

    def extract(self, par: str) -> list[Hit]:
        hits = []
        for m in self.cite.finditer(par):
            reporter = re.sub(r"\s+", " ", m.group(2))
            key = f"{m.group(1)} {reporter} {m.group(3)}"
            parties = case_name_before(par, m.start())
            hint = json.dumps([sorted(p) for p in parties]) if parties else ""
            hits.append(Hit("case", key, key, m.span(), hint))
        return hits

    def fetch(self, kind: str, key: str, fetcher: Fetcher) -> Fetched:
        q = urllib.parse.quote_plus(f'"{key}"')
        data = fetcher.cl_json(f"https://www.courtlistener.com/api/rest/v4/search/?q={q}&type=o")
        want = norm_cite(key)
        for r in data.get("results", []):
            if any(norm_cite(c) == want for c in r.get("citation", [])):
                url = "https://www.courtlistener.com" + r.get("absolute_url", "")
                text = None
                if fetcher.token and r.get("cluster_id"):
                    ops = fetcher.cl_json(f"https://www.courtlistener.com/api/rest/v4/opinions/?cluster={r['cluster_id']}")
                    parts = []
                    for op in ops.get("results", []):
                        for k in ("html_with_citations", "html_lawbox", "html_columbia", "html", "plain_text", "xml_harvard"):
                            if op.get(k):
                                parts.append(strip_html(op[k]))
                                break
                    text = " ".join(parts) or None
                return Fetched(url, text, r.get("caseName", ""))
        raise NotFound(f"CourtListener has no opinion reported at {key}")


class Federal(Adapter):
    """U.S. Code (Cornell LII) and C.F.R. (eCFR, LII fallback)."""
    name = "federal"
    label = "U.S. Code via Cornell LII; C.F.R. via eCFR (official), Cornell LII if eCFR is unreachable"
    kinds = ("usc", "cfr")

    def extract(self, par: str) -> list[Hit]:
        hits = [Hit("usc", f"{m.group(1)}/{m.group(2)}", f"{m.group(1)} U.S.C. § {m.group(2)}", m.span())
                for m in USC.finditer(par)]
        hits += [Hit("cfr", f"{m.group(1)}/{m.group(2)}", f"{m.group(1)} C.F.R. § {m.group(2)}", m.span())
                 for m in CFR.finditer(par)]
        return hits

    def _lii(self, kind: str, key: str, fetcher: Fetcher) -> Fetched:
        title, sec = key.split("/", 1)
        path = "uscode/text" if kind == "usc" else "cfr/text"
        url = f"https://www.law.cornell.edu/{path}/{title}/{sec}"
        text = strip_html(fetcher.get(url))
        if len(text) < MIN_SOURCE_CHARS:
            raise Blocked(f"{url} returned too little text")
        return Fetched(url, text)

    def _ecfr(self, key: str, fetcher: Fetcher) -> Fetched:
        title, sec = key.split("/", 1)
        api = (f"https://www.ecfr.gov/api/renderer/v1/content/enhanced/current/title-{title}?"
               + urllib.parse.urlencode({"section": sec}))
        text = strip_html(fetcher.get(api))
        if len(text) < MIN_SOURCE_CHARS or f"§ {sec}" not in text:
            raise Blocked(f"eCFR returned no text for {title} CFR {sec}")
        return Fetched(f"https://www.ecfr.gov/current/title-{title}/section-{sec}", text)

    def fetch(self, kind: str, key: str, fetcher: Fetcher) -> Fetched:
        if kind == "usc":
            return self._lii(kind, key, fetcher)
        try:
            return self._ecfr(key, fetcher)
        except Blocked as first:
            try:
                return self._lii(kind, key, fetcher)
            except Blocked as second:
                raise Blocked(f"{first}; fallback: {second}")


class IrsPublications(Adapter):
    """IRS publications, current edition on irs.gov."""
    name = "irs"
    label = "IRS publications via irs.gov (current edition; a cited year must match it)"
    kinds = ("irs-pub",)

    def extract(self, par: str) -> list[Hit]:
        hits = []
        for m in IRS_PUB.finditer(par):
            num, year = m.group(1).upper(), m.group(2)
            key = f"{num}@{year}" if year else num
            hits.append(Hit("irs-pub", key, f"IRS Pub. {num}" + (f" ({year})" if year else ""), m.span()))
        return hits

    def fetch(self, kind: str, key: str, fetcher: Fetcher) -> Fetched:
        num, _, year = key.partition("@")
        slug_ = num.lower().replace("-", "")
        url = f"https://www.irs.gov/publications/p{slug_}"
        text = strip_html(fetcher.get(url))
        if len(text) < MIN_SOURCE_CHARS:
            raise Blocked(f"{url} returned too little text")
        flat = re.sub(r"[\s-]", "", num)
        m = re.search(r"Publication\s+(" + r"-?".join(map(re.escape, flat)) + r")\s+\((\d{4})\)", text)
        if not m:
            raise Blocked(f"{url} does not read as Publication {num}; cannot confirm the edition")
        if year and m.group(2) != year:
            raise NotFound(f"irs.gov now carries the {m.group(2)} edition of Pub. {num}, not {year} — "
                           f"quote a saved copy of the {year} edition with [src: …]")
        return Fetched(url, text)


class LocalDocument(Adapter):
    name = "local"
    label = "A document in the repository, cited [src: relative/path] (PDFs need pdftotext)"
    kinds = ("src",)

    def extract(self, par: str) -> list[Hit]:
        return [Hit("src", m.group(1), f"[src: {m.group(1)}]", m.span()) for m in SRC.finditer(par)]

    def fetch(self, kind: str, key: str, fetcher: Fetcher) -> Fetched:
        url, text = fetcher.src(key)
        return Fetched(url, text)


def normalize_codes(codes) -> list[str]:
    out = []
    by_name = {name.upper(): code for code, (name, _) in JURISDICTIONS.items()}
    for c in codes:
        for part in str(c).split(","):
            p = part.strip().upper()
            if not p:
                continue
            p = by_name.get(p, p)
            if p not in out:
                out.append(p)
    return out


def build_adapters(codes=()) -> tuple[list[Adapter], list[str]]:
    """Active adapters for a matter's jurisdiction codes, plus notes for codes with no adapter."""
    states, notes = [], []
    for code in normalize_codes(codes):
        if code in FEDERAL_CODES:
            continue
        cls = STATE_ADAPTERS.get(code)
        if cls is None:
            notes.append(f"no adapter for jurisdiction {code}: its citations FAIL as unsupported")
        else:
            states.append(cls())
    adapters = states + [CaseLaw([a.reporters for a in states]), Federal(), IrsPublications(), LocalDocument()]
    return adapters, notes


def load_adapter_files(paths) -> None:
    """Import plug-in adapter files; each registers itself with @register."""
    sys.modules.setdefault("verify_sources", sys.modules[__name__])
    for i, p in enumerate(paths):
        path = pathlib.Path(p).expanduser().resolve()
        spec = importlib.util.spec_from_file_location(f"verify_sources_plugin_{i}", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load adapter file {path}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)


# ── extraction ────────────────────────────────────────────────────────────────


def extract(text: str, adapters: list[Adapter] | None = None) -> tuple[list[Authority], list[Quote]]:
    if adapters is None:
        adapters = build_adapters(())[0]
    auths: list[Authority] = []
    quotes: list[Quote] = []
    pars = paragraphs(text)
    for i, raw in enumerate(pars):
        par = flatten(raw)
        seen, covered = set(), []

        def add(kind, key, display, span, name_hint=""):
            covered.append(span)
            if (kind, key) not in seen:
                seen.add((kind, key))
                auths.append(Authority(kind, key, display, i, name_hint=name_hint))

        for ad in adapters:
            for h in ad.extract(par):
                add(h.kind, h.key, h.display, h.span, h.name_hint)
        for n, pat in enumerate(LOOSE_CITES):
            for m in pat.finditer(par):
                if any(s <= m.start() < e or s < m.end() <= e for s, e in covered):
                    continue
                if n == REPORTER_LIKE and NOT_A_REPORTER.search(m.group(0)):
                    continue
                frag = m.group(0).strip()
                add("unrecognized", frag, f"“{frag}”", m.span())

        blocks = blockquotes(raw)
        span = (i - 1, i, i + 1) if blocks else (i,)  # a blockquote's cite may lead in or follow
        for body in blocks:
            body = re.sub(r"\s*(?:—|--)\s*[^—]*$", "", body) if re.search(r"(?:—|--)\s*\S[^—]*$", body) else body
            body = body.strip().strip("“”\"")
            if len(body) >= MIN_QUOTE:
                quotes.append(Quote(body, span))
        rest = flatten("\n".join(ln for ln in raw.splitlines() if not ln.lstrip().startswith(">")))
        for pat in QUOTE_PATTERNS:
            for m in pat.finditer(rest):
                quotes.append(Quote(m.group(1), span))
    return auths, quotes


# ── snapshots (evidence only — never read back as a cache) ────────────────────


def slug(a: Authority) -> str:
    return re.sub(r"[^a-z0-9]+", "-", f"{a.kind}-{a.key}".lower()).strip("-")


def write_snapshot(path: pathlib.Path, url: str, body: str, name: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    head = f"source: {url}\nfetched: {dt.date.today().isoformat()}\nsha256: {digest}\n"
    if name:
        head += f"name: {name}\n"
    path.write_text(head + "---\n" + body, encoding="utf-8")


# ── verification ──────────────────────────────────────────────────────────────


def resolve(a: Authority, fetcher: Fetcher, adir: pathlib.Path, adapters: list[Adapter]) -> None:
    snap = adir / f"{slug(a)}.txt"
    try:
        if a.kind == "other":
            a.status = FAIL
            a.reason = ("another jurisdiction's law: no adapter is active for it, and cross-jurisdiction "
                        "matters escalate (jurisdiction gate)")
            return
        if a.kind == "unrecognized":
            a.status = FAIL
            if STATE_SECTION_SHAPE.search(a.key) and not any(ad.state for ad in adapters):
                a.reason = ("looks like a state code section, but no state adapter is active for this matter — "
                            "set advisory.jurisdiction in project.yaml or pass --jurisdiction")
            else:
                a.reason = ("citation form the gate cannot check — rewrite it in a supported form "
                            "(--list-adapters) or quote a saved copy with [src: …]")
            return
        ad = next((x for x in adapters if a.kind in x.kinds), None)
        if ad is None:
            a.status, a.reason = FAIL, f"no active adapter fetches '{a.kind}' citations"
            return
        got = ad.fetch(a.kind, a.key, fetcher)
        a.url, a.text = got.url, got.text
        if a.kind == "src":
            a.status = PASS
            return
        write_snapshot(snap, a.url, a.text or "", got.name)
        a.snapshot = str(snap)
        a.status = PASS
        if a.kind == "case" and a.name_hint:
            left, right = (set(x) for x in json.loads(a.name_hint))
            if not name_matches((left, right), got.name):
                a.status, a.reason = FAIL, f"cite belongs to '{got.name}', not the case named in the draft"
    except NotFound as e:
        a.status, a.reason = FAIL, str(e)
    except Blocked as e:
        a.status, a.reason = BLOCKED, str(e)
    except Exception as e:  # anything unexpected fails closed  # broad: citation gate must fail closed on unexpected parse states
        a.status, a.reason = BLOCKED, f"unexpected error: {type(e).__name__}: {e}"


def verify(draft: pathlib.Path, fetcher: Fetcher, adir: pathlib.Path, forbid=(), forbid_regex=(),
           jurisdictions=()) -> Report:
    text = draft.read_text(encoding="utf-8")
    rep = Report(str(draft))
    adapters, rep.notes = build_adapters(jurisdictions)
    rep.adapters = [a.name + (" (example)" if a.example else "") for a in adapters]
    rep.authorities, rep.quotes = extract(text, adapters)
    for a in rep.authorities:
        resolve(a, fetcher, adir, adapters)
    for q in rep.quotes:
        cands = [a for a in rep.authorities if a.paragraph in q.paragraphs and a.kind not in ("unrecognized", "other")]
        if not cands:
            q.status, q.reason = FAIL, "no source cited in the same paragraph (cite it, or mark [src: path])"
            continue
        usable = [a for a in cands if a.text]
        hit, why = None, ""
        for a in usable:
            ok, why = check_quote(q.text, a.text)
            if ok:
                hit = a
                break
        if hit:
            q.status, q.matched = PASS, hit.display
        elif len(usable) < len(cands):
            q.status = BLOCKED
            q.reason = "not found in the sources that could be read; others unreadable: " + ", ".join(
                f"{a.display} ({a.reason or 'no opinion text without COURTLISTENER_TOKEN'})"
                for a in cands if not a.text)
        else:
            q.status, q.reason = FAIL, f"{why or 'not found word-for-word'} in " + ", ".join(a.display for a in cands)
    low = text.lower()
    for lit in forbid:
        if lit and lit.lower() in low:
            rep.forbidden.append(lit)
    for pat in forbid_regex:
        for m in re.finditer(pat, text):
            rep.forbidden.append(m.group(0))
    return rep


def render(rep: Report) -> str:
    rows = rep.authorities + rep.quotes
    n = {s: sum(1 for r in rows if r.status == s) for s in (PASS, FAIL, BLOCKED)}
    out = [f"VERIFICATION — {rep.draft} — {dt.date.today().isoformat()}",
           f"Totals: PASS {n[PASS]} · FAIL {n[FAIL]} · BLOCKED {n[BLOCKED]}"
           + (f" · FORBIDDEN {len(rep.forbidden)}" if rep.forbidden else "")
           + " · good law NOT_CHECKED"]
    if rep.adapters:
        out.append("Adapters: " + ", ".join(rep.adapters))
    out += [f"Note: {x}" for x in rep.notes]
    out += ["", "| # | Item | Status | Evidence / reason |", "|---|---|---|---|"]
    k = 0
    for a in rep.authorities:
        k += 1
        out.append(f"| {k} | {a.display} | {a.status} | {a.reason or (a.snapshot or a.url)} |")
    for q in rep.quotes:
        k += 1
        short = q.text if len(q.text) <= 70 else q.text[:67] + "…"
        out.append(f"| {k} | quote “{short}” | {q.status} | {q.reason or 'found in ' + q.matched} |")
    for f in rep.forbidden:
        k += 1
        out.append(f"| {k} | forbidden text “{f}” | FAIL | strategy text must not go out |")
    for e in rep.errors:
        k += 1
        out.append(f"| {k} | configuration | FAIL | {e} |")
    if not rows and not rep.forbidden and not rep.errors:
        out.append("| – | nothing cited or quoted | PASS | – |")
    out += ["",
            "Good law: NOT_CHECKED for every authority — no free citator. Check any case before relying on it.",
            "Figures and dates: NOT checked by this script — source-verifier checks them by their own rules.",
            "RESULT: " + ("PASS" if rep.ok else "NOT VERIFIED — the draft stays in drafts/")]
    return "\n".join(out)


def log(rep: Report | None, adir: pathlib.Path, draft: pathlib.Path, error: str = "") -> None:
    adir.mkdir(parents=True, exist_ok=True)
    entry = {
        "date": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "draft": str(draft),
        "draft_sha256": hashlib.sha256(draft.read_bytes()).hexdigest(),
        "result": PASS if rep and rep.ok else FAIL,
    }
    if rep:
        entry["adapters"] = rep.adapters
        entry["items"] = (
            [{"item": a.display, "status": a.status, "reason": a.reason, "source": a.url} for a in rep.authorities]
            + [{"item": "quote: " + q.text[:120], "status": q.status, "reason": q.reason} for q in rep.quotes]
            + [{"item": "forbidden: " + f, "status": FAIL} for f in rep.forbidden]
            + [{"item": "configuration", "status": FAIL, "reason": e} for e in rep.errors])
    if error:
        entry["error"] = error
    with open(adir / "verification-log.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def matter_root(draft: pathlib.Path) -> pathlib.Path:
    for d in [draft.parent, *draft.parent.parents]:
        if (d / "project.yaml").exists():
            return d
    return draft.parent.parent if draft.parent.name == "drafts" else draft.parent


def _load_project(root: pathlib.Path) -> tuple[dict | None, str]:
    p = root / "project.yaml"
    if not p.exists():
        return None, ""
    raw = p.read_text(encoding="utf-8")
    try:
        import yaml
    except ImportError:
        return None, raw
    return (yaml.safe_load(raw) or {}), raw


def project_forbid(root: pathlib.Path) -> tuple[list[str], list[str]]:
    """Literal strategy strings: every `forbid:` list under a top-level block of project.yaml."""
    p = root / "project.yaml"
    if not p.exists() or "forbid" not in p.read_text(encoding="utf-8"):
        return [], []
    data, _ = _load_project(root)
    if data is None:
        return [], ["project.yaml lists forbid entries but PyYAML is not installed; cannot enforce them"]
    out = []
    for block in data.values():
        if isinstance(block, dict):
            out += [str(v) for v in (block.get("forbid") or [])]
    return out, []


def project_jurisdictions(root: pathlib.Path) -> list[str]:
    """`advisory.jurisdiction` from the matter's project.yaml (a list or a single code)."""
    data, raw = _load_project(root)
    if data is not None:
        j = (data.get("advisory") or {}).get("jurisdiction") if isinstance(data.get("advisory"), dict) else None
        if j is None:
            return []
        return [str(x) for x in (j if isinstance(j, list) else [j])]
    m = re.search(r"(?m)^\s+jurisdiction:\s*\[([^\]]*)\]", raw or "")  # no PyYAML: flow list only
    return [x.strip() for x in m.group(1).split(",")] if m else []


def list_adapters() -> str:
    rows = [("federal", Federal.label), ("irs", IrsPublications.label), ("cases", CaseLaw.label),
            ("local", LocalDocument.label)]
    out = ["Always on:"] + [f"  {n:<8} {lab}" for n, lab in rows]
    out.append("Jurisdiction adapters (select with --jurisdiction or advisory.jurisdiction):")
    out += [f"  {code:<8} {cls.label}" for code, cls in sorted(STATE_ADAPTERS.items())]
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("draft", nargs="?")
    ap.add_argument("--authorities", help="evidence folder (default: <matter>/authorities)")
    ap.add_argument("--jurisdiction", action="append", default=[],
                    help="state adapter code(s), e.g. AL (repeatable; overrides project.yaml)")
    ap.add_argument("--adapter-file", action="append", default=[], help="plug-in adapter .py file (repeatable)")
    ap.add_argument("--list-adapters", action="store_true", help="print the adapter registry and exit")
    ap.add_argument("--forbid", action="append", default=[], help="literal text that must not appear (repeatable)")
    ap.add_argument("--forbid-regex", action="append", default=[], help="regex that must not appear (repeatable)")
    ap.add_argument("--promote", action="store_true", help="on PASS, copy drafts/X to outbound/X")
    args = ap.parse_args(argv)
    files = args.adapter_file + [p for p in os.environ.get("VERIFY_SOURCES_ADAPTER_FILES", "").split(os.pathsep) if p]
    try:
        load_adapter_files(files)
    except Exception as e:  # a broken plug-in is a usage error, never a silent pass  # broad: arbitrary plug-in code
        print(f"cannot load adapter file: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    if args.list_adapters:
        print(list_adapters())
        return 0
    if not args.draft:
        ap.print_usage(sys.stderr)
        return 2
    draft = pathlib.Path(args.draft).resolve()
    if not draft.is_file():
        print(f"no such draft: {draft}", file=sys.stderr)
        return 2
    for pat in args.forbid_regex:
        try:
            re.compile(pat)
        except re.error as e:
            print(f"bad --forbid-regex {pat!r}: {e}", file=sys.stderr)
            return 2
    root = matter_root(draft)
    adir = pathlib.Path(args.authorities).resolve() if args.authorities else root / "authorities"
    fetcher = Fetcher(os.environ.get("COURTLISTENER_TOKEN"), base_dir=draft.parent, draft=draft)
    rep = None
    try:
        codes = (args.jurisdiction or project_jurisdictions(root)
                 or [os.environ.get("VERIFY_SOURCES_JURISDICTION", "")])
        extra, errors = project_forbid(root)
        rep = verify(draft, fetcher, adir, list(args.forbid) + extra, args.forbid_regex, codes)
        rep.errors += errors
    except Exception as e:  # never exit without a log line  # broad: gate entry barrier; unexpected failures surface as gate errors
        log(None, adir, draft, error=f"{type(e).__name__}: {e}")
        print(f"verification crashed: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print(render(rep))
    log(rep, adir, draft)
    if args.promote:
        if not rep.ok:
            print("not promoted: verification did not pass", file=sys.stderr)
        elif draft.parent.name != "drafts":
            print("not promoted: --promote only moves files out of a drafts/ folder", file=sys.stderr)
            return 1
        else:
            dest = draft.parent.parent / "outbound" / draft.name
            dest.parent.mkdir(exist_ok=True)
            shutil.copy2(draft, dest)
            print(f"promoted: {dest}")
    return 0 if rep.ok else 1


if __name__ == "__main__":
    sys.exit(main())
