---
name: showing-position
description: Use when a system reminder tagged "[plan-guard 위치 안내]" appears with a progress tree — reprint that tree at the very top of your next reply so the user always sees where you are in the overall plan.
---

# 진행 위치 트리를 응답 첫머리에 펴라

plan-guard의 위치 안내 훅은 할일 상태가 바뀔 때마다 "지금 계획 중 어디"를
나타내는 글자 트리를 system reminder(`[plan-guard 위치 안내]` 표시)로 네
컨텍스트에 넣는다. 너는 그 순간 코드 디테일에 묻혀 있더라도, 설계자는
전체 그림을 잃기 쉽다.

## 규율

`[plan-guard 위치 안내]`로 시작하는 진행 트리를 컨텍스트에서 보면:

1. **다음 응답의 맨 첫머리**에 그 트리를 그대로(코드블록으로) 펴서 보여준다.
2. 그 아래에 평소 설명을 이어간다.
3. 트리는 훅이 준 최신 것을 쓴다. 직접 지어내거나 옛 트리를 재사용하지 마라.

## 예시

훅이 넣어준 트리가 이렇다면:

```
계획 진행  2/4
├─ ✓ 설계 검증
├─ ✓ 트리 스크립트
├─ ← 지금 여기: 훅 등록
└─ ○ 규율 스킬
```

너의 다음 응답은 이 트리를 맨 위에 그대로 보여준 뒤, 훅 등록 작업 설명을
이어가는 형태가 된다.

## 안 보일 때

`[plan-guard 위치 안내]` 트리가 컨텍스트에 없으면(할일을 안 쓰는 즉흥 작업
등) 아무것도 하지 않는다. 트리를 억지로 만들지 마라.
