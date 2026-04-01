#!/usr/bin/env python3
"""Smoke-test the repo-task-proof-loop skill package."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile


REQUIRED_FRONTMATTER_KEYS = {"name", "description"}


def parse_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not match:
        raise ValueError("SKILL.md must start with YAML frontmatter.")
    frontmatter_text, body = match.groups()
    data: dict[str, str] = {}
    current_key: str | None = None
    for raw_line in frontmatter_text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if re.match(r"^[A-Za-z0-9_-]+:", line):
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip().strip('"')
            current_key = key.strip()
        elif current_key and line.startswith("  "):
            # Ignore nested metadata content for this smoke test.
            continue
    return data, body


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, check=True, text=True, capture_output=True)


def main() -> int:
    skill_root = Path(__file__).resolve().parent.parent
    skill_md = skill_root / "SKILL.md"
    task_loop = skill_root / "scripts" / "task_loop.py"
    codex_wording_files = [
        skill_root / "SKILL.md",
        skill_root / "README.md",
        skill_root / "references" / "REFERENCE.md",
        skill_root / "references" / "SUBAGENTS.md",
        skill_root / "references" / "COMMANDS.md",
    ]

    frontmatter, body = parse_frontmatter(skill_md)
    missing = sorted(REQUIRED_FRONTMATTER_KEYS - set(frontmatter.keys()))
    if missing:
        raise SystemExit(f"SKILL.md frontmatter missing keys: {', '.join(missing)}")

    if frontmatter["name"] != skill_root.name:
        raise SystemExit("SKILL.md name must match the parent directory name.")

    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", frontmatter["name"]):
        raise SystemExit("SKILL.md name does not match the allowed skill-name pattern.")

    if not body.strip():
        raise SystemExit("SKILL.md body must not be empty.")

    for path in codex_wording_files:
        content = path.read_text(encoding="utf-8")
        if "list_agents" in content:
            raise SystemExit(f"Codex-facing wording should prefer public child-thread inventory surfaces over raw list_agents mentions: {path}")
        if "automatic bounded fan-out" in content or "without waiting for a separate user request" in content:
            raise SystemExit(f"Codex-facing wording should not claim automatic Codex child spawning without explicit user authorization: {path}")
        if "Users should not need to request subagents" in content or "user should not need to request subagents" in content:
            raise SystemExit(f"Codex-facing wording should not imply that Codex child spawning requires no explicit user authorization: {path}")

    if "up to 3 built-in `explorer` children" not in body:
        raise SystemExit("SKILL.md should cap the Codex explorer fan-out wording at up to 3 parallel helpers.")
    if "validate`, `status`" not in body:
        raise SystemExit("SKILL.md should explicitly serialize validate and status after init.")
    if "explicitly asks for delegation or parallel agent work" not in body:
        raise SystemExit("SKILL.md should state that Codex child spawning requires explicit user authorization for delegation or parallel agent work.")
    if "The user should not need to name specific child roles or slash commands." not in body:
        raise SystemExit("SKILL.md should keep the Codex UX simple even when delegation is authorized.")

    with tempfile.TemporaryDirectory(prefix="repo-task-proof-loop-") as tmp_dir:
        repo = Path(tmp_dir) / "demo-repo"
        repo.mkdir(parents=True)
        run(["git", "init"], repo)

        init_result = run(
            [
                sys.executable,
                str(task_loop),
                "init",
                "--task-id",
                "demo-task",
                "--task-text",
                "Implement a demo task.",
                "--guides",
                "both",
                "--install-subagents",
                "both",
            ],
            repo,
        )
        validate_result = subprocess.run(
            [
                sys.executable,
                str(task_loop),
                "validate",
                "--task-id",
                "demo-task",
            ],
            cwd=repo,
            text=True,
            capture_output=True,
        )
        status_result = run(
            [
                sys.executable,
                str(task_loop),
                "status",
                "--task-id",
                "demo-task",
            ],
            repo,
        )

        validate_json = json.loads(validate_result.stdout)
        if validate_result.returncode != 0 or not validate_json.get("valid"):
            raise SystemExit(f"Validation failed: {validate_result.stdout}\n{validate_result.stderr}")

        init_sentinel = repo / ".agent" / "tasks" / "demo-task" / ".init-in-progress"
        init_sentinel.write_text("smoke-test-init-in-progress\n", encoding="utf-8")
        race_validate_result = subprocess.run(
            [
                sys.executable,
                str(task_loop),
                "validate",
                "--task-id",
                "demo-task",
            ],
            cwd=repo,
            text=True,
            capture_output=True,
        )
        race_status_result = run(
            [
                sys.executable,
                str(task_loop),
                "status",
                "--task-id",
                "demo-task",
            ],
            repo,
        )
        init_sentinel.unlink()

        race_validate_json = json.loads(race_validate_result.stdout)
        race_status_json = json.loads(race_status_result.stdout)
        if race_validate_result.returncode == 0:
            raise SystemExit("Expected validate to fail while the init sentinel is present.")
        if not race_validate_json.get("init_in_progress"):
            raise SystemExit("Expected validate output to report init_in_progress when the init sentinel is present.")
        if not any("still in progress" in error for error in race_validate_json.get("errors", [])):
            raise SystemExit("Expected validate to report that initialization is still in progress.")
        if not race_status_json.get("init_in_progress"):
            raise SystemExit("Expected status output to report init_in_progress when the init sentinel is present.")

        required_paths = [
            repo / ".agent" / "tasks" / "demo-task" / "spec.md",
            repo / ".agent" / "tasks" / "demo-task" / "evidence.json",
            repo / ".agent" / "tasks" / "demo-task" / "verdict.json",
            repo / ".agent" / "tasks" / "demo-task" / "raw" / "screenshot-1.png",
            repo / ".codex" / "agents" / "task-spec-freezer.toml",
            repo / ".claude" / "agents" / "task-spec-freezer.md",
            repo / "AGENTS.md",
            repo / "CLAUDE.md",
        ]
        for path in required_paths:
            if not path.exists():
                raise SystemExit(f"Expected path missing after init: {path}")

        codex_agent_files = [
            repo / ".codex" / "agents" / "task-spec-freezer.toml",
            repo / ".codex" / "agents" / "task-builder.toml",
            repo / ".codex" / "agents" / "task-verifier.toml",
            repo / ".codex" / "agents" / "task-fixer.toml",
        ]
        for path in codex_agent_files:
            content = path.read_text(encoding="utf-8")
            if "CLAUDE.md" in content:
                raise SystemExit(f"Codex agent template should not mention CLAUDE.md: {path}")

        managed_agents = (repo / "AGENTS.md").read_text(encoding="utf-8")
        if "explorer" not in managed_agents or "worker" not in managed_agents:
            raise SystemExit("Expected generated AGENTS.md managed block to mention Codex explorer/worker fan-out guidance.")
        if "before or after spec freeze" not in managed_agents or "only after the spec is frozen" not in managed_agents:
            raise SystemExit("Expected generated AGENTS.md managed block to distinguish explorer timing from worker timing.")
        if "explicitly asked for delegation or parallel agent work" not in managed_agents:
            raise SystemExit("Expected generated AGENTS.md managed block to require explicit user authorization before Codex fan-out.")

        generated_builder = (repo / ".codex" / "agents" / "task-builder.toml").read_text(encoding="utf-8")
        if "integration owner" not in generated_builder:
            raise SystemExit("Expected generated Codex task-builder template to describe the integration-owner role.")

        commands_reference = (skill_root / "references" / "COMMANDS.md").read_text(encoding="utf-8")
        if "Codex adaptive fan-out path" not in commands_reference:
            raise SystemExit("Expected COMMANDS.md to document the Codex adaptive fan-out orchestration path.")
        if "`/agent`" not in commands_reference or "child-thread inventory" not in commands_reference:
            raise SystemExit("Expected COMMANDS.md to mention public child-thread inventory guidance for Codex child reuse.")
        if "up to 3 built-in `explorer` children" not in commands_reference:
            raise SystemExit("Expected COMMANDS.md to cap the Codex explorer fan-out wording at up to 3 parallel helpers.")
        if "Spawn one built-in `explorer` child" not in commands_reference or "Spawn one built-in `worker` child" not in commands_reference:
            raise SystemExit("Expected COMMANDS.md to provide first-class helper prompts for built-in explorer and worker roles.")
        if "Do not run `status` or `validate` in parallel with `init`" not in commands_reference:
            raise SystemExit("Expected COMMANDS.md to document that validate and status must not race init.")
        if "only after Codex delegation is explicitly authorized by the user" not in commands_reference:
            raise SystemExit("Expected COMMANDS.md to require explicit user authorization before Codex adaptive helpers are used.")

        readme = (skill_root / "README.md").read_text(encoding="utf-8")
        if "Do not run `validate` or `status` in parallel with `init`." not in readme:
            raise SystemExit("Expected README.md to document that validate and status must not race init.")
        if "explicitly authorized to use subagents and bounded parallel helper work" not in readme:
            raise SystemExit("Expected README.md to carry explicit delegation authorization inside the Do Task prompt.")
        if "Do Task" not in readme:
            raise SystemExit("Expected README.md to expose the slim Do Task prompt surface.")
        if "initialize it first and then continue automatically after init completes" not in readme:
            raise SystemExit("Expected README.md to make Do Task the init-if-needed end-to-end path.")

        reference = (skill_root / "references" / "REFERENCE.md").read_text(encoding="utf-8")
        if "init_in_progress: true" not in reference:
            raise SystemExit("Expected REFERENCE.md to explain the retry-later init_in_progress status signal.")
        if "Only after the user has explicitly asked for sub-agents, delegation, or parallel agent work" not in reference:
            raise SystemExit("Expected REFERENCE.md to require explicit user authorization before Codex bounded fan-out.")

        skill_prompt = (skill_root / "agents" / "openai.yaml").read_text(encoding="utf-8")
        if "Do not run validate or status until init has fully finished." not in skill_prompt:
            raise SystemExit("Expected Codex default prompt metadata to serialize validate/status after init.")
        if "explorer" not in skill_prompt or "worker" not in skill_prompt:
            raise SystemExit("Expected Codex default prompt metadata to mention explorer/worker adaptive fan-out guidance.")
        if "user explicitly asks for sub-agents, delegation, or parallel agent work" not in skill_prompt:
            raise SystemExit("Expected Codex default prompt metadata to require explicit user authorization before child spawning.")

        claude_auto_repo = Path(tmp_dir) / "claude-auto-repo"
        claude_auto_repo.mkdir(parents=True)
        run(["git", "init"], claude_auto_repo)
        (claude_auto_repo / "AGENTS.md").write_text("# Existing AGENTS\n", encoding="utf-8")
        run(
            [
                sys.executable,
                str(task_loop),
                "init",
                "--task-id",
                "demo-task",
                "--task-text",
                "Implement a demo task.",
                "--guides",
                "auto",
                "--install-subagents",
                "claude",
            ],
            claude_auto_repo,
        )
        if not (claude_auto_repo / "CLAUDE.md").exists():
            raise SystemExit("Expected CLAUDE.md to be created for Claude installs in --guides auto mode.")

        codex_auto_repo = Path(tmp_dir) / "codex-auto-repo"
        codex_auto_repo.mkdir(parents=True)
        run(["git", "init"], codex_auto_repo)
        (codex_auto_repo / "CLAUDE.md").write_text("# Existing CLAUDE\n", encoding="utf-8")
        run(
            [
                sys.executable,
                str(task_loop),
                "init",
                "--task-id",
                "demo-task",
                "--task-text",
                "Implement a demo task.",
                "--guides",
                "auto",
                "--install-subagents",
                "codex",
            ],
            codex_auto_repo,
        )
        if not (codex_auto_repo / "AGENTS.md").exists():
            raise SystemExit("Expected AGENTS.md to be created for Codex installs in --guides auto mode.")

        guidance_repo = Path(tmp_dir) / "guidance-repo"
        guidance_repo.mkdir(parents=True)
        run(["git", "init"], guidance_repo)
        (guidance_repo / "AGENTS.md").write_text("# Root AGENTS\n", encoding="utf-8")
        (guidance_repo / "AGENTS.override.md").write_text("# Root AGENTS override\n", encoding="utf-8")
        nested_rule = guidance_repo / ".claude" / "rules" / "nested" / "workflow.md"
        nested_rule.parent.mkdir(parents=True, exist_ok=True)
        nested_rule.write_text("# Nested workflow rule\n", encoding="utf-8")
        run(
            [
                sys.executable,
                str(task_loop),
                "init",
                "--task-id",
                "demo-task",
                "--task-text",
                "Implement a demo task.",
                "--guides",
                "none",
                "--install-subagents",
                "none",
            ],
            guidance_repo,
        )
        guidance_spec = (guidance_repo / ".agent" / "tasks" / "demo-task" / "spec.md").read_text(encoding="utf-8")
        override_marker = "- AGENTS.override.md"
        agents_marker = "- AGENTS.md"
        rule_marker = "- .claude/rules/nested/workflow.md"
        override_index = guidance_spec.find(override_marker)
        agents_index = guidance_spec.find(agents_marker)
        if override_index == -1 or agents_index == -1:
            raise SystemExit("Expected guidance seeding to include AGENTS.override.md and AGENTS.md.")
        if override_index > agents_index:
            raise SystemExit("Expected AGENTS.override.md to appear before AGENTS.md in seeded guidance.")
        if rule_marker not in guidance_spec:
            raise SystemExit("Expected seeded guidance to include nested .claude/rules/**/*.md files.")

        print(json.dumps(
            {
                "skill_root": str(skill_root),
                "frontmatter_name": frontmatter["name"],
                "init_stdout": json.loads(init_result.stdout),
                "validate_stdout": validate_json,
                "status_stdout": json.loads(status_result.stdout),
                "init_race_checks": {
                    "validate_reports_init_in_progress": race_validate_json.get("init_in_progress") is True,
                    "validate_reports_still_in_progress_error": any(
                        "still in progress" in error for error in race_validate_json.get("errors", [])
                    ),
                    "status_reports_init_in_progress": race_status_json.get("init_in_progress") is True,
                },
                "claude_auto_guides": {
                    "agents_md": str(claude_auto_repo / "AGENTS.md"),
                    "claude_md": str(claude_auto_repo / "CLAUDE.md"),
                },
                "codex_auto_guides": {
                    "agents_md": str(codex_auto_repo / "AGENTS.md"),
                    "claude_md": str(codex_auto_repo / "CLAUDE.md"),
                },
                "guidance_seed_checks": {
                    "override_before_agents": True,
                    "nested_rule_detected": str(nested_rule),
                },
                "codex_adaptive_orchestration_checks": {
                    "managed_agents_mentions_parallel_roles": True,
                    "managed_agents_distinguishes_explorer_vs_worker_timing": True,
                    "managed_agents_require_explicit_user_authorization": True,
                    "builder_mentions_integration_owner": True,
                    "default_prompt_mentions_parallel_roles": True,
                    "default_prompt_requires_explicit_user_authorization": True,
                    "commands_reference_mentions_adaptive_fan_out": True,
                    "commands_reference_includes_builtin_helper_prompts": True,
                    "readme_keeps_internal_role_selection_simple": True,
                },
                "result": "PASS",
            },
            indent=2,
        ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
