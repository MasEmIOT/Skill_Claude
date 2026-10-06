# Walkthrough: Session A → Session B (real run)

The state in `sample-project/.claude/task-state/` was produced by actually running this flow with `tp.py`
(timestamps are real). Two tasks exist: `TASK-20260928-001` (worked on) and `TASK-20260928-002` (isolation check).

## Session A
```
/task-progress init "Build IoT Light System"
```
Claude runs `TP init …`, prints TASK CREATED, then works: creates `src/main.cpp`, `src/relay.cpp`, builds (T-001 PASS),
verifies WiFi reconnect on hardware (T-002 PASS), picks Firebase RTDB (D-001), hits "port busy" on upload (F-001),
discovers Firebase rules block writes and needs the user (B-001, WAITING_USER). Each is recorded when it happens.
```
/task-progress checkpoint "Build IoT Light System"
```
→ `checkpoint-002`, SESSION_HANDOFF rewritten. Session A closed.

## Between sessions
`src/relay.cpp` was deleted from the working tree (simulated accident).

## Session B
```
/task-progress resume TASK-20260928-001
```
1. `TP resolve` → `RESOLVED (task-id): TASK-20260928-001`.
2. `TP resume-pack` → loads only TASK-001 files; its VERIFY section reports
   `MISMATCH: src/relay.cpp listed under FILES CREATED but does not exist`.
3. Claude checks `git status` (`AD src/relay.cpp` → staged copy exists, working copy deleted) and PROGRESS
   (relay was only `[ATTEMPTED]`).
4. Reconciliation printed:
```
STATE / FILESYSTEM MISMATCH
- State says: src/relay.cpp created (relay driver, ATTEMPTED)
- Reality: file missing from working tree; git index still has a staged copy
- Resolution: recorded T-003 FAIL; git left untouched; driver re-implemented as part of next action
```
5. Summary:
```
========================================
TASK RESUMED
========================================
Task ID: TASK-20260928-001
Task: Build IoT Light System
Status: IN_PROGRESS
Objective: Control a light remotely via ESP32 relay + Firebase RTDB
Last checkpoint: checkpoint-002 (session-A)
Completed: PlatformIO build (T-001); WiFi reconnect (T-002)
Current work: relay driver — was ATTEMPTED, file now missing (reconciled)
Important decisions: D-001 Firebase RTDB (not MQTT/polling)
Failed attempts: F-001 upload with serial monitor open → close monitor first
Blockers: B-001 WAITING_USER — enable Firebase Email/Password auth + device user
Important files: src/main.cpp, src/relay.cpp, platformio.ini
Next immediate action: Flash firmware and test relaySet() on GPIO26 locally, verify active-HIGH
========================================
ACTIVE TASK (this session): TASK-20260928-001 — Build IoT Light System
```
6. Claude **continues without stopping**: rewrites `relay.cpp`, builds (T-004 PASS), tests the relay on
   hardware (T-005 PASS → assumption "active HIGH" becomes VERIFIED), re-checks the file (T-006 PASS),
   moves the next action to the Firebase listener, and checkpoints (`checkpoint-003`).

`/task-progress close TASK-20260928-001` at this point returns NOT READY (criteria unticked, B-001 open) —
the task cannot be marked COMPLETED.

Try it yourself on this copy:
```
cd examples/sample-project && git init -q
python3 ../../scripts/tp.py status TASK-20260928-001
python3 ../../scripts/tp.py resume-pack "build iot light system"
python3 ../../scripts/tp.py resume-pack TASK-20260928-002     # contains nothing from TASK-001
```
