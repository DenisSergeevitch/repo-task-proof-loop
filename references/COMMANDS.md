# Commands and role prompts

Use these prompts as the parent-orchestrator language when running the workflow manually or through product-specific subagents.

Replace `<TASK_ID>` and any placeholder text.

Codex orchestration mapping:

- `spawn_agent`: spawn one child with `agent_type` set to the role name from `.codex/agents/`
- built-in `explorer`: preferred Codex role for bounded read-only discovery and proof probes
- built-in `worker`: appropriate for bounded disjoint implementation or check shards when explicit ownership is possible
- `send_input`: preferred way to reuse a live builder child for evidence packing
- `resume_agent`: available when you intentionally want an older builder or fixer child back; do not use it to satisfy verifier freshness
- child-thread inventory: inspect the current child list before reusing or resuming a child. In Codex CLI, use `/agent`; in other Codex surfaces, use the exposed thread inventory if available.
- `update_plan`: optional way to mirror the current proof-loop step in Codex's todo/checklist UI; do not treat it as the durable workflow record
- CLI surfaces: `/agent` inspects or switches child threads, `/status` shows session config, `/review` reviews the working tree, and `/init` scaffolds a generic `AGENTS.md` if you are not using this skill's managed block

Claude Code note:

- Claude can automatically delegate from the main session based on the request, subagent descriptions, and current context. Write Claude-facing proof-loop prompts so the current phase is obvious.
- Claude may use TodoWrite or show a task/todo list UI for multi-step work. Treat that as optional session-scoped progress display only, not as the durable workflow record.
- The canonical proof-loop state always lives in `.agent/tasks/<TASK_ID>/...`.
- Keep the Claude workflow flat. These custom workflow agents are role endpoints, not recursive orchestrators.

## `init`

Parent action:

```bash
scripts/task_loop.py init --task-id <TASK_ID> [--task-file path/to/task.md | --task-text "task text"]
```

`init` is a serial prerequisite. Never overlap it with `freeze`, `build`, `evidence`, `verify`, `fix`, `validate`, `status`, or child-agent spawning.

After `init`, inspect `.agent/tasks/<TASK_ID>/spec.md` and confirm the repo-local structure is present.
In Codex, `/init` is optional and separate; this skill's initializer already manages the workflow block in `AGENTS.md`.
In Claude Code, if `init` just created or refreshed `.claude/agents/*` during the current session, do not assume those refreshed agents are already available mid-session.
In Claude Code, a TodoWrite list or visible task UI after `init` is optional session progress only. Do not treat it as a substitute for the repo-local task files.
In Claude Code, after `init`, normal phase prompts should stay task-focused and let Claude auto-delegate. If delegation is not specific enough, restate the phase more explicitly in natural language rather than relying on out-of-band controls.

## `freeze`

### Parent prompt for a spec-freezer subagent

Codex note:

- The child already receives in-scope `AGENTS.override.md` / `AGENTS.md` instructions automatically.
- If the child moves into a deeper directory or a path outside the parent's current scope, it should check for any more-specific Codex guide files that apply there.
- `CLAUDE.md` is not a Codex project instruction file. Only treat it as source material when the parent explicitly wants cross-tool alignment.
- If the parent previously fanned out `explorer` children, treat their reports as inputs to reconcile, not as final proof.

```text
You are in SPEC FREEZE mode for TASK_ID <TASK_ID>.

Read:
- .agent/tasks/<TASK_ID>/spec.md
- any user-provided task file or inline task text
- only the minimum relevant code needed to freeze the spec

Write or update:
- .agent/tasks/<TASK_ID>/spec.md

Requirements:
- Preserve the original task statement
- Produce explicit acceptance criteria labeled AC1, AC2, ...
- Include constraints
- Include non-goals
- Add a concise verification plan
- Resolve ambiguity narrowly and list assumptions
- Do not change production code
- Do not write evidence, verdict, or problems files
```

## `build`

### Parent prompt for a builder subagent

Codex note:

- The child already receives in-scope `AGENTS.override.md` / `AGENTS.md` instructions automatically.
- If the child moves into a deeper directory or a path outside the parent's current scope, it should check for any more-specific Codex guide files that apply there.
- If the parent used parallel helper children, treat their findings or diffs as scoped inputs to validate before claiming a criterion is satisfied.

```text
You are in BUILD mode for TASK_ID <TASK_ID>.

Read:
- .agent/tasks/<TASK_ID>/spec.md

Your job:
- Implement the task against the frozen spec
- Make the smallest safe change set that satisfies the acceptance criteria
- Run focused checks as needed
- Keep unrelated files untouched
- Do not write verdict.json or problems.md
- Do not claim final completion yet

Return to the parent with:
- files changed
- checks run
- open risks
```

## Codex adaptive helpers

Use these only after Codex delegation is explicitly authorized by the user and the task clearly splits into bounded scopes. Otherwise stay on the simpler serial proof loop.

### Parent prompt for parallel `explorer` children

```text
Spawn up to 3 built-in `explorer` children for TASK_ID <TASK_ID>.

Before spawning, inspect the current child-thread list and reuse an already-live scoped explorer only if it is still the right fit.

Each explorer must get exactly one scope:
- path prefix or subsystem
- question to answer
- read-only boundary

Each explorer returns only:
- scope inspected
- findings
- risks
- recommended next checks

Wait for all explorers. Then fold their findings into one spec-freezer, builder, or verifier step.
```

### Parent prompt for parallel `worker` children

```text
Spawn a bounded set of built-in `worker` children for TASK_ID <TASK_ID>.

Before spawning, inspect the current child-thread list and avoid duplicating an existing scoped worker unless you intentionally want a fresh child.

For each worker, define:
- exact file or module ownership
- acceptance criteria subset or check shard
- no-touch boundaries

Rules:
- do not write .agent/tasks/<TASK_ID>/evidence.md
- do not write .agent/tasks/<TASK_ID>/evidence.json
- do not write .agent/tasks/<TASK_ID>/verdict.json
- do not write .agent/tasks/<TASK_ID>/problems.md
- report files changed and checks run back to the parent

After the workers finish, continue the primary task-builder child so it can integrate the current repo state and own evidence packing.
```

### Parent prompts for built-in helper children in Codex adaptive fan-out

Use these when the task clearly benefits from bounded parallel work and the user has already explicitly asked for delegation or parallel agent work. Once delegation is authorized, choose them from task shape and current delegation availability, keep the task tree shallow, and keep proof-loop artifact ownership with the custom `task-*` roles.
Keep helper fan-out modest and wave-based. Prefer up to 3 parallel helper children at once, then wait before the next phase.

#### Built-in `explorer`

```text
Spawn one built-in `explorer` child for TASK_ID <TASK_ID>.

Scope:
- <one bounded question, subsystem, or path prefix>

Rules:
- Read relevant code, tests, and guides
- Do not edit production code
- Do not write proof-loop artifacts
- Do not spawn child agents

Return only:
- paths inspected
- constraints, risks, and existing patterns
- proof or verification gaps worth folding into the spec or evidence plan
```

#### Built-in `worker`

```text
Spawn one built-in `worker` child for TASK_ID <TASK_ID>.

Scope:
- <one bounded implementation or check shard>

Allowed paths:
- <explicit paths or modules>

Rules:
- Edit only the allowed paths
- Do not write .agent/tasks/<TASK_ID>/evidence.md
- Do not write .agent/tasks/<TASK_ID>/evidence.json
- Do not write .agent/tasks/<TASK_ID>/verdict.json
- Do not write .agent/tasks/<TASK_ID>/problems.md
- Do not spawn child agents

Return only:
- files changed
- checks run
- residual integration risks
```

## `evidence`

### Follow-up prompt to the same builder session

Codex note:

- In Codex, keep the builder child alive and send this as a follow-up instruction to that same child so it can reuse its own command results.

```text
PACK EVIDENCE for TASK_ID <TASK_ID>.

Do not change production code.

Read:
- .agent/tasks/<TASK_ID>/spec.md
- the current repository state
- any prior command results from this builder session

Write or update:
- .agent/tasks/<TASK_ID>/evidence.md
- .agent/tasks/<TASK_ID>/evidence.json
- .agent/tasks/<TASK_ID>/raw/build.txt
- .agent/tasks/<TASK_ID>/raw/test-unit.txt
- .agent/tasks/<TASK_ID>/raw/test-integration.txt
- .agent/tasks/<TASK_ID>/raw/lint.txt
- .agent/tasks/<TASK_ID>/raw/screenshot-1.png when a screenshot is useful

Rules:
- For each AC, assign PASS, FAIL, or UNKNOWN
- Every PASS must cite concrete proof
- FAIL and UNKNOWN must explain the gap
- Overall PASS only if every AC is PASS
- If sibling `explorer` or `worker` children gathered raw outputs, fold them into the evidence bundle here instead of letting each child write its own parallel evidence file
- Prefer raw artifacts over narrative prose

Return only:
- overall_status
- created or updated files
- commands a fresh verifier should rerun
```

In Claude Code, this follow-up is the default path. Use the fallback below only if the original builder session is unavailable or you intentionally want a fresh evidence-only run.

### Fallback prompt when the original builder session is unavailable

```text
You are in EVIDENCE-ONLY mode for TASK_ID <TASK_ID>.

Read:
- .agent/tasks/<TASK_ID>/spec.md
- the current repository state

Write the same evidence bundle as above.

Do not change production code.
```

## `verify`

### Parent prompt for a fresh verifier subagent

Codex note:

- Spawn a brand-new verifier child or a fresh standalone session for this step.
- Do not satisfy verifier freshness by resuming an older verifier child.
- If earlier helper children gathered raw outputs, treat them as hints only. The verifier still judges the current repository state and reruns whatever it needs.

```text
You are a strict fresh-session verifier for TASK_ID <TASK_ID>. You are not the implementer.

Read in this order:
1. .agent/tasks/<TASK_ID>/spec.md
2. .agent/tasks/<TASK_ID>/evidence.md
3. .agent/tasks/<TASK_ID>/evidence.json

Then independently inspect the current codebase and rerun verification.
Source of truth is the current repository state and current command results, not prior chat claims.
Use the currently available verification surface directly. If browser or MCP tools are available and relevant, use them rather than narrowing yourself to code reading alone.

Write:
- .agent/tasks/<TASK_ID>/verdict.json

If overall verdict is not PASS, also write:
- .agent/tasks/<TASK_ID>/problems.md

Rules:
- PASS an AC only if it is proven in the current codebase now
- FAIL if contradicted, broken, or incomplete
- UNKNOWN if it cannot be verified locally
- Overall PASS only if every AC PASS
- Do not modify production code
- Do not edit the evidence bundle

`problems.md` requirements for each non-PASS AC:
- criterion id and text
- status
- why it is not proven
- minimal reproduction steps
- expected vs actual
- affected files
- smallest safe fix
- corrective hint in 1-3 sentences

Return only:
- overall_verdict
- created files
- one-line reason for each non-PASS AC
```

## `fix`

### Parent prompt for a fixer subagent

Codex note:

- A fresh fixer is preferred for clean role separation, but Codex does not require fixer freshness.
- Reusing or resuming a fixer child is acceptable when you intentionally want that context back.
- If the parent hands the fixer narrowed findings from prior helper children, reconfirm them in the current repository before editing.

```text
You are a repair agent for TASK_ID <TASK_ID>.

Read only:
- .agent/tasks/<TASK_ID>/spec.md
- .agent/tasks/<TASK_ID>/verdict.json
- .agent/tasks/<TASK_ID>/problems.md

Your job:
- Reconfirm each listed FAIL or UNKNOWN condition before editing
- Make the smallest safe change set
- Avoid regressing already-passing criteria
- Rerun only the relevant checks
- Regenerate:
  - .agent/tasks/<TASK_ID>/evidence.md
  - .agent/tasks/<TASK_ID>/evidence.json
  - updated raw artifacts

Do not:
- write verdict.json
- claim final PASS without a fresh verifier
- make broad refactors unless required to satisfy a criterion

Return only:
- files changed
- checks rerun
- remaining risks
```

## `run`

### Default serial order

```text
Run this sequence strictly in order.
1. init <TASK_ID>
2. wait for init to finish, then confirm .agent/tasks/<TASK_ID>/spec.md exists
3. freeze <TASK_ID> using one spec-freezer child
4. build <TASK_ID> using one builder child
5. evidence <TASK_ID> in the same builder child by default, otherwise in evidence-only mode
6. verify <TASK_ID> using one fresh verifier child
7. if verdict is PASS, stop
8. if verdict is FAIL or UNKNOWN, run fix <TASK_ID> using one fixer child, fresh by default
9. run verify <TASK_ID> again using one fresh verifier child
10. repeat 7-9 until PASS or user stops the loop
```

### Codex adaptive fan-out path

Choose between this path and the simpler serial order automatically from the frozen spec, repo shape, and current delegation surface. Keep `init`, evidence ownership, and each verifier pass serialized either way.

```text
1. init <TASK_ID>
2. wait for init to finish, then confirm .agent/tasks/<TASK_ID>/spec.md exists
3. inspect the current child-thread list with /agent in the CLI or the current product's exposed child-thread inventory surface
4. if the spec is not stable yet, fan out up to 3 built-in `explorer` children in parallel with disjoint questions or path scopes
5. wait for those explorers, then freeze <TASK_ID> using one spec-freezer child
6. spawn one task-builder child as the integration owner
7. if implementation splits cleanly, fan out bounded built-in `worker` children in parallel with explicit file or module ownership
8. continue the live builder with send_input so it integrates the current repo state, reruns focused checks, and evidence <TASK_ID>
9. if proof still needs extra read-only probes, fan out bounded built-in `explorer` children in parallel to rerun disjoint checks or inspect separate proof gaps
10. wait for those proof explorers, then run verify <TASK_ID> using one fresh verifier child
11. if verdict is PASS, stop
12. if verdict is FAIL or UNKNOWN, run fix <TASK_ID> using one fixer child, then run verify <TASK_ID> again using one fresh verifier child
13. repeat 11-12 until PASS or user stops the loop
```

## `status`

Parent action:

```bash
scripts/task_loop.py status --task-id <TASK_ID>
```

If the repo is not yet initialized, run `init` first.
Do not run `status` or `validate` in parallel with `init`; wait for `init` to finish first. If `status` reports `init_in_progress: true`, retry later.
