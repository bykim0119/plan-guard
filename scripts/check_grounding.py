#!/usr/bin/env python3
"""설계 문서(specs/)의 「설계 결정」 4칸 체크리스트를 강제하는 검문 스크립트.

PostToolUse(Write|Edit) 훅. specs/ 하위 .md를 저장하면 「설계 결정」 섹션과
고정 4칸(범위/주춧돌 결정/핵심 가정·의존/성공·검증 기준)이 채워졌는지,
결정 줄에 유효한 꼬리표([확인]/[검증: 근거]/[미정: 이유])가 붙고 이유가
채워졌는지 검사한다. 위반이면 exit 2 + stderr로 Claude에게 피드백한다.
"""
import json
import re
import sys

TARGET = re.compile(r"/specs/[^/]*\.md$")
SECTION = re.compile(r"^##\s*설계\s*결정\b", re.MULTILINE)
H2 = re.compile(r"^##\s", re.MULTILINE)
HEADER = re.compile(r"^#{2,}\s", re.MULTILINE)

BOXES = [
    ("범위", re.compile(r"^#{3,}\s*범위", re.MULTILINE)),
    ("주춧돌 결정", re.compile(r"^#{3,}\s*주춧돌\s*결정", re.MULTILINE)),
    ("핵심 가정·의존", re.compile(r"^#{3,}\s*핵심\s*가정", re.MULTILINE)),
    ("성공·검증 기준", re.compile(r"^#{3,}\s*성공", re.MULTILINE)),
]

TAG = re.compile(r"\[(확인|검증|미정)(?::[ \t]*([^\]]*))?\]")
NA = re.compile(r"\bN/A\s*:\s*(\S)")


def is_target(path):
    return bool(path) and bool(TARGET.search(path))


def extract_section(text):
    """「설계 결정」 ## 헤더 다음부터 다음 ## 직전까지. 없으면 None."""
    m = SECTION.search(text)
    if not m:
        return None
    start = text.find("\n", m.end())
    start = start + 1 if start != -1 else len(text)
    nxt = H2.search(text, start)
    end = nxt.start() if nxt else len(text)
    return text[start:end]


def box_body(section, box_re):
    """섹션 안에서 한 칸의 본문(소제목 다음부터 다음 헤더 전까지). 없으면 None."""
    m = box_re.search(section)
    if not m:
        return None
    start = section.find("\n", m.end())
    start = start + 1 if start != -1 else len(section)
    nxt = HEADER.search(section, start)
    end = nxt.start() if nxt else len(section)
    return section[start:end]


def decision_blocks(body):
    """'- '로 시작하는 결정 항목을 그 하위 들여쓴 줄까지 묶어 반환."""
    blocks = []
    cur = None
    for ln in body.splitlines():
        if not ln.strip():
            continue
        if re.match(r"^-\s", ln):
            if cur is not None:
                blocks.append(cur)
            cur = ln
        elif cur is not None and (ln.startswith(" ") or ln.startswith("\t")):
            cur += "\n" + ln
        else:
            # 산문 줄: 열린 블록을 닫고 검사 대상에서 제외
            if cur is not None:
                blocks.append(cur)
                cur = None
    if cur is not None:
        blocks.append(cur)
    return blocks


def check_box(name, body):
    """한 칸의 위반 메시지 목록."""
    errors = []
    nonblank = [ln for ln in body.splitlines() if ln.strip()]
    if not nonblank:
        return [f"「{name}」 칸이 비었습니다. 채우거나 'N/A: 이유'로 명시하세요."]
    blocks = decision_blocks(body)
    # 칸 전체가 N/A 선언(결정 블록이 없을 때)
    if not blocks:
        if "N/A" in "\n".join(nonblank) and not NA.search("\n".join(nonblank)):
            errors.append(f"「{name}」의 N/A에 이유가 없습니다.")
        return errors
    for block in blocks:
        head = block.splitlines()[0].strip()
        if "N/A" in block:
            if not NA.search(block):
                errors.append(f"「{name}」의 N/A에 이유가 없습니다: {head}")
            continue
        m = TAG.search(block)
        if not m:
            errors.append(f"「{name}」의 결정에 꼬리표가 없습니다: {head}")
            continue
        kind, reason = m.group(1), (m.group(2) or "").strip()
        if kind in ("검증", "미정") and not reason:
            errors.append(f"「{name}」의 [{kind}]에 이유/근거가 없습니다: {head}")
    return errors


def check_section(section):
    """섹션 전체의 위반 메시지 목록."""
    errors = []
    for name, box_re in BOXES:
        body = box_body(section, box_re)
        if body is None:
            errors.append(f"「{name}」 칸이 없습니다. 소제목을 추가하세요.")
            continue
        errors.extend(check_box(name, body))
    return errors


def check_text(text):
    """(ok, message). 본문 문자열만 받는 순수 함수(테스트용)."""
    section = extract_section(text)
    if section is None:
        return False, (
            "plan-guard: 설계 문서에 「## 설계 결정」 섹션이 없어 저장을 막았습니다.\n"
            "범위/주춧돌 결정/핵심 가정·의존/성공·검증 기준 4칸을 갖추세요. "
            "4칸이 과한 가벼운 메모라면 specs/ 밖에 두세요."
        )
    errors = check_section(section)
    if errors:
        return False, (
            "plan-guard: 설계 결정 체크리스트 위반으로 저장을 막았습니다.\n"
            + "\n".join("  - " + e for e in errors)
        )
    return True, ""


def check_file(path):
    if not is_target(path):
        return True, ""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return True, ""
    return check_text(text)


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        sys.exit(0)
    path = (data.get("tool_input") or {}).get("file_path") or ""
    ok, msg = check_file(path)
    if not ok:
        print(msg, file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
