#!/usr/bin/env python3
"""project-manager — the deterministic half of the engine.

The model reads mail and drafts replies. This script does the parts a model gets wrong:
schema checks, date arithmetic, the DECIDED-decision lock, and rewriting the managed
blocks in index.md without touching the hand-written analysis around them.

The agent still edits project.yaml by hand for anything that takes judgment, so comments and
ordering survive. The script touches the file in exactly two mechanical places: `record`
rewrites the `last_run:` block, and `archive` lifts closed items out into
project-archive.yaml. Both re-parse the result and refuse to write if anything else moved.

    pm.py list                                   every registered project
    pm.py path     <id | folder | project.yaml>  resolve an id to its project.yaml
    pm.py validate <project.yaml> [--no-git] [--allow-decision-change]
    pm.py clocks   <project.yaml> [--today YYYY-MM-DD]
    pm.py query    <project.yaml> [--since YYYY-MM-DD]   the sync plan: Gmail/Drive searches
    pm.py health   [project.yaml …] [--now ISO]  which scheduled runs did not happen
    pm.py record   <project.yaml> --result "…" [--quiet | --headline "…" --log "…"]
                   [--event slug] [--commit] [--publish]
    pm.py usage    <project.yaml> [--days 30]    what the recorded runs cost (from runs.csv)
    pm.py render   <project.yaml> [--index PATH] [--check]
    pm.py queue    <project.yaml>
    pm.py archive  <project.yaml> [--days 14] [--dry-run]
    pm.py routine  <id> [--deployed FILE]        desired schedule spec / drift vs a saved trigger

Household settings (time zone, scheduler details, publishing) come from config/household.yaml in
the skill folder, or the file named by $PM_CONFIG; see config/household.example.yaml. Without it
the script uses the machine's local time zone and skips the scheduler drift checks that need it.

Python 3.9+ and PyYAML. Output is UTF-8 JSON with ensure_ascii off — never mojibake.
"""

import argparse
import datetime as dt
import difflib
import json
import os
import re
import subprocess
import sys
import tempfile

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is missing: python3 -m pip install --user pyyaml")

PROJECT_STATUSES = {"active", "paused", "complete"}
RUNTIMES = {"cloud", "local"}
DECISION_STATUSES = {"OPEN", "DECIDED"}
ACTION_STATUSES = {"open", "in_progress", "waiting", "blocked", "done", "dropped"}
CLOSED = {"done", "dropped", "answered", "withdrawn"}
QUESTION_STATUSES = {"open", "answered", "withdrawn"}
PARTY_STATUSES = {"active", "done", "declined", "dropped", "paused"}
PARTY_CLOSED = {"done", "declined", "dropped", "paused"}
RUN_RUNTIMES = {"cloud", "local", "interactive"}
# last_run.escalated holds keys pm.py itself emits, plus event:<slug>:<date> for an
# escalate_when trigger (which has no dated item to key off). A party gone silent keys on
# the date it was last heard from, so one silence pings once and a fresh one pings again. A key that does not match
# this grammar can never suppress anything, so the same item pings every run.
ESCALATED_KEY = re.compile(
    r"^(?:clock|action):[\w.-]+:(?:urgent|due-tomorrow|overdue(?::\d+d)?)$"
    r"|^question:[\w.-]+$"
    r"|^silent:[\w.-]+:\d{4}-\d{2}-\d{2}$"
    r"|^event:[\w.-]+:\d{4}-\d{2}-\d{2}$"
)
CLOCK_SKEW_MINUTES = 10
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_config(path=None):
    """config/household.yaml (or $PM_CONFIG). Missing → {}: every setting has a default."""
    path = path or os.environ.get("PM_CONFIG") or os.path.join(SKILL_DIR, "config", "household.yaml")
    try:
        with open(path, encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
    except FileNotFoundError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


CONFIG = load_config()
# The household's wall clock: "today" and "due" mean this zone. None = this machine's local zone.
HOME_TZ = os.environ.get("PM_TIMEZONE") or CONFIG.get("timezone") or None
REQUIRED = ["id", "title", "status", "owners", "notes_root", "runtime", "charter"]
ID_LISTS = ["decisions", "actions", "clocks", "questions", "needs_local"]
DATE_FIELDS = {
    "decisions": ["date"],
    "actions": ["due", "done_on"],
    "clocks": ["due"],
    "questions": ["raised"],
    "needs_local": ["raised"],
}
BLOCKS = ["status", "decisions", "actions", "clocks", "questions"]
DEFAULT_URGENCY_DAYS = 10
# An overdue item once pinged and then sat silent for two weeks while every run said quiet.
# It now pings again every this-many days overdue, until someone re-dates or closes it.
DEFAULT_REPING_DAYS = 7
HEALTH_GRACE_MINUTES = 120
ARCHIVE_NAME = "project-archive.yaml"
ARCHIVE_LISTS = ["actions", "clocks", "questions", "needs_local"]
EVENT_KEY_DAYS = 30

# The engine ignores any key it does not know, so a misnamed one hides state without an
# error: on 09-28 a file with `open_questions` and clocks dated by `date` validated clean
# while five questions and eight clocks were invisible and `clocks` said "quiet".
TOP_KEYS = {
    "id", "title", "status", "owners", "hard_deadline", "notes_root", "runtime", "trigger_id",
    "cadence", "calendar_for_reminders", "charter", "summary", "wind_down", "workstreams",
    "watch", "requirements", "do_not", "playbook_notes", "raid", "decisions", "actions",
    "clocks", "questions", "needs_local", "discard_drafts", "escalate_when", "last_run",
    "advisory", "legal", "tax_wealth", "health",
}
# Advisory-team blocks (docs/advisory-teams.md): validated by name only; each team owns its fields.
ADVISORY_TEAMS = ("legal", "tax_wealth", "health")
MAP_KEYS = {
    "cadence": {"cron", "urgency_window_days", "overdue_reping_days"},
    "charter": {"goal", "scope", "out_of_scope", "success_criteria"},
    "watch": {"parties", "identifiers", "keywords", "exclude", "drive_folders", "calendars", "web",
              "texts"},
    "raid": {"risks", "assumptions", "issues", "dependencies"},
    "last_run": {"at", "runtime", "result", "escalated"},
}
ITEM_KEYS = {
    "decisions": {"id", "text", "status", "date", "rationale", "ref"},
    "actions": {"id", "text", "owner", "due", "status", "next_step", "blocked_by", "draft_id",
                "ref", "done_on"},
    "clocks": {"id", "due", "item", "owner", "on_miss", "status", "done_on", "note", "source"},
    "questions": {"id", "text", "for", "blocking", "raised", "status", "answer", "ref"},
    "needs_local": {"id", "task", "why", "raised", "status", "done_on"},
    "discard_drafts": {"id", "subject", "why", "raised"},
    "workstreams": {"id", "title", "name", "notes", "status"},
    "parties": {"name", "org", "emails", "domains", "phones", "waiting_on", "last_heard",
                "silent_after_days", "status", "notes"},
}
ALIASES = {"open_questions": "questions", "date": "due", "deadline": "due", "open_actions": "actions",
           "todo": "actions", "todos": "actions", "deadlines": "clocks", "description": "text"}
LONG_FIELDS = {("actions", "next_step"): 900, ("clocks", "item"): 320, ("actions", "text"): 500}
BIG_FILE_BYTES = 32000
GMAIL_READ_DRAFT_TOOLS = {"search_threads", "get_thread", "get_message", "list_drafts", "get_draft",
                          "create_draft", "update_draft", "list_labels"}
NOTE = "_Generated from `project.yaml` by the project-manager skill. Edit the YAML, not this block._"


# ── loading ────────────────────────────────────────────────────────────────


def as_date(value):
    """YAML turns an unquoted 2026-10-12 into a date; a quoted one stays a string."""
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        return dt.date.fromisoformat(value.strip()[:10])
    raise ValueError("not a date: %r" % (value,))


def home_today(now=None, zone=None):
    """Today's date at home. A cloud sandbox runs on UTC, where an evening run is already
    'tomorrow' — which shifted clocks a day until the date came from here. Set `timezone` in
    config/household.yaml for any run that may happen off the household's own machine."""
    now = now or dt.datetime.now(dt.timezone.utc)
    zone = zone or HOME_TZ
    if not zone:
        return now.astimezone().date()
    try:
        from zoneinfo import ZoneInfo
        return now.astimezone(ZoneInfo(zone)).date()
    except (ImportError, KeyError, ValueError):  # pragma: no cover - no tz database
        return now.date()


def load(path):
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise SystemExit("%s: top level must be a mapping" % path)
    return data


def items(data, key):
    value = data.get(key) or []
    return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []


def is_party_open(party):
    """Parties use their own vocabulary: declined/dropped/paused stop the chase like done."""
    return str(party.get("status") or "active") not in PARTY_CLOSED


def as_dt(value):
    """Parse an ISO-8601 instant that carries a timezone. None stays None."""
    if value in (None, "", "null"):
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = dt.datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError("no timezone offset")
    return parsed


def _slug(text):
    return re.sub(r"[^\w.-]+", "-", str(text or "").lower()).strip("-") or "unnamed"


def parties(data):
    watch = data.get("watch") or {}
    return [p for p in (watch.get("parties") or []) if isinstance(p, dict)]


def is_open(item):
    return str(item.get("status") or "open") not in CLOSED


# ── validate ───────────────────────────────────────────────────────────────


def _unknown(key, allowed):
    hint = ALIASES.get(key)
    if hint not in allowed:
        close = difflib.get_close_matches(str(key), sorted(allowed), n=1, cutoff=0.6)
        hint = close[0] if close else None
    return " — did you mean %r?" % hint if hint else ""


def unknown_key_errors(data):
    """Every key the engine would silently ignore. See TOP_KEYS for why this is an error."""
    errors = []
    for key in data:
        if key not in TOP_KEYS:
            errors.append("unknown top-level key %r%s (the engine ignores keys it does not know)"
                          % (key, _unknown(key, TOP_KEYS)))
    for name, allowed in MAP_KEYS.items():
        block = data.get(name)
        if isinstance(block, dict):
            for key in block:
                if key not in allowed:
                    errors.append("%s: unknown key %r%s" % (name, key, _unknown(key, allowed)))
    groups = [(name, items(data, name)) for name in ITEM_KEYS if name != "parties"]
    groups.append(("parties", parties(data)))
    for name, rows in groups:
        allowed = ITEM_KEYS[name]
        label = "watch.parties" if name == "parties" else name
        for row in rows:
            for key in row:
                if key not in allowed:
                    errors.append("%s (%s): unknown key %r%s"
                                  % (label, row.get("id") or row.get("name"), key, _unknown(key, allowed)))
    return errors


def warnings(data, size=None):
    """Not errors — things that make every run slower or blunter. Printed, never fatal."""
    notes = []
    for (name, field), limit in LONG_FIELDS.items():
        for row in items(data, name):
            length = len(str(row.get(field) or ""))
            if length > limit:
                notes.append("%s %s: %s is %d characters — keep the current state there and move "
                             "the history to the Activity Log" % (name, row.get("id"), field, length))
    if size and size > BIG_FILE_BYTES:
        closed = sum(1 for name in ARCHIVE_LISTS for row in items(data, name) if not is_open(row))
        notes.append("project.yaml is %d bytes and every run reads all of it%s"
                     % (size, " — `pm.py archive` would lift out %d closed item(s)" % closed if closed else ""))
    return notes


def archive_path(yaml_path):
    return os.path.join(os.path.dirname(os.path.abspath(yaml_path)), ARCHIVE_NAME)


def load_archive(yaml_path):
    path = archive_path(yaml_path)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        loaded = yaml.safe_load(f)
    return loaded if isinstance(loaded, dict) else {}


def archive_collisions(data, archived):
    """An archived id is spent. Reusing A3 for a new action makes the log ambiguous."""
    errors = []
    for name in ARCHIVE_LISTS:
        used = {row.get("id") for row in items(archived, name)}
        for row in items(data, name):
            if row.get("id") in used:
                errors.append("%s %s: that id is already used in %s — take the next free number"
                              % (name, row.get("id"), ARCHIVE_NAME))
    return errors


def validate(data, now=None):
    errors = unknown_key_errors(data)
    for key in REQUIRED:
        if data.get(key) in (None, "", [], {}):
            errors.append("missing required field: %s" % key)
    if data.get("status") not in PROJECT_STATUSES:
        errors.append("status must be one of %s" % sorted(PROJECT_STATUSES))
    if data.get("runtime") not in RUNTIMES:
        errors.append("runtime must be one of %s" % sorted(RUNTIMES))
    try:
        as_date(data.get("hard_deadline"))
    except (ValueError, TypeError):
        errors.append("hard_deadline is not YYYY-MM-DD: %r" % (data.get("hard_deadline"),))
    cron = (data.get("cadence") or {}).get("cron") if isinstance(data.get("cadence"), dict) else None
    if cron:
        try:
            parse_cron(cron)
        except CronUnsupported:
            pass
        except ValueError as exc:
            errors.append("cadence.cron %r: %s" % (cron, exc))

    for key in ID_LISTS + ["discard_drafts"]:
        raw = data.get(key)
        if raw is not None and not isinstance(raw, list):
            errors.append("%s must be a list" % key)
            continue
        seen = set()
        for i, item in enumerate(raw or []):
            where = "%s[%d]" % (key, i)
            if not isinstance(item, dict):
                errors.append("%s must be a mapping" % where)
                continue
            iid = item.get("id")
            if not iid:
                errors.append("%s: missing id" % where)
            elif iid in seen:
                errors.append("%s: duplicate id %r" % (where, iid))
            else:
                seen.add(iid)
            for field in DATE_FIELDS.get(key, []):
                try:
                    as_date(item.get(field))
                except (ValueError, TypeError):
                    errors.append("%s (%s): %s is not YYYY-MM-DD: %r" % (where, iid, field, item.get(field)))

    for d in items(data, "decisions"):
        if d.get("status") not in DECISION_STATUSES:
            errors.append("decision %s: status must be OPEN or DECIDED" % d.get("id"))
    for a in items(data, "actions"):
        if str(a.get("status") or "open") not in ACTION_STATUSES:
            errors.append("action %s: status must be one of %s" % (a.get("id"), sorted(ACTION_STATUSES)))
    for q in items(data, "questions"):
        if str(q.get("status") or "open") not in QUESTION_STATUSES:
            errors.append("question %s: status must be one of %s" % (q.get("id"), sorted(QUESTION_STATUSES)))

    for i, p in enumerate(parties(data)):
        if not p.get("name"):
            errors.append("watch.parties[%d]: missing name" % i)
        try:
            as_date(p.get("last_heard"))
        except (ValueError, TypeError):
            errors.append("watch.parties[%d] (%s): last_heard is not YYYY-MM-DD" % (i, p.get("name")))
        limit = p.get("silent_after_days")
        if limit is not None and not isinstance(limit, int):
            errors.append("watch.parties[%d] (%s): silent_after_days must be an integer" % (i, p.get("name")))
        pstatus = p.get("status")
        if pstatus is not None and str(pstatus).split("#")[0].strip() not in PARTY_STATUSES:
            errors.append("watch.parties[%d] (%s): status must be one of %s"
                          % (i, p.get("name"), sorted(PARTY_STATUSES)))

    errors += last_run_errors(data.get("last_run") or {}, now)
    return errors


def last_run_errors(run, now=None):
    """last_run must be honest: a real past instant, a known runtime, and suppression keys
    in the grammar pm.py emits. Runs have hand-written all three wrong."""
    errors = []
    if not isinstance(run, dict):
        return ["last_run must be a mapping"]
    now = now or dt.datetime.now(dt.timezone.utc)
    stamp = run.get("at")
    if stamp not in (None, "", "null"):
        try:
            when = as_dt(stamp)
        except (ValueError, TypeError):
            errors.append("last_run.at is not an ISO-8601 instant with a timezone: %r "
                          "(use: date -u +%%Y-%%m-%%dT%%H:%%M:%%SZ)" % (stamp,))
        else:
            if when > now + dt.timedelta(minutes=CLOCK_SKEW_MINUTES):
                errors.append("last_run.at is in the future: %s — stamp it from the shell, "
                              "never by hand" % stamp)
    runtime = run.get("runtime")
    if runtime not in (None, "", "null") and str(runtime) not in RUN_RUNTIMES:
        errors.append("last_run.runtime must be one of %s" % sorted(RUN_RUNTIMES))
    raw = run.get("escalated")
    if raw is not None and not isinstance(raw, list):
        errors.append("last_run.escalated must be a list of keys")
    else:
        for key in raw or []:
            if not ESCALATED_KEY.match(str(key)):
                errors.append("last_run.escalated: %r is not a suppression key — use the keys "
                              "pm.py clocks emits (clock:C1:urgent, action:A2:overdue, question:Q3) "
                              "or event:<slug>:<YYYY-MM-DD> for an escalate_when trigger" % (key,))
    return errors


def _norm(text):
    return " ".join(str(text or "").split())


def decided_changes(old, new):
    """A DECIDED decision is locked: it cannot be removed, reopened or reworded.

    New information that contradicts one becomes a question for a human instead.
    """
    errors = []
    current = {d.get("id"): d for d in items(new, "decisions")}
    for d in items(old, "decisions"):
        if d.get("status") != "DECIDED":
            continue
        did = d.get("id")
        now = current.get(did)
        if now is None:
            errors.append("decision %s was DECIDED and has been removed" % did)
        elif now.get("status") != "DECIDED":
            errors.append("decision %s was DECIDED and has been reopened" % did)
        elif _norm(now.get("text")) != _norm(d.get("text")):
            errors.append("decision %s was DECIDED and its text has changed" % did)
    return errors


def head_version(path):
    """project.yaml as of HEAD, or None when untracked / not in git."""
    real = os.path.realpath(path)
    try:
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=os.path.dirname(real), capture_output=True, text=True, check=True, timeout=60,
        ).stdout.strip()
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("timed out running: %s" % " ".join(exc.cmd)) from exc
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    rel = os.path.relpath(real, os.path.realpath(top))
    shown = subprocess.run(["git", "show", "HEAD:" + rel], cwd=top, capture_output=True, text=True, timeout=60)
    if shown.returncode != 0:
        return None
    loaded = yaml.safe_load(shown.stdout)
    return loaded if isinstance(loaded, dict) else None


# ── clocks ─────────────────────────────────────────────────────────────────


def clocks(data, today):
    """Bucket everything with a date, find silent parties, and decide whether to notify.

    Notification is keyed, not level-triggered: an item that was already escalated on a
    previous run (its key is in last_run.escalated) does not ping again until it moves to
    a worse state — urgent → due-tomorrow → overdue. A daily ping about the same clock
    stops being read. Once overdue it pings again every `overdue_reping_days` (overdue:7d,
    overdue:14d, …): an item nobody re-dated or closed should not go quiet for good.

    The verdict is the whole of the clock side of "is this run quiet?": dated items, blocking
    questions and parties newly gone silent all key in here.
    """
    cadence = data.get("cadence") or {}
    window = int(cadence.get("urgency_window_days") or DEFAULT_URGENCY_DAYS)
    reping = cadence.get("overdue_reping_days")
    reping = DEFAULT_REPING_DAYS if reping is None else int(reping)
    report = {
        "today": today.isoformat(),
        "project_status": data.get("status"),
        "advisory": [k for k in ADVISORY_TEAMS if data.get(k)],
        "urgency_window_days": window,
        "overdue": [], "urgent": [], "upcoming": [],
        "silent_parties": [], "blocking_questions": [],
        "open_questions": 0, "needs_local": 0,
        "escalate_keys": [], "new_keys": [], "work": [], "verdict": "quiet",
    }
    keys = []
    words = {}

    def place(kind, item, text):
        due = as_date(item.get("due"))
        if due is None:
            return
        days = (due - today).days
        row = {"kind": kind, "id": item.get("id"), "item": text, "owner": item.get("owner"),
               "due": due.isoformat(), "days": days}
        base = "%s:%s" % (kind, item.get("id"))
        label = "%s %s (%s)" % (kind, item.get("id"), " ".join(str(text or "").split())[:90])
        if days < 0:
            weeks = (-days) // reping if reping > 0 else 0
            if weeks:
                row["stale"] = True  # re-pinged: re-date it, close it, or turn it into a question
            report["overdue"].append(row)
            keys.append(base + ":overdue" + (":%dd" % (weeks * reping) if weeks else ""))
            words[keys[-1]] = "%s is %d day(s) overdue%s" % (
                label, -days, " and still open — re-date it with the evidence, close it, or turn it "
                              "into a question" if weeks else "")
        elif days <= window:
            report["urgent"].append(row)
            keys.append(base + (":due-tomorrow" if days <= 1 else ":urgent"))
            words[keys[-1]] = "%s is due %s (%s)" % (
                label, due.isoformat(), "today" if days == 0 else "in %d day(s)" % days)
        else:
            report["upcoming"].append(row)

    for c in items(data, "clocks"):
        if is_open(c):
            place("clock", c, c.get("item"))
    for a in items(data, "actions"):
        if is_open(a):
            place("action", a, a.get("text"))

    for p in parties(data):
        last, limit = as_date(p.get("last_heard")), p.get("silent_after_days")
        if p.get("waiting_on") and last and limit is not None and is_party_open(p):
            silent = (today - last).days
            if silent > int(limit):
                report["silent_parties"].append({
                    "name": p.get("name"), "waiting_on": p.get("waiting_on"),
                    "last_heard": last.isoformat(), "days_silent": silent,
                })
                keys.append("silent:%s:%s" % (_slug(p.get("name")), last.isoformat()))
                words[keys[-1]] = ("%s has been silent %d days on: %s — check our ask was actually sent, "
                                   "then draft a short chase" % (p.get("name"), silent,
                                                                " ".join(str(p.get("waiting_on")).split())[:90]))

    for q in items(data, "questions"):
        if is_open(q):
            report["open_questions"] += 1
            if q.get("blocking"):
                report["blocking_questions"].append({"id": q.get("id"), "text": q.get("text"),
                                                     "for": q.get("for"), "blocking": q.get("blocking")})
                keys.append("question:%s" % q.get("id"))
                words[keys[-1]] = "question %s blocks %s and needs %s: %s" % (
                    q.get("id"), q.get("blocking"), q.get("for") or "a human",
                    " ".join(str(q.get("text") or "").split())[:90])

    report["needs_local"] = sum(1 for n in items(data, "needs_local") if is_open(n))
    for bucket in ("overdue", "urgent", "upcoming"):
        report[bucket].sort(key=lambda r: r["days"])

    already = set((data.get("last_run") or {}).get("escalated") or [])
    report["escalate_keys"] = keys
    report["new_keys"] = [k for k in keys if k not in already]
    report["work"] = [{"key": k, "what": words.get(k, k)} for k in report["new_keys"]]
    report["verdict"] = "escalate" if report["new_keys"] else "quiet"
    return report


# ── registry ───────────────────────────────────────────────────────────────


def repo_top(start=None):
    """The repo root: git's answer from `start`, else three levels above this script."""
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=start or os.getcwd(),
                             capture_output=True, text=True, check=True, timeout=60).stdout.strip()
        if out:
            return out
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("timed out running: %s" % " ".join(exc.cmd)) from exc
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))


def registry(top=None):
    """Every project.yaml git tracks outside skills/, as [(repo-relative path, data)]."""
    top = top or repo_top()
    listed = subprocess.run(["git", "ls-files", "*project.yaml"], cwd=top, capture_output=True, text=True, timeout=60)
    found = []
    for rel in sorted(listed.stdout.split("\n")):
        if not rel or rel.startswith("skills/") or os.path.basename(rel) != "project.yaml":
            continue
        full = os.path.join(top, rel)
        if not os.path.exists(full):
            continue
        try:
            data = load(full)
        except (SystemExit, yaml.YAMLError):
            continue
        if data.get("id"):
            found.append((rel, data))
    return found


def resolve(ref, top=None):
    """An id, a notes folder, or a project.yaml path → the project.yaml path."""
    if os.path.isfile(ref):
        return ref
    if os.path.isdir(ref) and os.path.isfile(os.path.join(ref, "project.yaml")):
        return os.path.join(ref, "project.yaml")
    top = top or repo_top()
    rows = registry(top)
    for rel, data in rows:
        if data.get("id") == ref:
            return os.path.relpath(os.path.join(top, rel))
    raise SystemExit("no project %r — known ids: %s" % (ref, ", ".join(str(d.get("id")) for _, d in rows)))


def listing(top=None):
    rows = []
    for rel, data in registry(top):
        run = data.get("last_run") or {}
        rows.append({
            "id": data.get("id"), "path": rel, "status": data.get("status"),
            "runtime": data.get("runtime"), "trigger_id": data.get("trigger_id"),
            "cron": (data.get("cadence") or {}).get("cron"),
            "advisory": [k for k in ADVISORY_TEAMS if data.get(k)],
            "last_run": str(run.get("at") or ""), "last_runtime": run.get("runtime"),
        })
    return rows


# ── cron and health ────────────────────────────────────────────────────────


class CronUnsupported(ValueError):
    """A valid schedule this script cannot reason about (day-of-month, month)."""


def _cron_field(text, low, high):
    values = set()
    for part in text.split(","):
        step = 1
        if "/" in part:
            part, raw = part.split("/", 1)
            step = int(raw)
        if part == "*":
            first, last = low, high
        elif "-" in part:
            a, b = part.split("-", 1)
            first, last = int(a), int(b)
        else:
            first = last = int(part)
        if first < low or last > high or first > last or step < 1:
            raise ValueError("field %r is out of range %d-%d" % (text, low, high))
        values.update(range(first, last + 1, step))
    return values


def parse_cron(expr):
    """`[CRON_TZ=Zone] minute hour dom month dow` → (tzinfo, minutes, hours, weekdays 0=Sun).

    Without CRON_TZ a cloud cron is UTC and does not follow DST. With it, it follows the zone.
    """
    parts = str(expr).split()
    zone = dt.timezone.utc
    if parts and parts[0].startswith("CRON_TZ="):
        name = parts.pop(0)[len("CRON_TZ="):]
        try:
            from zoneinfo import ZoneInfo
            zone = ZoneInfo(name)
        except (ImportError, KeyError, ValueError):
            try:
                ZoneInfo("UTC")
            except (ImportError, KeyError, ValueError):  # a sandbox with no tz database: not the file's fault
                raise CronUnsupported("no time zone database on this machine")
            raise ValueError("unknown time zone %r" % name)
    if len(parts) != 5:
        raise ValueError("expected five cron fields, got %d" % len(parts))
    minute, hour, dom, month, dow = parts
    minutes, hours = _cron_field(minute, 0, 59), _cron_field(hour, 0, 23)
    weekdays = {d % 7 for d in _cron_field(dow, 0, 7)}
    if dom != "*" or month != "*":
        raise CronUnsupported("day-of-month and month schedules are not understood")
    return zone, minutes, hours, weekdays


def last_fire(expr, now):
    """The most recent instant at or before `now` when this cron was due, or None."""
    zone, minutes, hours, weekdays = parse_cron(expr)
    local = now.astimezone(zone)
    for back in range(0, 8):
        day = local.date() - dt.timedelta(days=back)
        if (day.weekday() + 1) % 7 not in weekdays:
            continue
        for h in sorted(hours, reverse=True):
            for m in sorted(minutes, reverse=True):
                when = dt.datetime(day.year, day.month, day.day, h, m, tzinfo=zone)
                if when <= local:
                    return when
    return None


def _utc(when):
    return when.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if when else None


def health_row(data, now, path=None):
    """Did this project's last scheduled run happen? A run that dies before it starts (the
    weekly usage limit, a missing connector, a disabled trigger) leaves no trace in the repo
    except a last_run that stops moving — which is what this reads."""
    row = {"id": data.get("id"), "path": path, "cron": (data.get("cadence") or {}).get("cron"),
           "last_run": None, "expected": None, "missed": False, "note": None}
    run = data.get("last_run") or {}
    try:
        last = as_dt(run.get("at"))
    except (ValueError, TypeError):
        last = None
    row["last_run"] = _utc(last)
    # A local project with a cron is a scheduled task on the household's own machine and can
    # miss a fire just as a cloud trigger can; one without a cron is interactive.
    if data.get("status") != "active" or data.get("runtime") not in ("cloud", "local") or not row["cron"]:
        row["note"] = "not on a schedule"
        return row
    try:
        due = last_fire(row["cron"], now)
    except ValueError as exc:
        row["note"] = "cron not understood: %s" % exc
        return row
    if due is None:
        return row
    row["expected"] = _utc(due)
    if now - due < dt.timedelta(minutes=HEALTH_GRACE_MINUTES):
        row["note"] = "the latest fire is still inside the grace window"
        return row
    if last is None or last < due:
        row["missed"] = True
        row["hours_late"] = round((now - due).total_seconds() / 3600, 1)
        row["note"] = "no run recorded since the %s fire" % due.strftime("%a %m-%d %H:%M %Z")
    return row


# ── query ──────────────────────────────────────────────────────────────────


def _term(value):
    """A Gmail search term: quoted unless it is a bare address, domain or word."""
    text = str(value).strip().replace('"', "")
    return text if re.match(r"^[\w.@+-]+$", text) else '"%s"' % text


def _uniq(seq):
    seen, out = set(), []
    for x in seq:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def texts_plan(folders, since, last, top):
    """Retained text threads (the `texts` skill files them as <folder>/YYYY-MM.md). A text
    counts like an email, so the plan says which month files cover the window and whether
    anything landed in the folder since the last run."""
    plan = []
    for folder in folders or []:
        folder = str(folder.get("folder") if isinstance(folder, dict) else folder).strip("/")
        full = os.path.join(top, folder)
        months = sorted(f for f in (os.listdir(full) if os.path.isdir(full) else [])
                        if re.match(r"^\d{4}-\d{2}\.md$", f) and f[:7] >= since.strftime("%Y-%m"))
        changed = bool(months)
        if months and last is not None:
            log = subprocess.run(["git", "log", "-1", "--format=%H", "--since=%s" % last.isoformat(), "--", folder],
                                 cwd=top, capture_output=True, text=True, timeout=60)
            if log.returncode == 0:
                dirty = subprocess.run(["git", "status", "--porcelain", "--", folder],
                                       cwd=top, capture_output=True, text=True, timeout=60).stdout.strip()
                changed = bool(log.stdout.strip() or dirty)
        plan.append({"folder": folder, "files": [os.path.join(folder, m) for m in months],
                     "new_since_last_run": changed})
    return plan


def query(data, now, since=None, top=None):
    """The sync plan. Searches used to be written fresh each run, and drifted: some left out
    `-in:sent`, some the identifiers, and the date window moved a day either way. The window
    opens one day before the last run so a timezone edge never drops a message."""
    watch = data.get("watch") or {}
    run = data.get("last_run") or {}
    try:
        last = as_dt(run.get("at"))
    except (ValueError, TypeError):
        last = None
    if since is None:
        since = (last.astimezone(dt.timezone.utc).date() - dt.timedelta(days=1)) if last \
            else now.date() - dt.timedelta(days=14)
    domains, emails = [], []
    for p in parties(data):
        domains += [str(d).lower() for d in (p.get("domains") or [])]
        emails += [str(e).lower() for e in (p.get("emails") or [])]
    domains = _uniq(domains)
    emails = [e for e in _uniq(emails) if e.split("@")[-1] not in domains]
    who = emails + domains
    words = _uniq([_term(x) for x in (watch.get("identifiers") or []) + (watch.get("keywords") or [])])
    exclude = "".join(" -%s" % str(x).strip() for x in (watch.get("exclude") or []) if str(x).strip())
    after = "after:%s" % since.strftime("%Y/%m/%d")
    plan = {"since": since.isoformat(), "gmail": {}, "drive": [], "web": [], "open_draft_ids": [], "mandatory": []}
    inbound = ["from:%s" % _term(w) for w in who] + words
    if inbound:
        plan["gmail"]["inbound"] = "%s -in:sent -in:draft (%s)%s" % (after, " OR ".join(inbound), exclude)
        plan["mandatory"].append("gmail.inbound")
    if who:
        # Recipient terms, not bare ones: a bare domain also matches any digest the household
        # sends itself that quotes every project's correspondents.
        to = " OR ".join("to:%s OR cc:%s" % (_term(w), _term(w)) for w in who)
        plan["gmail"]["sent"] = "%s in:sent (%s)%s" % (after, to, exclude)
        plan["gmail"]["drafts"] = "(%s)" % " OR ".join("to:%s" % _term(w) for w in who)
        plan["mandatory"].append("gmail.sent")
    plan["open_draft_ids"] = _uniq([str(a.get("draft_id")) for a in items(data, "actions")
                                    if is_open(a) and a.get("draft_id")])
    for folder in watch.get("drive_folders") or []:
        if isinstance(folder, dict) and folder.get("id"):
            plan["drive"].append({"name": folder.get("name"), "id": folder.get("id"),
                                  "query": "parentId = '%s' and modifiedTime > '%sT00:00:00Z'"
                                           % (folder.get("id"), since.isoformat())})
    if plan["drive"]:
        plan["mandatory"].append("drive")
    plan["web"] = [w for w in (watch.get("web") or []) if isinstance(w, dict) and w.get("url")]
    if plan["web"]:
        plan["mandatory"].append("web")
    plan["texts"] = texts_plan(watch.get("texts"), since, last, top or repo_top())
    if plan["texts"]:
        plan["mandatory"].append("texts")
    return plan


# ── render ─────────────────────────────────────────────────────────────────


def _cell(value):
    return ("" if value is None else str(value)).replace("\n", " ").replace("|", "\\|").strip()


def _date(value):
    try:
        d = as_date(value)
    except (ValueError, TypeError):
        return _cell(value)
    return d.isoformat() if d else ""


def render_block(name, data):
    lines = [NOTE, ""]
    if name == "status":
        owners = ", ".join(data.get("owners") or [])
        lines.append("**Project status:** %s · **Owners:** %s · **Hard deadline:** %s"
                     % (data.get("status"), owners, _date(data.get("hard_deadline")) or "none"))
        run = data.get("last_run") or {}
        if run.get("at"):
            lines.append("")
            lines.append("**Last managed run:** %s (%s) — %s"
                         % (_cell(run.get("at")), run.get("runtime", "?"), _cell(run.get("result"))))
        summary = str(data.get("summary") or "").strip()
        if summary:
            lines += ["", summary]
        stale = items(data, "discard_drafts")
        if stale:
            lines += ["", "**Drafts to discard in Gmail** — superseded; the engine never deletes:"]
            for d in stale:
                why = " — %s" % _cell(d.get("why")) if d.get("why") else ""
                lines.append("- `%s` %s%s" % (_cell(d.get("id")), _cell(d.get("subject")), why))
    elif name == "decisions":
        rows = items(data, "decisions")
        if not rows:
            lines.append("_No decisions logged._")
        else:
            lines += ["| ID | Decision | Status | Date |", "| :-- | :--- | :--- | :--- |"]
            for d in rows:
                lines.append("| %s | %s | %s | %s |" % (_cell(d.get("id")), _cell(d.get("text")),
                                                        "✅ DECIDED" if d.get("status") == "DECIDED" else "⏳ OPEN",
                                                        _date(d.get("date"))))
    elif name == "actions":
        rows = [a for a in items(data, "actions") if is_open(a)]
        closed = len(items(data, "actions")) - len(rows)
        if not rows:
            lines.append("_No open actions._")
        else:
            lines += ["| # | Action | Owner | Due | Status | Next step |", "| :-- | :--- | :--- | :--- | :--- | :--- |"]
            rows.sort(key=lambda a: (_date(a.get("due")) or "9999", str(a.get("id"))))
            for a in rows:
                lines.append("| %s | %s | %s | %s | %s | %s |" % (
                    _cell(a.get("id")), _cell(a.get("text")), _cell(a.get("owner")),
                    _date(a.get("due")), _cell(a.get("status") or "open"), _cell(a.get("next_step"))))
        if closed:
            lines += ["", "_%d closed action(s) still in `project.yaml`; older ones are in "
                          "`project-archive.yaml`._" % closed]
    elif name == "clocks":
        rows = [c for c in items(data, "clocks") if is_open(c)]
        if not rows:
            lines.append("_No running clocks._")
        else:
            lines += ["| Due | Item | Owner | If missed |", "| :--- | :--- | :--- | :--- |"]
            rows.sort(key=lambda c: _date(c.get("due")) or "9999")
            for c in rows:
                lines.append("| %s | %s | %s | %s |" % (_date(c.get("due")) or "*on event*", _cell(c.get("item")),
                                                        _cell(c.get("owner")), _cell(c.get("on_miss"))))
    elif name == "questions":
        rows = [q for q in items(data, "questions") if is_open(q)]
        if not rows:
            lines.append("_No open questions._")
        for i, q in enumerate(rows, 1):
            tail = []
            if q.get("for"):
                tail.append("for %s" % _cell(q.get("for")))
            if q.get("blocking"):
                tail.append("**blocking:** %s" % _cell(q.get("blocking")))
            if q.get("raised"):
                tail.append("raised %s" % _date(q.get("raised")))
            lines.append("%d. **[%s]** %s%s" % (i, _cell(q.get("id")), _cell(q.get("text")),
                                                (" — " + " · ".join(tail)) if tail else ""))
    return "\n".join(lines) + "\n"


def bump_modified(text, today):
    """Keep the note's frontmatter `modified:` honest — runs kept forgetting to."""
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---", 4)
    if end == -1:
        return text
    head, rest = text[:end], text[end:]
    stamped = re.sub(r"(?m)^modified:.*$", "modified: %sT00:00:00Z" % today.isoformat(), head, count=1)
    return stamped + rest


def render(data, text):
    """Rewrite each <!-- pm:begin X --> … <!-- pm:end X --> block present. Idempotent."""
    found = []
    for name in BLOCKS:
        rx = re.compile(r"(<!-- pm:begin %s -->\n)(.*?)(<!-- pm:end %s -->)" % (name, name), re.S)
        if rx.search(text):
            body = render_block(name, data)
            text = rx.sub(lambda m, body=body: m.group(1) + body + m.group(3), text)
            found.append(name)
    return text, found


# ── what a run cost ────────────────────────────────────────────────────────

RUNS_NAME = "runs.csv"
RUN_FIELDS = ["at", "runtime", "outcome", "verdict", "seconds", "turns", "model", "input_tokens",
              "output_tokens", "cache_read_tokens", "cache_write_tokens", "headline"]
START_MARK_HOURS = 6


def _is_prompt(entry):
    """A transcript line where someone (or the scheduler) spoke — not a tool result."""
    if entry.get("type") != "user" or entry.get("isMeta") or entry.get("isSidechain"):
        return False
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        kinds = {b.get("type") for b in content if isinstance(b, dict)}
        return "text" in kinds and "tool_result" not in kinds
    return False


def find_transcript(session_id=None, home=None):
    """The running session's JSONL transcript, or None. $PM_TRANSCRIPT names one directly (any
    harness that writes the same line shape); otherwise Claude Code's transcript store is
    searched for $CLAUDE_CODE_SESSION_ID. No transcript just means the cost columns stay blank."""
    named = os.environ.get("PM_TRANSCRIPT")
    if named and not session_id:
        return named if os.path.isfile(named) else None
    sid = session_id or os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not sid:
        return None
    root = os.path.join(home or os.path.expanduser("~"), ".claude", "projects")
    return next((os.path.join(root, d, sid + ".jsonl") for d in (os.listdir(root) if os.path.isdir(root) else [])
                 if os.path.isfile(os.path.join(root, d, sid + ".jsonl"))), None)


def session_usage(now, session_id=None, home=None):
    """What the current turn of the agent session has cost so far, read from its own
    transcript: seconds since the prompt that started it, model turns, and tokens.

    Nothing in a run log or the repo recorded this — the first month's numbers had to be dug
    out of logs one run at a time. Returns {} when there is no readable transcript. The count
    stops at the record step, so the closing message is not in it."""
    path = find_transcript(session_id, home)
    if not path:
        return {}
    started, calls, model = None, {}, None
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(entry, dict):
                    continue
                if _is_prompt(entry):
                    started, calls = entry.get("timestamp"), {}
                elif entry.get("type") == "assistant":
                    msg = entry.get("message") or {}
                    if msg.get("id") and isinstance(msg.get("usage"), dict):
                        calls[msg["id"]] = msg["usage"]  # a streamed message repeats; the last line is final
                        model = msg.get("model") or model
    except OSError:
        return {}
    if not calls:
        return {}

    def total(key):
        return sum(int(u.get(key) or 0) for u in calls.values())

    out = {"turns": len(calls), "model": model, "input_tokens": total("input_tokens"),
           "output_tokens": total("output_tokens"), "cache_read_tokens": total("cache_read_input_tokens"),
           "cache_write_tokens": total("cache_creation_input_tokens")}
    try:
        out["seconds"] = max(0, int((now - as_dt(started)).total_seconds()))
    except (ValueError, TypeError):
        pass
    return out


def _start_mark(pid):
    return os.path.join(tempfile.gettempdir(), "pm-run-%s.start" % _slug(pid))


def mark_start(pid, now):
    """Remember when this run's sync began, for sessions with no transcript to time from."""
    path = _start_mark(pid)
    try:
        fresh = os.path.exists(path) and (now.timestamp() - os.path.getmtime(path)) < START_MARK_HOURS * 3600
        if not fresh:
            with open(path, "w") as f:
                f.write(now.isoformat())
    except OSError as e:
        print(f"warning: failed to persist state ({e})", file=sys.stderr)  # was silent; persistence failures must be visible


def seconds_since_mark(pid, now, clear=True):
    path = _start_mark(pid)
    try:
        with open(path) as f:
            began = as_dt(f.read().strip())
        if clear:
            os.remove(path)
    except (OSError, ValueError, TypeError):
        return None
    elapsed = int((now - began).total_seconds())
    return elapsed if 0 <= elapsed < START_MARK_HOURS * 3600 else None


def runs_path(yaml_path):
    return os.path.join(os.path.dirname(os.path.abspath(yaml_path)), RUNS_NAME)


def append_run(yaml_path, row):
    """One line per recorded run, in runs.csv beside the project file."""
    import csv
    path = runs_path(yaml_path)
    new = not os.path.exists(path)
    with open(path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RUN_FIELDS, extrasaction="ignore")
        if new:
            writer.writeheader()
        writer.writerow({k: ("" if row.get(k) is None else row.get(k)) for k in RUN_FIELDS})


def read_runs(yaml_path):
    import csv
    path = runs_path(yaml_path)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def usage_summary(rows, since=None):
    """Roll runs.csv up: how many runs, how long, how many tokens — split quiet from acted,
    because a quiet run is the one that should cost almost nothing."""
    def num(row, key):
        try:
            return int(row.get(key) or 0)
        except ValueError:
            return 0

    def median(values):
        values = sorted(values)
        if not values:
            return None
        mid = len(values) // 2
        return values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) // 2

    out = {}
    for outcome in ("quiet", "acted"):
        picked = [r for r in rows if r.get("outcome") == outcome and (since is None or str(r.get("at", ""))[:10] >= since.isoformat())]
        timed = [num(r, "seconds") for r in picked if r.get("seconds")]
        metered = [r for r in picked if r.get("turns")]
        tokens = {k: sum(num(r, k) for r in metered) for k in
                  ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")}
        out[outcome] = {"runs": len(picked), "median_seconds": median(timed),
                        "median_turns": median([num(r, "turns") for r in metered]),
                        "metered_runs": len(metered), "tokens": tokens,
                        "tokens_per_run": {k: (v // len(metered) if metered else None) for k, v in tokens.items()}}
    return out


# ── record ─────────────────────────────────────────────────────────────────

LOG_ANCHOR = re.compile(r"(?im)^(?:#{1,6}\s.*activity log.*|.*<summary>.*activity log.*)$")
LOG_ENTRY = re.compile(r"(?m)^### \d{4}-\d{2}-\d{2}\b.*$")
QUIET_ENTRY = re.compile(r"^### \d{4}-\d{2}-\d{2} — Quiet \(since (\d{4}-\d{2}-\d{2})\)\s*$")
LOG_MARKER = "<!-- pm:log -->"


def last_run_block(at, runtime, result, escalated):
    """The last_run block as text. JSON strings are valid YAML double-quoted scalars, which
    is the point: hand-written results kept breaking on quotes and colons."""
    lines = ["last_run:",
             "  at: %s" % json.dumps(at),
             "  runtime: %s" % runtime,
             "  result: %s" % json.dumps(result, ensure_ascii=False)]
    if escalated:
        lines.append("  escalated:")
        lines += ["    - %s" % json.dumps(key) for key in escalated]
    else:
        lines.append("  escalated: []")
    return lines


def set_last_run(text, block):
    """Swap the top-level last_run block for `block`, leaving every other byte alone."""
    lines = text.split("\n")
    start = next((i for i, line in enumerate(lines) if re.match(r"^last_run:\s*(#.*)?$", line)), None)
    if start is None:
        body = text if text.endswith("\n") else text + "\n"
        return body + "\n" + "\n".join(block) + "\n"
    end = start + 1
    while end < len(lines) and (lines[end][:1] in (" ", "\t") or not lines[end].strip()):
        end += 1
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    return "\n".join(lines[:start] + block + lines[end:])


def add_log(text, today, headline, body, quiet):
    """Put one entry at the top of the Activity Log. A quiet run rolls a single
    `Quiet (since …)` entry forward rather than adding a line a day."""
    if LOG_MARKER in text:
        at = text.index(LOG_MARKER) + len(LOG_MARKER)
        at = text.index("\n", at) + 1 if "\n" in text[at:] else len(text)
        first = LOG_ENTRY.search(text, at)
        if first and text[at:first.start()].strip():
            first = None
    else:
        anchor = LOG_ANCHOR.search(text)
        if not anchor:
            text = text.rstrip("\n") + "\n\n## Activity Log\n\n"
            anchor = LOG_ANCHOR.search(text)
        at = min(anchor.end() + 1, len(text))
        first = LOG_ENTRY.search(text, at)
        if not first:
            rest = text[at:].split("\n")
            skip = 0
            while skip < len(rest) and (not rest[skip].strip() or rest[skip].lstrip().startswith(("<details", "<summary"))):
                skip += 1
            at += sum(len(line) + 1 for line in rest[:skip])
            at = min(at, len(text))
    body = (body or "").strip()
    if quiet:
        since = today.isoformat()
        if first:
            was = QUIET_ENTRY.match(first.group(0))
            if was:
                since = was.group(1)
                nxt = LOG_ENTRY.search(text, first.end())
                stop = nxt.start() if nxt else len(text)
                close = text.find("</details>", first.end(), stop)
                stop = close if close != -1 else stop
                entry = "### %s — Quiet (since %s)\n%s\n\n" % (today.isoformat(), since, body)
                return text[:first.start()] + entry + text[stop:], "rolled the quiet entry forward"
        entry = "### %s — Quiet (since %s)\n%s\n\n" % (today.isoformat(), since, body)
    else:
        entry = "### %s — %s\n%s\n\n" % (today.isoformat(), headline, body)
    where = first.start() if first else at
    lead = "" if where == 0 or text[:where].endswith("\n\n") else "\n"
    return text[:where] + lead + entry + text[where:], "added a log entry"


def _git(args, cwd, check=True):
    done = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True, timeout=60)
    if check and done.returncode != 0:
        raise RuntimeError("git %s: %s" % (" ".join(args), (done.stderr or done.stdout).strip()))
    return done


def remote_session():
    """True in a hosted (cloud) agent session: $PM_REMOTE, or Claude Code's own marker."""
    return bool(os.environ.get("PM_REMOTE") or os.environ.get("CLAUDE_CODE_REMOTE"))


def _paths():
    return CONFIG.get("paths") or {}


def commit(top, paths, message):
    """Stage only the project's own files and commit. Returns the short sha, or None.
    When the repo has a mojibake guard (config `paths.mojibake_guard`, else tools/ or scripts/
    mojibake_guard.py), the staged change must pass it."""
    _git(["add", "-A", "--"] + paths, top)
    if _git(["diff", "--cached", "--quiet"], top, check=False).returncode == 0:
        return None
    named = _paths().get("mojibake_guard")
    candidates = [named] if named else ["tools/mojibake_guard.py", "scripts/mojibake_guard.py"]
    guard = next((os.path.join(top, c) for c in candidates if os.path.exists(os.path.join(top, c))), None)
    if guard:
        checked = subprocess.run([sys.executable, guard, "--staged"], cwd=top, capture_output=True, text=True, timeout=60)
        if checked.returncode != 0:
            raise RuntimeError("mojibake guard: %s" % (checked.stdout + checked.stderr).strip())
    _git(["commit", "-q", "-m", message], top)
    return _git(["rev-parse", "--short=8", "HEAD"], top).stdout.strip()


def publish(top, attempts=3):
    """Land this session's commit on origin/main and prove it got there.

    Fast path is a rebase in place and a plain push. When the tree holds someone else's
    uncommitted work, or the rebase is not clean, or local `main` carries other unpushed
    commits, fall back to cherry-picking the newest commit onto a throwaway worktree at
    origin/main. Never forces, never sweeps other commits along.
    """
    def based():
        return _git(["merge-base", "--is-ancestor", "origin/main", "HEAD"], top, check=False).returncode == 0

    how = "push"
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], top).stdout.strip()
    for _ in range(attempts):
        _git(["fetch", "-q", "origin", "main"], top)
        ahead = _git(["rev-list", "--reverse", "origin/main..HEAD"], top).stdout.split()
        if not ahead:
            return {"published": True, "how": "already on origin/main"}
        # On a session branch every commit ahead is this session's own. On `main` only the
        # newest is — older unpushed ones belong to someone else and stay put.
        whole = len(ahead) == 1 or branch != "main"
        dirty = bool(_git(["status", "--porcelain", "--untracked-files=no"], top).stdout.strip())
        if whole and not based() and not dirty:
            if _git(["rebase", "-q", "origin/main"], top, check=False).returncode == 0:
                how = "rebase + push"
            else:
                _git(["rebase", "--abort"], top, check=False)
        left = []
        if whole and based():
            sha = _git(["rev-parse", "HEAD"], top).stdout.strip()
            pushed = _git(["push", "-q", "origin", "HEAD:main"], top, check=False)
        else:
            how = "cherry-pick onto a fresh origin/main"
            left = ahead[:-1] if branch == "main" else []
            picks = ahead[-1:] if branch == "main" else ahead
            tmp = tempfile.mkdtemp(prefix="pm-publish-")
            try:
                _git(["worktree", "add", "-q", "--detach", tmp, "origin/main"], top)
                picked = _git(["cherry-pick"] + picks, tmp, check=False)
                if picked.returncode != 0:
                    _git(["cherry-pick", "--abort"], tmp, check=False)
                    return {"published": False, "how": how,
                            "error": "the commit conflicts with origin/main — resolve by hand: %s"
                                     % (picked.stderr or picked.stdout).strip()[:300]}
                sha = _git(["rev-parse", "HEAD"], tmp).stdout.strip()
                pushed = _git(["push", "-q", "origin", "HEAD:main"], tmp, check=False)
            finally:
                _git(["worktree", "remove", "--force", tmp], top, check=False)
        if pushed.returncode == 0:
            _git(["fetch", "-q", "origin", "main"], top)
            landed = _git(["merge-base", "--is-ancestor", sha, "origin/main"], top, check=False).returncode == 0
            prefix = (CONFIG.get("publish") or {}).get("session_branch_prefix")
            if landed and whole and prefix and branch.startswith(prefix) and remote_session():
                # Some hosted sessions insist the session branch itself is on the remote,
                # whatever main holds. Pushing it here saves the run a turn.
                _git(["push", "-q", "-u", "origin", "HEAD:refs/heads/%s" % branch], top, check=False)
            out = {"published": landed, "how": how, "sha": sha[:8]}
            if left:
                out["left_unpushed"] = [x[:8] for x in left]
            return out
    return {"published": False, "how": how, "error": "origin/main kept moving — push rejected %d times" % attempts}


def record(yaml_path, result, runtime, headline=None, log=None, quiet=False, events=(),
           index=None, now=None, today=None, allow_decision_change=False, write=True, usage=None):
    """The whole Record step in one move: stamp last_run from the clock, carry the
    suppression keys forward, validate, write the log entry, re-render index.md and add the
    run to runs.csv (with what it cost, when `usage` is given).

    Returns (report, errors). Nothing is written when there are errors."""
    now = now or dt.datetime.now(dt.timezone.utc)
    today = today or home_today(now)
    with open(yaml_path, encoding="utf-8") as f:
        text = f.read()
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        return {}, ["%s: top level must be a mapping" % yaml_path]
    try:
        report = clocks(data, today)
    except (ValueError, TypeError) as exc:
        return {}, ["a date in the file does not parse: %s" % exc]
    prior = [str(k) for k in ((data.get("last_run") or {}).get("escalated") or [])]
    kept = []
    for key in prior:
        if key.startswith("event:"):
            try:
                if (today - dt.date.fromisoformat(key[-10:])).days <= EVENT_KEY_DAYS:
                    kept.append(key)
            except ValueError:
                pass  # best-effort: unreadable/absent state falls back to defaults
    fresh = ["event:%s:%s" % (_slug(slug), today.isoformat()) for slug in events]
    escalated = _uniq(report["escalate_keys"] + kept + fresh)
    new_keys = [k for k in escalated if k not in prior]
    stamp = now.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    new_text = set_last_run(text, last_run_block(stamp, runtime, " ".join(str(result).split()), escalated))
    try:
        new_data = yaml.safe_load(new_text)
    except yaml.YAMLError as exc:
        return {}, ["rewriting last_run would break the file: %s" % exc]
    before = {k: v for k, v in data.items() if k != "last_run"}
    after = {k: v for k, v in (new_data or {}).items() if k != "last_run"}
    if before != after:
        return {}, ["last_run is not a plain top-level block here — fix the file by hand first"]
    errors = validate(new_data, now) + archive_collisions(new_data, load_archive(yaml_path))
    if not allow_decision_change:
        old = head_version(yaml_path)
        if old is not None:
            errors += decided_changes(old, new_data)
    if errors:
        return {}, errors
    said = {w["key"]: w["what"] for w in report["work"]}
    out = {"at": stamp, "runtime": runtime, "verdict": "escalate" if new_keys else "quiet",
           "new_keys": new_keys,
           "new": [{"key": k, "what": said.get(k, "an engine trigger fired this run")} for k in new_keys],
           "escalated": escalated,
           "stale_overdue": [r["id"] for r in report["overdue"] if r.get("stale")]}
    index = index or os.path.join(os.path.dirname(os.path.abspath(yaml_path)), "index.md")
    index_text = None
    if os.path.exists(index):
        with open(index, encoding="utf-8") as f:
            index_text = f.read()
        if quiet or headline:
            index_text, out["log"] = add_log(index_text, today, headline, log or result, quiet)
        index_text, found = render(new_data, index_text)
        if found:
            index_text = bump_modified(index_text, today)
        out["rendered"] = found
    else:
        out["log"] = "no index.md beside the project file"
    row = dict(usage or {})
    row.update({"at": stamp, "runtime": runtime, "outcome": "quiet" if quiet else "acted",
                "verdict": out["verdict"], "headline": "" if quiet else " ".join(str(headline or "").split())})
    out["cost"] = {k: row.get(k) for k in RUN_FIELDS[4:11] if row.get(k) is not None}
    if write:
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(new_text)
        if index_text is not None:
            with open(index, "w", encoding="utf-8") as f:
                f.write(index_text)
        append_run(yaml_path, row)
    return out, []


# ── archive ────────────────────────────────────────────────────────────────


def _closed_on(row):
    for field in ("done_on", "raised", "due"):
        try:
            when = as_date(row.get(field))
        except (ValueError, TypeError):
            when = None
        if when:
            return when
    return None


def archive(yaml_path, today, days=14, write=True, questions=False):
    """Lift closed actions, clocks and needs_local older than `days` out of project.yaml into
    project-archive.yaml beside it. Decisions never move: DECIDED ones are standing guidance
    and the lock checks them. Answered questions stay unless asked for — the answer is often
    the only place a fact from a human lives.

    Lines are cut by position so comments and layout survive, then the result is re-parsed
    and must equal the original minus exactly the archived items — or nothing is written."""
    with open(yaml_path, encoding="utf-8") as f:
        text = f.read()
    data = yaml.safe_load(text)
    root = yaml.compose(text)
    lines = text.split("\n")
    spans, moved = [], {}
    for key_node, value_node in root.value:
        name = key_node.value
        if name not in ARCHIVE_LISTS or not isinstance(value_node, yaml.SequenceNode):
            continue
        if name == "questions" and not questions:
            continue
        rows = data.get(name) or []
        for i, node in enumerate(value_node.value):
            row = rows[i]
            if not isinstance(row, dict) or is_open(row):
                continue
            when = _closed_on(row)
            if when is None or (today - when).days < days:
                continue
            first = node.start_mark.line
            # A flow item ends on its own closing line; a block item's end mark is the next
            # token, which already sits on the line after it.
            last = node.end_mark.line + 1 if node.flow_style else max(node.end_mark.line, first + 1)
            while last - 1 > first and (not lines[last - 1].strip() or lines[last - 1].lstrip().startswith("#")):
                last -= 1
            if not re.match(r"^\s*-\s", lines[first]):
                continue  # an item that does not start its own line: leave it be
            spans.append((first, last))
            moved.setdefault(name, []).append(row)
    if not spans:
        return {"archived": {}, "bytes_saved": 0}, []
    drop = set()
    for first, last in spans:
        drop.update(range(first, last))
    new_text = "\n".join(line for i, line in enumerate(lines) if i not in drop)
    for name in moved:
        if len(moved[name]) == len(data.get(name) or []):
            new_text = re.sub(r"(?m)^%s:[ \t]*(#.*)?$" % name, lambda m: "%s: []%s" % (name, "  " + m.group(1) if m.group(1) else ""),
                              new_text, count=1)
    try:
        new_data = yaml.safe_load(new_text)
    except yaml.YAMLError as exc:
        return {}, ["cutting the closed items would break the file: %s" % exc]
    expected = dict(data)
    for name, rows in moved.items():
        gone = {id(r) for r in rows}
        expected[name] = [r for r in data[name] if id(r) not in gone]
    if new_data != expected:
        return {}, ["could not cut the closed items cleanly — archive them by hand"]
    path = archive_path(yaml_path)
    kept = load_archive(yaml_path)
    for name, rows in moved.items():
        kept.setdefault(name, [])
        kept[name] += rows
    header = ("# Closed items lifted out of project.yaml by `pm.py archive` so runs read less.\n"
              "# History only — the engine never reads this file except to keep ids unique.\n"
              "# Search it when a closed item matters; never reuse an id listed here.\n\n")
    if write:
        with open(path, "w", encoding="utf-8") as f:
            f.write(header + yaml.safe_dump(kept, allow_unicode=True, sort_keys=False, width=100))
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(new_text)
    return {"archived": {name: [r.get("id") for r in rows] for name, rows in moved.items()},
            "bytes_saved": len(text.encode("utf-8")) - len(new_text.encode("utf-8")),
            "archive": os.path.relpath(path)}, []


# ── routine ────────────────────────────────────────────────────────────────


def _routine_settings(settings=None):
    return settings if settings is not None else (CONFIG.get("routine") or {})


def routine_dir(top=None, settings=None):
    """Where routine prompt files live: config `routine.dir`, relative to the skill folder
    (default `routines`)."""
    base = os.path.join(top, "skills", "project-manager") if top else SKILL_DIR
    return os.path.join(base, _routine_settings(settings).get("dir") or "routines")


def routine_file(pid, top=None, settings=None):
    return os.path.join(routine_dir(top, settings), "%s.md" % pid)


def routine_spec(pid, top=None, settings=None):
    """What the schedule should be, read from <routine dir>/<id>.md: frontmatter + prompt."""
    path = routine_file(pid, top, settings)
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if not text.startswith("---\n") or "\n---" not in text[4:]:
        raise SystemExit("%s: no frontmatter" % path)
    end = text.index("\n---", 4)
    meta = yaml.safe_load(text[4:end]) or {}
    prompt = text[end + 4:].strip() + "\n"
    return {"id": pid, "trigger_id": meta.get("trigger_id"), "name": meta.get("trigger_name"),
            "cron": meta.get("cron"), "prompt": prompt}


def _find(obj, key):
    """Every value stored under `key` anywhere in a nested structure."""
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                hits.append(v)
            hits += _find(v, key)
    elif isinstance(obj, list):
        for v in obj:
            hits += _find(v, key)
    return hits


def routine_drift(spec, deployed, project=None, settings=None):
    """Compare the routine file (and the project's own fields) with a saved trigger definition
    from a hosted agent scheduler (JSON with id, cron_expression, name, job_config,
    mcp_connections, notifications). Every line returned is something to fix; an empty list is
    in sync. The git-source and connector checks run only when config `routine.repo` /
    `routine.connectors` name what the trigger must carry."""
    settings = _routine_settings(settings)
    repo = settings.get("repo")
    connectors = list(settings.get("connectors") or [])
    trig = deployed.get("trigger", deployed)
    drift = []
    if trig.get("id") != spec["trigger_id"]:
        drift.append("trigger id: file says %s, the saved trigger is %s" % (spec["trigger_id"], trig.get("id")))
    if not trig.get("enabled", True):
        drift.append("the trigger is disabled")
    if _norm(trig.get("cron_expression")) != _norm(spec["cron"]):
        drift.append("cron: file %r, deployed %r" % (spec["cron"], trig.get("cron_expression")))
    if _norm(trig.get("name")) != _norm(spec["name"]):
        drift.append("name: file %r, deployed %r" % (spec["name"], trig.get("name")))
    prompts = [c for c in _find(trig.get("job_config") or {}, "content") if isinstance(c, str)]
    if not prompts:
        drift.append("no prompt found on the trigger")
    elif _norm(prompts[0]) != _norm(spec["prompt"]):
        drift.append("prompt: the deployed text differs from the file — redeploy it")
    urls = " ".join(str(u) for u in _find(trig.get("job_config") or {}, "url"))
    if repo and repo not in urls:
        drift.append("no %s git source — a run would have to clone by hand and stall" % repo)
    links = {c.get("name"): c for c in trig.get("mcp_connections") or [] if isinstance(c, dict)}
    for name in connectors:
        if name not in links:
            drift.append("connector missing: %s — the run cannot sync it" % name)
    allowed = (links.get("Gmail") or {}).get("permitted_tools")
    if "Gmail" in links:
        if not allowed:
            drift.append("Gmail has no permitted_tools list, so send, reply, forward and trash are callable")
        else:
            extra = sorted(set(allowed) - GMAIL_READ_DRAFT_TOOLS)
            if extra:
                drift.append("Gmail permits more than read + draft: %s" % ", ".join(extra))
    channel = ((trig.get("notifications") or {}).get("channel") or {})
    if not channel.get("push"):
        drift.append("push notifications are off — nobody would see an escalation")
    if project is not None:
        if project.get("trigger_id") != spec["trigger_id"]:
            drift.append("project.yaml trigger_id is %r, the routine file says %r"
                         % (project.get("trigger_id"), spec["trigger_id"]))
        if _norm((project.get("cadence") or {}).get("cron")) != _norm(spec["cron"]):
            drift.append("project.yaml cadence.cron is %r, the routine file says %r"
                         % ((project.get("cadence") or {}).get("cron"), spec["cron"]))
    return drift


def read_saved_json(path):
    """A saved tool result: tolerate the `HTTP 200` line and trailing notes around the JSON."""
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    return json.JSONDecoder().raw_decode(raw[raw.index("{"):])[0]


# ── queue ──────────────────────────────────────────────────────────────────


def queue(data):
    return {
        "questions": [q for q in items(data, "questions") if is_open(q)],
        "needs_local": [n for n in items(data, "needs_local") if is_open(n)],
    }


# ── cli ────────────────────────────────────────────────────────────────────


def _dump(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    day = "YYYY-MM-DD; default is today in %s" % (HOME_TZ or "the local time zone")

    sub.add_parser("list")

    pa = sub.add_parser("path")
    pa.add_argument("ref", help="project id, notes folder, or project.yaml")

    v = sub.add_parser("validate")
    v.add_argument("yaml")
    v.add_argument("--no-git", action="store_true", help="skip the DECIDED lock check against HEAD")
    v.add_argument("--allow-decision-change", action="store_true",
                   help="interactive only, when a human has explicitly reversed a decision")

    c = sub.add_parser("clocks")
    c.add_argument("yaml")
    c.add_argument("--today", help=day)

    qy = sub.add_parser("query")
    qy.add_argument("yaml")
    qy.add_argument("--since", help="YYYY-MM-DD; default is the day before last_run.at")

    h = sub.add_parser("health")
    h.add_argument("yaml", nargs="*", help="default: every registered project")
    h.add_argument("--now", help="ISO-8601 instant; default is now")
    h.add_argument("--check", action="store_true", help="exit 1 when any scheduled run was missed")

    rc = sub.add_parser("record")
    rc.add_argument("yaml")
    rc.add_argument("--result", required=True, help="one line: what this run found and did")
    rc.add_argument("--runtime", choices=sorted(RUN_RUNTIMES),
                    help="default: cloud in a remote session, else interactive")
    rc.add_argument("--quiet", action="store_true", help="nothing arrived, nothing due: roll the quiet log line")
    rc.add_argument("--headline", help="Activity Log heading for a run that did something")
    rc.add_argument("--log", help="Activity Log body; default is --result")
    rc.add_argument("--log-file", help="read the Activity Log body from a file")
    rc.add_argument("--event", action="append", default=[],
                    help="slug of an escalate_when trigger that fired (repeatable)")
    rc.add_argument("--today", help=day)
    rc.add_argument("--allow-decision-change", action="store_true")
    rc.add_argument("--commit", action="store_true", help="commit the project's folder")
    rc.add_argument("--publish", action="store_true", help="and land the commit on origin/main")
    rc.add_argument("--trailer", action="append", default=[], help="commit trailer line (repeatable)")

    r = sub.add_parser("render")
    r.add_argument("yaml")
    r.add_argument("--index", help="default: index.md beside project.yaml")
    r.add_argument("--check", action="store_true", help="exit 1 if the file would change; write nothing")
    r.add_argument("--today", help="YYYY-MM-DD used for the frontmatter modified: stamp")

    q = sub.add_parser("queue")
    q.add_argument("yaml")

    us = sub.add_parser("usage")
    us.add_argument("yaml")
    us.add_argument("--days", type=int, default=30, help="look back this many days (0 = everything)")

    ar = sub.add_parser("archive")
    ar.add_argument("yaml")
    ar.add_argument("--days", type=int, default=14, help="only items closed at least this long (default 14)")
    ar.add_argument("--dry-run", action="store_true")
    ar.add_argument("--questions", action="store_true",
                    help="also move answered questions (their answers leave the file the run reads)")
    ar.add_argument("--today", help=day)

    ro = sub.add_parser("routine")
    ro.add_argument("id")
    ro.add_argument("--deployed", help="file holding a saved trigger definition (JSON) to compare against")

    args = ap.parse_args(argv)

    if args.cmd == "list":
        _dump(listing())
        return 0
    if args.cmd == "path":
        print(resolve(args.ref))
        return 0
    if args.cmd == "health":
        now = as_dt(args.now) if args.now else dt.datetime.now(dt.timezone.utc)
        rows = [health_row(load(resolve(y)), now, y) for y in args.yaml] if args.yaml \
            else [health_row(data, now, rel) for rel, data in registry()]
        missed = [r for r in rows if r["missed"]]
        _dump({"now": _utc(now), "missed": missed,
               "ok": [r["id"] for r in rows if not r["missed"] and r["expected"]]})
        return 1 if (args.check and missed) else 0
    if args.cmd == "routine":
        spec = routine_spec(args.id)
        if not args.deployed:
            _dump(spec)
            return 0
        try:
            project = load(resolve(args.id))
        except SystemExit:
            project = None
        drift = routine_drift(spec, read_saved_json(args.deployed), project)
        for line in drift:
            print("✗ " + line)
        if not drift:
            print("✓ %s matches its routine file" % spec["trigger_id"])
        return 1 if drift else 0

    args.yaml = resolve(args.yaml)
    data = load(args.yaml)
    today = as_date(getattr(args, "today", None)) if getattr(args, "today", None) else home_today()

    if args.cmd == "validate":
        errors = validate(data) + archive_collisions(data, load_archive(args.yaml))
        if not args.no_git and not args.allow_decision_change:
            old = head_version(args.yaml)
            if old is not None:
                errors += decided_changes(old, data)
        if errors:
            for e in errors:
                print("✗ " + e)
            return 1
        for w in warnings(data, os.path.getsize(args.yaml)):
            print("⚠ " + w)
        print("✓ %s valid" % args.yaml)
        return 0

    if args.cmd == "clocks":
        _dump(clocks(data, today))
        return 0

    if args.cmd == "query":
        now = dt.datetime.now(dt.timezone.utc)
        mark_start(data.get("id"), now)
        _dump(query(data, now, as_date(args.since) if args.since else None))
        return 0

    if args.cmd == "usage":
        since = today - dt.timedelta(days=args.days) if args.days else None
        _dump({"project": data.get("id"), "since": since.isoformat() if since else None,
               "file": os.path.relpath(runs_path(args.yaml)), **usage_summary(read_runs(args.yaml), since)})
        return 0

    if args.cmd == "record":
        if not args.quiet and not args.headline:
            print("✗ pass --quiet, or --headline for a run that did something")
            return 2
        log = args.log
        if args.log_file:
            with open(args.log_file, encoding="utf-8") as f:
                log = f.read()
        runtime = args.runtime or ("cloud" if remote_session() else "interactive")
        now = dt.datetime.now(dt.timezone.utc)
        usage = session_usage(now)
        marked = seconds_since_mark(data.get("id"), now)
        if "seconds" not in usage and marked is not None:
            usage["seconds"] = marked
        out, errors = record(args.yaml, args.result, runtime, headline=args.headline, log=log,
                             quiet=args.quiet, events=args.event, today=today, now=now,
                             allow_decision_change=args.allow_decision_change, usage=usage)
        if errors:
            for e in errors:
                print("✗ " + e)
            print("✗ nothing was written")
            return 1
        if args.commit or args.publish:
            folder = os.path.dirname(os.path.realpath(args.yaml))
            top = os.path.realpath(repo_top(folder))
            root = os.path.relpath(folder, top)
            headline = "quiet run %s" % today.isoformat() if args.quiet else args.headline
            message = "%s: %s" % (data.get("id"), headline)
            if args.trailer:
                message += "\n\n" + "\n".join(args.trailer)
            try:
                out["commit"] = commit(top, [root], message)
                if args.publish:
                    out.update(publish(top))
            except RuntimeError as exc:
                out["error"] = str(exc)
        _dump(out)
        if out.get("error") or (args.publish and not out.get("published")):
            print("✗ recorded locally but NOT on origin/main — publish it by hand")
            return 3
        if args.quiet and out["verdict"] == "quiet":
            print("NEXT: reply with exactly one line starting `Quiet —` and stop.")
        else:
            print("NEXT: your final message must START with one line, under 200 characters, that leads "
                  "with what the human has to do. Then: what arrived, what was drafted or booked, and "
                  "every item under \"new\" above — each one handled or explained.")
        return 0

    if args.cmd == "archive":
        out, errors = archive(args.yaml, today, days=args.days, write=not args.dry_run,
                              questions=args.questions)
        if errors:
            for e in errors:
                print("✗ " + e)
            return 1
        _dump(out)
        return 0

    if args.cmd == "render":
        index = args.index or os.path.join(os.path.dirname(os.path.abspath(args.yaml)), "index.md")
        with open(index, encoding="utf-8") as f:
            before = f.read()
        after, found = render(data, before)
        if found:
            after = bump_modified(after, today)
        if not found:
            print("no pm:begin/pm:end markers in %s — nothing rendered" % index)
            return 0
        if args.check:
            print("%s: %s" % (index, "up to date" if after == before else "WOULD CHANGE"))
            return 0 if after == before else 1
        if after != before:
            with open(index, "w", encoding="utf-8") as f:
                f.write(after)
        print("rendered %s into %s%s" % (", ".join(found), index, "" if after != before else " (no change)"))
        return 0

    if args.cmd == "queue":
        _dump(queue(data))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
