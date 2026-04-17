"""Workout coach tool — JARVIS guides you through your workout with voice."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from app.tools.registry import tool

log = logging.getLogger("jarvis.tools.workout")

# Default workout plan — Suchet's beginner full-body routine
DEFAULT_PLAN: list[dict] = [
    {"name": "Goblet Squats", "sets": 2, "reps": "10 reps", "rest_sec": 60},
    {"name": "Dumbbell Floor Press", "sets": 2, "reps": "10 reps", "rest_sec": 60},
    {"name": "Dumbbell Rows (each arm)", "sets": 2, "reps": "10 reps each arm", "rest_sec": 60},
    {"name": "Overhead Press", "sets": 2, "reps": "8 reps", "rest_sec": 60},
    {"name": "Bicep Curls", "sets": 2, "reps": "10 reps", "rest_sec": 60},
    {"name": "Plank", "sets": 2, "reps": "15 seconds hold", "rest_sec": 45},
]

# Session state
_session: dict[str, Any] = {
    "active": False,
    "plan": [],
    "current_exercise": 0,
    "current_set": 0,
    "started_at": None,
    "completed_exercises": 0,
    "total_sets_done": 0,
}


def _reset_session():
    _session["active"] = False
    _session["plan"] = []
    _session["current_exercise"] = 0
    _session["current_set"] = 0
    _session["started_at"] = None
    _session["completed_exercises"] = 0
    _session["total_sets_done"] = 0


def _current_exercise_info() -> dict | None:
    if _session["current_exercise"] >= len(_session["plan"]):
        return None
    return _session["plan"][_session["current_exercise"]]


def _total_sets() -> int:
    return sum(ex["sets"] for ex in _session["plan"])


def _format_exercise_announcement(ex: dict, set_num: int) -> str:
    return (
        f"Exercise {_session['current_exercise'] + 1} of {len(_session['plan'])}: "
        f"{ex['name']}. Set {set_num} of {ex['sets']}. Do {ex['reps']}. Go!"
    )


@tool(
    name="start_workout",
    description=(
        "Start a workout session. JARVIS coaches through exercises one by one. "
        "Use when user says 'start workout', 'let's workout', 'gym time', 'exercise time', etc. "
        "Optionally pass a custom plan, otherwise uses the default full-body routine."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "plan": {
                "type": "array",
                "description": "Optional custom plan. Array of exercises with name, sets, reps, rest_sec.",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "sets": {"type": "integer"},
                        "reps": {"type": "string"},
                        "rest_sec": {"type": "integer"},
                    },
                },
            },
        },
        "required": [],
    },
)
async def start_workout_tool(input_data: dict[str, Any]) -> str:
    if _session["active"]:
        ex = _current_exercise_info()
        if ex:
            return (
                f"Workout already in progress, sir! Currently on {ex['name']}, "
                f"set {_session['current_set'] + 1} of {ex['sets']}. Say 'done' to continue."
            )

    _reset_session()
    _session["active"] = True
    _session["plan"] = input_data.get("plan") or [dict(e) for e in DEFAULT_PLAN]
    _session["started_at"] = datetime.now().isoformat()
    _session["current_set"] = 1

    ex = _current_exercise_info()
    total = _total_sets()
    plan_summary = ", ".join(e["name"] for e in _session["plan"])

    return (
        f"Workout started, sir! {len(_session['plan'])} exercises, {total} total sets. "
        f"Plan: {plan_summary}. "
        f"Let's begin! {_format_exercise_announcement(ex, 1)} "
        f"Say 'done' when you finish a set."
    )


@tool(
    name="workout_done_set",
    description=(
        "Mark current set as done and get next instruction. "
        "Use when user says 'done', 'finished', 'next', 'completed', 'next set' during workout."
    ),
    input_schema={"type": "object", "properties": {}, "required": []},
)
async def workout_done_set_tool(input_data: dict[str, Any]) -> str:
    if not _session["active"]:
        return "No workout in progress, sir. Say 'start workout' to begin."

    ex = _current_exercise_info()
    if not ex:
        return "Workout already completed!"

    _session["total_sets_done"] += 1
    current_set = _session["current_set"]

    if current_set < ex["sets"]:
        # More sets of same exercise
        _session["current_set"] = current_set + 1
        rest = ex["rest_sec"]
        return (
            f"Set {current_set} of {ex['name']} done! Nice work. "
            f"Rest {rest} seconds, then set {current_set + 1} of {ex['sets']}. "
            f"{ex['reps']}. Say 'done' when finished."
        )
    else:
        # Exercise complete, move to next
        _session["completed_exercises"] += 1
        _session["current_exercise"] += 1
        _session["current_set"] = 1

        next_ex = _current_exercise_info()
        if next_ex:
            rest = ex["rest_sec"]
            return (
                f"{ex['name']} complete! {_session['completed_exercises']} of "
                f"{len(_session['plan'])} exercises done. "
                f"Rest {rest} seconds. "
                f"Next up: {_format_exercise_announcement(next_ex, 1)} "
                f"Say 'done' when finished."
            )
        else:
            # All exercises done!
            elapsed = ""
            if _session["started_at"]:
                start = datetime.fromisoformat(_session["started_at"])
                mins = int((datetime.now() - start).total_seconds() / 60)
                elapsed = f" Total time: {mins} minutes."

            result = (
                f"Workout complete, sir! All {len(_session['plan'])} exercises, "
                f"{_session['total_sets_done']} total sets finished.{elapsed} "
                f"Great job getting back in the game! Rest well today."
            )
            _reset_session()
            return result


@tool(
    name="workout_status",
    description=(
        "Show current workout progress. "
        "Use when user asks 'where am I', 'what's left', 'how many sets left', 'workout status'."
    ),
    input_schema={"type": "object", "properties": {}, "required": []},
)
async def workout_status_tool(input_data: dict[str, Any]) -> str:
    if not _session["active"]:
        return "No workout in progress. Say 'start workout' to begin."

    ex = _current_exercise_info()
    total = _total_sets()
    remaining = total - _session["total_sets_done"]

    elapsed = ""
    if _session["started_at"]:
        start = datetime.fromisoformat(_session["started_at"])
        mins = int((datetime.now() - start).total_seconds() / 60)
        elapsed = f" You've been at it for {mins} minutes."

    lines = []
    for i, e in enumerate(_session["plan"]):
        if i < _session["current_exercise"]:
            lines.append(f"  DONE - {e['name']}")
        elif i == _session["current_exercise"]:
            lines.append(f"  NOW  - {e['name']} (set {_session['current_set']} of {e['sets']})")
        else:
            lines.append(f"  NEXT - {e['name']} ({e['sets']} sets)")

    status = "\n".join(lines)
    return (
        f"Workout progress: {_session['total_sets_done']}/{total} sets done, "
        f"{remaining} remaining.{elapsed}\n{status}"
    )


@tool(
    name="workout_skip",
    description=(
        "Skip current exercise and move to the next one. "
        "Use when user says 'skip', 'skip this', 'next exercise'."
    ),
    input_schema={"type": "object", "properties": {}, "required": []},
)
async def workout_skip_tool(input_data: dict[str, Any]) -> str:
    if not _session["active"]:
        return "No workout in progress."

    ex = _current_exercise_info()
    if not ex:
        return "No more exercises to skip."

    skipped = ex["name"]
    _session["current_exercise"] += 1
    _session["current_set"] = 1

    next_ex = _current_exercise_info()
    if next_ex:
        return (
            f"Skipped {skipped}. "
            f"Next: {_format_exercise_announcement(next_ex, 1)}"
        )
    else:
        _reset_session()
        return f"Skipped {skipped}. That was the last exercise. Workout ended."


@tool(
    name="workout_stop",
    description=(
        "Stop/end the workout early. "
        "Use when user says 'stop workout', 'end workout', 'I'm done', 'that's enough'."
    ),
    input_schema={"type": "object", "properties": {}, "required": []},
)
async def workout_stop_tool(input_data: dict[str, Any]) -> str:
    if not _session["active"]:
        return "No workout in progress."

    total = _total_sets()
    done = _session["total_sets_done"]

    elapsed = ""
    if _session["started_at"]:
        start = datetime.fromisoformat(_session["started_at"])
        mins = int((datetime.now() - start).total_seconds() / 60)
        elapsed = f" Duration: {mins} minutes."

    result = (
        f"Workout stopped. You completed {done} of {total} sets.{elapsed} "
        f"Good effort, sir. Even a partial workout beats no workout."
    )
    _reset_session()
    return result
