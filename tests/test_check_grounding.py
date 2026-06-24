import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import check_grounding as cg


class TestIsTarget(unittest.TestCase):
    def test_plans_md_is_target(self):
        self.assertTrue(cg.is_target("/x/docs/superpowers/plans/2026-06-24-foo.md"))

    def test_specs_md_is_target(self):
        self.assertTrue(cg.is_target("/x/docs/superpowers/specs/foo.md"))

    def test_other_md_is_not_target(self):
        self.assertFalse(cg.is_target("/x/README.md"))

    def test_non_md_is_not_target(self):
        self.assertFalse(cg.is_target("/x/plans/foo.py"))

    def test_empty_is_not_target(self):
        self.assertFalse(cg.is_target(""))


class TestExtractSection(unittest.TestCase):
    def test_no_section_returns_none(self):
        self.assertIsNone(cg.extract_assumptions_section("# Plan\n본문\n"))

    def test_extracts_until_next_header(self):
        text = "# Plan\n## 주춧돌 가정\n- \"a\"\n    근거: 미검증\n## 다음\n뒷부분\n"
        section = cg.extract_assumptions_section(text)
        self.assertIn("근거: 미검증", section)
        self.assertNotIn("뒷부분", section)

    def test_bracket_header_variant(self):
        text = "## [주춧돌 가정]\n- \"a\"\n    근거: 미검증\n"
        self.assertIsNotNone(cg.extract_assumptions_section(text))


class TestFindUnverified(unittest.TestCase):
    def test_verified_only_is_empty(self):
        section = '- "a"\n    근거: src/x.py:1 확인 ✓\n'
        self.assertEqual(cg.find_unverified(section), [])

    def test_unverified_is_flagged(self):
        section = '- "a"\n    근거: 미검증\n'
        self.assertEqual(len(cg.find_unverified(section)), 1)

    def test_intentional_is_exempt(self):
        section = '- "a"\n    근거: 미검증(의도적)\n'
        self.assertEqual(cg.find_unverified(section), [])


class TestCheckFile(unittest.TestCase):
    def _write(self, text):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "plans", "p.md")
        os.makedirs(os.path.dirname(p))
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return p

    def test_unverified_blocks(self):
        p = self._write("## 주춧돌 가정\n- \"a\"\n    근거: 미검증\n")
        ok, msg = cg.check_file(p)
        self.assertFalse(ok)
        self.assertIn("미검증", msg)

    def test_verified_passes(self):
        p = self._write("## 주춧돌 가정\n- \"a\"\n    근거: 확인 ✓\n")
        ok, _ = cg.check_file(p)
        self.assertTrue(ok)

    def test_no_section_passes(self):
        p = self._write("# Plan\n본문만 있음\n")
        ok, _ = cg.check_file(p)
        self.assertTrue(ok)

    def test_non_target_passes(self):
        ok, _ = cg.check_file("/x/README.md")
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
