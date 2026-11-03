"""대시보드(web/)가 호출하는 서버 함수 모음.

예전 Apps Script Code.gs 에 있던 함수들을 Python으로 옮긴 것.
화면은 /api/<함수명> 으로 호출하며, 함수명은 Apps Script 때와 같다.
"""
import json
import os

import pandas as pd
import requests

from fetch_data import fetch_table_all, supabase

ALLOWED_TABLES = {"mock_accident_data", "mock_penalty_data", "ml_safety_scores", "ml_model_eval"}


def _df_to_records(df: pd.DataFrame) -> list:
    # NaN → null 로 바꿔서 JSON 으로 보낼 수 있게 변환
    return json.loads(df.to_json(orient="records", force_ascii=False))


def _check_table(table_name: str) -> str:
    if table_name not in ALLOWED_TABLES:
        raise ValueError(f"허용되지 않은 테이블: {table_name}")
    return table_name


def fetchTrafficData(table_name: str = "mock_accident_data") -> list:
    return _df_to_records(fetch_table_all(_check_table(table_name or "mock_accident_data")))


def upsertTrafficData(table_name: str, records: list) -> dict:
    """엑셀 업로드 → incident_no(사고번호) 기준 중복 없이 적재."""
    if not records:
        return {"success": False, "error": "적재할 데이터가 없습니다."}
    table = _check_table(table_name or "mock_accident_data")
    try:
        for i in range(0, len(records), 500):
            supabase.table(table).upsert(records[i:i + 500], on_conflict="incident_no").execute()
        return {"success": True, "count": len(records)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def updatePenaltyStatus(record_id, status_value: str) -> bool:
    """조치 상태(미조치/조치중/완료) 변경. 단속 → 사고 테이블 순서로 찾음."""
    for table in ("mock_penalty_data", "mock_accident_data"):
        resp = supabase.table(table).update({"status": status_value}).eq("id", record_id).execute()
        if resp.data:
            return True
    return False


def fetchMlSafetyScores() -> list:
    """ML 예상 사고 건수를 화면용 안전 점수로 변환 (높을수록 안전).

    동네끼리 비교한 상대 점수: 예상 사고가 가장 적은 동 100점, 가장 많은 동 40점.
    """
    rows = fetchTrafficData("ml_safety_scores")
    if not rows:
        return []
    preds = [float(r.get("predicted_quarter_accidents") or 0) for r in rows]
    lo, hi = min(preds), max(preds)
    for r in rows:
        if r.get("safety_score") is None and r.get("predicted_quarter_accidents") is not None:
            pred = float(r["predicted_quarter_accidents"] or 0)
            r["safety_score"] = round(100 - (pred - lo) / (hi - lo) * 60) if hi > lo else 100
        if not r.get("computed_at") and r.get("target_period"):
            r["computed_at"] = f"예측 기간 {r['target_period']}"
    return sorted(rows, key=lambda r: r.get("risk_rank") or 9999)


def triggerMlRecompute() -> dict:
    """ML 재학습·예측 후 Supabase 저장 (같은 서버 안에서 바로 실행)."""
    from save_predictions import run_and_save
    try:
        return {"success": True, "data": run_and_save()}
    except Exception as e:
        return {"success": False, "error": str(e)}


def getAiPredictReport(last_year_cnt, this_year_cnt, rate_calc) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "[설정 필요] 환경 변수 GEMINI_API_KEY 를 추가하세요."
    model = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
    prompt = f"""
    당신은 세종특별자치시청 교통과 소속의 AI 빅데이터 지능형 의사결정 시스템입니다.
    아래 통계 원천 데이터를 바탕으로 교통사고 사각지대를 해소할 공문서용 추천 사유서를 작성하세요.

    [통계 지표]
    - 전년도 발생 위험 지표 수: {last_year_cnt}건
    - 금년도 누적 발생 위험 지표 수: {this_year_cnt}건
    - 전년 대비 교통 리스크 변동율: {rate_calc}%

    [출력 조건]
    1. 단 두 문장으로 핵심만 명확하게 요약 브리핑할 것.
    2. 데이터 변동 추이에 따라 'CCTV 1순위 후보 좌표 배치' 또는 '과속방지턱 필요 구간 확충'에 대한 선제적 예방 행정 결론을 명확히 제시할 것.
    """
    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={"x-goog-api-key": api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30,
        )
        if r.status_code != 200:
            return f"[API 호출 에러 {r.status_code}] (사유: {r.text[:100]})"
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"AI 분석 연동 예외 발생: {e}"


def _select_all(query_fn) -> list:
    """Supabase는 한 번에 1000행까지만 주므로 나눠서 모두 읽음."""
    rows, start = [], 0
    while True:
        page = query_fn().range(start, start + 999).execute().data
        rows.extend(page)
        if len(page) < 1000:
            return rows
        start += 1000


def getLiveStatus() -> dict:
    """실시간 관제 화면용: Supabase에 저장된 최신 ITS 데이터만 읽음 (ITS 호출 안 함)."""
    from its_client import MONTHLY_LIMIT, now_kst, usage_rows
    from its_collector import manual_refresh_check

    latest = supabase.table("its_traffic").select("collected_at").order("collected_at", desc=True).limit(1).execute().data
    updated_at = latest[0]["collected_at"] if latest else None
    speeds = {}
    if updated_at:
        rows = _select_all(lambda: supabase.table("its_traffic").select("link_id,speed").eq("collected_at", updated_at))
        speeds = {r["link_id"]: r["speed"] for r in rows}

    last_ev = supabase.table("its_events").select("last_seen_at").order("last_seen_at", desc=True).limit(1).execute().data
    active = (supabase.table("its_events").select("*").eq("last_seen_at", last_ev[0]["last_seen_at"]).execute().data
              if last_ev else [])
    feed = supabase.table("its_events").select("*").order("first_seen_at", desc=True).limit(20).execute().data
    cctv = supabase.table("its_cctv").select("cctv_key,road_type,name,lat,lon").execute().data

    usage = usage_rows()
    return {
        "updated_at": updated_at,
        "speeds": speeds,
        "events": active,
        "feed": feed,
        "cctv": cctv,
        "usage": {r["service"]: r["call_count"] for r in usage},
        "limit": MONTHLY_LIMIT,
        "refresh_blocked": manual_refresh_check(usage, now_kst().date()),
    }


def getCctvUrl(cctv_key: str) -> dict:
    """CCTV 영상 주소 (저장된 것 재사용, ITS 호출 안 함).
    주의: 스트림 응답 안에 ITS 키가 들어 있어 브라우저에서 보임 — 사용자 결정(2026-11-03)으로 직접 재생."""
    rows = supabase.table("its_cctv").select("url,url_fetched_at").eq("cctv_key", cctv_key).execute().data
    return rows[0] if rows else {}


def refreshLive() -> dict:
    """"지금 갱신" 버튼: 10분 간격·월 예비분 규칙을 지키는 서비스만 ITS 호출."""
    from its_collector import collect
    return {"result": collect(manual=True), "status": getLiveStatus()}


# 화면에서 호출할 수 있는 함수 목록 (여기 없는 이름은 거부)
API_FUNCTIONS = {
    f.__name__: f
    for f in (
        fetchTrafficData,
        upsertTrafficData,
        updatePenaltyStatus,
        fetchMlSafetyScores,
        triggerMlRecompute,
        getAiPredictReport,
        getLiveStatus,
        getCctvUrl,
        refreshLive,
    )
}
