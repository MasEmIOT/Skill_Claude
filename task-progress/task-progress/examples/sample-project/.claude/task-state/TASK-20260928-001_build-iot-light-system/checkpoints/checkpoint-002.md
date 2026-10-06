# checkpoint-002 — TASK-20260928-001

- Checkpoint ID: checkpoint-002
- Date: 2026-09-28T04:02:45+00:00
- Session: session-A
- Task ID: TASK-20260928-001
- Task Name: Build IoT Light System
- Status: IN_PROGRESS
- Previous checkpoint: checkpoint-001.md
- Event log position: 13

> IMMUTABLE. Do not edit. Corrections go into the next checkpoint.

## Completed since previous checkpoint

- [COMPLETED] PlatformIO project builds — evidence: T-001
- [COMPLETED] WiFi reconnect — evidence: T-002
- [ATTEMPTED] relay driver written, not flashed

## Problems

- Upload port busy (F-001) — solved by closing monitor.
- Firebase rules reject writes (B-001, waiting user).

## Decisions (IDs)

- D-001 Firebase RTDB

## Notes for the next session

- Relay can be tested locally without Firebase.

## Current status (snapshot of CURRENT_STATE)

- Phase: Implementation — device side
- Working on: Relay control path: Firebase listener → relaySet().
- Current problem: Firebase writes rejected by rules (B-001, waiting for user).

## Structured events since previous checkpoint (auto)

- 2026-09-28T04:02:45+00:00 · file · created · src/main.cpp
- 2026-09-28T04:02:45+00:00 · file · created · src/relay.cpp
- 2026-09-28T04:02:45+00:00 · file · important · src/main.cpp
- 2026-09-28T04:02:45+00:00 · file · important · platformio.ini
- 2026-09-28T04:02:45+00:00 · decision · D-001 · Use Firebase Realtime Database
- 2026-09-28T04:02:45+00:00 · test · T-001 · firmware builds — PASS
- 2026-09-28T04:02:45+00:00 · test · T-002 · WiFi reconnects after AP reboot — PASS
- 2026-09-28T04:02:45+00:00 · failed · F-001 · Upload on COM3 while monitor open
- 2026-09-28T04:02:45+00:00 · blocker · B-001 · Firebase rules reject writes
- 2026-09-28T04:02:45+00:00 · next · - · Flash firmware and test relaySet() on GPIO26 locally (no Firebase needed), verify active-HIGH assumption

## Git state (auto, read-only)

- Branch: `master`
- HEAD: `352fd70 init project`
- Uncommitted changes: 2 file(s)

```
?? .claude/
?? src/
```


## Next immediate action

Flash firmware and test relaySet() on GPIO26 locally (no Firebase needed), verify active-HIGH assumption
