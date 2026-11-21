#!/usr/bin/env python3
"""Mojibake guard for note writers (AGENTS.md Rule 6).

Two jobs:

1. **Write UTF-8, always.**  `write_text_utf8()` is the only way a script in this
   repo should put text on disk.  It opens the file with an explicit
   `encoding="utf-8"` so a C/POSIX locale, a `LANG=` that never got set, or a
   default encoding inherited from a cron shell cannot silently downgrade the
   note to ASCII.

2. **Refuse to write `?` where the source text had a non-ASCII character.**
   `assert_no_ascii_replacement(source, rendered)` compares what came in
   against what is about to go out and raises `MojibakeError` if an em dash,
   curly quote, arrow, `·`, non-breaking space or emoji has turned into `?`.
   This is the failure mode that damaged the ingested activity logs: text was
   run through `str.encode("ascii", errors="replace")` (or an equivalent, such
   as Apps Script's `Utilities.newBlob(s).getDataAsString("US-ASCII")`) on the
   way to the file, and every non-ASCII character became a question mark that
   nothing can recover afterwards.

Anything appending to an `index.md` should do:

    from mojibake_guard import assert_no_ascii_replacement, write_text_utf8

    entry = format_entry(subject, summary, ...)
    assert_no_ascii_replacement(subject + summary, entry)
    write_text_utf8(note_path, old_content + entry)

CLI:

    python3 scripts/mojibake_guard.py --scan [PATH ...]   # fail on damage not in the baseline
    python3 scripts/mojibake_guard.py --staged            # gate a commit
    python3 scripts/mojibake_guard.py --update-baseline   # re-record the accepted leftovers

`--scan` exits 1 only for a symptom that is NOT listed in
`scripts/mojibake_baseline.tsv`.  The baseline holds the lines nobody can
settle from the repo alone (a `?` the source system has to answer for), each
tagged with that source system, so the check can fail on new damage without
being red forever on old.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import pathlib
import re
import subprocess
import sys

__all__ = [
    "MojibakeError",
    "assert_clean",
    "assert_no_ascii_replacement",
    "find_ascii_replacements",
    "find_mojibake",
    "write_text_utf8",
]


class MojibakeError(ValueError):
    """Raised instead of writing a note that would lose a non-ASCII character."""


# Rule 6's symptom table, as patterns.  Order matters only for reporting.
#
# They run on a line with its URLs, inline code and path/query tokens blanked
# out (see _strip_noise): `page.aspx?id=7` and `search?query=` are real question
# marks, and were 795 of the 1,064 hits the first full scan reported.
MOJIBAKE_PATTERNS = [
    # Not next to a table pipe: `| ? |` is a hand-typed "unknown" cell.
    (re.compile(r"(?<=[^\s|]) \? (?=[^\s|])"), "' ? ' between words (was an em dash or a . separator)"),
    (re.compile(r"\?\?"), "'??' (was a multi-codepoint emoji)"),
    (re.compile(r"(?<=[A-Za-z0-9])\?(?=[A-Za-z0-9])"), "'?' inside a word (was a curly apostrophe, en dash or NBSP)"),
    # The ingestion entry's sender line: a display name never holds a question.
    (re.compile(r'^- \*\*From\*\*: "[^"]*\?'), "'?' in a sender display name (was a (R)/(TM) mark or a separator)"),
    (re.compile(r"â€"), "UTF-8 re-read as cp1252"),
    (re.compile(r"Â "), "mangled non-breaking space"),
    (re.compile(r"�"), "U+FFFD replacement character"),
]

_FENCE = re.compile(r"^\s*(```|~~~)")
_NOISE = [
    re.compile(r"`[^`]*`"),                                   # inline code
    re.compile(r"\]\([^)]*\)"),                               # markdown link target
    re.compile(r"(?:https?://|www\.|mailto:|file://)\S+"),    # bare URL
    re.compile(r"\S*[/=&]\S*\?\S*|\S*\?\S*[/=&]\S*"),         # path or query token
]


def _strip_noise(line: str) -> str:
    """Blank out the spans where a '?' is syntax, keeping column positions."""
    for pattern in _NOISE:
        line = pattern.sub(lambda m: " " * len(m.group()), line)
    return line


def _symptoms(line: str):
    probe = _strip_noise(line)
    for pattern, symptom in MOJIBAKE_PATTERNS:
        if pattern.search(probe):
            yield symptom


def find_mojibake(text: str):
    """Yield (line_number, symptom, line) for every Rule 6 symptom in *text*.

    Fenced code blocks are skipped: a regex or a shell `??` in one is code.
    """
    fenced = False
    for lineno, line in enumerate(text.splitlines(), 1):
        if _FENCE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        for symptom in _symptoms(line):
            yield lineno, symptom, line


def find_ascii_replacements(source: str, rendered: str):
    """Return the characters *source* had that *rendered* has turned into '?'.

    Compares the two as sequences rather than by index, so an entry that wraps
    the source text in Markdown (headings, bullets, quoting) still lines up.
    """
    lost = []
    matcher = difflib.SequenceMatcher(None, source, rendered, autojunk=False)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op != "replace":
            continue
        was, now = source[i1:i2], rendered[j1:j2]
        if not now or set(now) != {"?"}:
            continue
        for char in was:
            if ord(char) > 127:
                lost.append(char)
    return lost


def assert_no_ascii_replacement(source: str, rendered: str) -> None:
    """Raise MojibakeError if *rendered* replaced a non-ASCII char with '?'.

    `source` is the text as it arrived (the email subject, body or summary);
    `rendered` is the Markdown about to be written.
    """
    if "?" not in rendered:
        return
    lost = find_ascii_replacements(source, rendered)
    if lost:
        shown = " ".join(f"{c!r} (U+{ord(c):04X})" for c in dict.fromkeys(lost))
        raise MojibakeError(
            "refusing to write text that replaced non-ASCII characters with '?': "
            f"{shown}. The source text is not ASCII, so encode it as UTF-8 "
            "instead of ascii/latin-1 (AGENTS.md Rule 6)."
        )


def assert_clean(text: str, what: str = "text") -> None:
    """Raise MojibakeError if *text* already carries a Rule 6 symptom.

    Use it on the entry a writer is about to append (never on a whole legacy
    note — the ingested logs still hold damage nobody can recover).
    """
    hits = list(find_mojibake(text))
    if hits:
        lineno, symptom, line = hits[0]
        raise MojibakeError(
            f"refusing to write {what}: line {lineno} shows {symptom} "
            f"(AGENTS.md Rule 6)\n    {line.strip()[:160]}"
        )


def write_text_utf8(path, text: str, *, source: str | None = None) -> None:
    """Write *text* to *path* as UTF-8, refusing to persist mojibake.

    Pass `source` (the original, unmangled text) to also check that this write
    did not flatten a non-ASCII character into '?'.
    """
    if source is not None:
        assert_no_ascii_replacement(source, text)
    text.encode("utf-8")  # explicit: fail here, never via the filesystem
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


BASELINE = pathlib.Path(__file__).resolve().parent / "mojibake_baseline.tsv"
BASELINE_HEADER = """\
# Rule 6 baseline -- symptoms `mojibake_guard.py --scan` accepts (AGENTS.md Rule 6).
#
# Every line here is a '?' the repo cannot settle on its own.  The second column
# names the SOURCE SYSTEM that holds the original, i.e. where to look to rebuild it:
#   gmail-from-header  ingested email entry; the sender's display name lost a
#                      (R)/(TM) mark or separator.  Original: the message's raw
#                      From header in Gmail (the Gmail connector returns only
#                      the address, so open the message > Show original).
#   onenote:<notebook> note imported from that OneNote notebook (front-matter
#                      `notebook:`, created before 2025).  Mostly hand-typed
#                      "unknown" placeholders (`????`, `$??`); the notebook
#                      page is the original.
#   repo               written in this repo: a real `??` inside a quotation, or
#                      damage to fix here.
#
# Shrink-only.  Fix the line, then `python3 scripts/mojibake_guard.py
# --update-baseline`.  Never add a line to make new damage pass.
#
# path <TAB> source <TAB> sha1[:12] of the line <TAB> preview
"""


def _line_key(line: str) -> str:
    return hashlib.sha1(line.encode("utf-8")).hexdigest()[:12]


_NOTEBOOK = re.compile(r'^notebook:\s*"?([^"\n]+)"?\s*$', re.M)
_CREATED = re.compile(r"^created:\s*\"?(\d{4})", re.M)


def _source_of(line: str, head: str) -> str:
    """Name the source system that holds the original of a damaged *line*.

    *head* is the top of the note (its YAML front-matter).
    """
    if line.startswith("- **From**: "):
        return "gmail-from-header"
    notebook, created = _NOTEBOOK.search(head), _CREATED.search(head)
    if notebook and created and int(created.group(1)) < 2025:
        return f"onenote:{notebook.group(1).strip()}"
    return "repo"


def _load_baseline(path=BASELINE):
    accepted = set()
    try:
        rows = pathlib.Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return accepted
    for row in rows:
        if not row or row.startswith("#"):
            continue
        cols = row.split("\t")
        if len(cols) >= 3:
            accepted.add((cols[0], cols[2]))
    return accepted


def _default_paths():
    return sorted(
        p for p in pathlib.Path(".").rglob("*.md")
        if not any(part.startswith(".") for part in p.parts[:-1])
    )


def _collect(paths):
    """Return [(path, lineno, symptom, line)] plus the paths that would not read."""
    hits, unreadable = [], []
    for path in paths:
        p = pathlib.Path(path)
        if p.name == "AGENTS.md":  # documents the symptoms; false positive by construction
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as exc:
            unreadable.append((p.as_posix(), str(exc)))
            continue
        for lineno, symptom, line in find_mojibake(text):
            hits.append((p.as_posix(), lineno, symptom, line))
    return hits, unreadable


def _scan(paths, baseline=None) -> int:
    """Print every symptom not in *baseline*; return how many there were."""
    accepted = _load_baseline() if baseline is None else baseline
    hits, unreadable = _collect(paths)
    for path, exc in unreadable:
        print(f"{path}: cannot read as UTF-8: {exc}")
    new, known, seen = 0, set(), set()
    for path, lineno, symptom, line in hits:
        key = (path, _line_key(line))
        seen.add(key)
        if key in accepted:
            known.add((path, lineno))
            continue
        print(f"{path}:{lineno}: {symptom}\n    {line.strip()[:160]}")
        new += 1
    stale = len(accepted - seen)
    print(f"\n{new + len(unreadable)} line(s) with Rule 6 symptoms")
    print(f"{len(known)} baselined line(s) accepted (scripts/{BASELINE.name})")
    if stale:
        print(f"{stale} baseline entr(ies) no longer match anything; run --update-baseline to prune")
    return new + len(unreadable)


def _update_baseline(paths) -> int:
    hits, _ = _collect(paths)
    rows, heads = {}, {}
    for path, _lineno, _symptom, line in hits:
        if path not in heads:
            heads[path] = pathlib.Path(path).read_text(encoding="utf-8")[:600]
        preview = " ".join(line.split())[:100]
        rows[(path, _line_key(line))] = (path, _source_of(line, heads[path]), _line_key(line), preview)
    rank = lambda src: (0 if src.startswith("gmail") else 1 if src.startswith("onenote") else 2, src)
    body = "\n".join("\t".join(r) for r in sorted(rows.values(), key=lambda r: (rank(r[1]), r[0], r[3])))
    write_text_utf8(BASELINE, BASELINE_HEADER + body + "\n")
    print(f"wrote {len(rows)} line(s) to scripts/{BASELINE.name}")
    return 0


_HUNK = re.compile(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@")


def _staged_lines(diff: str):
    """{path: {line numbers this commit adds}} from a `git diff --cached --unified=0`."""
    added, path = {}, None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else None
        elif path and line.startswith("@@"):
            hunk = _HUNK.match(line)
            if hunk:
                start, count = int(hunk.group(1)), int(hunk.group(2) or 1)
                added.setdefault(path, set()).update(range(start, start + count))
    return added


def _staged() -> int:
    """Check only the lines this commit adds, so known-unrecoverable damage
    already in the logs does not block every future commit.

    Each file is read whole from the index, so a `??` inside a fenced block is
    judged the way `--scan` judges it: as text someone typed, not as damage.
    """
    diff = subprocess.run(
        ["git", "-c", "core.quotepath=off", "diff", "--cached", "--unified=0", "--no-renames",
         "--", "*.md", ":(exclude)AGENTS.md"],
        capture_output=True, text=True, check=True, timeout=60,
    ).stdout
    found = 0
    for path, lines in _staged_lines(diff).items():
        blob = subprocess.run(["git", "show", ":" + path], capture_output=True, check=True, timeout=60).stdout
        try:
            text = blob.decode("utf-8")
        except UnicodeDecodeError as exc:
            print(f"staged: {path} is not UTF-8 ({exc})")
            found += 1
            continue
        for lineno, symptom, line in find_mojibake(text):
            if lineno in lines:
                print(f"staged: {symptom}\n    {line.strip()[:160]}")
                found += 1
    return found


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scan", action="store_true", help="fail on Rule 6 damage in PATHs that is not baselined")
    parser.add_argument("--staged", action="store_true", help="fail on mojibake added by the staged diff")
    parser.add_argument("--update-baseline", action="store_true", help="re-record the accepted leftovers")
    parser.add_argument("paths", nargs="*", help="files to scan (default: every *.md)")
    args = parser.parse_args(argv)

    # `--scan .` used to read the directory as a file and report one bogus hit.
    paths = []
    for path in args.paths:
        p = pathlib.Path(path)
        paths.extend(sorted(q for q in p.rglob("*.md") if ".git" not in q.parts) if p.is_dir() else [p])

    if args.staged:
        found = _staged()
        print("clean" if not found else f"{found} newly added mojibake line(s)")
        return 1 if found else 0

    if args.update_baseline:
        return _update_baseline(_default_paths())

    if args.scan:
        return 1 if _scan(paths or _default_paths()) else 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
