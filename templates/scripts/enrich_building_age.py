"""villa_redev_screen.py 결과(candidates.json) → 건축물대장 표제부(BldRgstHubService/getBrTitleInfo)로 사용승인일·구조·층수 부착.
도로명만 있는 물건은 VWorld 역지오코딩으로 지번을 얻는다(별도 처리 필요). 법정동코드는 PublicDataReader 가 쓰는 공개 JSON(GitHub)을 직접 받아 쓴다(라이브러리 import 금지)."""
import json, os, re, sys, time
from pathlib import Path
import requests
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
KEY = os.environ["PUBLIC_DATA_SERVICE_KEY"]
WORK = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("_workspace/villa_redev")
BDONG_URL = "https://raw.githubusercontent.com/WooilJeong/code/main/code/code_dong/code_bdong.json"
API = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"


def bdong_map():
    cache = WORK / "bdong_seoul.json"
    if cache.exists():
        return json.load(open(cache, encoding="utf-8"))
    res = requests.get(BDONG_URL, timeout=60).json()
    cols = res["data"]  # pandas to_dict() 형식: {열이름: {행번호: 값}}
    m = {}
    for i in cols["시도명"]:
        if cols["시도명"][i] != "서울특별시" or not cols["읍면동명"].get(i):
            continue
        def _v(col):  # JSON 의 NaN 은 float('nan') 으로 들어와 truthy 다
            v = cols[col].get(i)
            return "" if v is None or (isinstance(v, float) and v != v) else str(v)
        if _v("말소일자") or _v("동리명"):
            continue
        m[f"{cols['시군구명'][i]} {cols['읍면동명'][i]}"] = str(cols["법정동코드"][i])
    json.dump(m, open(cache, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    return m


def parse_jibun(addr):
    m = re.search(r"서울특별시\s+(\S+구)\s+(\S+?동)\s+(산)?\s*(\d+)(?:-(\d+))?", addr)
    if not m:
        return None
    return m.group(1), m.group(2), "1" if m.group(3) else "0", int(m.group(4)), int(m.group(5) or 0)


def title_info(code10, gb, bun, ji):
    p = {"serviceKey": KEY, "sigunguCd": code10[:5], "bjdongCd": code10[5:10], "platGbCd": gb,
         "bun": f"{bun:04d}", "ji": f"{ji:04d}", "numOfRows": 20, "pageNo": 1, "_type": "json"}
    for a in range(3):
        try:
            r = requests.get(API, params=p, timeout=30)
            j = r.json()
            body = j["response"]["body"]
            items = body.get("items") or {}
            it = items.get("item") if isinstance(items, dict) else items
            if it is None:
                return []
            return it if isinstance(it, list) else [it]
        except Exception as e:
            print("  retry", a, str(e)[:80], r.text[:120] if 'r' in dir() else "")
            time.sleep(2)
    return None


def main():
    bd = bdong_map()
    d = json.load(open(WORK / "candidates.json", encoding="utf-8"))
    for i, rec in enumerate(d["items"]):
        pj = parse_jibun(rec["address"])
        if not pj:
            rec["bld"] = {"error": "jibun_parse"}; continue
        gu, dong, gb, bun, ji = pj
        code = bd.get(f"{gu} {dong}")
        if not code:
            rec["bld"] = {"error": f"bdong_code {gu} {dong}"}; continue
        its = title_info(code, gb, bun, ji)
        time.sleep(0.35)
        if its is None:
            rec["bld"] = {"error": "api"}; continue
        # 동이 여러 개면 물건 주소의 동 표기(예: '105동')와 맞는 것을 우선
        pick = None
        m = re.search(r"(\S+?동)\s+\d+층", rec["address"])
        for x in its:
            if m and m.group(1) and (x.get("dongNm") or "").replace(" ", "") == m.group(1):
                pick = x; break
        if pick is None and its:
            pick = max(its, key=lambda x: int(x.get("totArea") or 0))
        rec["bld"] = None if not pick else {
            "bldNm": pick.get("bldNm"), "dongNm": pick.get("dongNm"), "useAprDay": pick.get("useAprDay"),
            "pmsDay": pick.get("pmsDay"), "strctCdNm": pick.get("strctCdNm"), "mainPurpsCdNm": pick.get("mainPurpsCdNm"),
            "grndFlrCnt": pick.get("grndFlrCnt"), "ugrndFlrCnt": pick.get("ugrndFlrCnt"), "hhldCnt": pick.get("hhldCnt"),
            "rideUseElvtCnt": pick.get("rideUseElvtCnt"), "totArea": pick.get("totArea"), "n_dong": len(its)}
        print(i, rec["address"][:40], "→", (rec["bld"] or {}).get("useAprDay"), (rec["bld"] or {}).get("bldNm"))
    json.dump(d, open(WORK / "candidates.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
