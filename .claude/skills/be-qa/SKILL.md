---
name: be-qa
description: "ChordLens BE QA 검증 가이드. API 계약 검증, pytest 실행, 레이어 아키텍처 최종 확인. qa-reviewer 에이전트의 검증 기준."
---

# BE QA Guide

## QA 핵심 원칙

"존재 확인"이 아닌 **"경계면 교차 비교"**가 핵심이다.
- 실제 Response 모델 ↔ `docs/TRD_backend.md` API 명세 비교
- 실제 에러 코드 ↔ 명세 에러 코드 비교
- Optional 필드 처리 방식 ↔ FE 기대값 비교

## 검증 순서

### 1. 테스트 실행

```bash
python -m pytest tests/ -v
```

전체 통과 여부 확인. 실패 시 상세 오류 기록.

### 2. API 계약 검증

`docs/TRD_backend.md`의 API 명세와 실제 구현 비교:

| 검증 항목 | 확인 방법 |
|----------|----------|
| Response 필드명 | Pydantic 모델 필드 vs TRD 명세 필드 |
| 필드 타입 | `uuid.UUID` vs `str`, `int` vs `float` |
| Optional 처리 | `Optional[X] = None` vs 항상 반환 |
| 에러 상태코드 | `HTTPException(status_code=...)` vs TRD 에러 표 |
| 리스트 기본값 | `[]` vs `null` (FE가 어떤 값을 기대하는가) |

### 3. 레이어 아키텍처 확인

- Router에서 `get_supabase()` 직접 호출 없는지
- Service에서 `HTTPException` raise 없는지
- 오디오 처리 작업에서 `finally` 블록으로 임시 파일 정리되는지

### 4. 비동기 패턴 확인

- Supabase `AsyncClient` 호출에 모두 `await` 있는지
- 블로킹 파이프라인이 `asyncio.to_thread`로 감싸져 있는지

## 경계면 버그 패턴 (실제 발생 유형)

| 버그 유형 | 구체적 확인 방법 |
|----------|----------------|
| `cached=True` 경로 누락 필드 | 캐시 히트 응답에 모든 필드 존재하는지 |
| `cached=False` 경로 누락 필드 | 파이프라인 실행 후 모든 필드 채워지는지 |
| lyrics `None` vs `[]` | FE가 `null` 체크하는지 빈 배열 체크하는지 |
| `await` 누락 | Supabase 비동기 호출이 coroutine 반환하고 있지 않은지 |
| 임시 파일 미삭제 | `/tmp/chordlens/` 경로에 파일 남아있지 않는지 |

## 판정 기준

| 판정 | 조건 |
|------|------|
| 통과 | pytest 전부 통과 + API 계약 완전 일치 + 🔴 없음 |
| 조건부 통과 | pytest 통과 + 🟡만 있음 (다음 PR에서 해결 권고) |
| 재작업 | pytest 실패 또는 API 계약 불일치 또는 🔴 있음 |
