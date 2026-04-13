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
