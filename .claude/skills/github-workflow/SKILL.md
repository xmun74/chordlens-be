---
name: github-workflow
description: "ChordLens GitHub 작업 가이드. Issue 생성, 브랜치 생성, PR 생성, 커밋, 상태 업데이트 시 반드시 사용. FE/BE 라벨 구분, 브랜치 네이밍, 커밋 메시지 형식, PR 템플릿 포함."
---

# ChordLens GitHub Workflow

## 작업 순서

1. Issue 생성 → Issue 번호 확인
2. 브랜치 생성 (`feat/#번호-작업명`)
3. Issue 상태 → In Progress
4. 개발 완료 후 PR 생성
5. Issue 상태 → Done

## Issue 생성

```bash
# FE 작업 (chordlens repo)
gh issue create \
  --repo moon/chordlens \
  --label FE \
  --title "feat: 작업명" \
  --body "..."

# BE 작업 (chordlens-be repo)
gh issue create \
  --repo moon/chordlens-be \
  --label BE \
  --title "feat: 작업명" \
  --body "..."

# FE+BE 연동 (chordlens repo, 라벨 둘 다)
gh issue create \
  --repo moon/chordlens \
  --label FE --label BE \
  --title "feat: 작업명" \
  --body "..."
```

템플릿 형식 (feat / bug / chore) 반드시 사용.

## 브랜치 생성

```bash
git checkout -b feat/#이슈번호-작업명   # 새 기능
git checkout -b fix/#이슈번호-작업명    # 버그 수정
```

## 커밋 메시지

```
feat: #12 코드 타임라인 자동 스크롤 구현
fix: #15 코드 분석 API 타임아웃 수정
chore: #9 ESLint 설정 추가
```

## PR 생성

```bash
gh pr create \
  --title "feat: #12 작업명" \
  --body "$(cat <<'EOF'
closes #12

## 변경 사항
- ...

## 테스트
- [ ] ...
EOF
)"
```

`closes #이슈번호` PR 본문에 반드시 포함.

## 라벨 규칙

| 영향 범위  | repo         | 라벨       |
| ---------- | ------------ | ---------- |
| FE 전용    | chordlens    | `FE`       |
| BE 전용    | chordlens-be | `BE`       |
| FE+BE 연동 | chordlens    | `FE`, `BE` |
