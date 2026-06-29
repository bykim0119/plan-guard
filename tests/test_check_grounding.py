import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import check_grounding as cg  # noqa: E402


def section(scope="- 만들 것: X [확인]",
            corner="- DB = Qdrant [검증: 문서 확인]",
            assume="- A 가정 [검증: src:1 확인]",
            success="- 30-case ≥ 90% [확인]"):
    return (
        "## 설계 결정\n\n"
        f"### 범위\n{scope}\n\n"
        f"### 주춧돌 결정\n{corner}\n\n"
        f"### 핵심 가정·의존\n{assume}\n\n"
        f"### 성공·검증 기준\n{success}\n\n"
        "## 다음 섹션\n본문\n"
    )


class TestIsTarget(unittest.TestCase):
    def test_specs_md_is_target(self):
        self.assertTrue(cg.is_target("/x/docs/superpowers/specs/a.md"))

    def test_plans_md_not_target(self):
        self.assertFalse(cg.is_target("/x/docs/superpowers/plans/a.md"))

    def test_other_not_target(self):
        self.assertFalse(cg.is_target("/x/src/a.py"))


class TestSectionPresence(unittest.TestCase):
    def test_no_design_section_blocks(self):
        ok, msg = cg.check_text("## 개요\n본문\n")
        self.assertFalse(ok)
        self.assertIn("설계 결정", msg)

    def test_full_valid_passes(self):
        ok, msg = cg.check_text(section())
        self.assertTrue(ok, msg)


class TestBoxes(unittest.TestCase):
    def test_missing_box_blocks(self):
        text = section().replace("### 성공·검증 기준\n- 30-case ≥ 90% [확인]\n\n", "")
        ok, msg = cg.check_text(text)
        self.assertFalse(ok)
        self.assertIn("성공", msg)

    def test_empty_box_blocks(self):
        ok, msg = cg.check_text(section(scope=""))
        self.assertFalse(ok)
        self.assertIn("범위", msg)

    def test_na_with_reason_passes(self):
        ok, msg = cg.check_text(section(success="N/A: 순수 리팩토링이라 새 기준 없음"))
        self.assertTrue(ok, msg)

    def test_na_without_reason_blocks(self):
        ok, msg = cg.check_text(section(success="N/A:"))
        self.assertFalse(ok)


class TestTags(unittest.TestCase):
    def test_decision_without_tag_blocks(self):
        ok, msg = cg.check_text(section(scope="- 만들 것: X"))
        self.assertFalse(ok)

    def test_verify_without_reason_blocks(self):
        ok, msg = cg.check_text(section(corner="- DB = Qdrant [검증:]"))
        self.assertFalse(ok)

    def test_undecided_without_reason_blocks(self):
        ok, msg = cg.check_text(section(scope="- 만들 것: X [미정:]"))
        self.assertFalse(ok)

    def test_confirm_without_reason_passes(self):
        ok, msg = cg.check_text(section(scope="- 만들 것: X [확인]"))
        self.assertTrue(ok, msg)

    def test_colon_inside_reason_ok(self):
        ok, msg = cg.check_text(section(corner="- 비율 [검증: 80:20 측정]"))
        self.assertTrue(ok, msg)

    def test_subbullet_tag_ok(self):
        corner = "- DB = Qdrant\n    - 하이브리드 되나 [검증: 문서 확인]"
        ok, msg = cg.check_text(section(corner=corner))
        self.assertTrue(ok, msg)

    def test_prose_line_ignored(self):
        ok, msg = cg.check_text(section(scope="설명 문장입니다.\n- 만들 것: X [확인]"))
        self.assertTrue(ok, msg)


if __name__ == "__main__":
    unittest.main()
