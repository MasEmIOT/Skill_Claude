# Reconciliation & recovery

## A. Mismatch taxonomy (what to do when state and reality disagree)

| Observation | Likely cause | Action |
|---|---|---|
| File in FILES.md missing | deleted/renamed outside session, other branch | `git log --diff-filter=DR -- <path>`, `git branch`; if renamed → update FILES; if on other branch → note in CURRENT_STATE (don't checkout); if lost → downgrade dependent PROGRESS items |
| DELETED file exists again | restored/re-created | inspect; move to MODIFIED/CREATED with note |
| `[COMPLETED]` feature not in source | state over-claimed, or code reverted | grep/read source; downgrade to `[ATTEMPTED]`/`[PLANNED]`; add NOT_RUN/FAIL test entry describing the check |
| Test recorded PASS but fails now | regression or env change | new FAIL entry (don't edit old one); failed attempt if it's an approach issue; blocker if stuck |
| HEAD moved since checkpoint | work outside the skill / other session | `git log --oneline <old>..HEAD`, `git diff --stat <old>`; record relevant commits in RECENT CHANGES as "external change" |
| Branch changed | user switched branch | ask whether task continues on this branch before editing code |
| Uncommitted files not in FILES.md | other task / manual edits | inspect; add only if task-relevant; never revert |
| Checkpoint hash mismatch | someone edited history | do not "fix" silently; tell the user; record in next checkpoint; keep content |
| TASK.md ID ≠ directory ID | copy/paste between tasks | stop; treat as contamination; ask user which is right |
| Other task IDs mentioned in state files | cross-reference or contamination | verify each mention is an intentional link (e.g. "depends on TASK-…") |
| NEXT IMMEDIATE ACTION already done | state lagged behind | confirm in source; mark progress; `set-next` to the real next step |

Output format when found:
```
STATE / FILESYSTEM MISMATCH
- State says: …
- Reality: … (evidence: command/file)
- Resolution: … (state updated in: PROGRESS.md, TESTS.md T-012)
```
Principles: evidence beats records; old records are not rewritten, new records correct them; when evidence is
insufficient to decide, mark UNVERIFIED and ask the user rather than choosing.

## B. Recovery walkthrough (TASK STATE CORRUPTED)

1. `TP recover <ID>` (or `TP recover <ID> --name "<name>"` if the whole directory is gone).
   - Rebuilds only missing/corrupt files from templates with a RECONSTRUCTED banner.
   - Corrupt TASK.md is kept as `TASK.md.corrupt-<ts>`; name recovered from latest checkpoint if possible.
   - Next action is taken from the latest checkpoint if one survived.
   - Status set to PAUSED; RECOVERY_REPORT.md lists checkpoints, git state, recent commits, READMEs.
   - Index files are regenerated from directories (they are derived data).
2. Evidence order: filesystem → git (log, diff, blame on key files) → source → README/docs → run tests →
   surviving checkpoints (newest first) → SESSION_HANDOFF (if it survived).
3. Fill rebuilt files. Each inferred line gets `[RECONSTRUCTED]`; each test you actually re-ran is a normal
   entry (it is real evidence now).
4. Ask the user to confirm objective, acceptance criteria and anything [RECONSTRUCTED] that drives decisions.
5. `TP checkpoint <ID> --session recovery` with a summary of what was lost and how it was rebuilt;
   `TP set-status <ID> IN_PROGRESS`.

If only `task-index.md`/`active-tasks.md` are lost: `TP index`. Nothing else needed.
