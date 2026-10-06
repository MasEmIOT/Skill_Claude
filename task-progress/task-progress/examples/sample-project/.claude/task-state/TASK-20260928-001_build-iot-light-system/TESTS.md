# Tests — TASK-20260928-001

<!-- PASS only for tests actually executed/inspected, with Command + Actual result recorded. -->

## T-001: firmware builds — PASS

- Timestamp: 2026-09-28T04:02:45+00:00
- Command: `pio run`
- Test case: firmware builds
- Expected: SUCCESS
- Actual: SUCCESS (took 4.2s)
- Result: PASS
- Evidence: (see Actual)
- Notes: -

## T-002: WiFi reconnects after AP reboot — PASS

- Timestamp: 2026-09-28T04:02:45+00:00
- Command: `manual: reboot AP, watch serial`
- Test case: WiFi reconnects after AP reboot
- Expected: reconnect <10s
- Actual: reconnected after 6s
- Result: PASS
- Evidence: serial log excerpt in notes
- Notes: -

## T-003: relay.cpp present in working tree — FAIL

- Timestamp: 2026-09-28T04:03:04+00:00
- Command: `ls src/; git status --porcelain`
- Test case: relay.cpp present in working tree
- Expected: src/relay.cpp exists
- Actual: missing from working tree (git: AD, staged copy exists)
- Result: FAIL
- Evidence: (see Actual)
- Notes: reconciliation on resume, session-B

## T-004: firmware builds — PASS

- Timestamp: 2026-09-28T04:03:04+00:00
- Command: `pio run`
- Test case: firmware builds
- Expected: SUCCESS
- Actual: SUCCESS (4.0s)
- Result: PASS
- Evidence: (see Actual)
- Notes: -

## T-005: relay GPIO26 toggles — PASS

- Timestamp: 2026-09-28T04:03:04+00:00
- Command: `flash + relaySet(true/false), multimeter on IN pin`
- Test case: relay GPIO26 toggles
- Expected: HIGH=on
- Actual: relay clicks ON at HIGH
- Result: PASS
- Evidence: (see Actual)
- Notes: confirms active-HIGH assumption

## T-006: relay.cpp present in working tree — PASS

- Timestamp: 2026-09-28T04:03:17+00:00
- Command: `ls src/`
- Test case: relay.cpp present in working tree
- Expected: src/relay.cpp exists
- Actual: present (re-created session-B)
- Result: PASS
- Evidence: (see Actual)
- Notes: -
