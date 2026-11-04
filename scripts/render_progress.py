"""Render an explicit task-state snapshot as a standalone progress interface."""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

STATUSES = {"running", "waiting_user", "blocked", "failed", "not_started", "completed"}
REVIEW_PHASES = {"prepare", "review", "human_review"}
LEGACY_PHASES = {"pre_pr", "in_pr", "post_pr"}
TEMPLATE = Path(__file__).resolve().parents[1] / "assets" / "progress.html"


def timestamp(value: str) -> None:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Times must include a timezone")


def validate(state: dict) -> None:
    for field in ("task_id", "project", "title", "scope", "current_action", "user_message", "updated_at", "source_commit"):
        if not isinstance(state.get(field), str) or not state[field].strip():
            raise ValueError(f"Missing nonempty text field: {field}")
    timestamp(state["updated_at"])
    if state.get("status") not in STATUSES:
        raise ValueError("Invalid task status")
    goal = state.get("goal", {})
    if goal.get("mode") not in {"review", "end_to_end", "scoped"} or not goal.get("description"):
        raise ValueError("Record the user's overall goal and its mode")
    if goal["mode"] == "scoped" and not goal.get("scope_confirmation"):
        raise ValueError("A narrowed scope requires an explicit user instruction")
    criteria = goal.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        raise ValueError("Provide the goal's completion criteria")
    for criterion in criteria:
        if criterion.get("status") not in {"passed", "pending", "not_applicable"} or not criterion.get("title") or not criterion.get("id"):
            raise ValueError("Invalid completion criterion")
        if criterion["status"] == "passed" and not criterion.get("evidence"):
            raise ValueError("Passed completion criteria require evidence")
        if criterion["status"] == "not_applicable" and not criterion.get("reason"):
            raise ValueError("Excluded criteria require a reason tied to the user's goal")
    if state["status"] == "completed" and any(item["status"] == "pending" for item in criteria):
        raise ValueError("Overall task cannot be completed while required stages remain pending")
    for field in ("user_actions", "phases", "results", "issues", "checks", "files", "history", "links"):
        if not isinstance(state.get(field), list):
            raise ValueError(f"Expected list: {field}")
    if bool(state["user_actions"]) != (state["status"] == "waiting_user"):
        raise ValueError("Required user actions belong only to waiting_user; use next_step for proposals")
    for action in state["user_actions"]:
        if action.get("kind") is not None and action["kind"] not in {"technical_replan", "final_review", "target_acceptance", "missing_information"}:
            raise ValueError("Action kind must distinguish technical_replan, final_review, target_acceptance or missing_information")
        if not all(isinstance(action.get(key), str) and action[key].strip() for key in ("question", "recommendation", "impact")):
            raise ValueError("User actions need question, recommendation and impact")
        if not any(isinstance(action.get(key), str) and action[key].strip() for key in ("instruction", "reply_hint")):
            raise ValueError("User actions need a concrete instruction or direct-reply hint")
    phase_ids = {item.get("id") for item in state["phases"]}
    if (phase_ids not in (REVIEW_PHASES, LEGACY_PHASES) or len(state["phases"]) != 3
            or state.get("phase") not in phase_ids):
        raise ValueError("Provide the three distinct phases and a matching active phase")
    for item in state["phases"]:
        if item.get("status") not in STATUSES:
            raise ValueError("Invalid phase status")
    if state["status"] in {"blocked", "failed"} and not any(item.get("blocking") for item in state["issues"]):
        raise ValueError("Blocked/failed tasks need an explicit blocking issue and owner")
    for issue in state["issues"]:
        if not all(isinstance(issue.get(key), str) and issue[key].strip() for key in ("title", "impact", "owner", "next_action")):
            raise ValueError("Issues need title, impact, owner and next_action")
        if not isinstance(issue.get("blocking"), bool):
            raise ValueError("Issue blocking must be a boolean")
    next_step = state.get("next_step", {})
    if next_step.get("kind") not in {"automatic", "proposal", "none"} or not next_step.get("text") or not next_step.get("owner"):
        raise ValueError("Next step needs owner, text and kind: automatic/proposal/none")
    if state["status"] == "completed" and next_step["kind"] == "automatic":
        raise ValueError("Completed snapshots must not claim background continuation")
    for check in state["checks"]:
        if check.get("status") not in {"passed", "failed", "not_run"}:
            raise ValueError("Check status must be passed/failed/not_run")
        if check.get("observed_at"):
            timestamp(check["observed_at"])

    def links(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"href", "evidence_href"}:
                    if not isinstance(item, str) or urlparse(item).scheme not in {"http", "https", "file"}:
                        raise ValueError("Evidence links must use http, https or file")
                else:
                    links(item)
        elif isinstance(value, list):
            for item in value:
                links(item)

    links(state)


def render(state: dict) -> str:
    validate(state)
    payload = json.dumps(state, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    template = TEMPLATE.read_text(encoding="utf-8")
    if template.count("__STATE_JSON__") != 1:
        raise ValueError("Progress template must contain one state marker")
    return template.replace("__STATE_JSON__", payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, epilog="Default renderer: review-html. Set presentation.renderer=native only when explicitly selected.")
    parser.add_argument("state", type=Path, help="JSON task state; see assets/progress.example.json")
    parser.add_argument("--output", required=True, type=Path, help="Stable HTML output path, reused for this task")
    args = parser.parse_args()
    if args.state.resolve() == args.output.resolve():
        parser.error("State input and HTML output must be different files")
    try:
        state = json.loads(args.state.read_text(encoding="utf-8-sig"))
        renderer = state.get("presentation", {}).get("renderer", "review-html")
        if renderer in {"review-html", "answer-me-with-html"}:
            from answer_progress import render_answer_progress
            validate(state)
            render_answer_progress(state, args.state, args.output)
        elif renderer == "native":
            page = render(state)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(page, encoding="utf-8")
        else:
            raise ValueError("Unknown progress renderer")
    except (ValueError, KeyError, TypeError, AttributeError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(2, f"Progress page was not rendered: {error}\n")
    print(f"Rendered {state['task_id']} [{state['status']}] -> {args.output.resolve()}")


if __name__ == "__main__":
    main()
