---
name: repo-task-proof-loop
description: Repo-local workflow skill for large coding tasks. Initializes .agent/tasks/TASK_ID artifacts, installs project-scoped Codex and Claude subagents, updates AGENTS.md plus the repo's Claude guide file with the workflow, and runs a spec-freeze → build → evidence → verify → fix loop with fresh-session verification.
license: Apache-2.0
compatibility: Skills-compatible coding agents. Integrates with Codex and Claude Code project-scoped subagents. Bundled scripts require Python 3.10+.
metadata:
  author: OpenAI
  version: "1.0.0"
---

# Repo Task Proof Loop

Use this skill when the user wants a repeatable, auditable implementation workflow for a non-trivial coding task, especially a feature, refactor, migration, or bug fix that should leave repo-local proof in `.agent/tasks/<TASK_ID>/`.

All task artifacts created by this workflow must stay inside the repository.

When the examples below mention `scripts/task_loop.py`, that path is relative to this skill root. Run it while your shell working directory is inside the target repository.

## What this skill does

1. Initializes a strict repo-local task folder under `.agent/tasks/<TASK_ID>/`
2. Seeds or updates the required artifact files
3. Installs project-scoped Codex and Claude subagent templates into `.codex/agents/` and `.claude/agents/`
4. Updates the repo-root `AGENTS.md` Codex baseline plus the repo's Claude guide file (`CLAUDE.md` or `.claude/CLAUDE.md`) with a managed block that explains the workflow
5. Guides the agent through a strict loop:
   - spec freeze
   - builder implementation
   - evidence packing
   - fresh verification
   - minimal fix
   - fresh verification again until `PASS`

See:
- `references/REFERENCE.md`
- `references/COMMANDS.md`
- `references/SUBAGENTS.md`
- `references/SCHEMAS.md`

## Commands this skill supports

Treat the following words as commands when the user invokes this skill:

- `init <TASK_ID>`: create `.agent/tasks/<TASK_ID>/`, install or refresh subagent templates, and update `AGENTS.md` plus the repo's Claude guide file
- `freeze <TASK_ID>`: create or refine `spec.md` from the user task, task file, and repo guidance
- `build <TASK_ID>`: implement the task against the frozen spec
- `evidence <TASK_ID>`: create or refresh `evidence.md`, `evidence.json`, and raw artifacts without changing production code
- `verify <TASK_ID>`: run a fresh verifier pass and write `verdict.json`, plus `problems.md` when needed
- `fix <TASK_ID>`: apply the smallest safe fix set from `problems.md`, then refresh the evidence bundle
- `run <TASK_ID>`: execute the full loop from spec freeze through verification
- `status <TASK_ID>`: summarize current artifact status

If the user does not supply a command, infer the next step from repo state:
- If the task folder does not exist, run `init` first. If the user clearly wants initialization only, stop there. Otherwise, after `init` succeeds and `.agent/tasks/<TASK_ID>/spec.md` exists, continue by re-evaluating repo state in the same turn. Do not overlap `init` with `freeze`, `build`, `evidence`, `verify`, `fix`, `validate`, `status`, or subagent work.
- If `spec.md` is missing or placeholder-only, do `freeze`
- If implementation is not yet complete, do `build`
- If evidence is stale or missing, do `evidence`
- If no fresh verdict exists, do `verify`
- If verdict is not `PASS`, do `fix`

## Initialization step

Run the bundled initializer from the repository root or current working directory inside the repo:

```bash
scripts/task_loop.py init --task-id <TASK_ID>
```

Optional task seeding:

```bash
scripts/task_loop.py init --task-id <TASK_ID> --task-file path/to/task.md
scripts/task_loop.py init --task-id <TASK_ID> --task-text "User task text"
```

The initializer will:

- resolve the repo root
- create `.agent/tasks/<TASK_ID>/`
- create all required artifacts, including placeholders under `raw/`
- install project-scoped subagent files
- insert or refresh managed workflow blocks in `AGENTS.md` and the repo's Claude guide file

For Codex, the initializer keeps its managed workflow block in the repo-root `AGENTS.md`. Codex also supports `AGENTS.override.md` and configured fallback guide filenames; nested files closer to the code still take precedence, and this skill intentionally does not overwrite them.
If `init` creates or rewrites `AGENTS.md` during a running Codex session, start a new Codex session before relying on the updated instructions. Codex snapshots project-doc guidance at session start.

For Claude Code, the initializer keeps its managed workflow block in the repo-root `CLAUDE.md`. Claude Code also supports `.claude/CLAUDE.md`, `.claude/rules/*.md`, and `CLAUDE.local.md`, but this skill treats root `CLAUDE.md` as the primary project guide because Claude surfaces it directly.

In Claude Code, if `init` just wrote or refreshed `.claude/agents/*` during the current session, do not assume those updated agents are already available mid-session.

Treat `init` as a serial prerequisite. Never overlap it with `freeze`, `build`, `evidence`, `verify`, `fix`, `validate`, `status`, or child-agent spawning.

## Heavy-task default workflow

For large tasks, keep the user-facing request simple. In Codex, continue serially unless the user explicitly asks for delegation or parallel agent work; after that authorization, the skill can choose the internal child setup automatically when the current product surface supports delegation and the task shape warrants it.

### Preferred delegated sequence

1. Run `init <TASK_ID>` if needed. Wait for it to finish, then confirm `.agent/tasks/<TASK_ID>/spec.md` and the repo-local task structure exist before continuing.
2. Only after `init` completes, spawn exactly one spec-freezer subagent and wait for it
3. Spawn exactly one builder subagent and let it implement
4. Continue with the same builder session for evidence packing
5. Spawn exactly one fresh verifier subagent and wait for it
6. If verdict is not `PASS`, spawn exactly one fixer subagent
7. Spawn one fresh verifier subagent again
8. Repeat steps 6-7 until the verifier returns `PASS` or the user stops the loop

### Codex adaptive fan-out

Use this only after the user has explicitly authorized Codex delegation and the task is broad enough to benefit from bounded parallel work. Use the simpler serial sequence above for narrow tasks.

Good fits:

- multiple independent codebase questions must be answered before the spec is stable
- implementation can be split into disjoint write scopes
- proof requires several independent read-only checks across different surfaces

Codex pattern:

1. `init` stays serial.
2. If the task is still ambiguous, fan out up to 3 built-in `explorer` children in parallel. Give each one a single question, subsystem, or path scope. Wait for them, then freeze the spec.
3. Spawn one spec-freezer child and wait for it.
4. Spawn one `task-builder` child as the integration owner.
5. If implementation splits cleanly, the parent may also spawn bounded built-in `worker` children in parallel. Each worker must have explicit file or module ownership and must not write `evidence.md`, `evidence.json`, `verdict.json`, or `problems.md`.
6. Use `send_input` or the equivalent follow-up surface to keep the integration builder alive for evidence packing. The builder remains the single owner of the evidence bundle.
7. If extra proof is needed, the parent may fan out a small bounded set of read-only `explorer` children to rerun disjoint checks or inspect separate proof gaps in parallel. Those children may report commands, outputs, and findings, but they do not write `verdict.json`.
8. Run exactly one fresh verifier child for each verify pass.

### Platform behavior

- In Codex, keep the normal path serial and auto-mode-first after `init`. Avoid surfacing delegation internals unless they materially affect the work.
- In Codex, spawn bounded subagents only when the user explicitly asks for sub-agents, delegation, or parallel agent work.
- In Codex, once delegation is authorized, the skill may choose the matching child roles and whether to stay one-child-at-a-time or use bounded fan-out. The user should not need to name specific child roles or slash commands.
- In Codex, child spawning is still an explicit parent-orchestrator action. If the current Codex surface blocks delegation, say so briefly only when it materially affects the work, then continue serially.
- In Codex, keep the task tree shallow. The parent session should spawn research, builder, fixer, and verifier children directly instead of asking one custom task child to orchestrate more children.
- In Codex, once delegation is authorized, choose between one-child-at-a-time delegation and bounded fan-out from the frozen spec, repo shape, and current delegation surface. Keep `init`, evidence ownership, and every verifier pass serialized either way.
- In Codex, keep helper fan-out modest and wave-based. Prefer up to 3 parallel helper children at once, wait for that wave to finish, then decide the next phase.
- In Codex, built-in `explorer` is the first choice for read-only repo discovery and proof probes. Built-in `worker` is appropriate for bounded disjoint implementation or check reruns when you can assign explicit ownership.
- In Codex, reuse the live builder child for evidence packing by sending it a follow-up instruction. Verifier passes must use a fresh child or fresh session; do not satisfy verifier freshness by resuming an earlier verifier. Builder and fixer children can be reused or resumed when you intentionally want that context back.
- In Codex, inspect the current child-thread list before reusing or resuming a child. Use `/agent` in Codex CLI or any equivalent child-thread inventory surface available in the current Codex product surface.
- In Codex, the plan/todo checklist UI from `update_plan` is optional session guidance only. It is useful for live progress display, but it is not the source of truth for this workflow.
- In Claude Code, the skill should decide whether to stay on the main thread or let the main Claude session auto-delegate the current phase to a matching built-in or project subagent after `init`. The user should not need to request a specific Claude subagent or delegation mode separately.
- In Claude Code, TodoWrite or the visible task/todo UI is optional session-scoped progress display only. It can help with live tracking in the current session, but it is not the source of truth for this workflow.
- In Claude Code, prefer the installed project subagents from `.claude/agents/`, with descriptions written as proactive trigger conditions for the matching proof-loop phase. Claude's main session routes by the task request, subagent descriptions, and current context, so keep each phase prompt clear in natural language. Reuse the same builder child for the evidence step by default. Only run a fresh builder in evidence-only mode if the original builder session is unavailable or you intentionally discarded it. If `init` just refreshed `.claude/agents/*` during the current Claude session, fall back to the main thread or already-visible agents instead of assuming the refreshed ones are available immediately.
- In Claude Code, keep the orchestration flat: main-session auto-delegation is fine, but the proof-loop workflow agents themselves are leaf roles. The parent session should own the proof-loop phase transitions instead of asking one custom task agent to spawn another.
- In Claude Code, the canonical durable state is always the repo-local artifact set under `.agent/tasks/<TASK_ID>/`, especially `spec.md`, `evidence.md`, `evidence.json`, `verdict.json`, and `problems.md`.
- If subagents are unavailable, preserve the same role separation across separate sessions or clear mode changes in the current session.

Use the exact role prompts from `references/COMMANDS.md`.

## Spec freeze requirements

`spec.md` must contain at least:

- original task statement
- explicit acceptance criteria labeled `AC1`, `AC2`, ...
- constraints
- non-goals

It may also include:

- repo guidance sources
- verification plan
- assumptions resolved narrowly from the user request

Do not edit production code during spec freeze.

## Evidence packing requirements

`evidence.md` and `evidence.json` must judge each acceptance criterion independently with one of:

- `PASS`
- `FAIL`
- `UNKNOWN`

Evidence packing may run missing checks, but it must not keep changing production code.

Every `PASS` must cite concrete proof such as:

- file paths
- commands run
- exit codes
- output summaries
- artifact paths under `raw/`

Do not claim overall `PASS` in the evidence bundle unless every acceptance criterion is `PASS`.

## Fresh verification requirements

The verifier must be a fresh session or fresh subagent.
In Codex, do not satisfy this requirement by resuming a prior verifier child.

The verifier must judge the current repository state and current rerun results, not the builder narrative.

The verifier writes:

- `.agent/tasks/<TASK_ID>/verdict.json`
- `.agent/tasks/<TASK_ID>/problems.md` only when overall verdict is not `PASS`

`problems.md` must include, for each non-`PASS` criterion:

- criterion id and text
- status
- why it is not proven
- minimal reproduction steps
- expected vs actual
- affected files
- smallest safe fix
- corrective hint in 1-3 sentences

The verifier must not modify production code or backfill the evidence bundle.

## Fixer requirements

The fixer reads only:

- `spec.md`
- `verdict.json`
- `problems.md`

The fixer must:

- reconfirm each listed problem in the codebase before editing
- make the smallest safe change set
- avoid regressing already-passing criteria
- regenerate `evidence.md`, `evidence.json`, and raw artifacts
- stop without writing final sign-off

## Validation

Before claiming the workflow is correctly initialized or the artifact set is complete, run:

```bash
scripts/task_loop.py validate --task-id <TASK_ID>
```

Run `validate` only after `init` has fully finished. If it reports initialization in progress, wait and rerun it instead of treating that result as stable task failure.

For a quick summary:

```bash
scripts/task_loop.py status --task-id <TASK_ID>
```

Run `status` only after `init` has fully finished when you need stable task state. If it reports `init_in_progress: true`, treat that as a retry-later condition.

## Guardrails

- Keep `.agent/tasks/<TASK_ID>/` inside the repo
- Treat the Codex todo/checklist UI as ephemeral progress only; the durable workflow state lives in `.agent/tasks/<TASK_ID>/`
- Never claim task completion unless every acceptance criterion is `PASS`
- Separate evaluator and fixer roles
- Keep Codex fan-out shallow and bounded. Parallel helpers may inform the proof loop, but one builder still owns evidence and one fresh verifier still owns verdict.
- Keep the verifier fresh
- Prefer the smallest defensible diffs during fixes
- Preserve existing user guidance outside the managed blocks in `AGENTS.md` and the repo's chosen Claude guide file
