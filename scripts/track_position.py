#!/usr/bin/env python3
"""할일 진행 상황을 '지금 여기' 글자 트리로 클로드에게 보여주는 추적 스크립트.

PostToolUse(TaskCreate|TaskUpdate) 훅으로 호출된다. 차단하지 않는다 —
stdin JSON에서 할일 이벤트를 꺼내 작은 메모장(상태 파일)을 갱신하고,
진행도 트리를 만들어 hookSpecificOutput.additionalContext로 stdout에 낸다.
클로드는 규율 스킬(showing-position)에 따라 다음 응답 첫머리에 트리를 편다.
어떤 오류에도 exit 0으로 끝내 작업을 방해하지 않는다.
"""
import fcntl
import json
import os
import sys
import tempfile

NOTEPAD_NAME = ".plan-guard-position.json"


def normalize_event(data):
    """훅 stdin JSON → {kind,id,subject?/status?}. 관련 없으면 None."""
    tool = data.get("tool_name")
    if tool == "TaskCreate":
        task = (data.get("tool_response") or {}).get("task") or {}
        tid = task.get("id")
        if tid is None:
            return None
        return {"kind": "create", "id": str(tid),
                "subject": task.get("subject", "")}
    if tool == "TaskUpdate":
        ti = data.get("tool_input") or {}
        tid = ti.get("taskId")
        if tid is None:
            return None
        return {"kind": "update", "id": str(tid), "status": ti.get("status")}
    return None


def apply_event(notepad, event):
    """메모장 갱신. create가 update 뒤에 처음 오면 새 배치로 보고 리셋."""
    items = list((notepad or {}).get("items", []))
    last_kind = (notepad or {}).get("last_kind")
    kind = event["kind"]
    if kind == "create":
        if last_kind == "update":
            items = []  # 새 계획 배치 시작 → 리셋
        existing = next((it for it in items if it["id"] == event["id"]), None)
        if existing:
            existing["subject"] = event.get("subject", existing.get("subject", ""))
        else:
            items.append({"id": event["id"],
                          "subject": event.get("subject", ""),
                          "status": "pending"})
    elif kind == "update":
        for it in items:
            if it["id"] == event["id"]:
                it["status"] = event.get("status") or it.get("status", "pending")
                break
    return {"last_kind": kind, "items": items}


def render_tree(notepad):
    """진행도 글자 트리. 항목 없으면 빈 문자열."""
    items = (notepad or {}).get("items", [])
    if not items:
        return ""
    done = sum(1 for it in items if it.get("status") == "completed")
    total = len(items)
    lines = ["계획 진행  {}/{}".format(done, total)]
    for i, it in enumerate(items):
        branch = "└─" if i == total - 1 else "├─"
        status = it.get("status")
        subject = it.get("subject") or "(제목 없음)"
        if status == "completed":
            body = "✓ " + subject
        elif status == "in_progress":
            body = "← 지금 여기: " + subject
        else:
            body = "○ " + subject
        lines.append("{} {}".format(branch, body))
    return "\n".join(lines)


def notepad_path(cwd):
    base = cwd if cwd and os.path.isdir(cwd) else tempfile.gettempdir()
    return os.path.join(base, NOTEPAD_NAME)


def load_notepad(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "items" in data:
            return data
    except (OSError, ValueError):
        pass
    return {"last_kind": None, "items": []}


def save_notepad(path, notepad):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(notepad, f, ensure_ascii=False)
    except OSError:
        pass  # 저장 실패해도 작업을 방해하지 않는다


def _parse_notepad(raw):
    try:
        data = json.loads(raw.decode("utf-8"))
        if isinstance(data, dict) and "items" in data:
            return data
    except (ValueError, UnicodeDecodeError):
        pass
    return {"last_kind": None, "items": []}


def update_notepad(path, event):
    """파일 락으로 직렬화된 원자적 read-modify-write. 갱신된 메모장 반환.

    PostToolUse 훅은 병렬 도구 호출 때 동시에 여러 프로세스로 실행될 수 있다.
    배타 락(flock)으로 read-modify-write 전체를 감싸 한 번에 하나씩만 처리해,
    업데이트 유실과 쓰기 인터리빙(깨진 JSON)을 막는다.
    """
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    except OSError:
        return apply_event(load_notepad(path), event)  # 락 못 잡으면 최선만
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        raw = b""
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            raw += chunk
        notepad = apply_event(_parse_notepad(raw), event)
        data = json.dumps(notepad, ensure_ascii=False).encode("utf-8")
        os.lseek(fd, 0, os.SEEK_SET)
        os.ftruncate(fd, 0)
        os.write(fd, data)
        return notepad
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return 0
    event = normalize_event(data)
    if event is None:
        return 0
    path = notepad_path(data.get("cwd"))
    notepad = update_notepad(path, event)
    tree = render_tree(notepad)
    if tree:
        out = {"hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (
                "[plan-guard 위치 안내] 다음 응답 첫머리에 아래 진행 트리를 "
                "그대로 펴서 보여주세요:\n" + tree),
        }}
        print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
