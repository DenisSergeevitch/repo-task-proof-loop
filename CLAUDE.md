<!-- repo-task-proof-loop:start -->
## Repo task proof loop

For substantial features, refactors, and bug fixes, use the repo-task-proof-loop workflow.

Required artifact path:
- Keep all task artifacts in `.agent/tasks/<TASK_ID>/` inside this repository.

Required sequence:
1. Freeze `.agent/tasks/<TASK_ID>/spec.md` before implementation.
2. Implement against explicit acceptance criteria (`AC1`, `AC2`, ...).
3. Create `evidence.md`, `evidence.json`, and raw artifacts.
4. Run a fresh verification pass against the current codebase and rerun checks.
5. If verification is not `PASS`, write `problems.md`, apply the smallest safe fix, and reverify.

Hard rules:
- Do not claim completion unless every acceptance criterion is `PASS`.
- Verifiers judge current code and current command results, not prior chat claims.
- Fixers should make the smallest defensible diff.

Installed workflow agents:
- `.claude/agents/task-spec-freezer.md`
- `.claude/agents/task-builder.md`
- `.claude/agents/task-verifier.md`
- `.claude/agents/task-fixer.md`

Claude Code note:
- If `init` just created or refreshed these files during the current Claude Code session, do not assume the refreshed workflow agents are already available.
- The main Claude session may auto-delegate to these workflow agents when the current proof-loop phase matches their descriptions. If automatic delegation is not precise enough, make the current proof-loop phase more explicit in natural language.
- TodoWrite or the visible task/todo UI is optional session-scoped progress display only. The canonical durable proof-loop state is the repo-local artifact set under `.agent/tasks/<TASK_ID>/`.
- Keep this workflow flat. These generated workflow agents are role endpoints, not recursive orchestrators.
- Keep this block in the root `CLAUDE.md`. If the workflow needs longer repo guidance, prefer `@path` imports or `.claude/rules/*.md` instead of expanding this block.
<!-- repo-task-proof-loop:end -->
