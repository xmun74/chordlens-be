---
name: be-orchestrator
description: "ChordLens BE 개발 작업의 메인 오케스트레이터. FastAPI 엔드포인트 추가, 서비스 수정, Supabase 연동, 버그 수정, 오디오 파이프라인 수정, 성능 개선, GitHub Issue/PR 생성 시 반드시 이 스킬을 사용. 후속 작업: 기능 수정, 재구현, 업데이트, 이전 결과 개선, 다시 실행, 보완, 특정 부분만 다시 요청 시에도 반드시 사용."
---

# ChordLens BE Orchestrator

Plan → Implement → QA 3단계 파이프라인으로 BE 개발 작업을 조율한다.

## 실행 모드: 하이브리드 (파이프라인)

| Phase | 모드 | 팀원 |
|-------|------|------|
| Phase 2: Plan | 에이전트 팀 | planner + plan-critic |
| Phase 3: Implement | 에이전트 팀 | be-developer + code-critic |
| Phase 4: QA | 서브 에이전트 | qa-reviewer |
| Phase 5: GitHub | 서브 에이전트 | github-manager |

## 워크플로우

### Phase 0: 컨텍스트 확인

1. `_workspace/` 존재 여부 확인
2. 실행 모드 결정:
   - `_workspace/` **없음** → 초기 실행, Phase 1 진행
   - `_workspace/` **있음** + 부분 수정 요청:
     - "계획만 다시" → Phase 2(Plan)만 재실행, 기존 구현 보존
     - "구현만 다시" → Phase 3(Implement)부터 재실행
     - "QA만 다시" → Phase 4(QA)만 재실행
   - `_workspace/` **있음** + 새 작업 → `_workspace/`를 `_workspace_prev_{YYYYMMDD}/`로 이동 후 Phase 1

### Phase 1: 작업 분류 및 준비

1. 사용자 요청 분석
2. 작업 유형 결정:
   - **엔드포인트 추가**: 신규 라우터/서비스 구현
   - **서비스 수정**: 기존 서비스 로직 변경
   - **버그 수정**: 오류 원인 파악 후 수정
   - **성능 개선**: 캐싱/파이프라인 최적화
   - **GitHub 작업**: Issue/PR만 필요 → Phase 5로 바로 이동
3. `_workspace/` 생성
4. `_workspace/01_task.md`에 작업 지시 저장

### Phase 2: Plan (계획 수립)

**실행 모드:** 에이전트 팀

```
TeamCreate(
  team_name: "be-plan-team",
  members: [
    {
      name: "planner",
      model: "opus",
      prompt: """
        [.claude/agents/planner.md 전체 내용]
        [.claude/skills/be-plan/SKILL.md 전체 내용]

        작업: [_workspace/01_task.md 내용]

        1. app/ 디렉토리를 탐색하여 관련 기존 코드를 파악한다
        2. _workspace/02_plan.md를 작성한다
        3. 완료 후 plan-critic에게 SendMessage로 검토 요청
      """
    },
    {
      name: "plan-critic",
      model: "opus",
      prompt: """
        [.claude/agents/plan-critic.md 전체 내용]

        planner가 계획 완료 알림을 보내면:
        1. _workspace/02_plan.md를 읽는다
        2. _workspace/02_plan_critique.md를 작성한다
        3. 리더에게 판정 결과 SendMessage
      """
    }
  ]
)

TaskCreate(tasks: [
  { title: "계획 수립", assignee: "planner" },
  { title: "계획 비평", assignee: "plan-critic", depends_on: ["계획 수립"] }
])
```

완료 후 `_workspace/02_plan_critique.md` 읽어 🔴 확인:
- 🔴 있음 → planner에게 수정 지시 (최대 2회)
- 통과 → TeamDelete 후 Phase 3 진행

### Phase 3: Implement (구현)

**실행 모드:** 에이전트 팀

```
TeamCreate(
  team_name: "be-impl-team",
  members: [
    {
      name: "be-developer",
      model: "opus",
      prompt: """
        [.claude/agents/be-developer.md 전체 내용]
        [.claude/skills/be-development/SKILL.md 전체 내용]

        _workspace/02_plan.md를 읽고 구현을 시작한다:
        1. app/models/에 Pydantic 모델 먼저 정의
        2. app/services/에 비즈니스 로직 구현
        3. app/routers/에 라우터 연결
        4. python -m pytest tests/ -v 통과 확인
        5. 완료 후 code-critic에게 SendMessage
      """
    },
    {
      name: "code-critic",
      model: "opus",
      prompt: """
        [.claude/agents/code-critic.md 전체 내용]

        be-developer 완료 알림 수신 후:
        1. _workspace/02_plan.md 읽기
        2. 변경된 파일들 Read
        3. python -m pytest tests/ -v 실행
        4. 레이어 아키텍처 위반 확인
        5. _workspace/04_code_critique.md 작성
        6. 리더에게 판정 SendMessage
      """
    }
  ]
)

TaskCreate(tasks: [
  { title: "BE 구현", assignee: "be-developer" },
  { title: "코드 리뷰", assignee: "code-critic", depends_on: ["BE 구현"] }
])
```

완료 후 `_workspace/04_code_critique.md` 읽어 🔴 확인:
- 🔴 있음 → be-developer에게 수정 지시 (최대 2회)
- 통과 → TeamDelete 후 Phase 4 진행

### Phase 4: QA (최종 검증)

**실행 모드:** 서브 에이전트

```
Agent(
  description: "ChordLens BE QA 최종 검증",
  subagent_type: "general-purpose",
  model: "opus",
  prompt: """
    [.claude/agents/qa-reviewer.md 전체 내용]
    [.claude/skills/be-qa/SKILL.md 전체 내용]

    1. _workspace/02_plan.md 읽기
    2. _workspace/04_code_critique.md 읽기
    3. 구현 파일들 Read로 확인
    4. python -m pytest tests/ -v 실행
    5. API 계약 검증 (docs/TRD_backend.md 참조)
    6. _workspace/05_qa_report.md 작성
  """
)
```

QA 판정이 "재작업"인 경우:
- be-developer에게 수정 지시
- QA 재실행 (최대 1회)

### Phase 5: GitHub (선택)

사용자에게 GitHub 처리 여부 확인 후:

```
Agent(
  description: "GitHub 워크플로우 실행",
  subagent_type: "general-purpose",
  model: "opus",
  prompt: """
    [.claude/agents/github-manager.md 전체 내용]
    [.claude/skills/github-workflow/SKILL.md 전체 내용]

    작업 유형: [feat/fix/chore]
    작업 내용: [_workspace/01_task.md 요약]
    영향 범위: BE
    repo: moon/chordlens-be
  """
)
```

### Phase 6: 정리

1. `_workspace/` 보존
2. 결과 요약:
   - 구현된 파일 목록
   - QA 최종 판정
   - GitHub 처리 여부
3. 피드백 수집

## 데이터 흐름

```
사용자 요청
    ↓
_workspace/01_task.md
    ↓
[Plan Team] planner ←→ plan-critic
    ↓
_workspace/02_plan.md + 02_plan_critique.md
    ↓ TeamDelete
[Impl Team] be-developer ←→ code-critic
    ↓
실제 소스 파일 + _workspace/04_code_critique.md
    ↓ TeamDelete
[QA Sub-agent] qa-reviewer
    ↓
_workspace/05_qa_report.md
    ↓ (선택)
[GitHub Sub-agent] github-manager
```

## 에러 핸들링

| 상황 | 전략 |
|------|------|
| 계획 비평 🔴 2회 이후 미해결 | 사용자에게 계획 검토 요청 |
| 구현 비평 🔴 2회 이후 미해결 | 리더가 직접 수정 제안 |
| QA 재작업 1회 이후 미해결 | 사용자에게 보고, 수동 처리 제안 |
| 팀원 실패 | SendMessage로 상태 확인 → 1회 재시도 → 누락 명시 |
| pytest 실패 (의존성 문제) | `pip install pytest`로 설치 후 재실행 |

## 테스트 시나리오

### 정상 흐름 (엔드포인트 추가)
1. "GET /results/{id} 엔드포인트 추가"
2. Phase 1: 엔드포인트 추가 분류
3. Phase 2: planner 계획 (models → services → routers) → plan-critic 통과
4. Phase 3: be-developer 구현 → pytest 통과 → code-critic 통과
5. Phase 4: qa-reviewer API 계약 검증 통과
6. Phase 5: GitHub PR 생성

### 에러 흐름 (레이어 위반)
1. Phase 3에서 code-critic이 Router의 Supabase 직접 호출 발견
2. be-developer에게 서비스 레이어로 이동 지시
3. 수정 후 pytest 재실행 통과
4. Phase 4 QA 진행
