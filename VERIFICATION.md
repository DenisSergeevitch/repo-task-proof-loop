# Verification

This package was smoke-tested before packaging.

## Command run

```bash
python scripts/verify_package.py
```

## What the smoke test checks

- `SKILL.md` frontmatter exists and the `name` matches the parent directory
- the skill body is non-empty
- `scripts/task_loop.py init --task-id demo-task --task-text "Implement a demo task."` succeeds inside a fresh temporary git repository
- `scripts/task_loop.py validate --task-id demo-task` returns `valid: true`
- a task-local init sentinel makes `validate` report initialization-in-progress instead of only a misleading missing-files failure when `init` is still active
- `scripts/task_loop.py status --task-id demo-task` reports `init_in_progress: true` when the init sentinel is present
- the expected repo-local artifacts are created under `.agent/tasks/demo-task/`
- project-scoped subagent files are created under `.codex/agents/` and `.claude/agents/`
- `AGENTS.md` and `CLAUDE.md` are created with managed workflow blocks
- generated Codex agent files stay Codex-specific and do not tell Codex to read `CLAUDE.md`
- generated Codex AGENTS guidance mentions the bounded `explorer` / `worker` fan-out path
- generated Codex AGENTS guidance allows `explorer` fan-out before or after spec freeze and keeps `worker` fan-out post-freeze only
- generated Codex task-builder template still defines a single integration owner for evidence
- the Codex-facing skill metadata prompt mentions the `explorer` / `worker` adaptive fan-out path
- `references/COMMANDS.md` documents the Codex adaptive fan-out orchestration path, includes first-class built-in `explorer` / `worker` helper prompts, and mentions public child-thread inspection surfaces
- seeded guidance discovery includes `AGENTS.override.md` before `AGENTS.md`
- seeded guidance discovery includes nested `.claude/rules/**/*.md` files
- `--guides auto --install-subagents claude` creates `CLAUDE.md` even if the repo previously only had `AGENTS.md`
- `--guides auto --install-subagents codex` creates `AGENTS.md` even if the repo previously only had `CLAUDE.md`

## Last local result

PASS
