# Decisions — TASK-20260928-001

<!-- Read before changing architecture. Do not return to a rejected approach while a decision is ACTIVE.
Status values: ACTIVE | SUPERSEDED by D-xxx | REVERTED -->

## D-001: Use Firebase Realtime Database

- Date: 2026-09-28T04:02:45+00:00
- Status: ACTIVE
- Decision: Firebase RTDB as the command channel
- Reason: push-based updates, free tier, easy Flutter client later
- Alternatives considered: MQTT (needs broker), HTTP polling (latency)
- Consequence: must handle auth token refresh on ESP32
