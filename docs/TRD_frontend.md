# ChordLens — Frontend Technical Requirements Document (TRD)

---

## 메타데이터

| 항목       | 내용       |
| ---------- | ---------- |
| 문서 번호  | TRD-FE-001 |
| 프로젝트명 | ChordLens  |
| 작성일     | 2026-04-06 |
| 상태       | Draft      |
| 대상       | 프론트엔드 |
| 연관 문서  | PRD.md     |

---

## 1. 기술 스택

| 항목           | 기술           | 버전            | 용도                      |
| -------------- | -------------- | --------------- | ------------------------- |
| 프레임워크     | Next.js        | 16 (App Router) | SSR, 라우팅, API Route    |
| 스타일링       | Tailwind CSS   | 4               | 유틸리티 기반 스타일      |
| 서버 상태 관리 | TanStack Query | v5              | API 요청, 캐싱, 로딩 상태 |
| 언어           | TypeScript     | 5               | 타입 안정성               |
| 다이어그램     | Vexchords.js   | latest          | 기타 코드 SVG 렌더링      |
| 배포           | Vercel         | -               | 무료 플랜                 |

---

## 2. 프로젝트 구조

FSD(Feature-Sliced Design)를 Next.js App Router 환경에 맞게 적용한 구조다.
Next.js의 라우팅 컨벤션(`app/`)은 유지하되, 실제 UI 로직은 FSD 레이어(`src/`)에서 관리한다.

### FSD 레이어 역할

| 레이어     | 역할                                                 | 의존 방향                  |
| ---------- | ---------------------------------------------------- | -------------------------- |
| `shared`   | 재사용 유틸, 공통 타입, API 클라이언트, UI 기본 요소 | 없음 (최하위)              |
| `entities` | 도메인 모델 단위 (chord, video) — 상태·타입·UI 포함  | shared                     |
| `features` | 사용자 행동 단위 (코드 추출, 공유)                   | entities, shared           |
| `pages`    | 페이지 조합 레이어 — features + entities를 조립      | features, entities, shared |

> 상위 레이어는 하위 레이어를 import할 수 있지만, 역방향 import는 금지한다.

```
chordlens-frontend/
│
├── app/                                   # Next.js App Router (라우팅 전용)
│   ├── layout.tsx                         # 루트 레이아웃 (폰트, Provider 등록)
│   ├── page.tsx                           # → pages/home 렌더링
│   ├── result/
│   │   └── [id]/
│   │       └── page.tsx                   # → pages/result 렌더링 (SSR + OG)
│   └── api/
│       └── meta/
│           └── route.ts                   # YouTube 메타데이터 API Route
│
└── src/
    │
    ├── pages/                             # 레이어 4: 페이지 조합
    │   ├── home/
    │   │   └── ui/
    │   │       └── HomePage.tsx           # UrlInput + 결과 화면 조합
    │   └── result/
    │       └── ui/
    │           └── ResultPage.tsx         # 공유 링크 페이지 조합
    │
    ├── features/                          # 레이어 3: 사용자 행동 단위
    │   ├── extract-chord/                 # 핵심 기능: URL → 코드 추출
    │   │   ├── api/
    │   │   │   └── extractChord.ts        # Railway POST /extract 호출
    │   │   ├── model/
    │   │   │   └── useExtractChord.ts     # TanStack Query useMutation 훅
    │   │   └── ui/
    │   │       ├── UrlInputForm.tsx        # URL 입력창 + 버튼
    │   │       └── LoadingState.tsx        # 단계별 로딩 표시
    │   └── share-result/                  # 결과 공유 기능
    │       └── ui/
    │           └── ShareButton.tsx         # URL 클립보드 복사 버튼
    │
    ├── entities/                          # 레이어 2: 도메인 모델
    │   ├── chord/                         # 코드 도메인
    │   │   ├── model/
    │   │   │   └── types.ts               # ChordEntry, ChordResult 타입
    │   │   └── ui/
    │   │       ├── ChordDiagram.tsx        # Vexchords.js 단일 코드 카드
    │   │       ├── ChordGrid.tsx           # 코드 다이어그램 그리드
    │   │       └── ChordTimeline.tsx       # 시간별 코드 칩 타임라인
    │   └── video/                         # 영상 도메인
    │       ├── model/
    │       │   └── types.ts               # VideoMeta 타입
    │       └── ui/
    │           └── VideoCard.tsx           # 썸네일 + 제목 + 채널명 카드
    │
    └── shared/                            # 레이어 1: 공통 기반 (최하위)
        ├── api/
        │   └── railwayClient.ts           # Railway API 기본 fetch 클라이언트
        ├── lib/
        │   ├── chord.ts                   # 코드명 정규화 유틸
        │   └── youtube.ts                 # YouTube URL 유효성 검사 유틸
        ├── types/
        │   └── index.ts                   # 프로젝트 공통 타입
        └── ui/                            # 공통 UI 기본 요소
            ├── Button.tsx
            └── Spinner.tsx
```

---

## 3. 페이지 요구사항

### 3-1. 메인 페이지 (`/`)

**목적:** YouTube URL 입력 → 코드 분석 결과 표시

**렌더링 방식:** Client Component (사용자 인터랙션 중심)

**화면 상태 흐름:**

```
idle → loading → success
              ↘ error
```

| 상태      | 표시 내용                             |
| --------- | ------------------------------------- |
| `idle`    | URL 입력창 + 분석하기 버튼            |
| `loading` | 단계별 프로그레스 (추출 중 → 분석 중) |
| `success` | VideoCard + ChordTimeline + ChordGrid |
| `error`   | 에러 메시지 + 재시도 버튼             |

**요구사항:**

- URL 입력창은 붙여넣기(paste) 즉시 유효성 검사 수행
- YouTube URL 형식 검증: `youtube.com/watch?v=`, `youtu.be/` 두 형식 모두 허용
- 분석하기 버튼은 유효한 URL 입력 시에만 활성화
- 로딩 중 버튼 비활성화 및 스피너 표시
- 결과는 입력창 하단에 인라인으로 표시 (페이지 이동 없음)

---

### 3-2. 공유 링크 페이지 (`/result/[id]`)

**목적:** 분석 결과를 URL로 공유

**렌더링 방식:** Server Component (SSR — OG 메타태그 생성)

**요구사항:**

- Supabase에서 `id` 기준으로 결과 조회 후 서버에서 렌더링
- `generateMetadata`로 OG 태그 동적 생성

```typescript
// app/result/[id]/page.tsx
export async function generateMetadata({ params }): Promise<Metadata> {
  const result = await getResultById(params.id);
  return {
    title: `${result.title} — ChordLens`,
    description: `${result.chords.length}개 코드 추출됨`,
    openGraph: {
      title: result.title,
      images: [result.thumbnailUrl],
    },
  };
}
```

- 결과가 없으면 404 반환 (`notFound()`)
- 공유 버튼 클릭 시 현재 URL 클립보드 복사

---

### 3-3. API Route (`/api/meta`)

**목적:** Railway 서버 호출 전 YouTube 메타데이터 선조회 (썸네일, 제목 즉시 표시용)

**요구사항:**

- `GET /api/meta?url={youtube_url}`
- YouTube oEmbed API 활용 (무료, 인증 불필요)
- 응답: `{ title, thumbnailUrl, channelName }`

```typescript
// app/api/meta/route.ts
export async function GET(request: Request) {
  const url = new URL(request.url).searchParams.get("url");
  const oEmbed = await fetch(
    `https://www.youtube.com/oembed?url=${url}&format=json`,
  );
  const data = await oEmbed.json();
  return Response.json({
    title: data.title,
    thumbnailUrl: data.thumbnail_url,
    channelName: data.author_name,
  });
}
```

---

## 4. 컴포넌트 요구사항

### 4-1. UrlInput

| 항목        | 내용                                         |
| ----------- | -------------------------------------------- |
| 입력 타입   | `text` (URL paste 감지)                      |
| 유효성 검사 | YouTube URL 정규식 실시간 검사               |
| 버튼 상태   | 유효한 URL 입력 시 활성화, 로딩 중 비활성화  |
| 에러 표시   | 유효하지 않은 URL 입력 시 인라인 에러 메시지 |

```typescript
const YOUTUBE_REGEX =
  /^(https?:\/\/)?(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/)[\w-]{11}/;
```

---

### 4-2. LoadingState

단계별 진행 상태를 텍스트와 애니메이션으로 표시한다.

| 단계 | 메시지            |
| ---- | ----------------- |
| 1    | 오디오 추출 중... |
| 2    | 코드 분석 중...   |
| 3    | 완료!             |

- 각 단계는 TanStack Query의 `fetchStatus`와 서버 응답 기반으로 전환
- 폴링 없이 단일 요청으로 처리 (Railway 응답까지 대기)

---

### 4-3. ChordTimeline

시간 순서대로 코드 칩을 가로로 나열한다.

| 항목      | 내용                                    |
| --------- | --------------------------------------- |
| 레이아웃  | 가로 스크롤 (overflow-x: auto)          |
| 칩 내용   | 시간 + 코드명 (예: `00:12 Am`)          |
| 활성 상태 | 클릭한 칩 강조 표시                     |
| 상호작용  | 칩 클릭 시 ChordGrid에서 해당 코드 강조 |

---

### 4-4. ChordDiagram

Vexchords.js를 React에서 렌더링하는 래퍼 컴포넌트.

```typescript
// src/entities/chord/ui/ChordDiagram.tsx
'use client';

import { useEffect, useRef } from 'react';
import { ChordBox } from 'vexchords';

interface Props {
  chordName: string;       // "Am", "F", "G" 등
  fingers: number[][];     // Vexchords finger 포지션
  isActive?: boolean;      // 활성 강조 여부
}

export function ChordDiagram({ chordName, fingers, isActive }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    ref.current.innerHTML = '';
    const box = new ChordBox(ref.current, { width: 120, height: 140 });
    box.draw({ chord: fingers, position: 1 });
  }, [fingers]);

  return (
    <div className={`rounded-xl p-3 ${isActive ? 'ring-2 ring-blue-500' : ''}`}>
      <div ref={ref} />
      <p className="text-center text-sm font-medium mt-1">{chordName}</p>
    </div>
  );
}
```

---

## 5. TanStack Query 요구사항

### 5-1. 훅 정의

```typescript
// src/features/extract-chord/model/useExtractChord.ts
import { useMutation } from "@tanstack/react-query";
import { extractChords } from "../api/extractChord";

export function useExtractChord() {
  return useMutation({
    mutationFn: (youtubeUrl: string) => extractChords(youtubeUrl),
    onError: (error) => {
      console.error("코드 추출 실패:", error);
    },
  });
}
```

### 5-2. 캐싱 전략

| 항목        | 설정값           | 이유                                    |
| ----------- | ---------------- | --------------------------------------- |
| `staleTime` | `Infinity`       | 동일 URL 재분석 불필요 (서버 캐시 있음) |
| `gcTime`    | `1000 * 60 * 10` | 10분간 메모리 유지                      |
| `retry`     | `1`              | 네트워크 오류 시 1회 재시도             |

### 5-3. 공유 링크 페이지 결과 조회

```typescript
// 서버 컴포넌트에서는 TanStack Query 대신 직접 fetch 사용
// app/result/[id]/page.tsx
async function getResultById(id: string): Promise<ChordResult> {
  const res = await fetch(
    `${process.env.NEXT_PUBLIC_SUPABASE_URL}/rest/v1/chord_results?id=eq.${id}`,
    {
      headers: { apikey: process.env.SUPABASE_ANON_KEY! },
      cache: "force-cache",
    },
  );
  const [data] = await res.json();
  if (!data) notFound();
  return data;
}
```

---

## 6. 타입 정의

```typescript
// types/index.ts

export interface ChordEntry {
  time: string; // "0:12"
  chord: string; // "Am"
}

export interface ChordResult {
  id: string;
  title: string;
  channelName: string;
  thumbnailUrl: string;
  chords: ChordEntry[];
}

export type ExtractStatus =
  | "idle"
  | "extracting"
  | "recognizing"
  | "done"
  | "error";
```

---

## 7. 환경 변수

```bash
# .env

NEXT_PUBLIC_RAILWAY_URL=https://chordlens-server.railway.app
NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

---

## 8. 비기능 요구사항

### 8-1. 성능

| 항목                   | 기준                                             |
| ---------------------- | ------------------------------------------------ |
| Lighthouse Performance | 90점 이상                                        |
| LCP                    | 2.5초 이하                                       |
| Vexchords 렌더링       | 코드 다이어그램 20개 이하 기준 200ms 이내        |
| 번들 사이즈            | Vexchords.js dynamic import로 코드 스플리팅 적용 |

### 8-2. 접근성

- 기타 다이어그램 SVG에 `aria-label` 포함 (예: `aria-label="Am 코드 다이어그램"`)
- 키보드 탐색 지원 (Tab, Enter로 코드 칩 선택 가능)
- 컬러 대비 WCAG AA 기준 충족

### 8-3. 반응형

| 브레이크포인트       | 코드 그리드 열 수 |
| -------------------- | ----------------- |
| mobile (`< 640px`)   | 2열               |
| tablet (`640px ~`)   | 3열               |
| desktop (`1024px ~`) | 4열               |

---

## 9. 제약 사항

| 항목                  | 내용                                                                                                              |
| --------------------- | ----------------------------------------------------------------------------------------------------------------- |
| Vexchords SSR         | `useEffect` 내부에서만 렌더링 (`'use client'` 필수)                                                               |
| Next.js 16 App Router | Pages Router 혼용 금지. `app/`은 라우팅 전용, 실제 UI 로직은 `src/` FSD 레이어에서 관리                           |
| FSD 의존 방향         | 상위 레이어 → 하위 레이어만 허용. `shared`에서 `features` import 금지                                             |
| FSD 교차 import       | 동일 레이어 내 슬라이스 간 직접 import 금지. 예: `features/extract-chord`에서 `features/share-result` import 불가 |
| Tailwind CSS 4        | `@apply` 사용 최소화, 유틸리티 클래스 직접 사용 원칙                                                              |
| 브라우저 지원         | Chrome, Safari, Firefox 최신 2버전                                                                                |
