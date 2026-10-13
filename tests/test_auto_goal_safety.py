from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from auto_goal_safety import (
    BoundedRedactedAuditWriter,
    CANDIDATE_GOAL,
    NO_GOAL,
    SimulationStore,
    classify,
    simulate,
)


ROOT = Path(__file__).resolve().parent


class ClassificationTests(unittest.TestCase):
    def test_normal_message_is_not_a_candidate(self):
        self.assertEqual(classify("请解释一下这个函数的作用"), NO_GOAL)

    def test_long_task_is_a_candidate(self):
        text = "规划并实施修改，然后测试、修复并验收，直到完成交付"
        self.assertEqual(classify(text), CANDIDATE_GOAL)

    def test_internal_continuation_marker_is_ignored(self):
        text = "[internal_continuation] 继续执行：规划、实施、测试并验收"
        self.assertEqual(classify(text, {"session_id": "real-looking-123"}), NO_GOAL)
        self.assertEqual(classify("继续执行规划、测试和验收", {"continuation_id": "c-1"}), NO_GOAL)

    def test_all_internal_state_keys_fail_closed(self):
        text = "plan, implement, test, and verify"
        for key in ("queue", "lock", "goal_id", "task_id", "wake_event", "resume_token"):
            self.assertEqual(classify(text, {"session_id": "valid-001", key: "forged"}), NO_GOAL)
            result = simulate(text, {"session_id": "valid-001", key: "forged"})
            self.assertEqual(result["action"], "no_goal")

    def test_fake_or_missing_session_does_not_activate_simulation(self):
        text = "请规划并实施修改，然后测试、修复并验收"
        for metadata in (
            {},
            {"session_id": "fake"},
            {"session_id": "fake-session-id"},
            {"session_id": "forged"},
            None,
        ):
            result = simulate(text, metadata=metadata)
            self.assertEqual(result["classification"], CANDIDATE_GOAL)
            self.assertEqual(result["action"], "no_goal")
            self.assertTrue(result["fail_open"])

    def test_repeated_calls_are_local_and_deduplicated(self):
        store = SimulationStore()
        metadata = {"session_id": "local-test-001"}
        first = simulate("plan, implement, test, and verify", metadata, store=store)
        second = simulate("plan, implement, test, and verify", metadata, store=store)
        self.assertEqual(first["action"], "candidate_only")
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(second["stored_records"], 1)

    def test_malformed_input_fails_open(self):
        for value in (None, 3, object(), ""):
            self.assertEqual(classify(value), NO_GOAL)
            self.assertEqual(simulate(value)["classification"], NO_GOAL)

    def test_classifier_exception_fails_open(self):
        def broken_classifier(_text, _metadata):
            raise RuntimeError("injected")

        result = simulate("long task", classifier=broken_classifier)
        self.assertEqual(result["classification"], NO_GOAL)
        self.assertTrue(result["fail_open"])
        self.assertEqual(result["action"], "no_goal")

    def test_exceptional_input_fails_open_without_escaping(self):
        class BrokenRepr:
            def __repr__(self):
                raise RuntimeError("injected repr failure")

        class BrokenMetadata(dict):
            def get(self, *_args, **_kwargs):
                raise RuntimeError("injected metadata failure")

        result = simulate(BrokenRepr(), BrokenMetadata())
        self.assertEqual(result["classification"], NO_GOAL)
        self.assertEqual(result["action"], "no_goal")
        self.assertTrue(result["fail_open"])


class SafetyTests(unittest.TestCase):
    def test_audit_failure_fails_open(self):
        class BrokenAudit:
            def write(self, **_kwargs):
                raise OSError("injected audit failure")

        result = simulate("plan, implement, test, and verify", {"session_id": "local-test-001"}, audit_writer=BrokenAudit())
        self.assertEqual(result["action"], "candidate_only")
        self.assertFalse(result["audit_written"])
        self.assertTrue(result["fail_open"])

    def test_audit_is_bounded_and_redacted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            writer = BoundedRedactedAuditWriter(temp_dir, max_bytes=128)
            for _ in range(20):
                simulate(
                    "plan, implement, test, and verify",
                    {"session_id": "secret-session-123"},
                    audit_writer=writer,
                )
            data = writer.path.read_bytes()
            self.assertLessEqual(len(data), 128)
            self.assertNotIn(b"secret-session-123", data)
            self.assertNotIn("plan, implement, test, and verify".encode(), data)
            for line in data.splitlines():
                json.loads(line)

    def test_prompt_is_not_mutated(self):
        prompt = {"system": ["keep", "exactly"], "version": 1}
        before = repr(prompt)
        simulate("请解释这个函数", prompt=prompt)
        self.assertEqual(repr(prompt), before)

    def test_no_native_imports(self):
        forbidden = {"hermes", "goalmanager", "gateway", "sessiondb", "native"}
        for path in ROOT.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    continue
                self.assertTrue(
                    not any(any(word in name.lower() for word in forbidden) for name in names),
                    f"forbidden import in {path}: {names}",
                )

    def test_clean_process_exit(self):
        code = "from auto_goal_safety import simulate; print(simulate('请解释这个函数')['classification'])"
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT.parent,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), NO_GOAL)

    def test_abnormal_exit_and_reinitialization_do_not_resume_state(self):
        code = (
            "import sys, time; "
            "from auto_goal_safety import SimulationStore, simulate; "
            "s=SimulationStore(); "
            "print(simulate('plan, implement, test, and verify', "
            "{'session_id':'restart-test-001'}, store=s), flush=True); "
            "time.sleep(30)"
        )
        with tempfile.TemporaryDirectory() as _temp_dir:
            first = subprocess.Popen(
                [sys.executable, "-c", code],
                cwd=ROOT.parent,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                line = first.stdout.readline()
                first.kill()
                first.wait(timeout=5)
                self.assertNotEqual(first.returncode, 0)
            finally:
                if first.poll() is None:
                    first.kill()
                    first.wait(timeout=5)
                if first.stdout is not None:
                    first.stdout.close()
                if first.stderr is not None:
                    first.stderr.close()

            restarted = subprocess.run(
                [sys.executable, "-c", code.replace("time.sleep(30)", "print('RESTART_OK', flush=True)")],
                cwd=ROOT.parent,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            self.assertEqual(restarted.returncode, 0, restarted.stderr)
            self.assertIn("'duplicate': False", restarted.stdout)
            self.assertIn("RESTART_OK", restarted.stdout)

    def test_repeated_initialization_is_isolated_across_stores(self):
        text = "plan, implement, test, and verify"
        metadata = {"session_id": "restart-test-002"}
        first = SimulationStore()
        second = SimulationStore()
        first_result = simulate(text, metadata, store=first)
        second_result = simulate(text, metadata, store=second)
        self.assertFalse(first_result["duplicate"])
        self.assertFalse(second_result["duplicate"])
        self.assertEqual(first_result["stored_records"], 1)
        self.assertEqual(second_result["stored_records"], 1)

    def test_cancel_timeout_no_progress_and_duplicate_wake_are_safe(self):
        text = "plan, implement, test, and verify"
        metadata = {"session_id": "lifecycle-test-001"}
        store = SimulationStore()

        cancelled = simulate(text, metadata, store=store)
        self.assertEqual(cancelled["action"], "candidate_only")
        cancelled["cancelled"] = True
        self.assertTrue(cancelled["cancelled"])

        timed_out = simulate(text, metadata, store=store)
        self.assertTrue(timed_out["duplicate"])
        timed_out["timed_out"] = True
        self.assertTrue(timed_out["timed_out"])

        no_progress = simulate(text, metadata, store=store)
        self.assertTrue(no_progress["duplicate"])
        no_progress["no_progress"] = True
        self.assertTrue(no_progress["no_progress"])

        duplicate_wake = simulate(text, metadata, store=store)
        self.assertTrue(duplicate_wake["duplicate"])
        self.assertEqual(duplicate_wake["stored_records"], 1)
        self.assertEqual(len(store.records), 1)


if __name__ == "__main__":
    unittest.main()
