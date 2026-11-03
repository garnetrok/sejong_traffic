-- 실시간 관제(ITS) 테이블. Supabase 대시보드 > SQL Editor 에 붙여 넣고 Run.
-- 서버는 service_role 키로 읽고 쓰므로, RLS를 켜고 정책을 두지 않아 브라우저(anon)에서는 접근 불가.

-- 교통소통: 수집할 때마다 링크별 속도를 쌓음 (이력 보관)
create table if not exists its_traffic (
  collected_at  timestamptz not null,
  link_id       text not null,
  road_name     text,
  speed         real,          -- km/h
  travel_time   real,          -- 초
  created_date  text,          -- ITS 생성 시각 YYYYMMDDHH24MISS
  primary key (collected_at, link_id)
);

-- 돌발상황: 같은 돌발은 한 줄 (다시 수집되면 last_seen_at 만 갱신)
create table if not exists its_events (
  event_key          text primary key,   -- linkId + 발생일시 + 유형
  road_type          text,               -- 고속도로 / 국도 / 지방도 / 시군도 / 기타
  event_type         text,               -- 교통사고 / 공사 / 기상 / 재난 / 기타돌발 / 기타
  event_detail_type  text,
  start_date         text,
  end_date           text,
  lon                double precision,
  lat                double precision,
  link_id            text,
  road_name          text,
  road_no            text,
  road_drc_type      text,
  lanes_block_type   text,
  lanes_blocked      text,
  message            text,
  first_seen_at      timestamptz not null default now(),
  last_seen_at       timestamptz not null default now()
);

-- CCTV 목록 + 영상 주소 (주소는 만료 전까지 재사용)
create table if not exists its_cctv (
  cctv_key     text primary key,  -- 도로유형 + 이름
  road_type    text,              -- ex(고속도로) / its(국도)
  name         text,
  lon          double precision,
  lat          double precision,
  url          text,
  url_fetched_at timestamptz
);

-- ITS 서비스별 월 호출 횟수 (월 100건 한도 관리)
create table if not exists api_usage (
  month           text not null,  -- 'YYYY-MM'
  service         text not null,  -- trafficInfo / eventInfo / cctvInfo
  call_count      int  not null default 0,
  last_called_at  timestamptz,
  primary key (month, service)
);

alter table its_traffic enable row level security;
alter table its_events  enable row level security;
alter table its_cctv    enable row level security;
alter table api_usage   enable row level security;
