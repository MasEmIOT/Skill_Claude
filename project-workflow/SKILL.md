---
name: project-workflow
description: Manage a software project using persistent filesystem-based project memory, independent task sessions, structured task tracking, technical documentation, progress tracking, and project reporting. Use this skill when initializing a new project, creating a new task, analyzing or implementing a task, finalizing a task, reviewing project status, or synchronizing project knowledge.
disable-model-invocation: true
---

# Project Workflow

You are operating under a persistent project-management workflow.

Core principle:

> Conversation history is temporary working memory.
> Filesystem + Git are permanent project memory.

Never depend on previous Claude Code conversations when the required knowledge can be stored in the project filesystem.

The project must remain understandable to a completely new Claude Code session.

---

# COMMAND MODES

The user may invoke this skill with:

- `/project-workflow init`
- `/project-workflow task "<task description>"`
- `/project-workflow analyze`
- `/project-workflow review`
- `/project-workflow finalize`
- `/project-workflow status`
- `/project-workflow sync`

Interpret the user's arguments and execute the corresponding workflow.

If no mode is provided, inspect the current project state and determine the most appropriate workflow.

---

# GLOBAL RULES

Always:

1. Treat the repository/filesystem as persistent project memory.
2. Avoid relying on previous conversation history.
3. Read only the minimum relevant project documentation and source files.
4. Do not scan the entire repository unless there is a concrete reason.
5. Do not modify unrelated source files.
6. Do not refactor working code without justification.
7. Do not turn assumptions into facts.
8. Record important technical decisions in persistent documentation.
9. Keep current project state separate from historical information.
10. Keep task-specific knowledge separate from global project knowledge.
11. Update documentation when implementation changes project knowledge.
12. Prefer concise, high-value documentation over massive logs.

---

# STANDARD PROJECT MEMORY STRUCTURE

When appropriate, maintain:

project/
├── CLAUDE.md
├── docs/
│   ├── project-context.md
│   ├── architecture.md
│   ├── requirements.md
│   ├── decisions.md
│   ├── glossary.md
│   └── development-workflow.md
├── tasks/
│   ├── active/
│   ├── completed/
│   ├── analysis/
│   ├── reviews/
│   └── templates/
├── progress/
│   ├── current.md
│   ├── changelog.md
│   └── milestones.md
├── reports/
│   ├── technical/
│   ├── meetings/
│   └── qna/
└── source code...

Respect existing project organization.

Do not create duplicate structures if equivalent files already exist.

Do not reorganize a mature project merely to match this template.

---

# MODE: INIT

Command:

/project-workflow init

Goal:

Initialize the current project with a persistent Claude Code project-memory and task-management system.

First inspect:

- current directory
- repository structure
- source code
- README
- configuration
- existing documentation
- existing Claude configuration
- Git state if applicable

Do not modify application source code.

Create or update only project-management/documentation files.

Create a concise `CLAUDE.md`.

CLAUDE.md must explain:

- project purpose
- technology stack
- important architecture
- important conventions
- project-memory locations
- task workflow
- documentation rules
- source modification rules
- session independence principle

CLAUDE.md should NOT contain the full project documentation.

Create or update:

- docs/project-context.md
- docs/architecture.md
- docs/requirements.md
- docs/decisions.md
- docs/glossary.md
- docs/development-workflow.md
- progress/current.md
- progress/changelog.md
- progress/milestones.md
- tasks/templates/task-template.md
- tasks/templates/analysis-template.md
- tasks/templates/review-template.md

Only create files that are useful for the current project.

Extract verified information from the existing repository and documentation.

Do not invent missing information.

At the end, report:

1. created files
2. updated files
3. important knowledge extracted
4. current project state
5. recommended next task

---

# MODE: TASK

Command:

/project-workflow task "<description>"

Goal:

Create a new independent task context.

First read:

- CLAUDE.md
- docs/project-context.md
- progress/current.md

Then understand the requested task.

Create a task file under:

tasks/active/

Use a unique task ID such as:

TASK-001
TASK-002
TASK-003

Record:

- title
- objective
- background
- problem
- expected outcome
- relevant files
- requirements
- constraints
- dependencies
- acceptance criteria
- status

Do not implement the task unless the user explicitly asks.

The task file must contain enough information for a completely new Claude Code session to continue the task without relying on this conversation.

---

# MODE: ANALYZE

Command:

/project-workflow analyze

Goal:

Analyze the currently active task without unnecessary implementation.

Read:

- CLAUDE.md
- docs/project-context.md
- progress/current.md
- active task file
- relevant architecture/requirements documentation

Then inspect only relevant source files.

Produce task analysis containing:

- understanding
- root cause
- relevant components
- relevant files
- current behavior
- expected behavior
- possible solutions
- recommended solution
- risks
- dependencies
- implementation plan
- validation plan

Store the analysis persistently.

Do not modify unrelated code.

Do not invent facts.

---

# MODE: REVIEW

Command:

/project-workflow review

Goal:

Perform an independent review of the current task implementation.

Read:

- task definition
- task analysis
- relevant documentation
- Git diff
- relevant source files
- test results

Review:

- correctness
- architecture
- code quality
- edge cases
- regression risks
- tests
- documentation consistency

Write the review persistently.

Use one of:

APPROVED

or

NEEDS CHANGES

Do not modify implementation unless explicitly requested.

---

# MODE: FINALIZE

Command:

/project-workflow finalize

Goal:

Close the current task and synchronize persistent project knowledge.

Read:

- active task
- analysis
- review
- implementation changes
- Git diff
- test results

Update the relevant persistent files.

Potential files:

- tasks/active/TASK-XXX.md
- tasks/completed/TASK-XXX.md
- docs/project-context.md
- docs/architecture.md
- docs/requirements.md
- docs/decisions.md
- progress/current.md
- progress/changelog.md
- progress/milestones.md
- reports/technical/
- reports/qna/

Do NOT update every file automatically.

Only update files whose information has actually changed.

Record:

- what changed
- why
- files changed
- tests performed
- results
- remaining issues
- follow-up tasks

Move completed task information from active to completed when appropriate.

Ensure the project state can be understood by a new session.

---

# MODE: STATUS

Command:

/project-workflow status

Goal:

Provide the current project state using persistent files.

Read:

- docs/project-context.md
- progress/current.md
- active tasks
- recent changelog entries

Report:

- current phase
- completed work
- active work
- blocked work
- known issues
- next recommended tasks

Do not perform implementation.

---

# MODE: SYNC

Command:

/project-workflow sync

Goal:

Synchronize project knowledge after work has occurred outside the normal workflow.

Inspect:

- Git status
- recent Git history
- changed files
- current documentation
- active tasks

Identify discrepancies between:

- source code
- task files
- project context
- progress
- reports

Update only verified information.

Do not rewrite documentation unnecessarily.

Do not modify application logic.

---

# TASK SESSION POLICY

Each task should normally be handled in an independent Claude Code session.

A recommended lifecycle is:

New task
→ TASK file
→ analysis
→ implementation
→ testing
→ review
→ finalization
→ documentation synchronization
→ Git commit

Do not keep one Claude Code session alive merely to preserve project memory.

Persistent files must carry the knowledge between sessions.

---

# CONTEXT EFFICIENCY POLICY

Optimize context usage.

At the beginning of a task, prefer:

1. CLAUDE.md
2. project-context.md
3. progress/current.md
4. current task file
5. directly relevant documentation
6. relevant source files

Do not automatically read:

- every source file
- every historical task
- every report
- every old conversation-derived document

Only retrieve historical information when it is relevant to the current task.

---

# DOCUMENTATION QUALITY POLICY

Documentation should capture durable knowledge, not conversation transcripts.

Prefer:

"WiFi reconnection was changed from blocking retry logic to non-blocking state management because blocking retries delayed relay control."

Avoid:

"Claude said on Monday that the WiFi thing was probably causing the problem."

Documentation must be:

- factual
- concise
- current
- traceable
- useful to a future developer

---

# TECHNICAL DECISION POLICY

When a meaningful architecture or technical decision is made, record:

- decision
- context
- alternatives
- reason
- consequences

Do not record trivial implementation details as architecture decisions.

---

# REPORTING POLICY

When the project includes formal reports, meeting notes, Q&A documents, or progress reports:

Update them from verified project state.

Never treat a report as the source of truth for implementation.

Source code + verified technical documentation + Git history are the primary evidence.

Reports are presentation/documentation layers.

---

# SESSION HANDOFF POLICY

At the end of a significant task, ensure another Claude Code session can continue using only:

- CLAUDE.md
- project-context.md
- progress/current.md
- active task
- relevant documentation
- source code
- Git history

The previous conversation should not be required.

---

# FINAL CHECK

Before finishing any workflow:

Ask internally:

"Could a completely new Claude Code session understand the current state without seeing the previous conversation?"

If the answer is no:

- identify the missing durable knowledge
- store it in the appropriate project file
- keep the information concise
- then continue