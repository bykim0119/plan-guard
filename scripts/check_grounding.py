#!/usr/bin/env python3
"""계획/설계 문서에 검증 안 된 '주춧돌 가정'이 있으면 차단하는 검문 스크립트.

PostToolUse(Write|Edit) 훅으로 호출된다. stdin으로 받은 JSON에서 저장된
파일 경로를 꺼내, 그 파일이 검문 대상(specs/ · plans/ 하위 .md)이면
'주춧돌 가정' 섹션을 파싱해 `미검증`(의도적 아님) 항목을 찾는다.
하나라도 있으면 exit code 2 + stderr 메시지로 Claude에게 돌려보낸다.
"""
import json
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
