"""서울 다세대 조건검색 + 정비구역 매칭
조건: 전용≥30㎡ · 최저가 2~3억 · 유찰 1~3회(저감율 역산 80/64/51%) · 연식은 2단계(건축물대장)에서
출력: <workdir>/candidates.json  (사용: python templates/scripts/villa_redev_screen.py [_workspace/villa_redev])
정비구역 폴리곤은 maptest/_workspace 의 layer_zone_redev_{vworld,seoulplan}.geojson·layer_zone_sintong.geojson 을 그대로 쓴다.
"""
import json, math, re, sys, time
from datetime import datetime, timedelta
from pathlib import Path
import requests
from pyproj import Transformer
from shapely.geometry import shape, Point
from shapely.strtree import STRtree

sys.path.insert(0, r"C:\Users\m9938\maptest\scripts")
from collect_auction_capital import API, HEADERS, PAGE_SIZE, search_params  # noqa: E402

WORK = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("_workspace/villa_redev")  # 산출 디렉터리(인자)
MT = Path(r"C:\Users\m9938\maptest\_workspace")
COURTS = [("서울중앙", "B000210"), ("서울동부", "B000211"), ("서울남부", "B000212"),
          ("서울북부", "B000213"), ("서울서부", "B000215")]
AREA_RE = re.compile(r'([\d,]+(?:\.\d+)?)\s*㎡')
TO_WGS = Transformer.from_crs(
    "+proj=tmerc +lat_0=38 +lon_0=128 +k=0.9999 +x_0=400000 +y_0=600000 +ellps=bessel "
    "+towgs84=-115.80,474.99,674.11,1.16,-2.31,-1.63,6.43 +units=m +no_defs", "EPSG:4326", always_xy=True)


def crawl(session, code, days):
    p = search_params(days); p["cortOfcCd"] = code
    p["lwsDspslPrcMin"] = "200000000"; p["lwsDspslPrcMax"] = "300000000"
    items, total, page_no = [], None, 1
    while True:
        body = {"dma_pageInfo": {"pageNo": page_no, "pageSize": PAGE_SIZE, "bfPageNo": page_no - 1,
                                 "startRowNo": (page_no - 1) * PAGE_SIZE + 1, "totalCnt": "", "totalYn": "N", "groupTotalCount": 0},
                "dma_srchGdsDtlSrchInfo": p}
        for a in range(3):
            try:
                r = session.post(API, headers=HEADERS, json=body, timeout=30); r.raise_for_status()
                data = r.json().get("data", {}) or {}; break
            except Exception as e:
                print("  retry", a, e); time.sleep(3)
        else:
            break
        page = data.get("dlt_srchResult", []) or []
        if total is None:
            pi = data.get("dma_pageInfo", {}) or {}
            total = int(pi.get("totalCnt") or pi.get("groupTotalCount") or 0)
            max_page = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        if page_no == max_page:
            remain = total - len(items)
            if 0 <= remain < len(page):
                page = page[-remain:] if remain else []
        items.extend(page)
        if page_no >= max_page:
            break
        page_no += 1; time.sleep(1.2)
    return items, total


def area_of(it):
    src = ' '.join(str(it.get(k, '') or '') for k in ('convAddr', 'areaList', 'pjbBuldList'))
    v = [float(m.replace(',', '')) for m in AREA_RE.findall(src)]
    return max(v) if v else None


def fails_from_rate(rate):
    try:
        r = float(rate)
    except (TypeError, ValueError):
        return None
    if r >= 100:
        return 0
    return round(math.log(r / 100) / math.log(0.8))


def load_zones(fn):
    fc = json.load(open(MT / fn, encoding="utf-8"))
    geoms, props = [], []
    for f in fc["features"]:
        if not f.get("geometry"):
            continue
        g = shape(f["geometry"])
        if not g.is_valid:
            g = g.buffer(0)
        geoms.append(g); props.append(f["properties"])
    return STRtree(geoms), geoms, props


def hits(tree, geoms, props, pt, keys):
    out = []
    for idx in tree.query(pt):
        if geoms[idx].contains(pt):
            out.append({k: props[idx].get(k) for k in keys})
    return out


def main():
    days = 90
    WORK.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    raw = []
    for name, code in COURTS:
        its, total = crawl(s, code, days)
        print(f"{name}: {len(its)}/{total}")
        raw.extend(its)
    seen, uniq = set(), []
    for it in raw:
        k = it.get("docid") or (it.get("boCd"), it.get("saNo"), it.get("maemulSer"))
        if k in seen: continue
        seen.add(k); uniq.append(it)
    print("2~3억 건물 전체(서울5법원, 90일):", len(uniq))

    zv = load_zones("layer_zone_redev_vworld.geojson")
    zs = load_zones("layer_zone_redev_seoulplan.geojson")
    zt = load_zones("layer_zone_sintong.geojson")

    out = []
    for it in uniq:
        usage = it.get("dspslUsgNm") or ""
        if "다세대" not in usage and "연립" not in usage and "빌라" not in usage:
            continue
        if not (it.get("hjguSido") or "").startswith("서울"):
            continue
        area = area_of(it)
        if area is None or area < 30:
            continue
        rate = it.get("notifyMinmaePriceRate1")
        fails = fails_from_rate(rate)
        if fails is None or not (1 <= fails <= 3):
            continue
        low = int(it.get("notifyMinmaePrice1") or 0)
        if not (200_000_000 <= low <= 300_000_000):
            continue
        lon = lat = None
        x, y = it.get("xCordi"), it.get("yCordi")
        if x and y:
            lo, la = TO_WGS.transform(float(x), float(y))
            if 126 < lo < 128 and 37 < la < 38.5:
                lon, lat = round(lo, 6), round(la, 6)
        rec = {
            "case_no": " ".join((it.get("printCsNo") or "").replace("<br/>", " ").split()) or f"{it.get('jiwonNm')} {it.get('srnSaNo')}",
            "court": (it.get("jiwonNm") or "").strip(), "sa_no": it.get("saNo"), "maemul_ser": it.get("maemulSer"),
            "address": (it.get("printSt") or "").strip(), "sigungu": it.get("hjguSigu"), "dong": it.get("hjguDong"),
            "usage": usage, "area_m2": area, "appraisal": int(it.get("gamevalAmt") or 0), "min_bid": low,
            "rate": rate, "fails": fails, "sale_date": it.get("maeGiil"), "lon": lon, "lat": lat,
            "bld_info": (it.get("pjbBuldList") or "").replace("\n", " "),
        }
        if lon:
            pt = Point(lon, lat)
            rec["zone_vworld"] = hits(*zv, pt, ("name", "category", "sigungu", "type_code", "mgmt_no"))
            rec["zone_seoulplan"] = hits(*zs, pt, ("name", "category", "subtype", "stage", "sigungu"))
            rec["zone_sintong"] = hits(*zt, pt, ("name", "stage", "category"))
        else:
            rec["zone_vworld"] = rec["zone_seoulplan"] = rec["zone_sintong"] = []
        rec["in_zone"] = bool(rec["zone_vworld"] or rec["zone_seoulplan"] or rec["zone_sintong"])
        out.append(rec)
    out.sort(key=lambda r: (not r["in_zone"], r["sale_date"] or ""))
    (WORK / "candidates.json").write_text(json.dumps({"meta": {"collected_at": datetime.now().isoformat(timespec="seconds"),
                                                              "bid_window_days": days, "count": len(out),
                                                              "in_zone": sum(r["in_zone"] for r in out)}, "items": out},
                                                    ensure_ascii=False, indent=1), encoding="utf-8")
    print("후보:", len(out), "정비구역 안:", sum(r["in_zone"] for r in out), "좌표없음:", sum(1 for r in out if not r["lon"]))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
