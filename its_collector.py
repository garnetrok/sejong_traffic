"""ITS 실시간 데이터 수집 → Supabase 저장.

- 자동 수집(하루 1번, GitHub Actions → /collect): 세 서비스 모두
- "지금 갱신" 버튼: 마지막 호출 후 10분이 지나야 하고, 이번 달 남은 날의 자동 수집 몫은 남겨 둠
"""
import calendar
import datetime

from fetch_data import supabase
from its_client import MONTHLY_LIMIT, SEJONG_BBOX, call, now_kst, usage_rows

SEJONG_LINK_PREFIX = "413"  # 표준노드링크 링크ID 앞 3자리 = 세종
DAILY_COST = {"trafficInfo": 1, "eventInfo": 1, "cctvInfo": 2}  # 자동 수집 1회에 드는 호출 수
MIN_INTERVAL = datetime.timedelta(minutes=10)


def _items(resp: dict) -> list:
    header = resp.get("header", {})
    if header.get("resultCode") not in (0, "0", None):
        raise RuntimeError(f"ITS 오류 {header.get('resultCode')}: {header.get('resultMsg')}")
    return resp.get("body", {}).get("items") or []


def collect_traffic(use_cache=False) -> int:
    now = now_kst().isoformat()
    rows = [{
        "collected_at": now, "link_id": t["linkId"], "road_name": t.get("roadName"),
        "speed": float(t["speed"]) if t.get("speed") else None,
        "travel_time": float(t["travelTime"]) if t.get("travelTime") else None,
        "created_date": t.get("createdDate"),
    } for t in _items(call("trafficInfo", use_cache, type="all", **SEJONG_BBOX))
        if t.get("linkId", "").startswith(SEJONG_LINK_PREFIX)]
    for i in range(0, len(rows), 1000):
        supabase.table("its_traffic").insert(rows[i:i + 1000]).execute()
    return len(rows)


def collect_events(use_cache=False) -> int:
    # shortcut: 세종을 감싼 사각형 기준이라 경계 밖 돌발도 조금 섞임. 경계 폴리곤이 생기면 그걸로 거름
    now = now_kst().isoformat()
    rows = [{
        "event_key": f"{e.get('linkId')}_{e.get('startDate')}_{e.get('eventType')}_{e.get('eventDetailType')}",
        "road_type": e.get("type"), "event_type": e.get("eventType"),
        "event_detail_type": e.get("eventDetailType"),
        "start_date": e.get("startDate"), "end_date": e.get("endDate"),
        "lon": float(e["coordX"]) if e.get("coordX") else None,
        "lat": float(e["coordY"]) if e.get("coordY") else None,
        "link_id": e.get("linkId"), "road_name": e.get("roadName"), "road_no": e.get("roadNo"),
        "road_drc_type": e.get("roadDrcType"), "lanes_block_type": e.get("lanesBlockType"),
        "lanes_blocked": e.get("lanesBlocked"), "message": e.get("message"),
        "last_seen_at": now,  # first_seen_at 은 처음 넣을 때만 기본값(now)으로 채워짐
    } for e in _items(call("eventInfo", use_cache, type="all", eventType="all", **SEJONG_BBOX))]
    if rows:
        supabase.table("its_events").upsert(rows, on_conflict="event_key").execute()
    return len(rows)


def collect_cctv(use_cache=False) -> int:
    now = now_kst().isoformat()
    rows = {}
    for road_type in ("ex", "its"):  # ITS는 고속도로/국도를 따로 불러야 함 (호출 2회)
        resp = call("cctvInfo", use_cache, type=road_type, cctvType=4, **SEJONG_BBOX)
        for c in resp.get("response", {}).get("data") or []:
            key = f"{road_type}_{c['cctvname']}"
            rows[key] = {"cctv_key": key, "road_type": road_type, "name": c["cctvname"],
                         "lon": float(c["coordx"]), "lat": float(c["coordy"]),
                         "url": c["cctvurl"], "url_fetched_at": now}
    if rows:
        supabase.table("its_cctv").upsert(list(rows.values()), on_conflict="cctv_key").execute()
    return len(rows)


COLLECTORS = {"trafficInfo": collect_traffic, "eventInfo": collect_events, "cctvInfo": collect_cctv}


def manual_refresh_check(usage: list, today: datetime.date) -> dict:
    """서비스별로 지금 수동 갱신이 가능한지 {service: None(가능) 또는 사유}."""
    by = {r["service"]: r for r in usage}
    last = max((datetime.datetime.fromisoformat(r["last_called_at"]) for r in usage if r.get("last_called_at")),
               default=None)
    wait = last + MIN_INTERVAL - now_kst() if last else None
    days_left = calendar.monthrange(today.year, today.month)[1] - today.day + 1  # 오늘 포함
    result = {}
    for svc, cost in DAILY_COST.items():
        used = by.get(svc, {}).get("call_count", 0)
        if wait and wait.total_seconds() > 0:
            result[svc] = f"{int(wait.total_seconds() // 60) + 1}분 뒤에 다시 갱신할 수 있습니다"
        elif used + cost + cost * days_left > MONTHLY_LIMIT:
            result[svc] = "남은 날의 자동 수집 몫을 남기기 위해 이번 달 수동 갱신 불가"
        else:
            result[svc] = None
    return result


def collect(manual=False, use_cache=False) -> dict:
    """수집 실행. manual=True 면 10분 간격·월 예비분 규칙을 지킨 서비스만 호출."""
    blocked = manual_refresh_check(usage_rows(), now_kst().date()) if manual else {}
    result = {}
    for svc, fn in COLLECTORS.items():
        if blocked.get(svc):
            result[svc] = {"skipped": blocked[svc]}
            continue
        try:
            result[svc] = {"count": fn(use_cache)}
        except Exception as e:  # 한 서비스가 실패해도 나머지는 수집
            result[svc] = {"error": str(e)}
    return result


if __name__ == "__main__":
    import sys
    # 개발용: python its_collector.py --cache  → 저장된 응답으로 Supabase 채우기 (ITS 호출 0회)
    print(collect(use_cache="--cache" in sys.argv))
