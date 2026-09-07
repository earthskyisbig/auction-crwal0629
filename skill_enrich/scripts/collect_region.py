# -*- coding: utf-8 -*-
"""법원경매 물건을 '법원 없이 전국 + 서버 조건필터'로 API 직접 페이징 수집 → 시도 주소로 사후필터.

오늘의 핵심 발견 (SKILL.md 참조):
  - 검색 폼의 지역 드롭다운은 프로그램적 set 이 서버에 등록 안 됨 → 지역필터가 안 걸림.
  - 대신 cortOfcCd(법원)를 비우고, 캡처한 API 요청본문에 서버사이드 범위필터를 주입:
      lwsDspslPrcMin/Max(최저가) · objctArDtsMin/Max(전용면적) · flbdNcntMin/Max(유찰)
    → 전국 결과를 조건으로 좁힌 뒤 pageNo 로 결정론적 완전수집(totalCnt 대조).
  - 시도는 물건소재지(printSt) 접두어로 사후필터.

용도 소분류는 UI 드롭다운으로 설정(용도코드 자동생성 필요). 나머지 조건은 전부 API 본문 주입.

사용:
  python collect_region.py --sido 경기 --min-price 100000000 --max-price 300000000 \
      --area-min 59 --area-max 85 --flbd-min 1 --flbd-max 2 -o out.csv
  python collect_region.py --sido 서울 --scl 아파트 --flbd-min 1           # 서울 아파트 유찰1↑
  python collect_region.py --max-price 300000000 --no-region                # 전국(사후필터 없음)
"""
import argparse, json, math, os, re, csv, sys, time
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sido_codes import resolve, addr_matches

URL = "https://www.courtauction.go.kr/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ151F00.xml"
API = "https://www.courtauction.go.kr/pgj/pgjsearch/searchControllerMain.on"
COLUMNS = ['사건번호', '물건소재지', '전용면적', '감정가', '최저가', '저감율', '유찰횟수', '매각기일']
AREA_RE = re.compile(r'([\d,]+(?:\.\d+)?)\s*㎡')
PAGE_SIZE = 40  # ⚠️ 40 초과 시 서버 500
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
STEALTH = ['--no-sandbox', '--disable-blink-features=AutomationControlled',
           '--disable-features=site-per-process', '--lang=ko-KR']
FETCH = """async ([url,body])=>{const r=await fetch(url,{method:'POST',credentials:'include',
 headers:{'Content-Type':'application/json;charset=UTF-8','Accept':'application/json'},body:JSON.stringify(body)});
 const t=await r.text();let j=null;try{j=JSON.parse(t)}catch(e){}return {status:r.status,json:j,text:j?null:t.slice(0,200)};}"""


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sido', default=None, help='시도명 (예: 경기 / 서울특별시). 생략+--no-region 이면 전국')
    ap.add_argument('--no-region', action='store_true', help='시도 사후필터 없이 전국 결과 저장')
    ap.add_argument('--scl', default='아파트', help='용도 소분류 (UI 설정). "전체"면 중분류까지만')
    ap.add_argument('--lcl', default='건물'); ap.add_argument('--mcl', default='주거용건물')
    ap.add_argument('--min-price', type=int, default=None, help='최저가 하한(원)')
    ap.add_argument('--max-price', type=int, default=None, help='최저가 상한(원)')
    ap.add_argument('--area-min', type=float, default=None, help='전용면적 하한(㎡)')
    ap.add_argument('--area-max', type=float, default=None, help='전용면적 상한(㎡)')
    ap.add_argument('--flbd-min', type=int, default=None, help='유찰횟수 하한')
    ap.add_argument('--flbd-max', type=int, default=None, help='유찰횟수 상한')
    ap.add_argument('-o', '--output', default=None)
    ap.add_argument('--no-db', action='store_true', help='DuckDB 자동적재 끔')
    return ap.parse_args()


def sset(page, eid, val):
    return page.evaluate("""([eid,val])=>{const s=document.getElementById(eid);if(!s)return 0;
      const o=[...s.options].find(o=>o.value===val||o.text===val||o.text.includes(val));
      if(!o)return 0;s.value=o.value;s.dispatchEvent(new Event('change',{bubbles:true}));return 1;}""", [eid, val])

def money(v):
    try: return f"{int(v):,}원"
    except: return str(v)
def case_no(it):
    p = it.get('printCsNo', '')
    if p: return ' '.join(p.replace('<br/>', ' ').split())
    return f"{it.get('jiwonNm','').strip()} {it.get('srnSaNo','').strip()}".strip()
def low(it):
    v = it.get('notifyMinmaePrice1') or it.get('minmaePrice') or 0   # ⚠️ notifyMinmaePrice1 필수
    try: return int(v)
    except: return 0
def area(it):
    src = ' '.join(str(it.get(k, '') or '') for k in ('convAddr', 'areaList', 'pjbBuldList'))
    vals = [float(m.replace(',', '')) for m in AREA_RE.findall(src)]
    return max(vals) if vals else None
def giil(v):
    s = str(v or ''); return f"{s[:4]}.{s[4:6]}.{s[6:]}" if len(s) == 8 else s
def row(it):
    r = it.get('notifyMinmaePriceRate1', ''); a = area(it)
    return {'사건번호': case_no(it), '물건소재지': (it.get('printSt', '') or '').strip(),
            '전용면적': f"{a:g}㎡" if a else '', '감정가': money(it.get('gamevalAmt', '')),
            '최저가': money(low(it)), '저감율': f"{r}%" if r not in (None, '') else '',
            '유찰횟수': str(it.get('yuchalCnt', '')), '매각기일': giil(it.get('maeGiil', ''))}


def main():
    args = parse_args()
    prefixes = None
    if not args.no_region:
        if not args.sido:
            sys.exit('--sido 를 주거나 --no-region 을 쓰세요.')
        r = resolve(args.sido)
        if not r: sys.exit(f'시도 "{args.sido}" 를 못 알아봄. sido_codes.py 참조.')
        _, _, prefixes = r
        print(f"▶ 시도 사후필터: {prefixes}")

    cap = {}
    def on_req(rq):
        if 'searchControllerMain' in rq.url and rq.post_data: cap['body'] = rq.post_data
    all_items = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, args=STEALTH)
        c = b.new_context(user_agent=UA, locale="ko-KR", viewport={"width": 1280, "height": 900})
        c.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});window.chrome={runtime:{}};")
        page = c.new_page(); page.on("request", on_req)
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_function("()=>!!document.getElementById('mf_wfm_mainFrame_btn_gdsDtlSrch')", timeout=60000)
        time.sleep(2)
        # 용도만 UI 설정(용도코드 자동생성) → 세션/본문 확보
        sset(page, 'mf_wfm_mainFrame_sbx_rletLclLst', args.lcl); time.sleep(3)
        sset(page, 'mf_wfm_mainFrame_sbx_rletMclLst', args.mcl); time.sleep(3)
        if args.scl != '전체':
            sset(page, 'mf_wfm_mainFrame_sbx_rletSclLst', args.scl)
        time.sleep(1)
        page.evaluate("()=>document.getElementById('mf_wfm_mainFrame_btn_gdsDtlSrch').click()"); time.sleep(6)
        if 'body' not in cap:
            print("❌ 검색 본문 캡처 실패"); b.close(); return
        base = json.loads(cap['body'])
        s = base['dma_srchGdsDtlSrchInfo']
        s['cortOfcCd'] = ''                       # 법원 비움 = 전국
        if args.flbd_min is not None: s['flbdNcntMin'] = str(args.flbd_min)
        if args.flbd_max is not None: s['flbdNcntMax'] = str(args.flbd_max)
        if args.min_price is not None: s['lwsDspslPrcMin'] = str(args.min_price)
        if args.max_price is not None: s['lwsDspslPrcMax'] = str(args.max_price)
        if args.area_min is not None: s['objctArDtsMin'] = str(args.area_min)
        if args.area_max is not None: s['objctArDtsMax'] = str(args.area_max)
        print(f"▶ 서버조건: 최저가 {s.get('lwsDspslPrcMin') or '0'}~{s.get('lwsDspslPrcMax') or '∞'} "
              f"면적 {s.get('objctArDtsMin') or '0'}~{s.get('objctArDtsMax') or '∞'} "
              f"유찰 {s.get('flbdNcntMin') or '0'}~{s.get('flbdNcntMax') or '∞'}")

        def fetch(pno):
            body = json.loads(json.dumps(base))
            body['dma_pageInfo'] = {"pageNo": pno, "pageSize": PAGE_SIZE, "bfPageNo": "",
                                    "startRowNo": "", "totalCnt": "", "totalYn": "Y", "groupTotalCount": ""}
            for _ in range(3):
                res = page.evaluate(FETCH, [API, body])
                if res.get('json'): return res['json']
                time.sleep(2)
            return None

        first = fetch(1)
        if not first: print("❌ 1페이지 실패"); b.close(); return
        d = first.get('data', {})
        total = int(d.get('dma_pageInfo', {}).get('totalCnt') or 0)
        all_items.extend(d.get('dlt_srchResult', []))
        pages = max(1, math.ceil(total / PAGE_SIZE))
        print(f"▶ 전국 totalCnt={total} → {pages}페이지")
        for pno in range(2, pages + 1):
            j = fetch(pno)
            if not j: print(f"  [p{pno}] 실패"); continue
            all_items.extend(j.get('data', {}).get('dlt_srchResult', []))
            print(f"  [p{pno}] 누적 {len(all_items)}")
            time.sleep(0.3)
        b.close()

    # dedup
    seen, dd = set(), []
    for it in all_items:
        k = (case_no(it), (it.get('printSt', '') or '').strip())
        if k[0] and k in seen: continue
        seen.add(k); dd.append(it)
    ok = len(dd) >= total
    print(f"▶ 수집 고유 {len(dd)}/{total} {'✅정합' if ok else '❌누락'}")
    # 시도 사후필터
    if prefixes:
        dd = [it for it in dd if addr_matches(it.get('printSt', ''), prefixes)]
        print(f"▶ 시도 필터 후 {len(dd)}건")

    out = args.output or f"auction_{args.sido or '전국'}_{args.scl}.csv"
    rows = [row(it) for it in dd]
    with open(out, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS); w.writeheader(); w.writerows(rows)
    print(f"✅ {len(rows)}행 → {out}")

    if not args.no_db:
        try:
            import datetime
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            from ingest_to_db import ingest
            ingest(out, f"region_{args.sido or '전국'}_{args.scl}_{datetime.date.today():%Y_%m}")
        except Exception as e:
            print(f"⚠️  DB 자동적재 건너뜀: {e}")


if __name__ == '__main__':
    main()
