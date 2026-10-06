---
name: task-progress
description: Persistent per-task state layer so a task can span many Claude Code sessions without losing context. Use when the user runs /task-progress (init, resume, checkpoint, status, update, handoff, compact, close), mentions a Task ID like TASK-20260928-001, asks to resume/continue/pick up/hand off a task from a previous session, save progress, checkpoint, or "where were we". Also use it silently whenever a task is active in this session and something state-worthy happens (file changed, test run, decision, failed approach, blocker) — even while another skill (coding, testing, debugging, docs) is doing the actual work.
argument-hint: <init|resume|checkpoint|status|update|handoff|compact|close> "<task name or TASK-ID>"
---

# task-progress — persistent task state layer

Conversation memory dies with the session. The task state directory does not.
This skill makes each task a **self-contained, independently resumable state namespace** under
`.claude/task-state/`, so Session B can continue Session A's task with zero retelling.

It does not replace coding/testing/design/docs/debug skills. It sits under them: they do the work,
this skill records what happened and restores it later.

## 0. Tooling

`TP` below means: `python3 <this skill's directory>/scripts/tp.py` run from the project root
(project install: `.claude/skills/task-progress/scripts/tp.py`; personal: `~/.claude/skills/task-progress/scripts/tp.py`).
Python ≥ 3.8, stdlib only. State root = git toplevel (or cwd) + `/.claude/task-state/`.

Use `TP` for everything that must be exact (IDs, structured entries, checkpoints, verify, index).
Edit narrative files (CURRENT_STATE, SESSION_HANDOFF, PROGRESS, NEXT_STEPS lists, TASK.md body) directly.
Never hand-edit `task-index.md`, `active-tasks.md`, `checkpoints/*`, `history/events.log`.

| Need | Command |
|---|---|
| create task | `TP init "<name>" --project P --objective O --requirement R… --constraint C… --acceptance A… --next N` |
| find task | `TP resolve "<ref>"` · `TP list [--active]` |
| load context | `TP resume-pack "<ref>"` (priority files + latest checkpoint + auto verify) |
| structured entry | `TP add <ref> decision title= decision= reason= alternatives= consequence=` |
| | `TP add <ref> failed title= problem= approach= result= why= lesson= next=` |
| | `TP add <ref> test case= command= expected= actual= result=PASS\|FAIL\|PARTIAL\|NOT_RUN [evidence= notes=]` |
| | `TP add <ref> blocker title= cause= impact= action= [status=BLOCKED\|WAITING_USER attempts=]` |
| | `TP add <ref> file kind=important\|read\|created\|modified\|deleted path=<rel> [note=]` |
| change an entry | `TP set-entry <ref> B-002 Status RESOLVED` · `TP set-entry <ref> B-002 Resolution "…"` · `TP set-entry <ref> D-001 Status "SUPERSEDED by D-004"` |
| next action (both files) | `TP set-next <ref> "<text>"` |
| status | `TP set-status <ref> <STATUS> [--reason]` (COMPLETED is gated) |
| checkpoint | `TP checkpoint <ref> --summary-file <tmp.md> --session <label>` |
| checks | `TP verify <ref>` · `TP status <ref>` · `TP close-check <ref>` |
| history | `TP compact <ref> --keep 3` · `TP recover <ref> [--name]` · `TP index` |

Exit codes: 2 = ambiguous ref (ask user / use ID), 3 = not found, 4 = close-check failed, 5 = verify mismatch.

## 1. Non-negotiable rules

1. **Task ID is the only primary key.** Names/slugs are for humans. If `TP` says AMBIGUOUS, show the
   candidates and ask; never guess. Two tasks may share a name.
2. **No global "current task" file.** The task bound to *this session* is whichever one the user
   `init`-ed or `resume`-d here. Announce it: `ACTIVE TASK (this session): TASK-… — <name>`.
   Every `TP` call passes that explicit ID. Other sessions may be working on other tasks concurrently.
3. **Namespace isolation.** Only read/write files inside the resolved task's directory. Never carry
   decisions/blockers/next steps from a previously loaded task into another. On task switch, drop
   the old task's context and state that you did (see §4 resume, step 1).
4. **Evidence levels** — every PROGRESS item carries one tag:
   `[PLANNED]` intended · `[ATTEMPTED]` done, unverified · `[VERIFIED]` checked, cites evidence ·
   `[COMPLETED]` verified + integrated, cites evidence (`— evidence: T-003` / command / inspection).
   A plan is never recorded as done. Code written but not run is ATTEMPTED.
5. **Tests:** record PASS only after actually running/inspecting it, with the real command and
   observed output. `TP` rejects PASS without them. Never copy an old PASS forward as current.
6. **State is a claim, the repo is the truth.** On resume, verify before trusting (§4 step 3–4).
7. **Git is read-only for this skill.** Record branch/HEAD/uncommitted changes. Never commit,
   reset, revert, stash, checkout or rewrite history for task-progress purposes.
8. **Checkpoints are immutable.** Fix mistakes in the next checkpoint, not by editing old ones.
   History is archived, never deleted.
9. **Reconstructed ≠ recorded.** Anything inferred during recovery is tagged `[RECONSTRUCTED]`.
10. Reply to the user in their language; keep state files in English section headings (stable parsing).

## 2. State layout

```
.claude/task-state/
├── task-index.md            # generated: all tasks
├── active-tasks.md          # generated: IN_PROGRESS | BLOCKED | WAITING_USER | REVIEW
└── TASK-YYYYMMDD-NNN_<slug>/
    ├── TASK.md              # identity + objective/requirements/constraints/acceptance (header parsed by TP)
    ├── CURRENT_STATE.md     # the present; most important file for resuming
    ├── PROGRESS.md          # COMPLETED / IN_PROGRESS / PLANNED / BLOCKED, evidence-tagged
    ├── DECISIONS.md         # D-NNN
    ├── FAILED_ATTEMPTS.md   # F-NNN (mandatory, never pruned)
    ├── BLOCKERS.md          # B-NNN: BLOCKED | WAITING_USER | RESOLVED
    ├── FILES.md             # important/read/created/modified/deleted (paths relative to root)
    ├── TESTS.md             # T-NNN
    ├── NEXT_STEPS.md        # NEXT IMMEDIATE ACTION / SHORT TERM / LATER
    ├── SESSION_HANDOFF.md   # answers the 10 handoff questions
    ├── checkpoints/         # checkpoint-NNN.md (read-only) + INDEX.md (sha256)
    └── history/             # events.log (raw), COMPACTED_HISTORY.md, archive/
```

Status values: `IN_PROGRESS BLOCKED WAITING_USER REVIEW PAUSED COMPLETED ABANDONED`.
Field-level formats and examples: `references/state-format.md`.

## 3. Argument parsing

Arguments arrive as `$ARGUMENTS` (e.g. `resume "Build IoT Light System"`). First word = mode, rest = task ref
(quotes optional). If the harness doesn't substitute `$ARGUMENTS`, parse the user's message the same way.
No mode → run `TP list --active` and ask what to do. `update` with extra text → treat the text as the update content.

## 4. Modes

### init "<name>"
1. Extract objective/requirements/constraints/acceptance from the conversation. If the objective is
   genuinely unknown, init anyway with what you have and ask the user to fill gaps (don't block).
2. `TP init …` (creates ID, slug, dir, all files, checkpoint-001, index). Fill anything richer by editing TASK.md.
3. Print the TP "TASK CREATED" block, announce `ACTIVE TASK (this session)`, then start working on the
   task (the user usually wants work, not just a folder).

### resume "<name-or-id>"  — the critical path
1. **Resolve.** `TP resolve "<ref>"`. Exit 2 → list candidates, ask for the ID, stop. Exit 3 → show known
   tasks; if the user insists it existed, go to recovery. If another task was active in this session,
   say `Switching from TASK-X to TASK-Y — TASK-X context discarded` and do not reuse anything from it.
2. **Load.** `TP resume-pack "<ID>"`. It prints, in priority order: TASK, CURRENT_STATE, SESSION_HANDOFF,
   NEXT_STEPS, DECISIONS, BLOCKERS, FAILED_ATTEMPTS, PROGRESS, FILES, last 10 TESTS, compacted history,
   latest checkpoint, and an automatic VERIFY report. Don't read archived checkpoints unless investigating.
3. **Verify reality** (the pack's VERIFY is structural only; you do the semantic part):
   - every MISMATCH line; `git status`, `git log --oneline <HEAD-at-checkpoint>..HEAD` if HEAD moved;
   - open the IMPORTANT files and check that each `[COMPLETED]`/`[VERIFIED]` item is actually present in source;
   - re-run the cheapest relevant tests (build/compile/unit) when claims depend on them and it's safe;
   - check generated artifacts that state says exist.
4. **Reconcile** — if anything disagrees, print `STATE / FILESYSTEM MISMATCH`, investigate, decide the
   true state, then fix state: downgrade tags (COMPLETED→ATTEMPTED/PLANNED), add a test entry for what
   you ran, `set-entry` stale blockers, update CURRENT_STATE, record `Reconciled on resume: …` under
   RECENT CHANGES. Never silently trust state, never silently overwrite it. Procedure: `references/reconciliation-and-recovery.md`.
5. **Print the summary** exactly in this shape:
   ```
   ========================================
   TASK RESUMED
   ========================================
   Task ID / Task / Status / Objective / Last checkpoint /
   Completed / Current work / Important decisions / Failed attempts /
   Blockers / Important files / Reconciliation (if any) / Next immediate action
   ========================================
   ACTIVE TASK (this session): TASK-… — <name>
   ```
6. **Continue.** Immediately start executing NEXT IMMEDIATE ACTION (re-checking FAILED_ATTEMPTS and ACTIVE
   decisions first). Stop only if status is WAITING_USER, BLOCKED (with no actionable workaround),
   COMPLETED/ABANDONED, or the next action itself requires the user's input — then say exactly what's needed.

### checkpoint "<ref>"
1. Bring CURRENT_STATE, PROGRESS, NEXT_STEPS (`TP set-next`), FILES up to date first.
2. Write a temp summary (template `templates/checkpoint-summary.md`): completed since previous checkpoint
   (evidence-tagged), current status, problems, decision IDs, notes. TP adds events, git state, next action.
3. `TP checkpoint <ID> --summary-file /tmp/cp.md --session "<short session label>"`.
4. Rewrite SESSION_HANDOFF.md (it must answer all 10 questions; see state-format). Report checkpoint ID.

### handoff "<ref>"
Same as checkpoint, but SESSION_HANDOFF is written for a cold reader (assume zero context: include why the
current approach was chosen and which approaches are dead ends). End by telling the user the exact command:
`/task-progress resume <TASK_ID>`.

### status "<ref>"
`TP status <ref>` plus a 5–10 line human summary from CURRENT_STATE. Read-only: no edits, no work.

### update "<ref>" [text]
Apply the described change (new requirement → TASK.md + "Requirement Change Log"; progress; blocker; etc.)
via the right files/commands. With no text, sync all state files with what happened in this session.

### compact "<ref>"
`TP compact <ref> --keep 3` archives older checkpoints (moved, not deleted). Then write the **Synthesis**
section in `history/COMPACTED_HISTORY.md`: stable decisions, lessons learned, unresolved issues, important
failed attempts, how the approach evolved. Also: tighten CURRENT_STATE (history out, present in), move
finished PROGRESS detail into one line per feature with evidence, add a "Lessons" summary at the top of
FAILED_ATTEMPTS (never delete entries), mark superseded decisions. `TP verify` must stay clean. Suggest
compaction when checkpoints > ~8 or resume-pack gets long.

### close "<ref>"
1. For each acceptance criterion, collect real evidence (run tests now; don't rely on old PASS if code
   changed since). Tick `- [x] … — evidence: T-…` only when proven.
2. `TP close-check <ref>`. NOT READY → report exactly what's missing, keep status (or REVIEW), stop.
3. READY → update CURRENT_STATE/PROGRESS, final checkpoint (session `final`), SESSION_HANDOFF,
   then `TP set-status <ref> COMPLETED`. (TP refuses COMPLETED if gating fails; don't work around it.)
   If the user wants to stop without meeting criteria, use `PAUSED` or `ABANDONED --reason`.

## 5. Continuous updates (while any skill is working)

While a task is active in this session, update state **when the event happens**, not only at checkpoint.
Batch trivial edits, but never let a session end with state older than the work.

| Event | Update |
|---|---|
| file created/modified/deleted (task-relevant) | `TP add … file kind=…`; CURRENT_STATE › RECENT CHANGES |
| test/build/lint run | `TP add … test …` (PASS/FAIL/PARTIAL); PROGRESS tag change if it proves/disproves an item |
| test failed / approach abandoned | `TP add … failed …`; + blocker if progress is stopped |
| decision (architecture, library, protocol, data format) | `TP add … decision …`; supersede old via `set-entry` |
| blocker found / resolved | `TP add … blocker …` / `set-entry … Status RESOLVED` + Resolution; CURRENT_STATE › CURRENT BLOCKERS; task status if everything is stuck |
| needs user input | blocker `status=WAITING_USER`; `TP set-status … WAITING_USER` |
| feature done | PROGRESS item → `[VERIFIED]`/`[COMPLETED] — evidence: T-…` |
| new/changed requirement | TASK.md + Requirement Change Log |
| important discovery / assumption | CURRENT_STATE › IMPORTANT CONTEXT / CURRENT ASSUMPTIONS (UNVERIFIED/VERIFIED) |
| focus shifts | CURRENT_STATE › WHAT IS BEING WORKED ON; `TP set-next` |
| long session / before risky step / context getting large | `checkpoint` proactively and tell the user |
| user says stop, bye, done for today | checkpoint + handoff before replying |

Before retrying any approach: search FAILED_ATTEMPTS. Before changing architecture: read DECISIONS; if an
ACTIVE decision forbids it, tell the user and record a superseding decision only with a real reason.

## 6. Recovery

If files are missing/garbled, TASK.md header unreadable, index lost, or the whole task dir lost:
print `TASK STATE CORRUPTED`, run `TP recover <ID> [--name "<name>"]` (rebuilds only what's broken, keeps
corrupt originals as `*.corrupt-*`, sets PAUSED, writes RECOVERY_REPORT.md with git/checkpoint evidence).
Then reconstruct from: filesystem → git log/diff → source → README/docs → tests (run them) → surviving
checkpoints → SESSION_HANDOFF. Tag every inferred fact `[RECONSTRUCTED]`, confirm objective/acceptance with
the user, checkpoint with session `recovery`, restore status. Details: `references/reconciliation-and-recovery.md`.

## 7. Integration

- Suggested CLAUDE.md block and SessionStart hook (lists active tasks at session start): `references/integration.md`.
- Other skills need no changes; this skill observes their results and records them.

## 8. Reference files

- `references/state-format.md` — every file's schema, entry formats, examples, handoff questions.
- `references/reconciliation-and-recovery.md` — mismatch taxonomy, decision table, recovery walkthrough.
- `references/integration.md` — CLAUDE.md snippet, hooks, multi-session/concurrency notes, limitations.
- `tests/selftest.py` — run after modifying `tp.py`.
