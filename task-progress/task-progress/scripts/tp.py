#!/usr/bin/env python3
"""
tp.py — deterministic helper for the `task-progress` Claude Code skill.

Owns everything that must be exact: Task ID allocation, task resolution,
structured entries (D/F/T/B), immutable checkpoints, index rebuild, verify,
compact, recover, close gating. Free-form narrative files (CURRENT_STATE,
SESSION_HANDOFF, PROGRESS text, NEXT_STEPS lists) are edited by Claude directly.

State root: <project-root>/.claude/task-state/
Project root: $TASK_STATE_PROJECT_ROOT, else `git rev-parse --show-toplevel`, else cwd.

Only read-only git commands are ever executed.
Standard library only (Python >= 3.8).
"""
import argparse, contextlib, datetime as dt, hashlib, os, re, shutil, stat, subprocess, sys, unicodedata

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(SKILL_DIR, "templates")

STATE_FILES = ["TASK.md", "CURRENT_STATE.md", "PROGRESS.md", "DECISIONS.md", "FAILED_ATTEMPTS.md",
               "BLOCKERS.md", "FILES.md", "TESTS.md", "NEXT_STEPS.md", "SESSION_HANDOFF.md"]
# Order used by resume-pack (priority first, per compaction design)
PACK_ORDER = ["TASK.md", "CURRENT_STATE.md", "SESSION_HANDOFF.md", "NEXT_STEPS.md", "DECISIONS.md",
              "BLOCKERS.md", "FAILED_ATTEMPTS.md", "PROGRESS.md", "FILES.md", "TESTS.md"]
STATUSES = ["IN_PROGRESS", "BLOCKED", "WAITING_USER", "REVIEW", "PAUSED", "COMPLETED", "ABANDONED"]
ACTIVE = {"IN_PROGRESS", "BLOCKED", "WAITING_USER", "REVIEW"}
DIR_RE = re.compile(r"^(TASK-\d{8}-\d{3})_([a-z0-9-]+)$")
ID_RE = re.compile(r"^TASK-\d{8}-\d{3}$", re.I)
ENTRY_FILES = {"D": "DECISIONS.md", "F": "FAILED_ATTEMPTS.md", "T": "TESTS.md", "B": "BLOCKERS.md"}
FILE_SECTIONS = {"important": "IMPORTANT FILES", "read": "FILES READ", "created": "FILES CREATED",
                 "modified": "FILES MODIFIED", "deleted": "FILES DELETED"}
RECON_BANNER = "> ⚠ RECONSTRUCTED {ts} — this file was missing or corrupted. Content is rebuilt from evidence " \
               "(filesystem/git/checkpoints), NOT original history. Items marked [RECONSTRUCTED] are unconfirmed.\n\n"


# ----------------------------------------------------------------------------- basics
def now():
    return dt.datetime.now().astimezone().replace(microsecond=0).isoformat()

def die(msg, code=1):
    print(f"ERROR: {msg}", file=sys.stderr); sys.exit(code)

def run(cmd, cwd):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=20)
        return r.returncode, r.stdout.strip()
    except Exception as e:  # git missing etc.
        return 1, str(e)

def project_root():
    env = os.environ.get("TASK_STATE_PROJECT_ROOT")
    if env:
        return os.path.abspath(env)
    code, out = run(["git", "rev-parse", "--show-toplevel"], os.getcwd())
    return out if code == 0 and out else os.getcwd()

def state_root():
    return os.path.join(project_root(), ".claude", "task-state")

@contextlib.contextmanager
def lock():
    os.makedirs(state_root(), exist_ok=True)
    gi = os.path.join(state_root(), ".gitignore")
    if not os.path.exists(gi):
        with open(gi, "w") as g:
            g.write(".lock\n*.tmp\n")
    path = os.path.join(state_root(), ".lock")
    f = open(path, "w")
    try:
        try:
            import fcntl; fcntl.flock(f, fcntl.LOCK_EX)
        except ImportError:
            pass  # Windows: best effort
        yield
    finally:
        f.close()

def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()

def write(p, s):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(s)
    os.replace(tmp, p)  # atomic

def slugify(name, maxlen=50):
    s = name.replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    s = s[:maxlen].rstrip("-")
    return s or "task"

def norm(s):
    return slugify(s, 200)

def render(tpl, ctx):
    s = read(os.path.join(TEMPLATE_DIR, tpl))
    for k, v in ctx.items():
        s = s.replace("{{" + k + "}}", v)
    return s

def bullets(items, empty="_TBD_"):
    return "\n".join(f"- {i}" for i in items) if items else empty


# ----------------------------------------------------------------------------- task model
def header(task_dir):
    """Parse identity fields from TASK.md. Returns {} if missing/corrupt."""
    p = os.path.join(task_dir, "TASK.md")
    if not os.path.exists(p):
        return {}
    h = {}
    for line in read(p).splitlines()[:30]:
        m = re.match(r"^(Task ID|Task Name|Task Slug|Project|Created|Last Updated|Status):\s*(.*)$", line)
        if m:
            h[m.group(1)] = m.group(2).strip()
    return h

def all_tasks():
    root = state_root()
    out = []
    if not os.path.isdir(root):
        return out
    for d in sorted(os.listdir(root)):
        m = DIR_RE.match(d)
        full = os.path.join(root, d)
        if not (m and os.path.isdir(full)):
            continue
        h = header(full)
        out.append({"id": m.group(1), "slug": m.group(2), "dir": full, "dirname": d,
                    "name": h.get("Task Name", "?"), "status": h.get("Status", "CORRUPTED"),
                    "updated": h.get("Last Updated", "?"), "project": h.get("Project", "?"),
                    "header_ok": h.get("Task ID", "").upper() == m.group(1)})
    return out

def resolve(ref, quiet=False):
    """Resolve ref -> task dict. Priority: Task ID > dir name > slug > name > partial.
    Never picks randomly: ambiguity exits with code 2 and a candidate list."""
    ref = ref.strip().strip('"').strip("'")
    tasks = all_tasks()
    if not tasks:
        die(f"no tasks found under {state_root()}", 3)
    tiers = [
        ("task-id", [t for t in tasks if t["id"].upper() == ref.upper()]),
        ("dir-name", [t for t in tasks if t["dirname"] == ref.rstrip("/").split("/")[-1]]),
        ("slug", [t for t in tasks if t["slug"] == ref]),
        ("name", [t for t in tasks if norm(t["name"]) == norm(ref)]),
        ("partial", [t for t in tasks if norm(ref) and (norm(ref) in t["slug"] or norm(ref) in norm(t["name"]))]),
    ]
    for tier, hits in tiers:
        if not hits:
            continue
        if len(hits) == 1:
            if not quiet:
                print(f"RESOLVED ({tier}): {hits[0]['id']}  {hits[0]['name']}  [{hits[0]['status']}]", file=sys.stderr)
            return hits[0]
        active = [t for t in hits if t["status"] in ACTIVE]
        if tier != "partial" and len(active) == 1:
            others = ", ".join(t["id"] for t in hits if t is not active[0])
            print(f"RESOLVED ({tier}, only active match): {active[0]['id']}  (inactive same-name: {others})", file=sys.stderr)
            return active[0]
        print(f"AMBIGUOUS: '{ref}' matches {len(hits)} tasks ({tier}). Re-run with a Task ID:", file=sys.stderr)
        for t in hits:
            print(f"  {t['id']}  {t['name']}  [{t['status']}]  updated {t['updated']}  project {t['project']}", file=sys.stderr)
        sys.exit(2)
    print(f"NOT FOUND: '{ref}'. Known tasks:", file=sys.stderr)
    for t in tasks:
        print(f"  {t['id']}  {t['name']}  [{t['status']}]", file=sys.stderr)
    sys.exit(3)

def set_header_field(task_dir, field, value):
    p = os.path.join(task_dir, "TASK.md")
    s = read(p)
    s2, n = re.subn(rf"^{field}:.*$", f"{field}: {value}", s, count=1, flags=re.M)
    if n == 0:
        die(f"TASK.md has no '{field}:' line")
    write(p, s2)

def touch(task_dir):
    ts = now()
    set_header_field(task_dir, "Last Updated", ts)
    cs = os.path.join(task_dir, "CURRENT_STATE.md")
    if os.path.exists(cs):
        s = read(cs)
        write(cs, re.sub(r"^> Last Updated:.*$", f"> Last Updated: {ts}", s, count=1, flags=re.M))

def log_event(task_dir, kind, ident, summary):
    p = os.path.join(task_dir, "history", "events.log")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(f"{now()}\t{kind}\t{ident}\t{summary.replace(chr(10), ' ')}\n")

def section(text, title):
    """Return body of '## title' section (up to next '## ')."""
    m = re.search(rf"^## {re.escape(title)}\s*$(.*?)(?=^## |\Z)", text, flags=re.M | re.S)
    return m.group(1).strip() if m else None

def replace_section(text, title, body):
    pat = rf"(^## {re.escape(title)}\s*$)(.*?)(?=^## |\Z)"
    if not re.search(pat, text, flags=re.M | re.S):
        return text.rstrip() + f"\n\n## {title}\n\n{body}\n"
    return re.sub(pat, lambda m: f"{m.group(1)}\n\n{body}\n\n", text, count=1, flags=re.M | re.S)

def append_to_section(text, title, line):
    pat = rf"(^## {re.escape(title)}\s*$)(.*?)(?=^## |\Z)"
    m = re.search(pat, text, flags=re.M | re.S)
    if not m:
        return text.rstrip() + f"\n\n## {title}\n\n{line}\n"
    body = m.group(2).rstrip()
    new = f"{m.group(1)}{body}\n{line}\n\n" if body.strip() else f"{m.group(1)}\n\n{line}\n\n"
    return text[:m.start()] + new + text[m.end():]

def next_entry_id(task_dir, prefix):
    s = read(os.path.join(task_dir, ENTRY_FILES[prefix]))
    nums = [int(n) for n in re.findall(rf"^## {prefix}-(\d{{3}})", s, flags=re.M)]
    return f"{prefix}-{(max(nums) + 1 if nums else 1):03d}"

def git_snapshot(root):
    code, _ = run(["git", "rev-parse", "--is-inside-work-tree"], root)
    if code != 0:
        return None
    g = {}
    g["branch"] = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], root)[1] or "?"
    c, head = run(["git", "log", "-1", "--format=%h %s"], root)
    g["head"] = head if c == 0 and head else "(no commits)"
    g["status"] = run(["git", "status", "--porcelain"], root)[1]
    g["diffstat"] = run(["git", "diff", "--stat", "HEAD"], root)[1] if c == 0 else ""
    return g

def git_block(g):
    if g is None:
        return "Not a git repository.\n"
    return (f"- Branch: `{g['branch']}`\n- HEAD: `{g['head']}`\n"
            f"- Uncommitted changes: {len(g['status'].splitlines()) if g['status'] else 0} file(s)\n\n"
            f"```\n{g['status'] or '(clean)'}\n```\n\n"
            + (f"Diff stat vs HEAD:\n\n```\n{g['diffstat']}\n```\n" if g['diffstat'] else ""))


# ----------------------------------------------------------------------------- index
def rebuild_index():
    tasks = all_tasks()
    root = state_root()
    rows = "\n".join(f"| {t['id']} | {t['name']} | {t['status']} | {t['updated']} | `{t['dirname']}/` |" for t in tasks)
    hdr = "| Task ID | Task Name | Status | Last Updated | Path |\n|---|---|---|---|---|\n"
    note = "<!-- GENERATED by tp.py index from task directories. Task directories are the source of truth. -->\n\n"
    write(os.path.join(root, "task-index.md"), f"# Task Index\n\n{note}{hdr}{rows}\n")
    act = [t for t in tasks if t["status"] in ACTIVE]
    rows = "\n".join(f"| {t['id']} | {t['name']} | {t['status']} | {t['updated']} | `{t['dirname']}/` |" for t in act)
    write(os.path.join(root, "active-tasks.md"),
          f"# Active Tasks\n\nStatuses: {', '.join(sorted(ACTIVE))}\n\n{note}{hdr}{rows}\n")
    return tasks

def finish(task_dir):
    touch(task_dir)
    rebuild_index()


# ----------------------------------------------------------------------------- commands
def cmd_init(a):
    name = a.name.strip()
    if not name:
        die("task name required")
    with lock():
        root = state_root()
        os.makedirs(root, exist_ok=True)
        today = dt.datetime.now().strftime("%Y%m%d")
        seqs = [int(t["id"][-3:]) for t in all_tasks() if t["id"][5:13] == today]
        tid = f"TASK-{today}-{(max(seqs) + 1 if seqs else 1):03d}"
        slug = slugify(name)
        tdir = os.path.join(root, f"{tid}_{slug}")
        if os.path.exists(tdir):
            die(f"{tdir} already exists")
        ts = now()
        ctx = {"TASK_ID": tid, "TASK_NAME": name, "TASK_SLUG": slug,
               "PROJECT": a.project or os.path.basename(project_root()), "NOW": ts,
               "OBJECTIVE": a.objective or "_TBD — clarify with user_",
               "REQUIREMENTS": bullets(a.requirement), "CONSTRAINTS": bullets(a.constraint, "None stated."),
               "ACCEPTANCE": "\n".join(f"- [ ] {x}" for x in a.acceptance) if a.acceptance else "- [ ] _TBD — define with user_",
               "NEXT_ACTION": a.next or "Clarify objective, requirements and acceptance criteria, then plan the first implementation step."}
        os.makedirs(os.path.join(tdir, "checkpoints"))
        os.makedirs(os.path.join(tdir, "history"))
        for f in STATE_FILES:
            write(os.path.join(tdir, f), render(f, ctx))
        write(os.path.join(tdir, "checkpoints", "INDEX.md"),
              "# Checkpoint Index\n\n| Checkpoint | Created | Session | Location | SHA-256 |\n|---|---|---|---|---|\n")
        log_event(tdir, "init", tid, f"created '{name}'")
    task = resolve(tid, quiet=True)
    _checkpoint(task, a.session or "session-init", "## Completed since previous checkpoint\n\n- Task initialized.\n")
    rebuild_index()
    print("TASK CREATED\n")
    print(f"Task ID:\n{tid}\n\nTask Name:\n{name}\n\nTask Slug:\n{slug}\n")
    print(f"State Path:\n.claude/task-state/{tid}_{slug}/\n\nStatus:\nIN_PROGRESS")

def cmd_resolve(a):
    t = resolve(a.ref)
    print(t["id"]); print(t["dir"])

def cmd_list(a):
    tasks = all_tasks()
    for t in tasks:
        if a.active and t["status"] not in ACTIVE:
            continue
        print(f"{t['id']}  [{t['status']}]  {t['name']}  (updated {t['updated']})")
    if not tasks:
        print("(no tasks)")

def cmd_index(a):
    with lock():
        tasks = rebuild_index()
    print(f"index rebuilt: {len(tasks)} task(s)")

def cmd_brief(a):
    """For SessionStart hook: short, never fails."""
    try:
        act = [t for t in all_tasks() if t["status"] in ACTIVE]
    except Exception:
        return
    if not act:
        return
    print("task-progress: active tasks in this project (resume with /task-progress resume <TASK_ID>):")
    for t in act:
        print(f"  {t['id']} [{t['status']}] {t['name']}")
    print("No task is active in this session until one is explicitly resumed.")

def cmd_add(a):
    t = resolve(a.ref, quiet=True)
    d = t["dir"]
    ts = now()
    kv = dict(x.split("=", 1) for x in (a.field or []))
    with lock():
        if a.kind == "file":
            sec = FILE_SECTIONS.get(kv.get("kind", "").lower())
            if not sec or "path" not in kv:
                die("file needs kind=important|read|created|modified|deleted path=<relpath> [note=...]")
            p = os.path.join(d, "FILES.md")
            s = read(p)
            body = section(s, sec) or ""
            if f"`{kv['path']}`" in body:
                print(f"already listed under {sec}: {kv['path']}"); return
            line = f"- `{kv['path']}`" + (f" — {kv['note']}" if kv.get("note") else "") + f" ({ts[:10]})"
            write(p, append_to_section(s, sec, line))
            log_event(d, "file", kv["kind"], kv["path"])
            print(f"FILES.md[{sec}] += {kv['path']}")
        else:
            spec = {
                "decision": ("D", ["title", "decision", "reason", "alternatives", "consequence"],
                             ["Decision", "Reason", "Alternatives considered", "Consequence"]),
                "failed": ("F", ["title", "problem", "approach", "result", "why", "lesson", "next"],
                           ["Problem", "Approach attempted", "Result", "Why it failed", "What was learned", "Recommended next approach"]),
                "test": ("T", ["case", "command", "expected", "actual", "result"],
                         ["Command", "Test case", "Expected", "Actual", "Result", "Evidence", "Notes"]),
                "blocker": ("B", ["title", "cause", "impact", "action"],
                            ["Cause", "Impact", "Attempts", "Required action", "Needs user input"]),
            }[a.kind]
            prefix, required, labels = spec
            missing = [r for r in required if not kv.get(r)]
            if missing:
                die(f"{a.kind} requires fields: {', '.join(missing)}")
            eid = next_entry_id(d, prefix)
            if a.kind == "decision":
                title = kv["title"]
                lines = [f"- Date: {ts}", f"- Status: {kv.get('status', 'ACTIVE')}", f"- Decision: {kv['decision']}",
                         f"- Reason: {kv['reason']}", f"- Alternatives considered: {kv['alternatives']}",
                         f"- Consequence: {kv['consequence']}"]
            elif a.kind == "failed":
                title = kv["title"]
                lines = [f"- Date: {ts}"] + [f"- {lab}: {kv[k]}" for k, lab in zip(required[1:], labels)]
            elif a.kind == "test":
                res = kv["result"].upper()
                if res not in ("PASS", "FAIL", "NOT_RUN", "PARTIAL"):
                    die("result must be PASS|FAIL|PARTIAL|NOT_RUN")
                if res == "PASS" and (kv["command"].strip().lower() in ("", "n/a", "none") or not kv["actual"].strip()):
                    die("PASS requires the real command/inspection and the actual observed result")
                title = f"{kv['case']} — {res}"
                lines = [f"- Timestamp: {ts}", f"- Command: `{kv['command']}`", f"- Test case: {kv['case']}",
                         f"- Expected: {kv['expected']}", f"- Actual: {kv['actual']}", f"- Result: {res}",
                         f"- Evidence: {kv.get('evidence', '(see Actual)')}", f"- Notes: {kv.get('notes', '-')}"]
            else:  # blocker
                st = kv.get("status", "BLOCKED").upper()
                if st not in ("BLOCKED", "WAITING_USER"):
                    die("new blocker status must be BLOCKED or WAITING_USER")
                title = kv["title"]
                lines = [f"- Status: {st}", f"- Opened: {ts}", f"- Cause: {kv['cause']}", f"- Impact: {kv['impact']}",
                         f"- Attempts: {kv.get('attempts', 'none yet')}", f"- Required action: {kv['action']}",
                         f"- Needs user input: {'yes' if st == 'WAITING_USER' else kv.get('user', 'no')}",
                         "- Resolution: -"]
            p = os.path.join(d, ENTRY_FILES[prefix])
            write(p, read(p).rstrip() + f"\n\n## {eid}: {title}\n\n" + "\n".join(lines) + "\n")
            log_event(d, a.kind, eid, title)
            print(f"{eid} added to {ENTRY_FILES[prefix]}")
        finish(d)

def cmd_set_entry(a):
    t = resolve(a.ref, quiet=True)
    d = t["dir"]
    prefix = a.entry[0].upper()
    if prefix not in ENTRY_FILES:
        die("entry id must start with D-, F-, T- or B-")
    p = os.path.join(d, ENTRY_FILES[prefix])
    with lock():
        s = read(p)
        m = re.search(rf"^## {re.escape(a.entry.upper())}:.*?(?=^## |\Z)", s, flags=re.M | re.S)
        if not m:
            die(f"{a.entry} not found in {ENTRY_FILES[prefix]}")
        block = m.group(0)
        if re.search(rf"^- {re.escape(a.field)}:.*$", block, flags=re.M):
            nb = re.sub(rf"^- {re.escape(a.field)}:.*$", f"- {a.field}: {a.value}", block, count=1, flags=re.M)
        else:
            nb = block.rstrip() + f"\n- {a.field}: {a.value}\n\n"
        write(p, s[:m.start()] + nb + s[m.end():])
        log_event(d, "set-entry", a.entry.upper(), f"{a.field} = {a.value}")
        finish(d)
    print(f"{a.entry.upper()}.{a.field} = {a.value}")

def cmd_set_next(a):
    t = resolve(a.ref, quiet=True)
    d = t["dir"]
    with lock():
        for f in ("CURRENT_STATE.md", "NEXT_STEPS.md"):
            p = os.path.join(d, f)
            write(p, replace_section(read(p), "NEXT IMMEDIATE ACTION", a.text))
        log_event(d, "next", "-", a.text)
        finish(d)
    print("NEXT IMMEDIATE ACTION updated in CURRENT_STATE.md and NEXT_STEPS.md")

def cmd_set_status(a):
    t = resolve(a.ref, quiet=True)
    st = a.status.upper()
    if st not in STATUSES:
        die(f"status must be one of {STATUSES}")
    if st == "COMPLETED":
        ok, report = close_check(t)
        if not ok:
            print(report); die("refusing COMPLETED: close-check failed (fix evidence first)", 4)
    with lock():
        set_header_field(t["dir"], "Status", st)
        p = os.path.join(t["dir"], "CURRENT_STATE.md")
        write(p, replace_section(read(p), "CURRENT STATUS", st + (f" — {a.reason}" if a.reason else "")))
        log_event(t["dir"], "status", st, a.reason or "")
        finish(t["dir"])
    print(f"{t['id']} status -> {st}")

def latest_checkpoint(task_dir):
    cps = sorted(f for f in os.listdir(os.path.join(task_dir, "checkpoints")) if re.match(r"checkpoint-\d{3}\.md$", f))
    return os.path.join(task_dir, "checkpoints", cps[-1]) if cps else None

def _all_checkpoint_numbers(task_dir):
    nums = []
    for sub in ("checkpoints", os.path.join("history", "archive")):
        p = os.path.join(task_dir, sub)
        if os.path.isdir(p):
            nums += [int(m.group(1)) for f in os.listdir(p) if (m := re.match(r"checkpoint-(\d{3})\.md$", f))]
    return nums

def _checkpoint(t, session, summary):
    d = t["dir"]
    nums = _all_checkpoint_numbers(d)
    n = (max(nums) + 1) if nums else 1
    cid = f"checkpoint-{n:03d}"
    prev = latest_checkpoint(d)
    prev_pos = 0  # events are tracked by log position, not timestamps (same-second safe)
    if prev:
        m = re.search(r"^- Event log position: (\d+)$", read(prev), flags=re.M)
        prev_pos = int(m.group(1)) if m else 0
    ev = os.path.join(d, "history", "events.log")
    lines = read(ev).splitlines() if os.path.exists(ev) else []
    events = []
    for line in lines[prev_pos:]:
        parts = line.split("\t")
        if len(parts) == 4 and parts[1] != "checkpoint":
            events.append(f"- {parts[0]} · {parts[1]} · {parts[2]} · {parts[3]}")
    pos = len(lines) + 1  # include this checkpoint's own event line
    h = header(d)
    cs = read(os.path.join(d, "CURRENT_STATE.md"))
    ns = read(os.path.join(d, "NEXT_STEPS.md"))
    g = git_snapshot(project_root())
    body = (f"# {cid} — {t['id']}\n\n"
            f"- Checkpoint ID: {cid}\n- Date: {now()}\n- Session: {session}\n- Task ID: {t['id']}\n"
            f"- Task Name: {h.get('Task Name', '?')}\n- Status: {h.get('Status', '?')}\n"
            f"- Previous checkpoint: {os.path.basename(prev) if prev else 'none'}\n- Event log position: {pos}\n\n"
            f"> IMMUTABLE. Do not edit. Corrections go into the next checkpoint.\n\n"
            f"{summary.strip()}\n\n"
            f"## Current status (snapshot of CURRENT_STATE)\n\n"
            f"- Phase: {(section(cs, 'CURRENT PHASE') or '?').splitlines()[0]}\n"
            f"- Working on: {(section(cs, 'WHAT IS BEING WORKED ON') or '?')}\n"
            f"- Current problem: {(section(cs, 'CURRENT PROBLEM') or '?')}\n\n"
            f"## Structured events since previous checkpoint (auto)\n\n" + ("\n".join(events) or "- none") + "\n\n"
            f"## Git state (auto, read-only)\n\n{git_block(g)}\n"
            f"## Next immediate action\n\n{section(ns, 'NEXT IMMEDIATE ACTION') or '?'}\n")
    p = os.path.join(d, "checkpoints", f"{cid}.md")
    write(p, body)
    os.chmod(p, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    digest = hashlib.sha256(body.encode()).hexdigest()
    idx = os.path.join(d, "checkpoints", "INDEX.md")
    with open(idx, "a", encoding="utf-8") as f:
        f.write(f"| {cid} | {now()} | {session} | checkpoints/ | {digest} |\n")
    hp = os.path.join(d, "SESSION_HANDOFF.md")
    write(hp, re.sub(r"Latest checkpoint:.*$", f"Latest checkpoint: {cid}", read(hp), count=1, flags=re.M))
    log_event(d, "checkpoint", cid, session)
    return cid, p

def cmd_checkpoint(a):
    t = resolve(a.ref, quiet=True)
    summary = read(a.summary_file) if a.summary_file else "## Completed since previous checkpoint\n\n- (no summary provided)\n"
    with lock():
        cid, p = _checkpoint(t, a.session or f"session-{dt.datetime.now():%Y%m%d-%H%M}", summary)
        finish(t["dir"])
    print(f"CHECKPOINT CREATED: {cid}\n{p}")

def verify(t):
    """Return list of (level, message). level: MISMATCH | WARN | INFO."""
    d, root, out = t["dir"], project_root(), []
    for f in STATE_FILES:
        if not os.path.exists(os.path.join(d, f)):
            out.append(("MISMATCH", f"state file missing: {f} (run recover)"))
    h = header(d)
    if not h.get("Task ID"):
        out.append(("MISMATCH", "TASK.md header unreadable (run recover)"))
    elif h["Task ID"].upper() != t["id"]:
        out.append(("MISMATCH", f"TASK.md says {h['Task ID']} but directory is {t['id']} — possible cross-task contamination"))
    for f in STATE_FILES:
        p = os.path.join(d, f)
        if os.path.exists(p):
            foreign = set(re.findall(r"TASK-\d{8}-\d{3}", read(p))) - {t["id"]}
            if foreign:
                out.append(("WARN", f"{f} mentions other task IDs {sorted(foreign)} — confirm this is intentional cross-reference"))
    fp = os.path.join(d, "FILES.md")
    if os.path.exists(fp):
        s = read(fp)
        for key, sec in FILE_SECTIONS.items():
            for rel in re.findall(r"`([^`]+)`", section(s, sec) or ""):
                exists = os.path.exists(os.path.join(root, rel))
                if key == "deleted" and exists:
                    out.append(("MISMATCH", f"{rel} listed as DELETED but exists"))
                elif key != "deleted" and not exists:
                    out.append(("MISMATCH", f"{rel} listed under {sec} but does not exist"))
    pp = os.path.join(d, "PROGRESS.md")
    if os.path.exists(pp):
        for line in (section(read(pp), "COMPLETED") or "").splitlines():
            if line.startswith("- ") and "evidence:" not in line.lower():
                out.append(("WARN", f"COMPLETED item without evidence: {line[2:80]}"))
    try:
        c1 = section(read(os.path.join(d, "CURRENT_STATE.md")), "NEXT IMMEDIATE ACTION")
        c2 = section(read(os.path.join(d, "NEXT_STEPS.md")), "NEXT IMMEDIATE ACTION")
        if (c1 or "").strip() != (c2 or "").strip():
            out.append(("WARN", "NEXT IMMEDIATE ACTION differs between CURRENT_STATE.md and NEXT_STEPS.md (use set-next)"))
        if not (c2 or "").strip() or "_TBD" in (c2 or ""):
            out.append(("WARN", "NEXT IMMEDIATE ACTION is empty/TBD"))
    except FileNotFoundError:
        pass
    idx = os.path.join(d, "checkpoints", "INDEX.md")
    if os.path.exists(idx):
        for m in re.finditer(r"^\| (checkpoint-\d{3}) \| [^|]+\| [^|]+\| ([^|]+)\| ([0-9a-f]{64}) \|", read(idx), flags=re.M):
            cid, loc, dig = m.group(1), m.group(2).strip(), m.group(3)
            p = os.path.join(d, "checkpoints", f"{cid}.md")
            if not os.path.exists(p):
                p = os.path.join(d, "history", "archive", f"{cid}.md")
            if not os.path.exists(p):
                out.append(("MISMATCH", f"{cid} missing (recorded in INDEX)"))
            elif hashlib.sha256(read(p).encode()).hexdigest() != dig:
                out.append(("MISMATCH", f"{cid} content changed after creation (checkpoints are immutable)"))
    g = git_snapshot(root)
    lc = latest_checkpoint(d)
    if g and lc:
        cp = read(lc)
        mb = re.search(r"^- Branch: `(.+)`$", cp, flags=re.M)
        mh = re.search(r"^- HEAD: `(.+)`$", cp, flags=re.M)
        if mb and mb.group(1) != g["branch"]:
            out.append(("INFO", f"branch changed since {os.path.basename(lc)}: {mb.group(1)} -> {g['branch']}"))
        if mh and mh.group(1) != g["head"]:
            out.append(("INFO", f"HEAD moved since {os.path.basename(lc)}: '{mh.group(1)}' -> '{g['head']}' (inspect git log)"))
        if g["status"]:
            listed = read(fp) if os.path.exists(fp) else ""
            for line in g["status"].splitlines():
                path = line[3:].split(" -> ")[-1]
                if path.startswith(".claude/task-state/"):
                    continue
                if f"`{path}`" not in listed:
                    out.append(("INFO", f"uncommitted change not tracked in FILES.md: {path} (may belong to another task)"))
    return out

def cmd_verify(a):
    t = resolve(a.ref, quiet=True)
    res = verify(t)
    print(f"VERIFY {t['id']} — {t['name']}")
    if not res:
        print("OK: state is internally consistent with the filesystem (tests are NOT re-run by this check).")
    for lvl, msg in res:
        print(f"{lvl}: {msg}")
    if any(l == "MISMATCH" for l, _ in res):
        print("\nSTATE / FILESYSTEM MISMATCH — investigate before trusting state.")
        sys.exit(5)

def cmd_resume_pack(a):
    t = resolve(a.ref)
    d = t["dir"]
    print(f"######## RESUME PACK — {t['id']} — {t['name']} ########")
    print(f"# Namespace: {d}\n# Only content below belongs to {t['id']}. Ignore any other task's state.\n")
    for f in PACK_ORDER:
        p = os.path.join(d, f)
        print(f"\n======== {t['id']} / {f} ========")
        if not os.path.exists(p):
            print("(MISSING)"); continue
        s = read(p)
        if f == "TESTS.md":
            entries = re.split(r"(?=^## T-\d{3})", s, flags=re.M)
            if len(entries) > a.tests + 1:
                s = entries[0] + f"(… {len(entries) - 1 - a.tests} older test entries omitted …)\n\n" + "".join(entries[-a.tests:])
        print(s.rstrip())
    comp = os.path.join(d, "history", "COMPACTED_HISTORY.md")
    if os.path.exists(comp):
        print(f"\n======== {t['id']} / history/COMPACTED_HISTORY.md ========\n{read(comp).rstrip()}")
    lc = latest_checkpoint(d)
    print(f"\n======== {t['id']} / latest checkpoint: {os.path.basename(lc) if lc else 'none'} ========")
    if lc:
        print(read(lc).rstrip())
    print(f"\n======== {t['id']} / VERIFY (automatic) ========")
    for lvl, msg in verify(t) or [("OK", "no structural mismatch")]:
        print(f"{lvl}: {msg}")
    print(f"\n######## END RESUME PACK — {t['id']} ########")

def cmd_status(a):
    t = resolve(a.ref, quiet=True)
    d = t["dir"]
    h = header(d)
    prog = read(os.path.join(d, "PROGRESS.md"))
    counts = {s: len([l for l in (section(prog, s) or "").splitlines() if l.startswith("- ")])
              for s in ("COMPLETED", "IN_PROGRESS", "PLANNED", "BLOCKED")}
    bl = read(os.path.join(d, "BLOCKERS.md"))
    open_b = [f"{m.group(1)} [{m.group(3)}] {m.group(2)}" for m in
              re.finditer(r"^## (B-\d{3}): (.*?)\n\n- Status: (\w+)", bl, flags=re.M) if m.group(3) != "RESOLVED"]
    lc = latest_checkpoint(d)
    print(f"{t['id']} — {h.get('Task Name')}\nStatus: {h.get('Status')}   Updated: {h.get('Last Updated')}")
    print("Progress: " + "  ".join(f"{k}={v}" for k, v in counts.items()))
    print("Open blockers: " + (", ".join(open_b) if open_b else "none"))
    print(f"Latest checkpoint: {os.path.basename(lc) if lc else 'none'}")
    print("Next immediate action: " + (section(read(os.path.join(d, 'NEXT_STEPS.md')), 'NEXT IMMEDIATE ACTION') or '?'))
    issues = verify(t)
    print(f"Verify: {sum(1 for l, _ in issues if l == 'MISMATCH')} mismatch, {sum(1 for l, _ in issues if l == 'WARN')} warn")

def cmd_compact(a):
    t = resolve(a.ref, quiet=True)
    d = t["dir"]
    cpdir = os.path.join(d, "checkpoints")
    cps = sorted(f for f in os.listdir(cpdir) if re.match(r"checkpoint-\d{3}\.md$", f))
    old = cps[:-a.keep] if a.keep > 0 else cps
    if not old:
        print(f"nothing to compact ({len(cps)} checkpoint(s), keep={a.keep})"); return
    with lock():
        arch = os.path.join(d, "history", "archive")
        os.makedirs(arch, exist_ok=True)
        lines = []
        for f in old:
            s = read(os.path.join(cpdir, f))
            date = (re.search(r"^- Date: (.+)$", s, flags=re.M) or [None, "?"])[1]
            nxt = section(s, "Next immediate action") or "?"
            done = section(s, "Completed since previous checkpoint") or "-"
            lines.append(f"### {f[:-3]} ({date})\n\nCompleted (as recorded):\n{done}\n\nNext action at that time: {nxt}\n")
            shutil.move(os.path.join(cpdir, f), os.path.join(arch, f))  # moved, never deleted
        ev = os.path.join(d, "history", "events.log")
        if os.path.exists(ev):
            shutil.copy(ev, os.path.join(arch, f"events-until-{dt.datetime.now():%Y%m%d-%H%M%S}.log"))
        comp = os.path.join(d, "history", "COMPACTED_HISTORY.md")
        existing = read(comp) if os.path.exists(comp) else f"# Compacted History — {t['id']}\n\n> Synthesized from archived checkpoints (originals kept in history/archive/).\n"
        cno = len(re.findall(r"^## Compaction C-", existing, flags=re.M)) + 1
        block = (f"\n## Compaction C-{cno:03d} — {now()} — {old[0][:-3]} … {old[-1][:-3]}\n\n"
                 f"### Synthesis (Claude must write this)\n\n_TBD: stable decisions, lessons learned, unresolved issues, important failed attempts._\n\n"
                 f"### Raw extracts (auto)\n\n" + "\n".join(lines))
        write(comp, existing.rstrip() + "\n" + block)
        log_event(d, "compact", f"C-{cno:03d}", f"archived {len(old)} checkpoints")
        finish(d)
    print(f"COMPACTED: {len(old)} checkpoint(s) moved to history/archive/ (not deleted). "
          f"Now write the 'Synthesis' section in history/COMPACTED_HISTORY.md.")

def close_check(t):
    d, rep, ok = t["dir"], [], True
    task = read(os.path.join(d, "TASK.md"))
    ac = section(task, "Acceptance Criteria") or ""
    crit = [l for l in ac.splitlines() if re.match(r"^- \[[ xX]\]", l)]
    if not crit or any("_TBD" in c for c in crit):
        ok = False; rep.append("FAIL: acceptance criteria not defined")
    for c in crit:
        if c.startswith("- [ ]"):
            ok = False; rep.append(f"FAIL: unmet criterion: {c[6:]}")
        elif "evidence:" not in c.lower():
            ok = False; rep.append(f"FAIL: ticked criterion without evidence: {c[6:]}")
        else:
            rep.append(f"ok: {c[6:]}")
    bl = read(os.path.join(d, "BLOCKERS.md"))
    for m in re.finditer(r"^## (B-\d{3}): (.*?)\n\n- Status: (\w+)", bl, flags=re.M):
        if m.group(3) != "RESOLVED":
            ok = False; rep.append(f"FAIL: open blocker {m.group(1)} [{m.group(3)}] {m.group(2)}")
    tests = read(os.path.join(d, "TESTS.md"))
    latest = {}
    for m in re.finditer(r"^## T-\d{3}: (.*) — (PASS|FAIL|PARTIAL|NOT_RUN)$", tests, flags=re.M):
        latest[m.group(1).strip()] = m.group(2)
    if not latest:
        ok = False; rep.append("FAIL: no recorded tests")
    for case, res in latest.items():
        if res != "PASS":
            ok = False; rep.append(f"FAIL: latest result of '{case}' is {res}")
    for lvl, msg in verify(t):
        if lvl == "MISMATCH":
            ok = False; rep.append(f"FAIL: {msg}")
    return ok, "\n".join(rep)

def cmd_close_check(a):
    t = resolve(a.ref, quiet=True)
    ok, rep = close_check(t)
    print(f"CLOSE CHECK {t['id']}: {'READY' if ok else 'NOT READY'}\n{rep}")
    sys.exit(0 if ok else 4)

def cmd_recover(a):
    root = state_root()
    os.makedirs(root, exist_ok=True)
    ts = now()
    t = None
    try:
        t = resolve(a.ref, quiet=True)
    except SystemExit:
        if not (ID_RE.match(a.ref) and a.name):
            die("task not found. To recreate a lost task directory pass its Task ID and --name.", 3)
    with lock():
        if t is None:
            tid = a.ref.upper()
            tdir = os.path.join(root, f"{tid}_{slugify(a.name)}")
            os.makedirs(os.path.join(tdir, "checkpoints"), exist_ok=True)
            os.makedirs(os.path.join(tdir, "history"), exist_ok=True)
            t = {"id": tid, "dir": tdir, "slug": slugify(a.name), "name": a.name}
        d = t["dir"]
        m = DIR_RE.match(os.path.basename(d))
        lc = latest_checkpoint(d) if os.path.isdir(os.path.join(d, "checkpoints")) else None
        cp_name = re.search(r"^- Task Name: (.+)$", read(lc), flags=re.M) if lc else None
        name = a.name or header(d).get("Task Name") or (cp_name.group(1) if cp_name else None) \
            or m.group(2).replace("-", " ") + " [RECONSTRUCTED name]"
        nxt = (section(read(lc), "Next immediate action") if lc else None) or \
              "[RECONSTRUCTED] Review RECOVERY_REPORT.md, confirm real state with the user, then set next action."
        ctx = {"TASK_ID": t["id"], "TASK_NAME": name, "TASK_SLUG": m.group(2), "PROJECT": os.path.basename(project_root()),
               "NOW": ts, "OBJECTIVE": "[RECONSTRUCTED] _unknown — confirm with user_", "REQUIREMENTS": "[RECONSTRUCTED] _unknown_",
               "CONSTRAINTS": "[RECONSTRUCTED] _unknown_", "ACCEPTANCE": "- [ ] _TBD — [RECONSTRUCTED], confirm with user_",
               "NEXT_ACTION": nxt}
        rebuilt = []
        for f in STATE_FILES:
            p = os.path.join(d, f)
            corrupt = f == "TASK.md" and os.path.exists(p) and not header(d).get("Task ID")
            if not os.path.exists(p) or corrupt:
                if corrupt:
                    shutil.copy(p, p + f".corrupt-{dt.datetime.now():%Y%m%d%H%M%S}")
                body = render(f, ctx)
                first_nl = body.index("\n") + 1
                write(p, body[:first_nl] + "\n" + RECON_BANNER.format(ts=ts) + body[first_nl:])
                if f == "TASK.md":
                    set_header_field(d, "Status", "PAUSED")
                rebuilt.append(f)
        idx = os.path.join(d, "checkpoints", "INDEX.md")
        if not os.path.exists(idx):
            write(idx, "# Checkpoint Index\n\n> ⚠ RECONSTRUCTED — original index lost; hashes below were computed at recovery time.\n\n"
                       "| Checkpoint | Created | Session | Location | SHA-256 |\n|---|---|---|---|---|\n")
            with open(idx, "a", encoding="utf-8") as fh:
                for sub in ("checkpoints", os.path.join("history", "archive")):
                    sp = os.path.join(d, sub)
                    for f in sorted(os.listdir(sp)) if os.path.isdir(sp) else []:
                        if re.match(r"checkpoint-\d{3}\.md$", f):
                            fh.write(f"| {f[:-3]} | [RECONSTRUCTED] | ? | {sub}/ | {hashlib.sha256(read(os.path.join(sp, f)).encode()).hexdigest()} |\n")
            rebuilt.append("checkpoints/INDEX.md")
        pr = project_root()
        g = git_snapshot(pr)
        glog = run(["git", "log", "--oneline", "-25"], pr)[1] if g else "not a git repo"
        cps = sorted(os.listdir(os.path.join(d, "checkpoints")))
        readmes = [f for f in os.listdir(pr) if f.lower().startswith("readme")]
        rep = (f"# Recovery Report — {t['id']}\n\n- Generated: {ts}\n- Rebuilt files: {', '.join(rebuilt) or 'none'}\n\n"
               f"Everything reconstructed from this evidence must be tagged [RECONSTRUCTED] until confirmed.\n\n"
               f"## Evidence: checkpoints present\n\n" + "\n".join(f"- {c}" for c in cps) + "\n\n"
               f"## Evidence: latest checkpoint\n\n{os.path.basename(lc) if lc else 'none'}\n\n"
               f"## Evidence: git\n\n{git_block(g)}\nRecent commits:\n\n```\n{glog}\n```\n\n"
               f"## Evidence: docs\n\n" + ("\n".join(f"- {r}" for r in readmes) or "- none") + "\n\n"
               f"## Claude TODO\n\n1. Read latest checkpoint + SESSION_HANDOFF (if they survived).\n2. Inspect source, git log, README, run tests.\n"
               f"3. Fill rebuilt files; tag inferred facts [RECONSTRUCTED].\n4. Confirm objective/acceptance with the user.\n"
               f"5. Record a checkpoint noting the recovery; set status back from PAUSED.\n")
        write(os.path.join(d, "RECOVERY_REPORT.md"), rep)
        log_event(d, "recover", "-", f"rebuilt: {', '.join(rebuilt) or 'none'}")
        rebuild_index()
    print(f"TASK STATE CORRUPTED → recovery scaffold written for {t['id']}\nRebuilt: {', '.join(rebuilt) or 'none'}\n"
          f"Report: {os.path.join(d, 'RECOVERY_REPORT.md')}")


def main():
    ap = argparse.ArgumentParser(prog="tp.py", description="task-progress state helper")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("init"); p.add_argument("name"); p.add_argument("--project"); p.add_argument("--objective")
    p.add_argument("--requirement", action="append", default=[]); p.add_argument("--constraint", action="append", default=[])
    p.add_argument("--acceptance", action="append", default=[]); p.add_argument("--next"); p.add_argument("--session")
    p.set_defaults(fn=cmd_init)
    p = sp.add_parser("resolve"); p.add_argument("ref"); p.set_defaults(fn=cmd_resolve)
    p = sp.add_parser("list"); p.add_argument("--active", action="store_true"); p.set_defaults(fn=cmd_list)
    p = sp.add_parser("index"); p.set_defaults(fn=cmd_index)
    p = sp.add_parser("brief"); p.set_defaults(fn=cmd_brief)
    p = sp.add_parser("add"); p.add_argument("ref"); p.add_argument("kind", choices=["decision", "failed", "test", "blocker", "file"])
    p.add_argument("field", nargs="*", help="key=value pairs"); p.set_defaults(fn=cmd_add)
    p = sp.add_parser("set-entry"); p.add_argument("ref"); p.add_argument("entry"); p.add_argument("field"); p.add_argument("value")
    p.set_defaults(fn=cmd_set_entry)
    p = sp.add_parser("set-next"); p.add_argument("ref"); p.add_argument("text"); p.set_defaults(fn=cmd_set_next)
    p = sp.add_parser("set-status"); p.add_argument("ref"); p.add_argument("status"); p.add_argument("--reason")
    p.set_defaults(fn=cmd_set_status)
    p = sp.add_parser("checkpoint"); p.add_argument("ref"); p.add_argument("--summary-file"); p.add_argument("--session")
    p.set_defaults(fn=cmd_checkpoint)
    p = sp.add_parser("verify"); p.add_argument("ref"); p.set_defaults(fn=cmd_verify)
    p = sp.add_parser("resume-pack"); p.add_argument("ref"); p.add_argument("--tests", type=int, default=10)
    p.set_defaults(fn=cmd_resume_pack)
    p = sp.add_parser("status"); p.add_argument("ref"); p.set_defaults(fn=cmd_status)
    p = sp.add_parser("compact"); p.add_argument("ref"); p.add_argument("--keep", type=int, default=3); p.set_defaults(fn=cmd_compact)
    p = sp.add_parser("close-check"); p.add_argument("ref"); p.set_defaults(fn=cmd_close_check)
    p = sp.add_parser("recover"); p.add_argument("ref"); p.add_argument("--name"); p.set_defaults(fn=cmd_recover)
    a = ap.parse_args()
    a.fn(a)

if __name__ == "__main__":
    main()
