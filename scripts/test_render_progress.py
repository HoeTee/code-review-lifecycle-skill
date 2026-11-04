"""Check progress-state invariants that prevent misleading user actions."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from render_progress import render, validate
from answer_progress import build_draft


EXAMPLE = Path(__file__).resolve().parents[1] / "assets/progress.example.json"


class ProgressStateTests(unittest.TestCase):
    def setUp(self):
        self.state = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def test_completed_snapshot_preserves_unstarted_phases_and_evidence_time(self):
        self.state["checks"] = [{"title": "Earlier check", "status": "passed", "observed_at": "2025-12-31T08:00:00Z"}]
        original = deepcopy(self.state)
        page = render(self.state)
        self.assertEqual(self.state, original)
        payload = page.split('<script id="task-state" type="application/json">', 1)[1].split('</script>', 1)[0]
        restored = json.loads(payload)
        self.assertEqual(restored["phases"][1]["status"], "not_started")
        self.assertEqual(restored["checks"][0]["observed_at"], "2025-12-31T08:00:00Z")

    def test_waiting_requires_an_action_with_impact_and_reply(self):
        self.state["status"] = "waiting_user"
        with self.assertRaises(ValueError):
            validate(self.state)
        self.state["user_actions"] = [{"question": "Choose target", "recommendation": "Reuse current target", "impact": "Changes deployment scope", "instruction": "Reuse current target"}]
        validate(self.state)
        self.state["status"] = "completed"
        with self.assertRaises(ValueError):
            validate(self.state)

    def test_blocked_requires_a_concrete_owner_and_recovery_action(self):
        self.state["status"] = "blocked"
        with self.assertRaises(ValueError):
            validate(self.state)
        self.state["issues"] = [{"blocking": True, "title": "Runner unavailable", "owner": "Platform operator", "impact": "CI cannot start", "next_action": "Restore runner access"}]
        validate(self.state)

    def test_rejects_executable_links_and_escapes_embedded_script_terminator(self):
        self.state["links"] = [{"label": "bad", "href": "javascript:alert(1)"}]
        with self.assertRaises(ValueError):
            validate(self.state)
        self.state["links"] = []
        self.state["title"] = "</script><script>alert(1)</script>"
        page = render(self.state)
        self.assertNotIn(self.state["title"], page)
        self.assertIn("\\u003c/script\\u003e", page)

    def test_finished_snapshot_cannot_claim_automatic_background_continuation(self):
        self.state["next_step"]["kind"] = "automatic"
        with self.assertRaises(ValueError):
            validate(self.state)

    def test_end_to_end_goal_cannot_finish_after_only_local_checks(self):
        self.state["goal"]["mode"] = "end_to_end"
        self.state["goal"]["criteria"].append({"id": "pull_request", "title": "PR created", "status": "pending"})
        with self.assertRaisesRegex(ValueError, "required stages remain pending"):
            validate(self.state)
        self.state["status"] = "running"
        validate(self.state)

    def test_narrowed_goal_requires_user_scope_and_passed_criteria_need_evidence(self):
        del self.state["goal"]["scope_confirmation"]
        with self.assertRaisesRegex(ValueError, "explicit user instruction"):
            validate(self.state)
        self.state["goal"]["mode"] = "end_to_end"
        del self.state["goal"]["criteria"][0]["evidence"]
        with self.assertRaisesRegex(ValueError, "require evidence"):
            validate(self.state)

    def test_information_request_can_use_direct_reply_without_a_dummy_command(self):
        self.state["status"] = "waiting_user"
        self.state["user_actions"] = [{"question": "Where is the private dependency?", "recommendation": "Use its existing source", "impact": "CI cannot install it", "reply_hint": "Reply with the existing download instructions"}]
        validate(self.state)
        self.assertIn("existing download instructions", render(self.state))

    def test_delivery_text_evidence_renders_without_becoming_a_url(self):
        self.state["goal"]["criteria"] = [{"id": "delivery", "title": "Delivered", "status": "passed", "evidence": "Archive checksums verified in the recorded execution"}]
        validate(self.state)
        original = deepcopy(self.state)
        draft = build_draft(self.state, EXAMPLE)
        self.assertIn("Archive checksums verified", draft)
        self.assertNotIn("[打开交付包]", draft)
        self.assertEqual(self.state, original)

    def test_delivery_accepts_explicit_url_and_legacy_url_evidence(self):
        criterion = {"id": "delivery", "title": "Delivered", "status": "passed", "evidence": "Checksums verified", "evidence_href": "file:///C:/delivery/package.zip"}
        self.state["goal"]["criteria"] = [criterion]
        validate(self.state)
        self.assertIn("[打开交付包](file:///C:/delivery/package.zip)", build_draft(self.state, EXAMPLE))
        del criterion["evidence_href"]
        criterion["evidence"] = "https://example.com/package.zip"
        self.assertIn("[打开交付包](https://example.com/package.zip)", build_draft(self.state, EXAMPLE))
        criterion["evidence_href"] = "javascript:alert(1)"
        with self.assertRaises(ValueError):
            validate(self.state)

    def test_pr_table_separates_successful_checks_from_missing_human_and_merge(self):
        self.state["prs"] = [{"number": 7, "head": "1234567890", "ci_status": "success", "ai_status": "passed", "ai_completed_reviews": 2, "human_status": "pending", "merged": False}, {"number": 8, "head": "abcdef1234", "ci_status": "in_progress"}]
        original = deepcopy(self.state)
        draft = build_draft(self.state, EXAMPLE)
        self.assertIn("#7 | 12345678 | ok 通过 | ok 通过（2次） | warn 待处理 | warn 未合并", draft)
        self.assertIn("#8 | abcdef12 | warn 进行中 | warn 未记录 | warn 未记录 | warn 未记录", draft)
        self.assertEqual(self.state, original)

    def test_replan_and_final_review_have_different_visible_labels(self):
        self.state["status"] = "waiting_user"
        action = {"question": "Choose", "recommendation": "Concrete recommendation", "impact": "Explained impact", "reply_hint": "Reply here", "kind": "technical_replan"}
        self.state["user_actions"] = [action]
        validate(self.state)
        self.assertIn("当前关口：三轮后的方案决策", build_draft(self.state, EXAMPLE))
        action["kind"] = "final_review"
        self.assertIn("当前关口：合并前最终人工审核", build_draft(self.state, EXAMPLE))
        action["kind"] = "untyped_approval"
        with self.assertRaises(ValueError):
            validate(self.state)


if __name__ == "__main__":
    unittest.main()
