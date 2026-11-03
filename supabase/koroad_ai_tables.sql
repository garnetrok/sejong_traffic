-- 사고다발지역(도로교통공단) + AI 브리핑 캐시. Supabase SQL Editor 에 붙여 넣고 Run.

-- 도로교통공단 공식 선정 사고다발지역 (연 1회 갱신 데이터)
create table if not exists koroad_hotspots (
  hotspot_key   text primary key,      -- 유형_연도_지점코드
  category      text not null,         -- 지자체별 / 결빙 / 자전거 / 법규위반 …
  year          int  not null,
  spot_nm       text,
  occrrnc_cnt   int,                   -- 발생 건수
  caslt_cnt     int,                   -- 사상자 수
  dth_dnv_cnt   int,                   -- 사망
  se_dnv_cnt    int,                   -- 중상
  sl_dnv_cnt    int,                   -- 경상
  wnd_dnv_cnt   int,                   -- 부상신고
  lon           double precision,
  lat           double precision,
  geom          jsonb,                 -- 구역 폴리곤 (GeoJSON)
  collected_at  timestamptz not null default now()
);

-- Gemini 브리핑: 같은 수집 데이터로는 한 번만 생성해서 재사용
create table if not exists ai_briefings (
  based_on    timestamptz primary key,  -- 근거가 된 ITS 수집 시각
  briefing    text not null,
  facts       jsonb,                    -- Gemini에 넘긴 숫자 (검증용)
  created_at  timestamptz not null default now()
);

alter table koroad_hotspots enable row level security;
alter table ai_briefings    enable row level security;
