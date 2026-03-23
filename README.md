# Repo Task Proof Loop

This skill was built from [OpenClaw-RL: Train Any Agent Simply by Talking](https://arxiv.org/html/2603.10165v1) and applies its proven approach to agentic flows in a repo-local workflow.

> "next-state signals are universal, and policy can learn from all of them simultaneously."

Repo Task Proof Loop is a repo-local workflow skill for non-trivial coding tasks.

It creates a durable task folder under `.agent/tasks/<TASK_ID>/`, installs project-scoped Codex and Claude subagents, updates `AGENTS.md` and `CLAUDE.md` with the workflow, and drives a strict implementation loop:

`spec freeze → build → evidence → fresh verify → minimal fix → fresh verify`

The goal is simple: keep all proof of work inside the repository, separate implementation from verification, and make it easy to resume or audit a task later.

## What problem this solves

Large coding-agent tasks often fail in predictable ways:

- the agent claims the job is done without durable proof
- the same session both implements and judges its own work
- acceptance criteria drift during the task
- a later session cannot tell what was actually verified
- repo guidance in `AGENTS.md` or `CLAUDE.md` is ignored or not reused

This skill addresses that by enforcing a repo-local artifact set and role-separated subagents.

## What this skill installs and manages

Inside the target repository:

```text
.agent/tasks/<TASK_ID>/
  spec.md
  evidence.md
  evidence.json
  raw/
    build.txt
    test-unit.txt
    test-integration.txt
    lint.txt
    screenshot-1.png
  verdict.json
  problems.md
```

Also inside the target repository:

```text
.codex/agents/
  task-spec-freezer.toml
  task-builder.toml
  task-verifier.toml
  task-fixer.toml

.claude/agents/
  task-spec-freezer.md
  task-builder.md
  task-verifier.md
  task-fixer.md
```

And managed workflow blocks in:

- `AGENTS.md`
- `CLAUDE.md`

The managed blocks are updated in place and are designed to preserve unrelated user content outside the managed section.

## Quick prompts to begin work with this skill

Pick the prompt that matches the current task state.

### Init

```text
Spawn subagents. Use $repo-task-proof-loop to initialize this repository for the repo-local spec -> build -> evidence -> verify -> fix workflow. Install or refresh the project-scoped subagents, update the managed workflow guidance, and set this repo up to follow the proof-loop philosophy for future tasks.
```

### Status

```text
Spawn subagents. Use $repo-task-proof-loop to find the existing repo-local task that matches the task described below, inspect its artifacts, and report the matched task ID, current status, and next recommended step.
...
```

### Build

```text
Spawn subagents. Use $repo-task-proof-loop to continue the task described below in this repository. Reuse the matching repo-local task if it already exists; if not, stop after explaining that init should be run first.
...
```

For `Status` and `Build`, replace `...` with either `Task file: <path/to/task-file.md>` on the next line or the task text pasted on following lines.

## Installation

Install the skill as a project skill.

### Codex

Unzip or copy this directory to:

```text
.agents/skills/repo-task-proof-loop/
```

### Claude Code

Unzip or copy this directory to:

```text
.claude/skills/repo-task-proof-loop/
```

If you use both tools on the same repository, install the skill in both locations or keep one canonical copy and sync it.

## Quick start

1. Install the skill in your repository.
2. Start your coding agent with the scenario prompt above that matches your task state.
3. Let the skill initialize the repo-local task structure.
4. Let the agent execute the workflow using role-separated subagents.
5. Validate before sign-off.

## Manual helper commands

The bundled helper script currently ships three CLI commands:

- `init`
- `validate`
- `status`

The workflow phases `freeze`, `build`, `evidence`, `verify`, `fix`, and `run` are skill-level commands for the agent, not direct CLI subcommands in the current package.

Set `SKILL_PATH` to the installed skill directory:

### Codex example

```bash
SKILL_PATH=.agents/skills/repo-task-proof-loop
```

### Claude Code example

```bash
SKILL_PATH=.claude/skills/repo-task-proof-loop
```

### Initialize a task

```bash
python3 "$SKILL_PATH/scripts/task_loop.py" init \
  --task-id feature-auth-hardening \
  --task-file docs/tasks/auth-hardening.md
```

You can also seed the task from inline text:

```bash
python3 "$SKILL_PATH/scripts/task_loop.py" init \
  --task-id feature-auth-hardening \
  --task-text "Implement auth hardening for session refresh and logout."
```

Useful options:

- `--guides auto|agents|claude|both|none`
- `--install-subagents both|codex|claude|none`
- `--force`

### Validate a task bundle

```bash
python3 "$SKILL_PATH/scripts/task_loop.py" validate \
  --task-id feature-auth-hardening
```

### Show current task status

```bash
python3 "$SKILL_PATH/scripts/task_loop.py" status \
  --task-id feature-auth-hardening
```

## Workflow model

This skill is built around six roles and states.

### 1. Spec freeze

Create or refine `.agent/tasks/<TASK_ID>/spec.md`.

The spec must contain at least:

- original task statement
- explicit acceptance criteria labeled `AC1`, `AC2`, ...
- constraints
- non-goals

It may also include assumptions and a concise verification plan.

### 2. Build

A builder subagent implements the task against the frozen spec.

The builder should make the smallest safe change set that satisfies the acceptance criteria.

### 3. Evidence

The same builder session should switch into evidence mode when possible.

It writes:

- `evidence.md`
- `evidence.json`
- raw artifacts under `raw/`

Evidence may conclude `PASS`, `FAIL`, or `UNKNOWN` for each acceptance criterion. It must not keep changing production code.

### 4. Fresh verify

A fresh verifier session inspects the current repository state and reruns checks.

It writes:

- `verdict.json`
- `problems.md` when the verdict is not `PASS`

The verifier must not edit production code.

### 5. Fix

A fresh fixer session reads:

- `spec.md`
- `verdict.json`
- `problems.md`

It applies the smallest safe fix set, regenerates the evidence bundle, and stops without writing final sign-off.

### 6. Verify again

A fresh verifier session reruns verification.

If the task is still not `PASS`, the workflow loops:

`fix → verify → fix → verify`

## Subagent roles

This skill installs four role-specific subagents for both Codex and Claude Code.

### `task-spec-freezer`

Purpose:
- freeze the task into `spec.md`

Boundaries:
- may read repo guidance and relevant code
- must not change production code
- must not write `verdict.json` or `problems.md`

### `task-builder`

Purpose:
- implement the task
- later switch into evidence mode

Boundaries:
- in `BUILD`, implement against the spec
- in `EVIDENCE`, do not change production code

### `task-verifier`

Purpose:
- perform fresh-session verification against the current codebase

Boundaries:
- must not edit production code
- must not patch the evidence bundle to make it look complete
- must write `verdict.json`
- must write `problems.md` only when the verdict is not `PASS`

### `task-fixer`

Purpose:
- repair only what the verifier identified

Boundaries:
- must reread the spec and verifier output
- must reconfirm the problem before editing
- must regenerate evidence after the fix
- must not write final sign-off

## How the agent should use subagents

### Codex

Codex requires explicit delegation. The parent agent should clearly ask for one named child at a time.

Example shape:

```text
Spawn one `task-verifier` agent for TASK_ID <TASK_ID>. Wait for it. It must verify the current codebase and write verdict.json and, if needed, problems.md.
```

### Claude Code

Claude Code should use the installed project agents under `.claude/agents/`.

Example shape:

```text
Use the `task-builder` agent for TASK_ID <TASK_ID> in BUILD mode. When implementation is done, keep the same child in EVIDENCE mode if possible.
```

## Guardrails

- All task artifacts must stay inside the repository.
- Do not claim task completion unless every acceptance criterion is `PASS`.
- Keep implementer, verifier, and fixer roles separate.
- Keep verifier passes fresh.
- Prefer minimal diffs during repairs.
- Preserve unrelated user guidance outside the managed blocks in `AGENTS.md` and `CLAUDE.md`.

## What `init` does

`init` is the strict schema bootstrap for any repository using this workflow.

It will:

- create `.agent/tasks/<TASK_ID>/`
- seed the full artifact set, including placeholders
- install project-scoped Codex and Claude subagents by default
- insert or refresh managed workflow blocks in `AGENTS.md` and `CLAUDE.md`
- reuse current repo guidance when present

This makes it suitable for repositories that already rely on `AGENTS.md`, `CLAUDE.md`, or both.

## Validation and smoke testing

The package includes a smoke test:

```bash
python3 "$SKILL_PATH/scripts/verify_package.py"
```

It checks the skill structure, initializes a temporary git repository, installs the task artifacts and subagents, and validates the generated task bundle.

## Limitations

This skill is designed to orchestrate subagent use, but actual subagent spawning behavior depends on the host product.

- In Codex, the parent must explicitly request subagents.
- In Claude Code, the parent should use the installed project agents.
- If a platform cannot continue the same builder child into evidence mode, the workflow falls back to a second builder child in evidence-only mode.

The skill is honest about this boundary. It packages the workflow, role prompts, and repo-local conventions so the parent agent can execute the loop reliably.

## Repository contents in this package

```text
repo-task-proof-loop/
  README.md
  SKILL.md
  VERIFICATION.md
  agents/openai.yaml
  assets/
  references/
  scripts/
```

## Publishing note

This repository is ready to publish as a skill package. The most important things to preserve are:

- the exact skill directory name: `repo-task-proof-loop`
- the repo-local artifact contract under `.agent/tasks/<TASK_ID>/`
- the role-separated subagent files
- the managed workflow blocks in `AGENTS.md` and `CLAUDE.md`

If you extend the package later, keep the verifier and fixer roles separate.
