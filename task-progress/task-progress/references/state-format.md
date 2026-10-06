# State file formats

Contents: 1 TASK.md · 2 CURRENT_STATE.md · 3 PROGRESS.md · 4 DECISIONS.md · 5 FAILED_ATTEMPTS.md ·
6 BLOCKERS.md · 7 FILES.md · 8 TESTS.md · 9 NEXT_STEPS.md · 10 SESSION_HANDOFF.md · 11 checkpoints · 12 history · 13 naming

All files: Markdown, `## ` headings are section keys (TP parses them — do not rename).
Structured entries (D/F/T/B) are created by `TP add` so IDs and fields stay consistent.

## 1. TASK.md
Header lines (plain `Key: value`, first 30 lines, parsed by TP):
`Task ID`, `Task Name`, `Task Slug`, `Project`, `Created`, `Last Updated`, `Status`.
Sections: Objective · Requirements · Constraints · Acceptance Criteria · Requirement Change Log.
Acceptance criteria are checkboxes; tick only with evidence:
```
- [x] Relay toggles from the app within 1 s — evidence: T-007
- [ ] Schedule survives reboot
```
Change `Status` only via `TP set-status` (keeps CURRENT_STATE + index in sync, gates COMPLETED).

## 2. CURRENT_STATE.md  (present tense only; rewrite in place)
Sections: CURRENT TASK · CURRENT STATUS · CURRENT PHASE · WHAT IS BEING WORKED ON · LAST COMPLETED WORK ·
CURRENT PROBLEM · IMPORTANT CONTEXT · CURRENT ASSUMPTIONS · RECENT CHANGES · CURRENT BLOCKERS · NEXT IMMEDIATE ACTION.
- RECENT CHANGES: last ~10 dated bullets; older ones live in checkpoints.
- CURRENT ASSUMPTIONS: each tagged `UNVERIFIED` or `VERIFIED (T-004)`.
- NEXT IMMEDIATE ACTION: one concrete, executable step ("Fix overshoot in `pid.c:compute()` — Kd too low, try 0.8"),
  not a theme ("improve PID"). Set via `TP set-next` so NEXT_STEPS matches.

## 3. PROGRESS.md
```
## COMPLETED
- [COMPLETED] WiFi connect + reconnect — evidence: T-003, T-005
## IN_PROGRESS
- [ATTEMPTED] Remote relay control (code in src/relay.cpp, not yet flashed)
## PLANNED
- [PLANNED] Scheduling
## BLOCKED
- [PLANNED] Firebase auth — blocked by B-001
```
`TP verify` warns on COMPLETED items without `evidence:`.

## 4. DECISIONS.md
```
## D-001: Use Firebase Realtime Database
- Date: …
- Status: ACTIVE            # or: SUPERSEDED by D-004 | REVERTED
- Decision: …
- Reason: …
- Alternatives considered: MQTT, HTTP REST
- Consequence: …
```

## 5. FAILED_ATTEMPTS.md
```
## F-001: Upload via COM3
- Date / Problem / Approach attempted / Result / Why it failed / What was learned / Recommended next approach
```
Never delete. Compaction may add a `## Lessons (summary)` block at the top that references F-IDs.

## 6. BLOCKERS.md
```
## B-001: Firebase rules reject writes
- Status: BLOCKED | WAITING_USER | RESOLVED
- Opened / Cause / Impact / Attempts / Required action / Needs user input / Resolution
```
Resolve with `TP set-entry <ID> B-001 Status RESOLVED` and `… Resolution "<how>"`.

## 7. FILES.md
Sections IMPORTANT FILES · FILES READ · FILES CREATED · FILES MODIFIED · FILES DELETED.
Line: ``- `src/relay.cpp` — relay driver (2026-09-28)``. Paths relative to project root. `TP verify` checks
existence (DELETED must not exist). Record only task-relevant files.

## 8. TESTS.md
```
## T-003: WiFi reconnects after AP reboot — PASS
- Timestamp / Command / Test case / Expected / Actual / Result / Evidence / Notes
```
Results: PASS · FAIL · PARTIAL · NOT_RUN. Manual inspections are fine as tests: command = what you did
("read src/relay.cpp, confirmed debounce"). Latest entry per test case counts for close-check.

## 9. NEXT_STEPS.md
NEXT IMMEDIATE ACTION (exactly one) · SHORT TERM (ordered bullets) · LATER.

## 10. SESSION_HANDOFF.md — must answer
1 Which task? · 2 What was the goal? · 3 What has been completed? (with evidence) · 4 What is currently being
worked on? · 5 What files matter? · 6 What decisions matter? · 7 What failed? · 8 What blockers exist? ·
9 What has been tested? · 10 What must the next session do first?
Write for a reader with zero context. Header line `Latest checkpoint:` is maintained by TP.

## 11. checkpoints/
`checkpoint-NNN.md`, created by `TP checkpoint`, chmod read-only, sha256 recorded in `checkpoints/INDEX.md`.
Contains: Checkpoint ID, Date, Session, Task ID/Name, Status, Previous checkpoint, Event log position,
your summary (completed since previous, problems, decisions…), CURRENT_STATE snapshot, structured events
since the previous checkpoint (auto), git state (auto), next immediate action. Numbering never restarts,
including after compaction.

## 12. history/
- `events.log` — raw TSV of every TP write: `timestamp  kind  id  summary` (RAW SESSION HISTORY layer).
- `archive/` — compacted checkpoints and event-log copies (originals, untouched).
- `COMPACTED_HISTORY.md` — synthesis written by Claude at each compaction.
Context layering: events.log → checkpoints → CURRENT_STATE/HANDOFF → COMPACTED_HISTORY. Resume reads from the right.

## 13. Naming
- Task ID `TASK-YYYYMMDD-NNN`: date of creation (local), NNN = next free number for that date in this project
  (allocated under a file lock; unique within a project's state root).
- Slug: ASCII-folded (Vietnamese diacritics and đ handled), lowercase, `-` separated, ≤ 50 chars.
  "Xây dựng hệ thống đèn IoT" → `xay-dung-he-thong-den-iot`.
- Directory: `TASK-YYYYMMDD-NNN_<slug>/`. The ID prefix is authoritative; the slug is cosmetic and is never
  renamed if the task is renamed (rename = edit `Task Name` in TASK.md).
