"""Habitat Code tools — PR strategy, repo info, QA drafts, earnings tracker."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from app.tools.registry import tool

log = logging.getLogger("jarvis.tools.habitat")

# Earnings tracker
_earnings: list[dict] = []
_submissions: list[dict] = []

REPOS = {
    "opa": {"lang": "Go", "github": "open-policy-agent/opa", "desc": "Open Policy Agent — policy engine"},
    "jerryscript": {"lang": "C", "github": "jerryscript-project/jerryscript", "desc": "Lightweight JS engine for IoT"},
    "blender": {"lang": "C/C++", "github": "blender/blender", "desc": "3D creation suite"},
    "goja": {"lang": "Go", "github": "dop251/goja", "desc": "ECMAScript/JS engine in Go"},
    "cue": {"lang": "Go", "github": "cue-lang/cue", "desc": "Data validation language"},
    "devito": {"lang": "Python", "github": "devitocodes/devito", "desc": "Symbolic finite difference DSL"},
    "tidb": {"lang": "Go", "github": "pingcap/tidb", "desc": "Distributed SQL database"},
    "vitess": {"lang": "Go", "github": "vitessio/vitess", "desc": "Database clustering for MySQL"},
    "consul": {"lang": "Go", "github": "hashicorp/consul", "desc": "Service mesh / discovery"},
    "rust-analyzer": {"lang": "Rust", "github": "rust-lang/rust-analyzer", "desc": "Rust IDE support"},
}


@tool(
    name="habitat_repo_info",
    description="Get info about a Habitat Code repo. Use when user asks about repos, languages, or which repo to pick.",
    input_schema={
        "type": "object",
        "properties": {
            "repo_name": {"type": "string", "description": "Repo name like 'opa', 'blender', 'tidb'. Say 'all' for all repos."},
        },
        "required": ["repo_name"],
    },
)
async def habitat_repo_info_tool(input_data: dict[str, Any]) -> str:
    name = input_data["repo_name"].lower().strip()
    if name == "all":
        lines = []
        for k, v in REPOS.items():
            lines.append(f"{k} ({v['lang']}): {v['desc']} — github.com/{v['github']}")
        return "Habitat Season 2 repos:\n" + "\n".join(lines)
    repo = REPOS.get(name)
    if repo:
        return f"{name} — Language: {repo['lang']}, GitHub: github.com/{repo['github']}, Description: {repo['desc']}"
    return f"Unknown repo: {name}. Available: {', '.join(REPOS.keys())}"


@tool(
    name="habitat_strategy",
    description="Get strategy advice for a Habitat Code task. Use when user asks how to make a task worth $1600 or how to approach a PR.",
    input_schema={
        "type": "object",
        "properties": {
            "context": {"type": "string", "description": "What the user is working on or asking about"},
        },
        "required": ["context"],
    },
)
async def habitat_strategy_tool(input_data: dict[str, Any]) -> str:
    return """Habitat $1600 Strategy:
1. MINIMAL description — don't over-explain, let AI guess wrong
2. MAXIMUM implicit requirements — test what a competent engineer would always do
3. Sweet spot: 100-500 insertions, 4-15 files, cross-module changes
4. Focus on: parsers, query engines, policy evaluators (behaviorally complex)
5. Test edge cases, error handling, spec compliance — things AI misses
6. Implementation-agnostic — describe WHAT not HOW
7. Never include the solution in the description
8. Reserve FIRST, clone LATER — speed wins (5 per repo max)
9. Triple-check commit hashes — base hash = parent of merge commit
10. All test files/functions must have __HABITAT suffix"""


@tool(
    name="habitat_qa_drafts",
    description="Generate 3 QA draft styles for a Habitat submission. User MUST rewrite in their own words.",
    input_schema={
        "type": "object",
        "properties": {
            "task_summary": {"type": "string", "description": "Brief description of what the task tests"},
            "result": {"type": "string", "description": "'pass' or 'fail'"},
            "reason": {"type": "string", "description": "Why it passed or failed"},
        },
        "required": ["task_summary", "result", "reason"],
    },
)
async def habitat_qa_drafts_tool(input_data: dict[str, Any]) -> str:
    summary = input_data["task_summary"]
    result = input_data["result"]
    reason = input_data["reason"]

    return f"""3 QA Draft Styles (REWRITE IN YOUR OWN WORDS):

TECHNICAL:
The AI {'successfully implemented' if result == 'pass' else 'failed to implement'} {summary}. {reason}. The {'test suite confirmed correct behavior' if result == 'pass' else 'test failures indicate missing edge cases and implicit requirements'}.

SHORT:
{'Passed' if result == 'pass' else 'Failed'} — {reason}.

CASUAL:
{'So this one passed,' if result == 'pass' else 'This one didnt make it,'} {reason.lower()}. {'Tests all green.' if result == 'pass' else 'Tests caught the gaps.'}

IMPORTANT: Suchet, rewrite these in YOUR words. AI detectors will check."""


@tool(
    name="habitat_earnings",
    description="Track Habitat earnings. Add a completed task or show total earnings.",
    input_schema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "'add' to log earnings, 'show' to see total"},
            "repo": {"type": "string", "description": "Repo name (for 'add')"},
            "amount": {"type": "number", "description": "Amount earned in USD (for 'add')"},
        },
        "required": ["action"],
    },
)
async def habitat_earnings_tool(input_data: dict[str, Any]) -> str:
    action = input_data["action"].lower()
    if action == "add":
        repo = input_data.get("repo", "unknown")
        amount = input_data.get("amount", 0)
        _earnings.append({
            "repo": repo,
            "amount": amount,
            "date": datetime.now().strftime("%Y-%m-%d"),
        })
        total = sum(e["amount"] for e in _earnings)
        return f"Logged ${amount} from {repo}. Total this session: ${total}. Season 1+2 total: ${3200 + total}"
    else:
        if not _earnings:
            return "No earnings logged this session. Previous total: $3200 (Season 1: $1400, Season 2: $1800)"
        total = sum(e["amount"] for e in _earnings)
        lines = [f"  {e['repo']}: ${e['amount']} ({e['date']})" for e in _earnings]
        return f"Session earnings:\n" + "\n".join(lines) + f"\nSession total: ${total}\nAll-time: ${3200 + total}"


@tool(
    name="habitat_checklist",
    description="Pre-submit checklist for a Habitat task. Use before submitting to catch mistakes.",
    input_schema={"type": "object", "properties": {}},
)
async def habitat_checklist_tool(input_data: dict[str, Any]) -> str:
    return """HABITAT PRE-SUBMIT CHECKLIST:
1. Golden patch = source code ONLY (no tests)?
2. Test patch = tests ONLY (no source fix)?
3. All test files have __HABITAT suffix?
4. All test functions have __HABITAT suffix?
5. Base commit hash = parent of merge commit (NOT merge commit itself)?
6. Tests FAIL without golden patch?
7. Tests PASS with golden patch?
8. Description is MINIMAL (doesn't give away solution)?
9. Implicit requirements tested (error handling, edge cases)?
10. No refactoring or dependency changes?
11. Test runner updated if new test files added?
12. QA written in YOUR OWN words (not AI)?"""


# --- Task tracking ---
_tasks: list[dict] = []


@tool(
    name="habitat_track_task",
    description="Track a Habitat task — log repo, PR, status, hashes. Use when starting or updating a task.",
    input_schema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "'add', 'update', 'list'"},
            "repo": {"type": "string", "description": "Repo name"},
            "pr_number": {"type": "string", "description": "PR number or link"},
            "base_hash": {"type": "string", "description": "Base commit hash (what you reserve)"},
            "merge_hash": {"type": "string", "description": "Merge commit hash"},
            "status": {"type": "string", "description": "reserved, in-progress, submitted, passed, failed, rejected"},
        },
        "required": ["action"],
    },
)
async def habitat_track_task_tool(input_data: dict[str, Any]) -> str:
    action = input_data["action"].lower()

    if action == "add":
        task = {
            "repo": input_data.get("repo", ""),
            "pr": input_data.get("pr_number", ""),
            "base_hash": input_data.get("base_hash", ""),
            "merge_hash": input_data.get("merge_hash", ""),
            "status": input_data.get("status", "reserved"),
            "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        _tasks.append(task)
        return f"Task #{len(_tasks)} tracked: {task['repo']} PR {task['pr']} — {task['status']}"

    elif action == "update":
        if _tasks:
            task = _tasks[-1]
            if input_data.get("status"):
                task["status"] = input_data["status"]
            return f"Task updated: {task['repo']} PR {task['pr']} — {task['status']}"
        return "No tasks to update."

    else:  # list
        if not _tasks:
            return "No tasks tracked yet. Say 'track task' when you start working on a PR."
        lines = []
        for i, t in enumerate(_tasks, 1):
            lines.append(f"{i}. {t['repo']} PR {t['pr']} [{t['status']}] — base: {t['base_hash'][:12] if t['base_hash'] else 'N/A'}")
        return "Habitat tasks:\n" + "\n".join(lines)


@tool(
    name="habitat_implicit_ideas",
    description="Suggest implicit requirement ideas for a given code change type. Use when brainstorming what tests to write.",
    input_schema={
        "type": "object",
        "properties": {
            "change_type": {"type": "string", "description": "Type of change: parser, API endpoint, query engine, error handling, config, CLI, data structure, etc."},
            "language": {"type": "string", "description": "Programming language: Go, Python, C, Rust", "default": "Go"},
        },
        "required": ["change_type"],
    },
)
async def habitat_implicit_ideas_tool(input_data: dict[str, Any]) -> str:
    change_type = input_data["change_type"].lower()
    lang = input_data.get("language", "Go")

    ideas = {
        "parser": [
            "Empty input handling",
            "Malformed/incomplete input",
            "Unicode/special characters",
            "Deeply nested structures",
            "Maximum depth/length limits",
            "Whitespace variations",
            "Comment handling within parsed content",
            "Error messages are descriptive (not just 'parse error')",
            "Line/column number in error messages",
            "Graceful degradation on partial input",
        ],
        "api": [
            "Invalid HTTP methods return 405",
            "Missing required fields return descriptive errors",
            "Empty body handling",
            "Content-Type validation",
            "Concurrent request handling",
            "Rate limiting behavior",
            "Response format consistency",
            "Error response structure matches success structure",
            "Pagination edge cases (page 0, negative, beyond last)",
            "Authorization checks before data access",
        ],
        "query": [
            "Empty result set returns correct structure",
            "NULL/nil value handling in conditions",
            "Case sensitivity behavior",
            "Ordering stability (deterministic)",
            "Limit/offset boundary conditions",
            "Invalid column/field names",
            "Type coercion edge cases",
            "Subquery result handling",
            "Aggregate functions on empty sets",
            "Injection-like input safety",
        ],
        "error": [
            "Error message doesn't leak internal paths",
            "Error codes are consistent",
            "Wrapped errors preserve original cause",
            "Concurrent error handling",
            "Timeout produces specific error type",
            "Resource cleanup on error (no leaks)",
            "Error recovery doesn't corrupt state",
            "Partial failure handling (some succeed, some fail)",
            "Nested error unwrapping works correctly",
            "User-facing vs internal error distinction",
        ],
        "config": [
            "Default values when config missing",
            "Invalid config value types",
            "Environment variable override precedence",
            "Empty string vs unset distinction",
            "Config reload/hot-reload behavior",
            "File permission handling",
            "Circular reference detection",
            "Deprecated field warnings",
            "Unknown field handling (strict vs lenient)",
            "Path resolution (relative vs absolute)",
        ],
        "cli": [
            "No arguments shows help",
            "Unknown flag handling",
            "Mutually exclusive flags",
            "Flag shorthand and longhand both work",
            "Exit codes are correct (0=success, 1=error)",
            "Stderr vs stdout separation",
            "Pipe-friendly output format",
            "Signal handling (SIGINT graceful shutdown)",
            "Version flag works",
            "Verbose/quiet mode behavior",
        ],
    }

    # Find matching category
    matched = None
    for key in ideas:
        if key in change_type:
            matched = key
            break

    if matched:
        items = ideas[matched]
        lines = [f"  {i}. {item}" for i, item in enumerate(items, 1)]
        return f"Implicit requirement ideas for {change_type} ({lang}):\n" + "\n".join(lines) + "\n\nPick 3-5 that apply to your specific PR. These are what AI typically misses."
    else:
        # Generic ideas
        return f"""Generic implicit requirement ideas for {change_type}:
1. Nil/null/zero value handling
2. Concurrent/parallel access safety
3. Error messages are descriptive and actionable
4. Resource cleanup (no leaks on early return)
5. Boundary conditions (empty, max, negative)
6. Type safety at interfaces
7. Backward compatibility preserved
8. Documentation/comments match behavior
9. Logging at appropriate levels
10. Idempotency where expected

Pick the ones that apply to your PR. Ask about a specific category for more targeted ideas."""


@tool(
    name="habitat_submission_limits",
    description="Check Habitat submission limits and rules. Use when user asks about limits, reservations, or rules.",
    input_schema={"type": "object", "properties": {}},
)
async def habitat_limits_tool(input_data: dict[str, Any]) -> str:
    active = len([t for t in _tasks if t.get("status") in ("reserved", "in-progress")])
    submitted_today = len([t for t in _tasks if t.get("status") == "submitted"])

    return f"""HABITAT LIMITS:
- Max 7 reservations at a time (you have {active} active)
- Max 5 tasks per repo
- Max 50 submissions per 24 hours (you've submitted {submitted_today} today)
- Payout: AI <=50% pass = $1600, AI >50% = $0 REJECTED
- AI 0% pass = Too Hard (must add hints)
- Reserve FIRST, clone LATER
- QA must be human-written for ALL runs"""


@tool(
    name="habitat_open_site",
    description="Open Habitat Code website or a specific repo on GitHub.",
    input_schema={
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "'habitat' for the site, or repo name like 'opa' for GitHub"},
        },
        "required": ["target"],
    },
)
async def habitat_open_site_tool(input_data: dict[str, Any]) -> str:
    from app.tools.system import run_powershell
    target = input_data["target"].lower().strip()

    if target in ("habitat", "site", "code"):
        await run_powershell("Start-Process 'https://code.habitat.inc'")
        return "Opened Habitat Code website"
    elif target in ("slack", "announcements"):
        await run_powershell("Start-Process 'https://app.slack.com'")
        return "Opened Slack — check #announcements"
    elif target in ("deel", "payment"):
        await run_powershell("Start-Process 'https://app.deel.com'")
        return "Opened Deel for payments"
    elif target in REPOS:
        repo = REPOS[target]
        await run_powershell(f"Start-Process 'https://github.com/{repo['github']}'")
        return f"Opened {target} on GitHub: {repo['github']}"
    else:
        return f"Unknown target: {target}. Try: habitat, slack, deel, or a repo name like opa, tidb, etc."


@tool(
    name="habitat_pr_sweet_spot",
    description="Check if a PR matches the $1600 sweet spot criteria. Describe the PR and get a score.",
    input_schema={
        "type": "object",
        "properties": {
            "insertions": {"type": "integer", "description": "Number of lines inserted"},
            "deletions": {"type": "integer", "description": "Number of lines deleted"},
            "files_changed": {"type": "integer", "description": "Number of files changed"},
            "has_tests": {"type": "boolean", "description": "Does the PR already have tests?"},
            "is_refactor": {"type": "boolean", "description": "Is it a refactoring PR?"},
            "change_type": {"type": "string", "description": "Type: feature, bugfix, enhancement, refactor"},
        },
        "required": ["insertions", "files_changed", "change_type"],
    },
)
async def habitat_pr_sweet_spot_tool(input_data: dict[str, Any]) -> str:
    ins = input_data["insertions"]
    dels = input_data.get("deletions", 0)
    files = input_data["files_changed"]
    has_tests = input_data.get("has_tests", False)
    is_refactor = input_data.get("is_refactor", False)
    change_type = input_data["change_type"].lower()

    score = 0
    notes = []

    # Insertions sweet spot: 100-500
    if 100 <= ins <= 500:
        score += 3
        notes.append("Insertions in sweet spot (100-500)")
    elif 50 <= ins < 100:
        score += 1
        notes.append("Insertions a bit low but workable")
    elif ins > 500:
        score += 1
        notes.append("Large PR — harder to write comprehensive tests")
    else:
        notes.append("Too small — not enough complexity")

    # Files: 4-15
    if 4 <= files <= 15:
        score += 3
        notes.append("Files changed in sweet spot (4-15)")
    elif files > 15:
        score += 1
        notes.append("Many files — complex but harder to test everything")
    elif files < 4:
        score += 1
        notes.append("Few files — may be too simple")

    # Cross-module is better
    if files >= 4:
        score += 1
        notes.append("Likely cross-module (good)")

    # No refactoring
    if is_refactor:
        score -= 3
        notes.append("REFACTORING — NOT ALLOWED")
    else:
        score += 1

    # Change type
    if change_type in ("feature", "enhancement", "bugfix"):
        score += 2
        notes.append(f"Good change type: {change_type}")
    elif change_type == "refactor":
        score -= 3
        notes.append("REFACTORING — NOT ALLOWED")

    # Tests
    if not has_tests:
        score += 1
        notes.append("No existing tests — we write our own (good control)")

    # Score
    max_score = 11
    pct = (score / max_score) * 100
    rating = "EXCELLENT" if pct >= 80 else "GOOD" if pct >= 60 else "OKAY" if pct >= 40 else "SKIP"

    return f"""PR SCORE: {score}/{max_score} ({pct:.0f}%) — {rating}
+{ins}/-{dels} | {files} files | {change_type}

Analysis:
""" + "\n".join(f"  {'✓' if 'good' in n.lower() or 'sweet' in n.lower() else '⚠' if 'NOT' in n else '•'} {n}" for n in notes)
