-- ChordLens chord_results 테이블
-- Supabase Dashboard > SQL Editor 에서 실행

create table if not exists chord_results (
    id           uuid primary key default gen_random_uuid(),
    video_url    text        not null,
    title        text        not null,
    channel_name text        not null,
    thumbnail_url text       not null,
    chords       jsonb       not null default '[]'::jsonb,
    lyrics       jsonb       null,     -- [{ time, text }] 배열, 자막 없으면 null
    created_at   timestamptz not null default now()
);

-- 캐시 조회 성능 (video_url 기준 조회)
create index if not exists idx_chord_results_video_url
    on chord_results (video_url);

-- 최신 1건 조회 성능 (created_at DESC)
create index if not exists idx_chord_results_created_at
    on chord_results (created_at desc);

-- 조회수 컬럼 추가
alter table chord_results
    add column if not exists view_count integer not null default 0;

-- 인기순 조회 성능
create index if not exists idx_chord_results_view_count
    on chord_results (view_count desc);

-- 조회수 원자적 증가 함수
create or replace function increment_view_count(result_id uuid)
returns void as $$
  update chord_results set view_count = view_count + 1 where id = result_id;
$$ language sql;
