"""브리핑 근거 숫자 점검 (DB·Gemini 호출 없음). 실행: .venv\\Scripts\\python.exe tests\\test_briefing_facts.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dashboard_api import _dist_m, _links, build_briefing_facts  # noqa: E402

links = _links()
normal = [k for k, v in links.items() if v["rank"] not in ("101", "102")]
a, b, c = normal[:3]
lon, lat = links[a]["mid"]

status = {
    "updated_at": "2026-11-03T05:44:19+00:00",
    "speeds": {a: 5.0, b: 50.0, c: None},  # a만 정체(15 미만), c는 정보 없음
    "events": [{"event_type": "교통사고", "event_detail_type": "추돌", "road_name": "테스트로", "message": "2차로 사고",
                "lon": lon, "lat": lat}],
    "hotspots": [
        {"spot_nm": "가까운곳", "category": "지자체별", "year": 2025, "occrrnc_cnt": 21, "caslt_cnt": 29,
         "dth_dnv_cnt": 0, "se_dnv_cnt": 2, "lon": lon + 0.002, "lat": lat},   # 약 180m
        {"spot_nm": "먼곳", "category": "자전거", "year": 2025, "occrrnc_cnt": 4, "caslt_cnt": 4,
         "dth_dnv_cnt": 0, "se_dnv_cnt": 0, "lon": lon + 0.1, "lat": lat},     # 약 9km
    ],
}
f = build_briefing_facts(status)

assert f["정체구간_총수"] == 1, f
assert f["일반도로_평균속도"] == 27.5, f          # (5 + 50) / 2, None 제외
assert f["정체_도로_상위"][0]["최저속도"] == 5.0
assert f["정체_도로_상위"][0]["인근_사고다발지역"] == ["가까운곳(지자체별, 2025년 21건)"], f["정체_도로_상위"]
assert f["진행중_돌발"][0]["인근_사고다발지역"] == ["가까운곳(지자체별, 2025년 21건)"]
assert len(f["사고다발지역"]) == 2
assert "_mid" not in f["정체_도로_상위"][0]
assert 150 < _dist_m(lon, lat, lon + 0.002, lat) < 200
print("ok")
