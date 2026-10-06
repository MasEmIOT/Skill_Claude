# Integration, hooks, concurrency, limitations

## Install
Project-scoped (recommended; state and skill travel with the repo):
```
<project>/.claude/skills/task-progress/   ← this folder
```
Personal (all projects): `~/.claude/skills/task-progress/`. State always lives in the *project*:
`<project>/.claude/task-state/`.

Commit `.claude/task-state/` if you want state shared across machines/teammates; otherwise add it to
`.gitignore`. (Either way the skill never commits for you.)

## CLAUDE.md block (makes continuous updating reliable)
Skills only load when triggered; CLAUDE.md is always loaded. Add to the project CLAUDE.md:
```markdown
## Task state (task-progress skill)
- Task state lives in `.claude/task-state/`, one directory per Task ID. Never use another task's state.
- When a task is active in this session (after `/task-progress init|resume`), keep its state current as work
  happens (files, tests, decisions, failed attempts, blockers, next action) using the task-progress skill,
  even while other skills do the work.
- Never mark anything COMPLETED/PASS without evidence. Never commit/reset/revert git for task-progress.
- Before ending a session with an active task, run a checkpoint.
```

## SessionStart hook (optional)
Prints active tasks into the new session's context so Claude knows they exist (it does NOT auto-resume;
binding a task to a session stays explicit). `.claude/settings.json`:
```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command",
        "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/skills/task-progress/scripts/tp.py\" brief" } ] }
    ]
  }
}
```
(Adjust the path for a personal install.) `brief` never fails and prints nothing if there are no active tasks.
A ready-made file is in `hooks/settings.example.json`.

## Working with other skills
Pattern: other skill acts → result observed → task-progress records it. Examples:
- coding skill edits `src/relay.cpp` → `TP add <ID> file kind=modified path=src/relay.cpp`, RECENT CHANGES.
- testing skill: test fails → TESTS (FAIL), FAILED_ATTEMPTS if an approach died, BLOCKERS if stuck, CURRENT_STATE.
- architecture skill writes an ADR → DECISIONS entry that links to the ADR file.
- documentation/report/slides skills → FILES (created) + PROGRESS item.
This skill never overrides another skill's instructions about *how* to do the work.

## Concurrency
- ID allocation and TP writes take a file lock (`.claude/task-state/.lock`; fcntl on POSIX, best effort on Windows).
- Two sessions on **different** tasks: safe (separate directories).
- Two sessions on the **same** task: not supported as a workflow; last narrative write wins. Structured entries
  (D/F/T/B) and checkpoints stay consistent because they are appended under the lock.

## Known limitations
- Continuous updating is a behavioral protocol, not an enforced hook: Claude Code has no event that fires on
  "decision made". The CLAUDE.md block + skill description make it reliable, not guaranteed. Checkpoint before
  closing sessions.
- `TP verify` is structural (files, hashes, git, evidence tags). Semantic truth (does feature X really work?)
  still needs Claude to read code/run tests on resume.
- Checkpoint immutability = read-only permission + sha256 detection, not cryptographic protection.
- Task IDs are unique per project state root, not globally across machines working on unmerged copies;
  if two clones create tasks on the same day and later merge, rename one directory's NNN and its TASK.md ID.
- `$ARGUMENTS` substitution depends on the Claude Code version; SKILL.md falls back to parsing the message.
