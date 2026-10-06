# Failed Attempts — TASK-20260928-001

<!-- Mandatory. Check here before retrying anything. Never delete entries; compaction may add a Lessons summary at the top. -->

## F-001: Upload on COM3 while monitor open

- Date: 2026-09-28T04:02:45+00:00
- Problem: pio upload failed
- Approach attempted: uploaded to COM3 directly
- Result: Could not open port: busy
- Why it failed: serial monitor held the port
- What was learned: close monitor or use --monitor-port handoff
- Recommended next approach: pio run -t upload after closing monitor
