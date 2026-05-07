---
name: be-plan
description: "ChordLens BE 계획 수립 가이드. planner 에이전트의 계획서 작성 기준 및 탐색 순서."
---

# BE Plan Guide

## 탐색 순서

계획서 작성 전 다음 순서로 코드베이스를 탐색한다:

1. `app/models/` — 기존 Pydantic 타입 확인
2. `app/services/` — 유사한 서비스 패턴 파악
3. `app/routers/` — 라우터 구조 확인
4. `tests/` — 기존 테스트 패턴 파악
5. `app/db.py` — Supabase 클라이언트 패턴
6. `docs/TRD_backend.md` — API 명세 확인

## 계획서 품질 기준

### 필수 포함 사항

1. **변경 파일 목록** — 수정할 파일과 이유 (신규 생성 포함)
2. **엔드포인트 스펙** — 신규 API인 경우 request/response/error 명세
3. **Supabase 변경** — 스키마/쿼리 변경이 있으면 명시
4. **구현 단계** — Model → Service → Router 순서
5. **테스트 케이스** — 정상 케이스 1개 이상 + 에러 케이스 1개 이상

### 아키텍처 체크

계획서 작성 전 확인:

- [ ] 제안하는 구조가 Router → Service → Model 레이어를 준수하는가?
- [ ] 새 서비스는 기존 서비스와 책임이 명확히 분리되어 있는가?
- [ ] Supabase 접근은 service 레이어에만 있는가?
- [ ] 오디오 처리 작업이면 임시 파일 정리 로직을 포함했는가?
- [ ] 외부 API/오디오 처리 작업이면 타임아웃을 고려했는가?

## 작업 유형별 체크포인트

### 엔드포인트 추가
- 새 Pydantic 모델(Request/Response)이 정의되는가?
- 신규 라우터를 `app/main.py`에 등록하는 단계가 있는가?

### 서비스 수정
- 기존 테스트에 영향이 있는가?
- 캐싱 로직 변경 시 기존 데이터와 호환되는가?

### 버그 수정
- 버그 재현 케이스가 테스트로 추가되는가?
- 수정이 다른 서비스에 영향을 주는가?

### Supabase 스키마 변경
- `supabase/schema.sql` 업데이트가 포함되는가?
- 기존 데이터 마이그레이션이 필요한가?
