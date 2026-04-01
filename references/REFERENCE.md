
# Reference

When the examples below mention `scripts/task_loop.py`, that path is relative to this skill root. Run it while your shell working directory is inside the target repository.

This skill is designed to be portable, but the repository-local artifacts and subagent files it creates must stay in the target repository.

## Recommended install locations

### Codex

Project skill:
- `.agents/skills/repo-task-proof-loop/`

Personal skill:
- `$HOME/.agents/skills/repo-task-proof-loop/`

### Claude Code

Project skill:
- `.claude/skills/repo-task-proof-loop/`

Personal skill:
- `~/.claude/skills/repo-task-proof-loop/`

The same skill directory can be reused in either product. The initialization script writes repo-local workflow files into the current repository, not into the skill directory.

Claude Code note:
- This skill manages its workflow block in the project-root `CLAUDE.md`.
- Claude Code also loads `.claude/CLAUDE.md`, `.claude/rules/*.md`, and `CLAUDE.local.md`, but those remain compatible add-ons outside this skill's managed block.

## Repo files created by `init`

```text
.agent/tasks/TASK_ID/
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

The initializer also creates or refreshes these project-level integration files:

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

And it inserts a managed workflow block into:

- repo-root `AGENTS.md`
- one Claude guide file: `CLAUDE.md` or `.claude/CLAUDE.md`

If both Claude guide locations exist, the initializer updates the repo-root `CLAUDE.md` and leaves `.claude/CLAUDE.md` untouched. The managed block is replaced in place on re-run, so user-authored content outside the managed markers is preserved.
For Codex, the managed block always lives in repo-root `AGENTS.md`. That file acts as the repo-wide baseline. More-specific nested `AGENTS.override.md`, `AGENTS.md`, or configured fallback filenames still take precedence in their directory trees, and the initializer does not rewrite them.
If `init` creates or rewrites `AGENTS.md` during a running Codex session, start a new Codex session before relying on the updated instructions.
In Claude Code, `CLAUDE.md` is the project guide file Claude checks during onboarding. When `--guides auto` is used together with `--install-subagents claude` or `--install-subagents both`, the initializer ensures `CLAUDE.md` exists even if the repo previously only had `AGENTS.md`.

## Commands

### Initialize workflow files

```bash
scripts/task_loop.py init --task-id my-task
```

Codex CLI also has `/init` to scaffold a generic `AGENTS.md`, but this skill's initializer already manages the workflow block and does not require `/init`.

In Claude Code, if `init` just created or refreshed `.claude/agents/*` during the current session, do not assume those refreshed agents are already available mid-session.

Seed the task from a task file:

```bash
scripts/task_loop.py init --task-id my-task --task-file docs/task.md
```

Seed the task from inline text:

```bash
scripts/task_loop.py init --task-id my-task --task-text "Implement feature X"
```

Control which guide files are created or updated:

```bash
scripts/task_loop.py init --task-id my-task --guides auto
scripts/task_loop.py init --task-id my-task --guides both
scripts/task_loop.py init --task-id my-task --guides agents
scripts/task_loop.py init --task-id my-task --guides claude
scripts/task_loop.py init --task-id my-task --guides none
```

For Claude Code, `--guides auto` updates an existing `CLAUDE.md` or `.claude/CLAUDE.md`. If neither exists and Claude subagents are being installed, it creates `CLAUDE.md`.

`--guides auto` keeps existing guide files up to date, creates both guides when none exist yet, and also creates the product-native guide when you install that product's agents (`CLAUDE.md` for Claude, `AGENTS.md` for Codex).

Control which project subagent sets are installed:

```bash
scripts/task_loop.py init --task-id my-task --install-subagents both
scripts/task_loop.py init --task-id my-task --install-subagents codex
scripts/task_loop.py init --task-id my-task --install-subagents claude
scripts/task_loop.py init --task-id my-task --install-subagents none
```

### Validate the artifact set

```bash
scripts/task_loop.py validate --task-id my-task
```

Run `validate` only after `init` has finished. If it reports initialization in progress, wait and rerun instead of treating that output as the durable workflow state.

### Summarize current status

```bash
scripts/task_loop.py status --task-id my-task
```

Run `status` only after `init` has finished when you need stable task state. If it returns `init_in_progress: true`, treat that as a retry-later signal.

## Expected working pattern

1. Initialize the task folder
2. Freeze the spec
3. Implement
4. Pack evidence
5. Fresh verify
6. Fix if needed
7. Fresh verify again

Codex adaptive orchestration:

- Keep normal Codex usage auto-mode-first and serial by default. Users do not need child-management details unless they explicitly want delegated or parallel agent work.
- Only after the user has explicitly asked for sub-agents, delegation, or parallel agent work may the parent choose between the serial path above and bounded fan-out from the frozen spec, repo shape, and current delegation surface.
- Once delegation is authorized, the parent may fan out bounded built-in `explorer` or `worker` children in parallel when a large Codex task has independent research questions, disjoint write scopes, or several read-only proof probes.
- Keep helper fan-out modest and wave-based. Prefer up to 3 parallel helper children at once, then wait before the next phase.
- Keep the task tree shallow. The parent session should orchestrate children directly instead of asking one custom task child to spawn more children.
- One integration builder still owns `evidence.md` and `evidence.json`.
- One fresh verifier still owns `verdict.json` and `problems.md`.

For exact prompts to use with child agents, see `references/COMMANDS.md`.

Claude adaptive delegation:

- Let the main Claude Code session decide whether to auto-delegate the current proof-loop phase to a matching project subagent. Users should not need to name a specific Claude subagent for normal operation.
- Keep prompts phase-focused so the current need is obvious, for example “freeze the spec”, “run a fresh verification pass”, or “repair the non-PASS criteria”.
- If automatic delegation is not specific enough, tighten the natural-language prompt for the current proof-loop phase rather than relying on out-of-band controls.
- Keep the proof loop flat even when delegation is automatic. The parent session still owns phase transitions, the evidence bundle stays with one builder, and each verify pass stays fresh.

## Notes

- The initializer does not write the final `spec.md` content for you. It creates the strict file structure and seeds the task statement when provided. The actual spec freeze is an agent step.
- `evidence.json` and `verdict.json` are created with valid placeholder content so validation can run immediately after `init`.
- `raw/screenshot-1.png` is created as a tiny placeholder PNG so the required path exists from the start.
- Guidance discovery for seeded task specs includes repo-visible `AGENTS.override.md`, `AGENTS.md`, root `CLAUDE.md`, `.claude/CLAUDE.md`, and `.claude/rules/**/*.md` when present.
- That seeded guidance list is a workflow artifact, not a literal dump of Codex's automatic project-doc context.
- Codex can also load extra fallback filenames configured via `project_doc_fallback_filenames`. The initializer does not try to infer every user's Codex config layer, so treat the seeded guidance list as best-effort when custom fallback filenames matter.
- Codex may also render an `update_plan` checklist or todo list in the UI. Treat that as ephemeral session progress, not as durable proof-loop state.
- Codex CLI surfaces most relevant to this workflow are `/agent`, `/status`, `/review`, and `/init` (generic scaffold only).
- Before reusing or resuming a Codex child, inspect the current child-thread list in `/agent` in the CLI or the equivalent child-thread inventory surface exposed by the current Codex product surface.
- Built-in `explorer` is the preferred Codex role for read-only repo discovery and proof probes. Built-in `worker` is appropriate for bounded disjoint implementation or check shards when explicit ownership is possible.
- Claude Code also loads `.claude/rules/*.md` and `.claude/CLAUDE.md` as project guidance. The initializer discovers those files when seeding guidance sources for the task.
- After installing or refreshing `.claude/agents/` in the current Claude Code session, do not assume the new agent list is already available.
- Claude Code uses the subagent `description` field to decide when the main session should delegate automatically. Phrase project agent descriptions as proactive trigger conditions when you want Claude to pick them on its own.
- For this workflow, treat the generated Claude agents as flat role endpoints. Do not expect one workflow agent to recursively spawn another.
- Claude Code may also render TodoWrite or a task/todo UI for multi-step work. Treat that as optional session-scoped progress display only. The canonical durable workflow state is the repo-local artifact set under `.agent/tasks/<TASK_ID>/`.
