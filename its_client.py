"""국가교통정보센터(ITS) OpenAPI 호출.

서비스마다 월 100건 한도라서:
- 실제 호출할 때마다 이번 달 서비스별 횟수를 Supabase api_usage 에 기록하고, 한도에 닿으면 호출하지 않음
- 받은 응답 원문은 .its_cache/ 에 저장해 두고 개발·테스트 때 재사용 (use_cache=True, 깃에는 안 올라감)
"""
import datetime
import json
import os
from pathlib import Path

import requests

from fetch_data import supabase

BASE_URL = "https://openapi.its.go.kr:9443"
# 세종시를 감싸는 사각형. 경계 밖(대전·공주·청주 일부)도 조금 포함됨
SEJONG_BBOX = {"minX": 127.13, "maxX": 127.42, "minY": 36.40, "maxY": 36.74}
MONTHLY_LIMIT = 100
CACHE_DIR = Path(__file__).parent / ".its_cache"
KST = datetime.timezone(datetime.timedelta(hours=9))  # Windows엔 tz DB가 없어 고정 오프셋 사용


def now_kst() -> datetime.datetime:
    return datetime.datetime.now(KST)


def usage_rows() -> list:
    """이번 달 서비스별 호출 기록 [{service, call_count, last_called_at}]"""
    return (supabase.table("api_usage").select("service,call_count,last_called_at")
            .eq("month", now_kst().strftime("%Y-%m")).execute().data)


def monthly_usage(service: str) -> int:
    return next((r["call_count"] for r in usage_rows() if r["service"] == service), 0)


def _count(service: str) -> None:
    supabase.table("api_usage").upsert({
        "month": now_kst().strftime("%Y-%m"), "service": service,
        "call_count": monthly_usage(service) + 1, "last_called_at": now_kst().isoformat(),
    }).execute()


def call(service: str, use_cache: bool = False, **params) -> dict:
    """ITS API 응답(JSON)을 돌려줌. use_cache=True 면 저장된 응답이 있을 때 호출하지 않음."""
    label = "_".join(f"{k}-{v}" for k, v in sorted(params.items()) if k not in SEJONG_BBOX)
    cache_file = CACHE_DIR / f"{service}_{label}.txt"
    if use_cache and cache_file.exists():
        text = cache_file.read_text(encoding="utf-8")
    else:
        if monthly_usage(service) >= MONTHLY_LIMIT:
            raise RuntimeError(f"{service} 이번 달 호출 한도({MONTHLY_LIMIT}건) 도달 — 호출하지 않음")
        _count(service)  # 실패해도 ITS가 횟수를 셀 수 있으니 호출 전에 기록
        r = requests.get(f"{BASE_URL}/{service}",
                         params={"apiKey": os.environ["ITS_API_KEY"], "getType": "json", **params}, timeout=60)
        r.raise_for_status()
        text = r.text
        if use_cache:
            CACHE_DIR.mkdir(exist_ok=True)
            cache_file.write_text(text, encoding="utf-8")
    if text.lstrip().startswith("<"):  # getType=json 이어도 오류는 XML로 올 때가 있음
        raise RuntimeError(f"{service} JSON이 아닌 응답: {text[:200]}")
    return json.loads(text)
