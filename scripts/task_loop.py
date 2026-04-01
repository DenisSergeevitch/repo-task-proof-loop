#!/usr/bin/env python3
"""Initialize and validate repo-local task proof loop artifacts."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
TEMPLATES_DIR = SKILL_ROOT / "assets" / "templates"

REQUIRED_TASK_FILES = [
    "spec.md",
    "evidence.md",
    "evidence.json",
    "verdict.json",
    "problems.md",
    "raw/build.txt",
    "raw/test-unit.txt",
    "raw/test-integration.txt",
    "raw/lint.txt",
    "raw/screenshot-1.png",
]

STATUS_VALUES = {"PASS", "FAIL", "UNKNOWN"}
INIT_SENTINEL_FILE = ".init-in-progress"

PNG_PLACEHOLDER = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x04\x00\x00\x00\xb5\x1c\x0c\x02\x00\x00\x00\x0bIDATx\xdac\xfc"
    b"\xff\x1f\x00\x03\x03\x02\x00\xefe\xf6\xe4\x00\x00\x00\x00IEND\xaeB`\x82"
)

MANAGED_START = "<!-- repo-task-proof-loop:start -->"
MANAGED_END = "<!-- repo-task-proof-loop:end -->"
CODEX_GUIDE_CANDIDATES = (
    Path("AGENTS.override.md"),
    Path("AGENTS.md"),
)
CLAUDE_GUIDE_CANDIDATES = (
    Path("CLAUDE.md"),
    Path(".claude") / "CLAUDE.md",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fail(message: str, exit_code: int = 1) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(exit_code)


def validate_task_id(task_id: str) -> str:
    if not task_id:
        fail("TASK_ID cannot be empty.")
    if "/" in task_id or "\\" in task_id or ".." in task_id:
        fail("TASK_ID must not contain path separators or '..'.")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", task_id):
        fail("TASK_ID may contain only letters, numbers, dot, underscore, and hyphen.")
    return task_id


def discover_repo_root(start: Path) -> Path:
    start = start.resolve()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start,
            check=True,
            capture_output=True,
            text=True,
        )
        git_root = result.stdout.strip()
        if git_root:
            return Path(git_root).resolve()
    except Exception:
        pass

    current = start
    while True:
        if (current / ".git").exists():
            return current
        if current.parent == current:
            return start
        current = current.parent


def relative_or_absolute(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except Exception:
        return str(path.resolve())


def path_chain(repo_root: Path, current: Path) -> list[Path]:
    repo_root = repo_root.resolve()
    current = current.resolve()
    chain = [repo_root]
    if repo_root == current:
        return chain
    try:
        rel = current.relative_to(repo_root)
    except ValueError:
        return chain
    cursor = repo_root
    for part in rel.parts:
        cursor = cursor / part
        chain.append(cursor)
    return chain


def guidance_candidates_for_directory(directory: Path) -> list[Path]:
    candidates: list[Path] = []
    for rel_path in (*CODEX_GUIDE_CANDIDATES, Path("CLAUDE.md"), Path(".claude") / "CLAUDE.md"):
        candidate = directory / rel_path
        if candidate.exists():
            candidates.append(candidate)

    rules_dir = directory / ".claude" / "rules"
    if rules_dir.is_dir():
        for candidate in sorted(path for path in rules_dir.rglob("*.md") if path.is_file()):
            if candidate.is_file():
                candidates.append(candidate)

    return candidates


def discover_guidance_files(repo_root: Path, current: Path) -> list[Path]:
    found: list[Path] = []
    seen: set[Path] = set()
    for directory in path_chain(repo_root, current):
        for candidate in guidance_candidates_for_directory(directory):
            if candidate.exists():
                resolved = candidate.resolve()
                if resolved not in seen:
                    found.append(candidate)
                    seen.add(resolved)
    return found


def load_text_template(name: str) -> str:
    path = TEMPLATES_DIR / name
    return path.read_text(encoding="utf-8")


def render_template(text: str, mapping: dict[str, str]) -> str:
    rendered = text
    for key, value in mapping.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def init_sentinel_path(task_dir: Path) -> Path:
    return task_dir / INIT_SENTINEL_FILE


def mark_init_in_progress(task_dir: Path) -> None:
    sentinel = init_sentinel_path(task_dir)
    sentinel.write_text(f"{utc_now_iso()}\n", encoding="utf-8")


def clear_init_in_progress(task_dir: Path) -> None:
    sentinel = init_sentinel_path(task_dir)
    try:
        sentinel.unlink()
    except FileNotFoundError:
        pass


def has_managed_block(path: Path) -> bool:
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    return MANAGED_START in content and MANAGED_END in content


def write_text_file(path: Path, content: str, *, force: bool = False) -> bool:
    ensure_parent(path)
    if path.exists() and not force:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def write_binary_file(path: Path, content: bytes, *, force: bool = False) -> bool:
    ensure_parent(path)
    if path.exists() and not force:
        return False
    path.write_bytes(content)
    return True


def upsert_managed_block(path: Path, block: str) -> str:
    ensure_parent(path)
    if path.exists():
        content = path.read_text(encoding="utf-8")
    else:
        content = ""

    if MANAGED_START in content and MANAGED_END in content:
        pattern = re.compile(
            re.escape(MANAGED_START) + r".*?" + re.escape(MANAGED_END),
            re.DOTALL,
        )
        new_content = pattern.sub(block.strip(), content).rstrip() + "\n"
        action = "updated"
    else:
        if content.strip():
            new_content = content.rstrip() + "\n\n" + block.strip() + "\n"
        else:
            new_content = block.strip() + "\n"
        action = "created" if not path.exists() else "appended"

    path.write_text(new_content, encoding="utf-8")
    return action


def placeholder_task_statement(task_file: str | None, task_text: str | None) -> str:
    if task_text:
        return task_text.strip()
    if task_file:
        try:
            return Path(task_file).read_text(encoding="utf-8").strip()
        except Exception as exc:
            return f"Unable to read task file `{task_file}` at init time: {exc}"
    return "TODO: paste or summarize the original user task here."


def guidance_bullets(repo_root: Path, current: Path) -> str:
    discovered = discover_guidance_files(repo_root, current)
    if not discovered:
        return "- None detected at init time."
    return "\n".join(f"- {relative_or_absolute(path, repo_root)}" for path in discovered)


def choose_claude_guide_path(repo_root: Path) -> Path:
    for rel_path in CLAUDE_GUIDE_CANDIDATES:
        candidate = repo_root / rel_path
        if has_managed_block(candidate):
            return candidate
    for rel_path in CLAUDE_GUIDE_CANDIDATES:
        candidate = repo_root / rel_path
        if candidate.exists():
            return candidate
    return repo_root / "CLAUDE.md"


def template_context(task_id: str, repo_root: Path, current: Path, task_file: str | None, task_text: str | None) -> dict[str, str]:
    return {
        "TASK_ID": task_id,
        "CREATED_AT": utc_now_iso(),
        "REPO_ROOT": str(repo_root.resolve()),
        "WORKING_DIR": str(current.resolve()),
        "GUIDANCE_SOURCES": guidance_bullets(repo_root, current),
        "TASK_STATEMENT": placeholder_task_statement(task_file, task_text),
    }


def install_task_files(task_dir: Path, context: dict[str, str], *, force: bool = False) -> list[str]:
    created: list[str] = []

    file_map = {
        task_dir / "spec.md": render_template(load_text_template("spec.md.tmpl"), context),
        task_dir / "evidence.md": render_template(load_text_template("evidence.md.tmpl"), context),
        task_dir / "evidence.json": render_template(load_text_template("evidence.json.tmpl"), context),
        task_dir / "verdict.json": render_template(load_text_template("verdict.json.tmpl"), context),
        task_dir / "problems.md": render_template(load_text_template("problems.md.tmpl"), context),
        task_dir / "raw" / "build.txt": load_text_template("raw.build.txt.tmpl"),
        task_dir / "raw" / "test-unit.txt": load_text_template("raw.test-unit.txt.tmpl"),
        task_dir / "raw" / "test-integration.txt": load_text_template("raw.test-integration.txt.tmpl"),
        task_dir / "raw" / "lint.txt": load_text_template("raw.lint.txt.tmpl"),
    }

    for path, content in file_map.items():
        if write_text_file(path, content, force=force):
            created.append(str(path))

    screenshot = task_dir / "raw" / "screenshot-1.png"
    if write_binary_file(screenshot, PNG_PLACEHOLDER, force=force):
        created.append(str(screenshot))

    return created


def install_codex_agents(repo_root: Path) -> list[str]:
    target_dir = repo_root / ".codex" / "agents"
    target_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for template_name in (
        "task-spec-freezer.toml.tmpl",
        "task-builder.toml.tmpl",
        "task-verifier.toml.tmpl",
        "task-fixer.toml.tmpl",
    ):
        content = (TEMPLATES_DIR / "codex" / template_name).read_text(encoding="utf-8")
        target = target_dir / template_name.replace(".tmpl", "")
        target.write_text(content, encoding="utf-8")
        written.append(str(target))
    return written


def install_claude_agents(repo_root: Path) -> list[str]:
    target_dir = repo_root / ".claude" / "agents"
    target_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for template_name in (
        "task-spec-freezer.md.tmpl",
        "task-builder.md.tmpl",
        "task-verifier.md.tmpl",
        "task-fixer.md.tmpl",
    ):
        content = (TEMPLATES_DIR / "claude" / template_name).read_text(encoding="utf-8")
        target = target_dir / template_name.replace(".tmpl", "")
        target.write_text(content, encoding="utf-8")
        written.append(str(target))
    return written


def update_guides(repo_root: Path, guides: str, install_subagents: str) -> dict[str, str]:
    actions: dict[str, str] = {}
    if guides == "none":
        return actions

    agents_guide = repo_root / "AGENTS.md"
    claude_guide = choose_claude_guide_path(repo_root)
    existing_claude_guides = [
        repo_root / rel_path
        for rel_path in CLAUDE_GUIDE_CANDIDATES
        if (repo_root / rel_path).exists()
    ]

    want_codex = install_subagents in {"both", "codex"}
    want_claude = install_subagents in {"both", "claude"}

    include_agents = guides in {"both", "agents"}
    include_claude = guides in {"both", "claude"}

    if guides == "auto":
        include_agents = agents_guide.exists()
        include_claude = bool(existing_claude_guides)

        if want_codex and not include_agents:
            include_agents = True
        if want_claude and not include_claude:
            include_claude = True

        if not include_agents and not include_claude:
            include_agents = True
            include_claude = True

    guide_targets: list[tuple[Path, str]] = []
    if include_agents:
        guide_targets.append((agents_guide, load_text_template("managed-block-agents.md.tmpl")))
    if include_claude:
        guide_targets.append((claude_guide, load_text_template("managed-block-claude.md.tmpl")))

    for path, template in guide_targets:
        action = upsert_managed_block(path, template)
        actions[str(path)] = action

    return actions


def json_load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_evidence(data: Any, task_id: str) -> list[str]:
    errors: list[str] = []
    required_keys = {
        "task_id",
        "overall_status",
        "acceptance_criteria",
        "changed_files",
        "commands_for_fresh_verifier",
        "known_gaps",
    }
    if not isinstance(data, dict):
        return ["evidence.json must contain a JSON object."]
    missing = sorted(required_keys - set(data.keys()))
    if missing:
        errors.append(f"evidence.json missing keys: {', '.join(missing)}")
    if data.get("task_id") != task_id:
        errors.append("evidence.json task_id does not match the requested TASK_ID.")
    if data.get("overall_status") not in STATUS_VALUES:
        errors.append("evidence.json overall_status must be PASS, FAIL, or UNKNOWN.")
    criteria = data.get("acceptance_criteria")
    if not isinstance(criteria, list):
        errors.append("evidence.json acceptance_criteria must be a list.")
    else:
        for index, item in enumerate(criteria):
            if not isinstance(item, dict):
                errors.append(f"evidence.json acceptance_criteria[{index}] must be an object.")
                continue
            for key in ("id", "text", "status", "proof", "gaps"):
                if key not in item:
                    errors.append(f"evidence.json acceptance_criteria[{index}] missing key: {key}")
            if item.get("status") not in STATUS_VALUES:
                errors.append(f"evidence.json acceptance_criteria[{index}].status must be PASS, FAIL, or UNKNOWN.")
    return errors


def validate_verdict(data: Any, task_id: str) -> list[str]:
    errors: list[str] = []
    required_keys = {"task_id", "overall_verdict", "criteria", "commands_run", "artifacts_used"}
    if not isinstance(data, dict):
        return ["verdict.json must contain a JSON object."]
    missing = sorted(required_keys - set(data.keys()))
    if missing:
        errors.append(f"verdict.json missing keys: {', '.join(missing)}")
    if data.get("task_id") != task_id:
        errors.append("verdict.json task_id does not match the requested TASK_ID.")
    if data.get("overall_verdict") not in STATUS_VALUES:
        errors.append("verdict.json overall_verdict must be PASS, FAIL, or UNKNOWN.")
    criteria = data.get("criteria")
    if not isinstance(criteria, list):
        errors.append("verdict.json criteria must be a list.")
    else:
        for index, item in enumerate(criteria):
            if not isinstance(item, dict):
                errors.append(f"verdict.json criteria[{index}] must be an object.")
                continue
            for key in ("id", "status", "reason"):
                if key not in item:
                    errors.append(f"verdict.json criteria[{index}] missing key: {key}")
            if item.get("status") not in STATUS_VALUES:
                errors.append(f"verdict.json criteria[{index}].status must be PASS, FAIL, or UNKNOWN.")
    return errors


def cmd_init(args: argparse.Namespace) -> int:
    current = Path(args.repo_root).resolve() if args.repo_root else Path.cwd().resolve()
    repo_root = discover_repo_root(current)
    task_id = validate_task_id(args.task_id)
    task_dir = repo_root / ".agent" / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    mark_init_in_progress(task_dir)
    try:
        context = template_context(task_id, repo_root, current, args.task_file, args.task_text)
        created_files = install_task_files(task_dir, context, force=args.force)

        installed_agents: list[str] = []
        if args.install_subagents in {"both", "codex"}:
            installed_agents.extend(install_codex_agents(repo_root))
        if args.install_subagents in {"both", "claude"}:
            installed_agents.extend(install_claude_agents(repo_root))

        guide_actions = update_guides(repo_root, args.guides, args.install_subagents)

        result = {
            "repo_root": str(repo_root),
            "task_id": task_id,
            "task_dir": str(task_dir),
            "created_or_overwritten_task_files": created_files,
            "installed_or_refreshed_subagent_files": installed_agents,
            "guide_file_actions": guide_actions,
        }
        print(json.dumps(result, indent=2))
        return 0
    finally:
        clear_init_in_progress(task_dir)


def cmd_validate(args: argparse.Namespace) -> int:
    current = Path(args.repo_root).resolve() if args.repo_root else Path.cwd().resolve()
    repo_root = discover_repo_root(current)
    task_id = validate_task_id(args.task_id)
    task_dir = repo_root / ".agent" / "tasks" / task_id

    missing = [str(task_dir / rel) for rel in REQUIRED_TASK_FILES if not (task_dir / rel).exists()]
    errors: list[str] = []
    init_in_progress = init_sentinel_path(task_dir).exists()

    if not task_dir.exists():
        errors.append(f"Task directory does not exist: {task_dir}")
    elif init_in_progress:
        errors.append(
            f"Task initialization is still in progress: {init_sentinel_path(task_dir)}. "
            "Rerun validate after init completes."
        )

    evidence_path = task_dir / "evidence.json"
    verdict_path = task_dir / "verdict.json"

    if evidence_path.exists():
        try:
            evidence = json_load(evidence_path)
            errors.extend(validate_evidence(evidence, task_id))
        except Exception as exc:
            errors.append(f"Failed to parse evidence.json: {exc}")

    if verdict_path.exists():
        try:
            verdict = json_load(verdict_path)
            errors.extend(validate_verdict(verdict, task_id))
        except Exception as exc:
            errors.append(f"Failed to parse verdict.json: {exc}")

    valid = not missing and not errors
    report = {
        "repo_root": str(repo_root),
        "task_id": task_id,
        "task_dir": str(task_dir),
        "init_in_progress": init_in_progress,
        "valid": valid,
        "missing_files": missing,
        "errors": errors,
    }
    print(json.dumps(report, indent=2))
    return 0 if valid else 1


def cmd_status(args: argparse.Namespace) -> int:
    current = Path(args.repo_root).resolve() if args.repo_root else Path.cwd().resolve()
    repo_root = discover_repo_root(current)
    task_id = validate_task_id(args.task_id)
    task_dir = repo_root / ".agent" / "tasks" / task_id

    report: dict[str, Any] = {
        "repo_root": str(repo_root),
        "task_id": task_id,
        "task_dir": str(task_dir),
        "exists": task_dir.exists(),
        "init_in_progress": init_sentinel_path(task_dir).exists(),
        "required_files_present": {},
        "evidence_overall_status": None,
        "verdict_overall_status": None,
        "non_pass_criteria": [],
    }

    for rel in REQUIRED_TASK_FILES:
        report["required_files_present"][rel] = (task_dir / rel).exists()

    evidence_path = task_dir / "evidence.json"
    if evidence_path.exists():
        try:
            evidence = json_load(evidence_path)
            report["evidence_overall_status"] = evidence.get("overall_status")
        except Exception as exc:
            report["evidence_overall_status"] = f"PARSE_ERROR: {exc}"

    verdict_path = task_dir / "verdict.json"
    if verdict_path.exists():
        try:
            verdict = json_load(verdict_path)
            report["verdict_overall_status"] = verdict.get("overall_verdict")
            criteria = verdict.get("criteria", [])
            if isinstance(criteria, list):
                for item in criteria:
                    if isinstance(item, dict) and item.get("status") in {"FAIL", "UNKNOWN"}:
                        report["non_pass_criteria"].append(
                            {
                                "id": item.get("id"),
                                "status": item.get("status"),
                                "reason": item.get("reason"),
                            }
                        )
        except Exception as exc:
            report["verdict_overall_status"] = f"PARSE_ERROR: {exc}"

    print(json.dumps(report, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Repo task proof loop helper.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize repo-local task artifacts and integration files.")
    init_parser.add_argument("--task-id", required=True, help="Task identifier, e.g. feature-auth-hardening")
    init_parser.add_argument("--task-file", help="Optional path to a task description file to seed spec.md")
    init_parser.add_argument("--task-text", help="Optional inline task text to seed spec.md")
    init_parser.add_argument("--repo-root", help="Optional working directory inside the repo. Defaults to the current directory.")
    init_parser.add_argument(
        "--guides",
        choices=["auto", "agents", "claude", "both", "none"],
        default="auto",
        help="Which guide files to create or update.",
    )
    init_parser.add_argument(
        "--install-subagents",
        choices=["both", "codex", "claude", "none"],
        default="both",
        help="Which project-scoped subagent sets to install or refresh.",
    )
    init_parser.add_argument("--force", action="store_true", help="Overwrite existing task artifact templates.")
    init_parser.set_defaults(func=cmd_init)

    validate_parser = subparsers.add_parser("validate", help="Validate required task files and JSON structures.")
    validate_parser.add_argument("--task-id", required=True, help="Task identifier to validate.")
    validate_parser.add_argument("--repo-root", help="Optional working directory inside the repo. Defaults to the current directory.")
    validate_parser.set_defaults(func=cmd_validate)

    status_parser = subparsers.add_parser("status", help="Summarize current task artifact status.")
    status_parser.add_argument("--task-id", required=True, help="Task identifier to summarize.")
    status_parser.add_argument("--repo-root", help="Optional working directory inside the repo. Defaults to the current directory.")
    status_parser.set_defaults(func=cmd_status)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
