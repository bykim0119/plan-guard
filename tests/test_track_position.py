import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import track_position as tp


class TestNormalizeEvent(unittest.TestCase):
    def test_taskcreate_maps_to_create(self):
        data = {"tool_name": "TaskCreate",
                "tool_response": {"task": {"id": "1", "subject": "설계 검증"}}}
        ev = tp.normalize_event(data)
        self.assertEqual(ev, {"kind": "create", "id": "1", "subject": "설계 검증"})

    def test_taskupdate_maps_to_update(self):
        data = {"tool_name": "TaskUpdate",
                "tool_input": {"taskId": "1", "status": "completed"}}
        ev = tp.normalize_event(data)
        self.assertEqual(ev, {"kind": "update", "id": "1", "status": "completed"})

    def test_numeric_id_is_stringified(self):
        data = {"tool_name": "TaskUpdate",
                "tool_input": {"taskId": 7, "status": "in_progress"}}
        self.assertEqual(tp.normalize_event(data)["id"], "7")

    def test_other_tool_returns_none(self):
        self.assertIsNone(tp.normalize_event({"tool_name": "Write"}))

    def test_missing_id_returns_none(self):
        self.assertIsNone(tp.normalize_event(
            {"tool_name": "TaskCreate", "tool_response": {"task": {}}}))


class TestApplyEvent(unittest.TestCase):
    def _empty(self):
        return {"last_kind": None, "items": []}

    def test_create_appends_pending_item(self):
        np = tp.apply_event(self._empty(),
                            {"kind": "create", "id": "1", "subject": "A"})
        self.assertEqual(np["items"],
                         [{"id": "1", "subject": "A", "status": "pending"}])
        self.assertEqual(np["last_kind"], "create")

    def test_update_changes_status_by_id(self):
        np = {"last_kind": "create",
              "items": [{"id": "1", "subject": "A", "status": "pending"}]}
        np = tp.apply_event(np, {"kind": "update", "id": "1", "status": "completed"})
        self.assertEqual(np["items"][0]["status"], "completed")

    def test_create_after_update_resets_batch(self):
        np = {"last_kind": "update",
              "items": [{"id": "1", "subject": "old", "status": "completed"}]}
        np = tp.apply_event(np, {"kind": "create", "id": "9", "subject": "new"})
        self.assertEqual([it["id"] for it in np["items"]], ["9"])

    def test_consecutive_creates_accumulate(self):
        np = tp.apply_event(self._empty(),
                            {"kind": "create", "id": "1", "subject": "A"})
        np = tp.apply_event(np, {"kind": "create", "id": "2", "subject": "B"})
        self.assertEqual([it["id"] for it in np["items"]], ["1", "2"])

    def test_update_unknown_id_is_noop(self):
        np = {"last_kind": "create",
              "items": [{"id": "1", "subject": "A", "status": "pending"}]}
        np = tp.apply_event(np, {"kind": "update", "id": "X", "status": "completed"})
        self.assertEqual(np["items"][0]["status"], "pending")


class TestRenderTree(unittest.TestCase):
    def test_empty_is_blank(self):
        self.assertEqual(tp.render_tree({"items": []}), "")

    def test_marks_and_progress(self):
        np = {"items": [
            {"id": "1", "subject": "설계 검증", "status": "completed"},
            {"id": "2", "subject": "트리 스크립트", "status": "completed"},
            {"id": "3", "subject": "훅 등록", "status": "in_progress"},
            {"id": "4", "subject": "규율 스킬", "status": "pending"},
        ]}
        tree = tp.render_tree(np)
        self.assertIn("2/4", tree)
        self.assertIn("✓ 설계 검증", tree)
        self.assertIn("← 지금 여기: 훅 등록", tree)
        self.assertIn("○ 규율 스킬", tree)
        self.assertTrue(tree.rstrip().endswith("○ 규율 스킬"))
        self.assertIn("└─", tree)
        self.assertIn("├─", tree)


class TestLoadSaveRoundtrip(unittest.TestCase):
    def test_save_then_load(self):
        d = tempfile.mkdtemp()
        path = tp.notepad_path(d)
        np = {"last_kind": "create",
              "items": [{"id": "1", "subject": "한글", "status": "pending"}]}
        tp.save_notepad(path, np)
        self.assertEqual(tp.load_notepad(path), np)

    def test_load_missing_returns_empty(self):
        np = tp.load_notepad("/no/such/file.json")
        self.assertEqual(np, {"last_kind": None, "items": []})

    def test_notepad_path_uses_cwd(self):
        d = tempfile.mkdtemp()
        self.assertTrue(tp.notepad_path(d).startswith(d))


class TestConcurrentUpdates(unittest.TestCase):
    """병렬 훅 프로세스가 같은 메모장을 동시에 갱신해도 유실·깨짐이 없어야 한다."""

    SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts",
                          "track_position.py")

    def _payload(self, i):
        return json.dumps({
            "tool_name": "TaskCreate", "cwd": self.dir,
            "tool_response": {"task": {"id": str(i), "subject": "T%d" % i}},
        })

    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def test_parallel_creates_all_survive(self):
        import subprocess
        n = 25
        procs = [subprocess.Popen(
            [sys.executable, self.SCRIPT], stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(n)]
        # 먼저 전부 띄운 뒤 거의 동시에 입력을 흘려보내 동시성을 만든다
        for i, p in enumerate(procs):
            p.stdin.write(self._payload(i).encode("utf-8"))
            p.stdin.close()
        for p in procs:
            p.wait()
        path = tp.notepad_path(self.dir)
        notepad = tp.load_notepad(path)  # 깨진 JSON이면 빈 메모장을 돌려줌
        ids = sorted(int(it["id"]) for it in notepad["items"])
        self.assertEqual(ids, list(range(n)),
                         "동시 갱신에서 항목이 유실되거나 파일이 깨졌다")


if __name__ == "__main__":
    unittest.main()
