# Current State — TASK-20260928-001

> Always reflects the present. Rewrite sections in place; history belongs in checkpoints/.
> Last Updated: 2026-09-28T04:03:17+00:00

## CURRENT TASK

TASK-20260928-001 — Build IoT Light System

## CURRENT STATUS

IN_PROGRESS

## CURRENT PHASE


Implementation — device side

## WHAT IS BEING WORKED ON


Relay control path: Firebase listener → relaySet().

## LAST COMPLETED WORK


Relay driver verified locally on GPIO26 (T-005).

## CURRENT PROBLEM


Firebase writes rejected by rules (B-001, waiting for user).

## IMPORTANT CONTEXT


- Relay on GPIO26, active HIGH.
- Serial monitor must be closed before upload (F-001).

## CURRENT ASSUMPTIONS


- Relay module is active HIGH — VERIFIED (T-005)

## RECENT CHANGES

- session-B — Reconciled on resume: src/relay.cpp missing from working tree (staged copy in git index). Relay item was only [ATTEMPTED]; re-implemented instead of touching git (T-003).
- 2026-09-28T04:02:45+00:00 — Task created.

## CURRENT BLOCKERS


- B-001 Firebase rules reject writes [WAITING_USER]

## NEXT IMMEDIATE ACTION



Wait for user on B-001 (Firebase auth). Meanwhile: write Firebase stream listener in src/main.cpp calling relaySet()

