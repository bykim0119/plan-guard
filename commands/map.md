---
description: 계획 문서의 Mermaid 구조도를 Windows 브라우저에 렌더해서 연다
argument-hint: <계획문서.md 경로>
---

`$1`로 주어진 계획/설계 문서의 Mermaid 구조도를 브라우저로 띄운다.
경로가 비어 있으면 사용자에게 어떤 문서인지 물어본 뒤 실행한다.

다음을 실행하라:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render_map.py" "$1"
```

실행 결과("열었습니다: ... (블록 N개)")를 사용자에게 그대로 전한다.
블록이 0개면, 그 문서에 ```mermaid 코드블록이 있는지 확인하라고 안내한다.
