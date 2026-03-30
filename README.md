# Repo Task Proof Loop

Repo Task Proof Loop is a repo-local workflow skill for non-trivial coding tasks.

It creates a durable task folder under `.agent/tasks/<TASK_ID>/`, installs project-scoped Codex and Claude subagents, updates `AGENTS.md` and `CLAUDE.md` with the workflow, and drives a strict loop:

`freeze -> build -> evidence -> fresh verify -> fix -> fresh verify -> ... until PASS`

The goal is simple:
- keep all proof of work inside the repository
- separate implementation from verification
- make it easy to resume, audit, or hand off a task later

This skill was built from [OpenClaw-RL: Train Any Agent Simply by Talking](https://arxiv.org/html/2603.10165v1) and applies its role-separated workflow ideas to repo-local agent work.

> "next-state signals are universal, and policy can learn from all of them simultaneously."

## The most important thing to understand

This package has **two layers**:

1. A helper script: `scripts/task_loop.py`
2. A workflow skill for the agent

They are not the same thing.

### What `task_loop.py` does

The helper script currently provides only three real CLI commands:
- `init`
- `validate`
- `status`

Those commands initialize and validate the repo-local artifact structure.

### What the skill does

The workflow phases:
- `freeze`
- `build`
- `evidence`
- `verify`
- `fix`
- `run`

are **skill-level commands for the agent**, not direct CLI subcommands in the current package.

That means:
- `build`, `freeze`, and `verify` are not exposed as `task_loop.py` subcommands in the current package
- `build <TASK_ID>` is something the **agent** performs by following the skill instructions
- `run <TASK_ID>` means: the **agent** orchestrates the whole loop until a fresh verifier returns `PASS`

If you only remember one rule, remember this one:

> `task_loop.py` bootstraps and validates the workflow. The agent executes the workflow phases.

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

The managed blocks are updated in place and preserve unrelated user content outside the managed section.

## What should usually be committed

In most repositories using this workflow, the following should usually be committed:
- `.agent/tasks/<TASK_ID>/`
- `.codex/agents/`
- `.claude/agents/`
- `AGENTS.md`
- `CLAUDE.md`

This preserves the repo-local audit trail, the frozen spec, the evidence bundle, verifier output, and the project-scoped workflow setup for future sessions.

The following should usually **not** be committed:
- secrets or local `.env` files
- application runtime data
- user uploads, local databases, caches, exports, or other machine-local generated data
- raw artifacts that contain private or sensitive data

A practical rule of thumb is:
- commit proof-loop workflow files
- do not commit secrets or unrelated runtime data

If a raw artifact under `.agent/tasks/<TASK_ID>/raw/` contains secrets, private data, or very large binaries, replace it with a safer summary or redact it before committing, according to your repository policy.

## What to type in practice

### 1. Initialize a repository for proof-loop work

Use this once per repository when the workflow has not been installed yet:

```text
Spawn subagents.
Use $repo-task-proof-loop to initialize this repository for the repo-local spec -> build -> evidence -> verify -> fix workflow.
Install or refresh the project-scoped subagents.
Update the managed workflow guidance.
Set this repo up to follow the proof-loop philosophy for future tasks.
```

### 2. Start or continue work on a task

If a matching repo-local task may already exist:

```text
Spawn subagents.
Use $repo-task-proof-loop to continue the task described below in this repository.
Reuse the matching repo-local task if it already exists.
If not, stop after explaining that init should be run first.
...
```

Replace `...` with either:
- `Task file: path/to/task.md`
- or the task text itself

### 3. Run the full loop until a fresh verifier returns `PASS`

This is the most important prompt when you want the agent to stop doing phase-by-phase work and just finish the loop:

```text
Spawn subagents.
Use $repo-task-proof-loop to run <TASK_ID>.
Resume from the current repo-local artifacts.
Continue the proof-loop until a fresh verifier returns PASS.
Stop only if blocked or if a user decision is required.
```

This is the closest thing to an "automatic mode" in the current package.

### 4. Ask for the current task status

```text
Spawn subagents.
Use $repo-task-proof-loop to find the existing repo-local task that matches the task described below.
Inspect its artifacts.
Report the matched task ID, current status, and next recommended step.
...
```

### 5. Add more functionality to an existing task

If you want to extend the same product/task instead of creating a brand-new task:

```text
Spawn subagents.
Use $repo-task-proof-loop to run <TASK_ID>.
Apply the following functional change.
Update the existing repo-local spec if needed.
Continue the proof-loop until a fresh verifier returns PASS.
Stop only if blocked or if a user decision is required.
...
```

## Quick start

1. Install the skill in your repository.
2. Initialize the repository with the `Init` prompt above if needed.
3. Give the agent the task text.
4. Let the agent freeze the spec.
5. Let the agent build, pack evidence, verify, fix if needed, and verify again until `PASS`.
6. Validate before sign-off.

## Where the task description actually lives

This is another common source of confusion.

### On `init`

`init` may seed the task folder with the original task statement if you provide:
- `--task-file`
- or `--task-text`

But `init` does **not** produce the final task spec.

### On `freeze`

`freeze` is the step that turns the user task into the canonical repo-local spec in:

```text
.agent/tasks/<TASK_ID>/spec.md
```

That frozen spec must contain at least:
- original task statement
- explicit acceptance criteria labeled `AC1`, `AC2`, ...
- constraints
- non-goals

It may also include:
- assumptions
- repo guidance sources
- a concise verification plan

After `freeze`, the source of truth for the task is no longer the chat message. It is `spec.md`.

## Workflow model

This skill is built around six workflow phases.

### 1. Freeze

Create or refine `.agent/tasks/<TASK_ID>/spec.md`.

The spec-freezer may read repo guidance and only the minimum relevant code needed to freeze the task.
It must not change production code.

### 2. Build

A builder subagent implements the task against the frozen spec.

The builder should make the smallest safe change set that satisfies the acceptance criteria.

### 3. Evidence

The same builder session should switch into evidence mode when possible.

It writes:
- `evidence.md`
- `evidence.json`
- raw artifacts under `raw/`

Evidence may conclude `PASS`, `FAIL`, or `UNKNOWN` per acceptance criterion.
It must not keep changing production code.

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

`fix -> verify -> fix -> verify`

## What `run <TASK_ID>` means

`run <TASK_ID>` is not a CLI command.
It is an instruction to the agent to orchestrate the phases in order.

Conceptually, `run` means:

1. Ensure `init` has already happened
2. If needed, run `freeze`
3. Run `build`
4. Run `evidence`
5. Run `verify`
6. If verdict is `PASS`, stop
7. If verdict is `FAIL` or `UNKNOWN`, run `fix`
8. Run `verify` again
9. Repeat until `PASS` or a blocker requires user input

If you prompt the agent only with `build <TASK_ID>`, it should do only that phase.
If you want the whole loop, ask for `run <TASK_ID>` or explicitly say `continue until PASS`.

## What `task_loop.py` actually supports

The bundled helper script currently ships three CLI commands:

- `init`
- `validate`
- `status`

Set `SKILL_PATH` to the installed skill directory.

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

Codex requires explicit delegation.

The parent agent should:
- not assume subagents spawn automatically
- explicitly spawn one named child at a time
- wait for the current child before moving to the next proof-loop role
- not batch `init` with later phases

Example shape:

```text
Spawn one `task-verifier` agent for TASK_ID <TASK_ID>.
Wait for it.
It must verify the current codebase.
It must write verdict.json and, if needed, problems.md.
```

### Claude Code

Claude Code should use the installed project agents under `.claude/agents/`.

Example shape:

```text
Use the `task-builder` agent for TASK_ID <TASK_ID> in BUILD mode.
When implementation is done, keep the same child in EVIDENCE mode if possible.
```

## Reasoning guidance

Reasoning effort is not hard-coded into this skill.
The skill defines roles and boundaries, but the host agent chooses the model and reasoning settings.

A practical default is:
- `freeze`: `medium`
- `build`: `medium`
- `evidence`: `medium`
- `verify`: `high`
- `fix`: `medium` or `high`

If unspecified, the parent/orchestrating agent should choose reasoning automatically per phase.

## Reusing an existing task vs creating a new one

Reuse the existing task when:
- you are extending the same feature or product area
- the change still belongs to the same acceptance-criteria family
- you want to keep one durable audit trail for that work

Create a new `TASK_ID` when:
- the new work is independently shippable
- the acceptance criteria are substantially different
- the new task would make the old spec confusing or overloaded

A good rule of thumb:
- same feature, same product slice -> reuse the task
- different feature or different objective -> create a new task

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

## Common misunderstandings

### "I ran `init`. Why is my task not fully described yet?"

Because `init` creates structure and placeholders.
The real task freeze happens on `freeze`, which writes the canonical `spec.md`.

### "Why am I still typing `freeze`, `build`, and `verify` by hand?"

Because those are skill-level commands for the agent.
If you ask phase-by-phase, the agent should execute one phase at a time.
If you want the full loop, ask for `run <TASK_ID>` or explicitly say `continue until PASS`.

### "Why doesn't `task_loop.py build` exist?"

Because the current package does not implement workflow phases as CLI subcommands.
It implements bootstrap and validation helpers; the agent performs the workflow.

### "Do I have to specify reasoning effort?"

No.
You can, but you do not have to.
If you leave it unspecified, the host agent should choose appropriate reasoning for each phase.

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
