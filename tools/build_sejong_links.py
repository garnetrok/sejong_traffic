"""표준노드링크(전국 SHP)에서 세종 구간만 잘라 지도용 GeoJSON 생성. 개발 PC에서 가끔 한 번 실행.

준비: data/nodelink/MOCT_LINK.* (ITS 노드링크 자료실 zip에서 압축 해제)
     pip install pyshp pyproj   (서버에는 필요 없음)
실행: .venv\\Scripts\\python.exe tools\\build_sejong_links.py
"""
import json
import sys
from pathlib import Path

import shapefile
from pyproj import Transformer

ROOT = Path(__file__).resolve().parent.parent
SEJONG_PREFIX = "413"  # 링크ID 앞 3자리 = 관리 권역 (세종)
# 노드링크 좌표계: GRS80 중부원점(가산 600000) = EPSG:5186
to_wgs84 = Transformer.from_crs("EPSG:5186", "EPSG:4326", always_xy=True)


def main():
    # shortcut: ITS 소통정보가 실제로 들어오는 링크만 포함 (캐시된 응답 기준). 링크가 늘면 새 응답으로 다시 실행
    cached = ROOT / ".its_cache" / "trafficInfo_type-all.txt"
    traffic_ids = {t["linkId"] for t in json.loads(cached.read_text(encoding="utf-8"))["body"]["items"]}

    reader = shapefile.Reader(str(ROOT / "data" / "nodelink" / "MOCT_LINK"), encoding="cp949")
    features = []
    for sr in reader.iterShapeRecords():
        rec = sr.record.as_dict()
        link_id = rec["LINK_ID"]
        if not link_id.startswith(SEJONG_PREFIX) or link_id not in traffic_ids:
            continue
        xs, ys = zip(*sr.shape.points)
        lons, lats = to_wgs84.transform(xs, ys)
        features.append({
            "type": "Feature",
            "properties": {"id": link_id, "name": rec["ROAD_NAME"], "rank": rec["ROAD_RANK"],
                           "max_spd": rec["MAX_SPD"], "lanes": rec["LANES"]},
            "geometry": {"type": "LineString",
                         "coordinates": [[round(x, 5), round(y, 5)] for x, y in zip(lons, lats)]},
        })

    out = ROOT / "static" / "sejong_links.geojson"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"type": "FeatureCollection", "features": features},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    # 자체 점검: 모든 좌표가 세종 근처(위도 36.3~36.8, 경도 127.0~127.5)인지
    bad = [f["properties"]["id"] for f in features
           if not all(36.3 < y < 36.8 and 127.0 < x < 127.5 for x, y in f["geometry"]["coordinates"])]
    assert not bad, f"세종 밖 좌표: {bad[:5]}"
    print(f"{len(features)}개 링크 → {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    sys.exit(main())
