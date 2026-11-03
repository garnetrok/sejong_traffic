"""'지금 갱신' 제한 규칙 점검. 실행: .venv\\Scripts\\python.exe tests\\test_its_collector.py (ITS 호출 없음)"""
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from its_collector import manual_refresh_check  # noqa: E402
from its_client import now_kst  # noqa: E402

nov3 = datetime.date(2026, 11, 3)  # 11월은 30일 → 오늘 포함 남은 날 28일
old = (now_kst() - datetime.timedelta(hours=1)).isoformat()
recent = (now_kst() - datetime.timedelta(minutes=3)).isoformat()

# 1) 사용량 적고 1시간 전 호출 → 모두 가능
r = manual_refresh_check([{"service": "trafficInfo", "call_count": 1, "last_called_at": old}], nov3)
assert r == {"trafficInfo": None, "eventInfo": None, "cctvInfo": None}, r

# 2) 3분 전에 호출 → 10분 제한
r = manual_refresh_check([{"service": "eventInfo", "call_count": 1, "last_called_at": recent}], nov3)
assert all(v and "분 뒤" in v for v in r.values()), r

# 3) 소통 71회 사용: 71 + 1 + 28일치 예비 = 100 → 가능 / 72회면 101 → 불가
assert manual_refresh_check([{"service": "trafficInfo", "call_count": 71, "last_called_at": old}], nov3)["trafficInfo"] is None
assert "자동 수집 몫" in manual_refresh_check([{"service": "trafficInfo", "call_count": 72, "last_called_at": old}], nov3)["trafficInfo"]

# 4) CCTV는 1회에 2건: 42 + 2 + 2*28 = 100 → 가능 / 43이면 불가
assert manual_refresh_check([{"service": "cctvInfo", "call_count": 42, "last_called_at": old}], nov3)["cctvInfo"] is None
assert manual_refresh_check([{"service": "cctvInfo", "call_count": 43, "last_called_at": old}], nov3)["cctvInfo"]

print("ok")
