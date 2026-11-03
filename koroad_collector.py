"""도로교통공단 사고다발지역(data.go.kr) 수집 → Supabase koroad_hotspots.

공식 선정 데이터라 1년에 한 번 바뀜. 가장 최근 연도부터 거꾸로 찾아 데이터가 있는 해를 저장.
"""
import json
import os

import requests

from fetch_data import supabase
from its_client import now_kst

SEJONG = {"siDo": 36, "guGun": 110}  # 도로교통공단 지역코드: 세종특별자치시
# 유형: (API 경로, 선정 기준 설명). 활용신청이 승인된 것만 넣음
CATEGORIES = {
    "지자체별": ("frequentzoneLg/getRestFrequentzoneLg",
              "1년간 전체 사고 중 반경 150m 내 3건 이상인 지점 상위 3곳"),
    "법규위반": ("frequentzoneLgrViolt/getRestFrequentzoneLgrViolt",
             "1년간 신호위반 사고 반경 100m 내 6건 이상, 또는 중앙선침범 사고 반경 300m 내 3건 이상(사망 포함 시 2건)"),
    "자전거": ("frequentzoneBicycle/getRestFrequentzoneBicycle",
            "1년간 자전거 관련 사고 반경 200m 내 4건 이상(사망 포함 시 3건)"),
    "결빙": ("frequentzoneFreezing/getRestFrequentzoneFreezing",
           "최근 5년간 서리·결빙 노면 사고 반경 200m 내 3건 이상(사망 포함 시 2건)"),
}


def _fetch(path: str, year: int) -> list:
    r = requests.get(f"https://apis.data.go.kr/B552061/{path}", params={
        "ServiceKey": os.environ["DATA_GO_KR_KEY"], "searchYearCd": year, "type": "json",
        "numOfRows": 100, "pageNo": 1, **SEJONG}, timeout=30)
    r.raise_for_status()
    body = r.json()
    if body.get("resultCode") == "03":  # NODATA: 그 해 자료 없음
        return []
    if body.get("resultCode") != "00":
        raise RuntimeError(f"사고다발지역 API 오류 {body.get('resultCode')}: {body.get('resultMsg')}")
    return body["items"]["item"]


def collect_hotspots() -> dict:
    result = {}
    this_year = now_kst().year
    for category, (path, _) in CATEGORIES.items():
        for year in range(this_year, this_year - 5, -1):
            items = _fetch(path, year)
            if items:
                break
        rows = [{
            "hotspot_key": f"{category}_{year}_{i['spot_cd']}", "category": category, "year": year,
            "spot_nm": i.get("spot_nm"), "occrrnc_cnt": i.get("occrrnc_cnt"), "caslt_cnt": i.get("caslt_cnt"),
            "dth_dnv_cnt": i.get("dth_dnv_cnt"), "se_dnv_cnt": i.get("se_dnv_cnt"),
            "sl_dnv_cnt": i.get("sl_dnv_cnt"), "wnd_dnv_cnt": i.get("wnd_dnv_cnt"),
            "lon": float(i["lo_crd"]), "lat": float(i["la_crd"]),
            "geom": json.loads(i["geom_json"]) if i.get("geom_json") else None,
            "collected_at": now_kst().isoformat(),
        } for i in items]
        if rows:
            # 새 연도 자료가 나오면 그 유형의 옛 연도 지점은 지움
            supabase.table("koroad_hotspots").delete().eq("category", category).neq("year", year).execute()
            supabase.table("koroad_hotspots").upsert(rows, on_conflict="hotspot_key").execute()
        result[category] = {"year": year if rows else None, "count": len(rows)}
    return result


if __name__ == "__main__":
    print(collect_hotspots())
