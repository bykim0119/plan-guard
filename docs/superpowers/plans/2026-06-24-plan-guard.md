# plan-guard 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 계획의 검증 안 된 "주춧돌 가정"을 문서 저장 시점에 막고, 계획의 구조를 Mermaid 지도로 그려 브라우저로 보는 Claude Code 플러그인(계획 검증 기능 + 구조도)을 만든다.

**Architecture:** 두 겹 방어 — (1) 예방: 계획을 쓸 때 "주춧돌 가정 + 근거"를 명시하게 하는 스킬, (2) 검문: 문서 저장(Write/Edit) 직후 PostToolUse 훅이 파이썬 스크립트로 `미검증` 주춧돌을 찾아 차단. 구조도는 계획 문서 안 Mermaid 코드블록(정본)을 슬래시 명령이 추출해 HTML로 감싸 `explorer.exe`로 브라우저에 띄운다.

**Tech Stack:** Python 3 표준 라이브러리만(외부 의존성 0), Claude Code 플러그인(plugin.json / hooks / skills / commands), Mermaid.js(CDN, 브라우저 렌더), WSL `explorer.exe` 연동.

## Global Constraints

- **언어/의존성:** Python 3, 표준 라이브러리만. 외부 패키지 설치 금지(어디서나 바로 실행되게).
- **테스트 프레임워크:** `unittest`(표준 라이브러리). 실행은 `python3 -m unittest discover -s tests -v` (작업 디렉토리는 `plan-guard/`).
- **커밋하지 않음:** 사용자 요청에 따라 git 커밋을 하지 않는다. 표준 TDD의 "commit" 단계는 **"동작 확인(verify)" 단계로 대체**한다. 로컬 파일 작업만.
- **작업 루트:** 모든 경로는 `/mnt/e/ipynbs_port/harness/plan-guard/` 기준.
- **주춧돌 섹션 형식 규약(machine-readable, 모든 task가 따름):**
  ```
  ## 주춧돌 가정
  - "<가정 내용>"
      근거: <확인 방법> ✓          ← 검증됨, 통과
  - "<가정 내용>"
      근거: 미검증                  ← 차단 대상
  - "<가정 내용>"
      근거: 미검증(의도적)          ← 탈출구, 통과
  ```
  - 헤더 인식: 줄 시작의 `#`(1개 이상) + `주춧돌 가정` (대괄호 `[]`는 선택).
  - 차단 판정: 주춧돌 섹션 안의 한 줄에 `근거:`와 `미검증`이 둘 다 있고 `의도적`이 없으면 → 차단.
  - 섹션 자체가 없으면 → **통과**(섹션 생성은 예방 스킬이 담당, 검문은 과잉 차단하지 않음).
- **검문 대상 파일:** 경로에 `/specs/` 또는 `/plans/`가 포함된 `.md` 파일만. 그 외는 통과.

---

## File Structure

```
plan-guard/
├─ .claude-plugin/
│  └─ plugin.json              # 플러그인 매니페스트 (Task 1)
├─ hooks/
│  └─ hooks.json               # PostToolUse 훅 등록 (Task 3)
├─ scripts/
│  ├─ check_grounding.py       # 검문 스크립트: 미검증 주춧돌 차단 (Task 2)
│  └─ render_map.py            # 지도 렌더: Mermaid → HTML → 브라우저 (Task 5)
├─ skills/
│  └─ grounding-plans/
│     └─ SKILL.md              # 예방 규율: 주춧돌+근거 명시 (Task 4)
├─ commands/
│  └─ map.md                   # /지도 슬래시 명령 (Task 6)
└─ tests/
   ├─ test_check_grounding.py  # Task 2
   └─ test_render_map.py       # Task 5
```

각 파일은 한 가지 책임만 진다. 스크립트(검문·렌더)는 순수 함수로 분리해 단위 테스트하고, 매니페스트·훅·스킬·명령은 얇은 연결만 담당한다.

---

## Task 1: 플러그인 뼈대 + 매니페스트

**Files:**
- Create: `.claude-plugin/plugin.json`

**Interfaces:**
- Consumes: 없음
- Produces: 플러그인 루트 식별(`plugin.json`). 이후 모든 task가 이 플러그인 안에 파일을 추가한다.

- [ ] **Step 1: 매니페스트 작성**

`.claude-plugin/plugin.json`:

```json
{
  "name": "plan-guard",
  "version": "0.1.0",
  "description": "계획의 검증 안 된 주춧돌 가정을 막고, 계획 구조를 Mermaid 지도로 보여주는 플러그인",
  "author": { "name": "bykim0119" }
}
```

- [ ] **Step 2: 동작 확인(verify)**

Run: `python3 -c "import json; json.load(open('.claude-plugin/plugin.json')); print('valid')"`
Expected: `valid` 출력 (유효한 JSON).

---

## Task 2: 검문 스크립트 `check_grounding.py` (TDD 핵심)

**Files:**
- Create: `scripts/check_grounding.py`
- Test: `tests/test_check_grounding.py`

**Interfaces:**
- Consumes: 없음(표준 라이브러리만).
- Produces:
  - `is_target(path: str) -> bool`
  - `extract_assumptions_section(text: str) -> str | None`
  - `find_unverified(section: str) -> list[str]`  (차단 사유가 되는 `근거:` 줄들)
  - `check_file(path: str) -> tuple[bool, str]`  (ok, 메시지)
  - `main()` — stdin의 PostToolUse JSON을 읽어 차단 시 exit code 2 + stderr 메시지.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_check_grounding.py`:

```python
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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python3 -m unittest discover -s tests -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'check_grounding'` (스크립트 미작성).

- [ ] **Step 3: 스크립트 구현**

`scripts/check_grounding.py`:

```python
#!/usr/bin/env python3
"""계획/설계 문서에 검증 안 된 '주춧돌 가정'이 있으면 차단하는 검문 스크립트.

PostToolUse(Write|Edit) 훅으로 호출된다. stdin으로 받은 JSON에서 저장된
파일 경로를 꺼내, 그 파일이 검문 대상(specs/ · plans/ 하위 .md)이면
'주춧돌 가정' 섹션을 파싱해 `미검증`(의도적 아님) 항목을 찾는다.
하나라도 있으면 exit code 2 + stderr 메시지로 Claude에게 돌려보낸다.
"""
import json
import os
import re
import sys

TARGET = re.compile(r"/(specs|plans)/[^/]*\.md$")
HEADER = re.compile(r"^#+\s*\[?\s*주춧돌\s*가정\s*\]?", re.MULTILINE)
NEXT_HEADER = re.compile(r"^#+\s", re.MULTILINE)


def is_target(path):
    return bool(path) and bool(TARGET.search(path))


def extract_assumptions_section(text):
    """'주춧돌 가정' 헤더부터 다음 헤더 직전까지를 반환. 없으면 None."""
    m = HEADER.search(text)
    if not m:
        return None
    start = m.end()
    nxt = NEXT_HEADER.search(text, start)
    end = nxt.start() if nxt else len(text)
    return text[start:end]


def find_unverified(section):
    """차단 사유가 되는 '근거:' 줄 목록. '미검증' 있고 '의도적' 없으면 차단."""
    bad = []
    for line in section.splitlines():
        if "근거:" in line and "미검증" in line and "의도적" not in line:
            bad.append(line.strip())
    return bad


def check_file(path):
    """(ok, message) 반환. ok=False면 차단."""
    if not is_target(path):
        return True, ""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return True, ""  # 못 읽으면 통과(차단으로 작업을 망치지 않음)
    section = extract_assumptions_section(text)
    if section is None:
        return True, ""  # 섹션 없으면 통과(예방 스킬이 담당)
    bad = find_unverified(section)
    if bad:
        joined = "\n".join("  - " + b for b in bad)
        msg = (
            "plan-guard: 검증 안 된 주춧돌 가정이 있어 저장을 막았습니다.\n"
            "아래 가정을 실제로 확인(파일 읽기·명령 실행·문서 확인)하고 "
            "근거를 채운 뒤 다시 저장하세요. 일부러 둔 가정이면 "
            "'미검증(의도적)'으로 표시하면 통과합니다.\n" + joined
        )
        return False, msg
    return True, ""


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        sys.exit(0)  # 입력을 못 읽으면 통과
    tool_input = data.get("tool_input") or {}
    path = tool_input.get("file_path") or ""
    ok, msg = check_file(path)
    if not ok:
        print(msg, file=sys.stderr)
        sys.exit(2)  # PostToolUse: exit 2 → 메시지를 Claude에게 피드백
    sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS (모든 테스트 OK).

- [ ] **Step 5: 동작 확인(verify) — end-to-end 파이프 테스트**

Run:
```bash
printf '## 주춧돌 가정\n- "x"\n    근거: 미검증\n' > /tmp/plans_p.md
mkdir -p /tmp/plans && mv /tmp/plans_p.md /tmp/plans/p.md
echo "{\"tool_input\":{\"file_path\":\"/tmp/plans/p.md\"}}" | python3 scripts/check_grounding.py; echo "exit=$?"
```
Expected: stderr에 "검증 안 된 주춧돌 가정" 메시지, `exit=2`.

---

## Task 3: 훅 등록 `hooks.json`

**Files:**
- Create: `hooks/hooks.json`

**Interfaces:**
- Consumes: `scripts/check_grounding.py` (Task 2)
- Produces: PostToolUse(Write|Edit) 시점에 검문 스크립트를 실행하는 훅 설정.

- [ ] **Step 1: 훅 설정 작성**

`hooks/hooks.json` (`${CLAUDE_PLUGIN_ROOT}`는 Claude Code가 플러그인 루트로 치환):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/check_grounding.py\"",
            "statusMessage": "주춧돌 가정 검증 중..."
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 2: 동작 확인(verify) — 구조 검증**

Run:
```bash
python3 -c "import json; json.load(open('hooks/hooks.json')); print('valid json')"
jq -e '.hooks.PostToolUse[] | select(.matcher==\"Write|Edit\") | .hooks[] | select(.type==\"command\")' hooks/hooks.json >/dev/null && echo "hook ok"
```
Expected: `valid json` 그리고 `hook ok`.

---

## Task 4: 예방 스킬 `grounding-plans/SKILL.md`

**Files:**
- Create: `skills/grounding-plans/SKILL.md`

**Interfaces:**
- Consumes: Global Constraints의 주춧돌 섹션 형식 규약.
- Produces: 계획 작성 시 Claude가 따르는 규율 문서. 검문 훅(Task 2)이 기대하는 바로 그 형식으로 주춧돌 섹션을 만들게 한다.

- [ ] **Step 1: 스킬 문서 작성**

`skills/grounding-plans/SKILL.md`:

```markdown
---
name: grounding-plans
description: Use when writing a spec or implementation plan, before finalizing it — forces load-bearing assumptions to be made explicit with evidence so plans aren't built on unverified guesses.
---

# 계획의 주춧돌 가정을 근거로 받쳐라

계획이 통째로 기대는 **주춧돌 가정**(이게 틀리면 계획 전체가 폐기되는 전제)을
추측으로 깔지 마라. 계획/설계 문서를 마무리하기 전에 다음을 한다.

## 1. 주춧돌 가정을 따로 짚는다

문서에 `## 주춧돌 가정` 섹션을 만들고, 계획 전체가 의존하는 가정을 나열한다.
"이 루트로 가면 이걸 쓸 수 있을 것이다" 류의 전제가 바로 주춧돌이다.

## 2. 각 가정에 근거를 붙인다

가정마다 바로 아래 줄에 `근거:`를 적는다. 근거는 **실제로 확인한 것**이어야
한다 — 읽은 파일과 줄 번호, 실행한 명령과 결과, 찾은 문서.

확인하지 않았으면 솔직히 `미검증`이라고 적는다. 숨기지 마라.

## 3. 형식 (검문 훅이 읽는 규약)

​```
## 주춧돌 가정
- "auth 모듈이 토큰 갱신을 자체 처리한다"
    근거: src/auth/token.ts:42 직접 확인 ✓
- "X 라이브러리가 스트리밍을 지원한다"
    근거: 미검증
- "사용자는 한국어 UI만 쓴다"
    근거: 미검증(의도적)
​```

- `근거:` 줄에 `미검증`이 있고 `의도적`이 없으면 → 저장 시 **차단**된다.
- 일부러 둔 가정이면 `미검증(의도적)`으로 표시하면 통과한다.

## 4. 막히면

검문에 막히면 그 가정을 **실제로 확인**하고 근거를 채운 뒤 다시 저장한다.
확인이 불가능하거나 의도적 가정이면 `미검증(의도적)`으로 바꾼다.
```

- [ ] **Step 2: 동작 확인(verify) — frontmatter/형식 점검**

Run:
```bash
head -4 skills/grounding-plans/SKILL.md
grep -q "## 주춧돌 가정" skills/grounding-plans/SKILL.md && echo "section rule present"
```
Expected: frontmatter(`name:`, `description:`)가 보이고 `section rule present` 출력.

---

## Task 5: 지도 렌더 스크립트 `render_map.py` (TDD)

**Files:**
- Create: `scripts/render_map.py`
- Test: `tests/test_render_map.py`

**Interfaces:**
- Consumes: 없음(표준 라이브러리만).
- Produces:
  - `extract_mermaid(text: str) -> list[str]`
  - `build_html(blocks: list[str], title: str = "구조도") -> str`
  - `main(argv)` — 인자로 받은 계획 문서에서 Mermaid를 뽑아 HTML 임시파일로 쓰고 `explorer.exe`로 연다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_render_map.py`:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import render_map as rm


class TestExtractMermaid(unittest.TestCase):
    def test_extracts_single_block(self):
        text = "글\n```mermaid\ngraph TD\n A-->B\n```\n끝\n"
        blocks = rm.extract_mermaid(text)
        self.assertEqual(len(blocks), 1)
        self.assertIn("graph TD", blocks[0])

    def test_extracts_multiple_blocks(self):
        text = "```mermaid\nA\n```\n```mermaid\nB\n```\n"
        self.assertEqual(len(rm.extract_mermaid(text)), 2)

    def test_no_block_returns_empty(self):
        self.assertEqual(rm.extract_mermaid("그냥 글"), [])


class TestBuildHtml(unittest.TestCase):
    def test_html_contains_mermaid_div_and_cdn(self):
        html = rm.build_html(["graph TD\n A-->B"])
        self.assertIn('class="mermaid"', html)
        self.assertIn("graph TD", html)
        self.assertIn("mermaid", html.lower())
        self.assertIn("<!doctype html>", html.lower())

    def test_empty_blocks_still_valid_html(self):
        html = rm.build_html([])
        self.assertIn("<!doctype html>", html.lower())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python3 -m unittest discover -s tests -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'render_map'`.

- [ ] **Step 3: 스크립트 구현**

`scripts/render_map.py`:

```python
#!/usr/bin/env python3
"""계획 문서의 Mermaid 구조도를 HTML로 감싸 Windows 브라우저로 띄운다.

WSL 환경 전제: explorer.exe로 Windows 기본 브라우저를 연다.
HTML은 Mermaid.js CDN을 사용하므로 인터넷 연결이 필요하다.
"""
import html as html_mod
import os
import re
import subprocess
import sys
import tempfile

MERMAID = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)


def extract_mermaid(text):
    return [b.strip("\n") for b in MERMAID.findall(text)]


def build_html(blocks, title="구조도"):
    if blocks:
        divs = "\n".join(
            '<div class="mermaid">\n{}\n</div>'.format(html_mod.escape(b))
            for b in blocks
        )
    else:
        divs = "<p>이 문서에서 Mermaid 구조도를 찾지 못했습니다.</p>"
    return (
        "<!doctype html>\n<html lang=\"ko\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<title>{title}</title>\n"
        "<script src=\"https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js\"></script>\n"
        "<script>mermaid.initialize({{startOnLoad:true}});</script>\n"
        "<style>body{{font-family:sans-serif;padding:24px;}}</style>\n"
        "</head>\n<body>\n<h1>{title}</h1>\n{divs}\n</body>\n</html>\n"
    ).format(title=html_mod.escape(title), divs=divs)


def _to_windows_path(path):
    try:
        out = subprocess.run(
            ["wslpath", "-w", path], capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return path


def open_in_browser(html_path):
    subprocess.run(["explorer.exe", _to_windows_path(html_path)], check=False)


def main(argv):
    if len(argv) < 2:
        print("사용법: render_map.py <계획문서.md>", file=sys.stderr)
        return 1
    src = argv[1]
    with open(src, encoding="utf-8") as f:
        text = f.read()
    blocks = extract_mermaid(text)
    title = "구조도 — " + os.path.basename(src)
    html = build_html(blocks, title)
    fd, html_path = tempfile.mkstemp(suffix=".html", prefix="plan_guard_map_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(html)
    open_in_browser(html_path)
    print("열었습니다: {} (블록 {}개)".format(html_path, len(blocks)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS (Task 2 테스트 + Task 5 테스트 모두 OK).

- [ ] **Step 5: 동작 확인(verify) — 실제 렌더 + 브라우저**

Run: `python3 scripts/render_map.py docs/superpowers/plans/2026-06-24-plan-guard.md`
Expected: "열었습니다: ... (블록 N개)" 출력, Windows 브라우저에 이 계획 문서의 구조도가 렌더되어 뜸. (이 plan 문서엔 Mermaid 블록이 없으면 "찾지 못했습니다" 안내가 뜸 — 그 경우 Mermaid 블록이 있는 문서로 재확인.)

---

## Task 6: `/지도` 슬래시 명령

**Files:**
- Create: `commands/map.md`

**Interfaces:**
- Consumes: `scripts/render_map.py` (Task 5)
- Produces: 사용자가 `/plan-guard:map <문서경로>`로 부르면 그 문서의 구조도를 브라우저로 여는 명령.

- [ ] **Step 1: 명령 문서 작성**

`commands/map.md`:

```markdown
---
description: 계획 문서의 Mermaid 구조도를 Windows 브라우저에 렌더해서 연다
argument-hint: <계획문서.md 경로>
---

`$1`로 주어진 계획/설계 문서의 Mermaid 구조도를 브라우저로 띄운다.
경로가 비어 있으면 사용자에게 어떤 문서인지 물어본 뒤 실행한다.

다음을 실행하라:

​```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render_map.py" "$1"
​```

실행 결과("열었습니다: ... (블록 N개)")를 사용자에게 그대로 전한다.
블록이 0개면, 그 문서에 `​```mermaid` 코드블록이 있는지 확인하라고 안내한다.
```

- [ ] **Step 2: 동작 확인(verify)**

Run:
```bash
head -4 commands/map.md
grep -q "render_map.py" commands/map.md && echo "command wired"
```
Expected: frontmatter가 보이고 `command wired` 출력.

---

## Self-Review (작성자 체크 결과)

**1. Spec coverage** — 설계 문서 각 항목 대응:
- 5.1 예방(스킬) → Task 4 ✓
- 5.2 검문(훅, 가벼운 방식) → Task 2(스크립트) + Task 3(등록) ✓
- 5.3 탈출구(`미검증(의도적)`) → Task 2 `find_unverified` + Task 4 규율 ✓
- 6 구조도(Mermaid 정본, 색 강조) → 형식은 Task 4 규약 + Task 5 렌더. 단 **색 강조(검증=초록/미검증=빨강)는 Mermaid `classDef`로 계획 작성자가 칠하는 규약**으로, Task 4 스킬에 색 규약을 한 줄 더 넣는 것이 좋다(아래 보완).
- 6 `/지도` 브라우저 보기 → Task 5 + Task 6 ✓
- 6.1 환경 전제(explorer.exe, npx) → Task 5에서 explorer.exe 사용 ✓

**보완(인라인 반영 지시):** Task 4 SKILL.md의 형식 예시에, 미검증 주춧돌을 지도에서 빨갛게 칠하는 Mermaid 규약 한 줄을 추가한다 —
`classDef unverified fill:#f88;` 를 쓰고 미검증 노드에 `:::unverified`를 붙인다는 안내. (검문은 텍스트 `근거:` 줄로 판정하므로 색은 사람이 보기 위한 표시일 뿐, 차단 로직과 무관.)

**2. Placeholder scan** — "TBD/TODO/적절히 처리" 없음. 모든 코드 step에 완전한 코드 포함 ✓

**3. Type consistency** — 함수명 일관: `is_target`, `extract_assumptions_section`, `find_unverified`, `check_file`(check_grounding) / `extract_mermaid`, `build_html`, `open_in_browser`, `main`(render_map). 테스트가 부르는 이름과 구현 이름 일치 ✓

---

## 설치/등록 (구현 후 1회, 비-task 참고)

이 플러그인을 로컬에서 쓰려면 Claude Code에 로컬 플러그인으로 등록해야 한다(디렉토리 소스). 구현 완료 후 별도로 안내한다. 이번 계획의 task 범위에는 포함하지 않는다.
