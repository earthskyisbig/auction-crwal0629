#!/usr/bin/env python3
"""
법원경매 단일 사건 상세분석기 (courtauction.go.kr)

검색 → 상세페이지(moveDtlPage) 진입 → 5개 문서 데이터 캡처:
  1) 매각물건명세서 (요약: 최선순위설정/배당요구종기/작성일/비고)
  2) 사건상세조회 (csBaseInfo)
  3) 현황조사서 (selectCurstExmndc.on)
  4) 감정평가서요약 (aeeWevlMnpntLst)
  5) 인근매각물건사례 (selectAroundDspslGds.on / selectAroundProgGds.on)

사용:
  python3 analyze_case.py --court 남양주지원 --case 2025타경2412
  python3 analyze_case.py --court 서울중앙지방법원 --year 2025 --caseno 102237 -o out.json

⚠️ 매각물건명세서(임차인 상세)는 매각기일 1주 전, 현황조사서/감정평가서는 2주 전부터 열람 가능.
   그 전에는 임차인 표(점유자/전입/확정일자/보증금/배당요구)가 비어 있을 수 있다.
"""
import argparse, json, re, sys, time
from playwright.sync_api import sync_playwright

SEARCH_URL = "https://www.courtauction.go.kr/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ151F00.xml"

# ── 스텔스 브라우저 (court-auction-scraper 와 동일 패턴) ──────────────
STEALTH_ARGS = ['--no-sandbox', '--disable-blink-features=AutomationControlled',
                '--disable-features=site-per-process', '--lang=ko-KR']
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
INIT_JS = ("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
           "Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});"
           "window.chrome={runtime:{}};")

# WebSquare .on 엔드포인트 in-page fetch (세션 쿠키 재사용)
FETCH_JS = """
async ([url, bodyObj]) => { try {
  const res = await fetch(url,{method:'POST',credentials:'include',
    headers:{'Content-Type':'application/json;charset=UTF-8','Accept':'application/json'},
    body:JSON.stringify(bodyObj)});
  const txt = await res.text(); let j=null; try{ j=JSON.parse(txt); }catch(e){}
  return {status:res.status, json:j, text: j?null:txt.slice(0,300)};
} catch(e){ return {err:String(e)}; } }
"""


def set_select(page, el_id, value):
    return page.evaluate(f"""() => {{const s=document.getElementById('{el_id}'); if(!s)return false;
        const o=Array.from(s.options).find(o=>o.value==='{value}'||o.text==='{value}'||o.text.includes('{value}'));
        if(!o)return false; s.value=o.value; s.dispatchEvent(new Event('change',{{bubbles:true}})); return true;}}""")


def parse_case(args):
    """--case '2025타경2412' 또는 --year/--caseno 조합 → (year, caseno)."""
    if args.case:
        m = re.match(r'\s*(\d{4})\s*타경\s*(\d+)', args.case)
        if not m:
            m = re.match(r'\s*(\d{4})\D+(\d+)', args.case)
        if not m:
            sys.exit(f"사건번호 파싱 실패: {args.case}  (예: 2025타경2412)")
        return m.group(1), m.group(2)
    if args.year and args.caseno:
        return args.year, re.sub(r'\D', '', args.caseno)
    sys.exit("--case '2025타경2412' 또는 --year 2025 --caseno 2412 를 지정하라")


def fmt_won(v):
    try: return f"{int(v):,}원"
    except Exception: return str(v)


def fmt_ymd(v):
    s = str(v or '')
    return f"{s[:4]}.{s[4:6]}.{s[6:8]}" if len(s) >= 8 else s


def _slice(text, starts, ends):
    """text 에서 starts 중 첫 매칭 위치 ~ 그 뒤 ends 중 첫 매칭 위치 사이를 반환."""
    si = -1
    for s in starts:
        si = text.find(s)
        if si != -1:
            break
    if si == -1:
        return ''
    ei = len(text)
    for e in ends:
        j = text.find(e, si)
        if j != -1:
            ei = min(ei, j)
    return text[si:ei]


# ── 매각물건명세서 임차인 표 구조화 (StreamDocs 좌표 기반) ──────────────
_DATE = re.compile(r'20\d{2}\.\s?\d{1,2}\.\s?\d{1,2}\.?')
_AMT = re.compile(r'\d{1,3}(?:,\d{3})+')
_NAME = re.compile(r'^([가-힣]{2,5})\s')


def _reconstruct_lines(runs):
    """StreamDocs runs(rect 포함) → 시각적 라인 리스트(y 내림차순, 각 라인은 x로 정렬).
    텍스트를 그냥 이어붙이면 표 셀이 뒤섞이므로 좌표로 행을 복원한다."""
    items = []
    for r in runs:
        rect = r.get('rect') or []
        if not rect:
            continue
        items.append((rect[0].get('bottom', 0), rect[0].get('left', 0), r.get('text', '')))
    items.sort(key=lambda t: (-t[0], t[1]))
    lines = []
    for y, x, txt in items:
        for ln in lines:
            if abs(ln['y'] - y) <= 5:
                ln['parts'].append((x, txt))
                break
        else:
            lines.append({'y': y, 'parts': [(x, txt)]})
    out = []
    for ln in lines:
        ln['parts'].sort(key=lambda p: p[0])
        out.append({'y': ln['y'], 'text': ' '.join(p[1] for p in ln['parts']).strip()})
    return out


def parse_tenant_table(runs0, chosun_setting=''):
    """명세서 1페이지 runs → 임차인 구조화 + 대항력(인수) 판정.

    반환: {'없음':bool, '임차인':[{성명,보증금,임대차기간시작,전입신고일,확정일자,배당요구일,원문행}],
           '인수위험':bool, '대항력앞선임차인':[성명…]}
    ⚠️ 성명이 줄바꿈된 기관명(예: 주택도시보증공사)은 조각으로 잡힐 수 있어 '원문행'을 항상 병기한다.
    """
    lines = _reconstruct_lines(runs0)
    y_hdr = next((l['y'] for l in lines if '성  명' in l['text'] or '성 명' in l['text']), None)
    y_bigo = next((l['y'] for l in lines if '<비고>' in l['text']), None)
    band = [l for l in lines if (y_bigo or 0) < l['y'] < (y_hdr or 10 ** 9)]
    joined = ' '.join(l['text'] for l in band)
    if '임차내역없음' in joined or '임차 내역 없음' in joined:
        return {'없음': True, '임차인': [], '인수위험': False, '대항력앞선임차인': []}
    tenants = []
    for l in band:
        t = l['text']
        if not (_AMT.search(t) and _DATE.search(t)):
            continue
        amt_m = max(_AMT.finditer(t), key=lambda m: int(m.group().replace(',', '')))
        before = [d.strip() for d in _DATE.findall(t[:amt_m.start()])]
        after = [d.strip() for d in _DATE.findall(t[amt_m.end():])]
        nm = _NAME.match(t)
        tenants.append({
            '성명': nm.group(1) if nm else '(원문참조)',
            '보증금': int(amt_m.group().replace(',', '')),
            '임대차기간시작': before[0] if before else '',
            '전입신고일': after[0] if len(after) > 0 else '',
            '확정일자': after[1] if len(after) > 1 else '',
            '배당요구일': after[2] if len(after) > 2 else '',
            '원문행': re.sub(r'\s{2,}', ' ', t).strip(),
        })
    # 대항력 판정: 전입신고일 < 최선순위설정일 → 보증금 매수인 인수 위험
    def _norm(d):
        m = re.match(r'(20\d{2})\.\s?(\d{1,2})\.\s?(\d{1,2})', (d or '').replace(' ', ''))
        return tuple(int(x) for x in m.groups()) if m else None
    cm = _DATE.search((chosun_setting or '').replace(' ', ''))
    base = _norm(cm.group()) if cm else None
    risky = [t['성명'] for t in tenants if base and _norm(t['전입신고일']) and _norm(t['전입신고일']) < base]
    return {'없음': False, '임차인': tenants, '인수위험': bool(risky), '대항력앞선임차인': risky}


def collect(court, year, caseno, headless=True):
    """검색 → 상세 진입 → dma_result + 현황조사서 + 인근매각/진행 반환."""
    captures = []
    def on_response(r):
        try:
            if r.url.endswith('.on'):
                captures.append({'url': r.url, 'body': r.json()})
        except Exception:
            pass

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, args=STEALTH_ARGS)
        ctx = browser.new_context(user_agent=UA, locale="ko-KR",
                                  viewport={"width": 1280, "height": 900})
        ctx.add_init_script(INIT_JS)
        ctx.on("response", on_response)
        page = ctx.new_page()

        page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_function(
            "() => !!document.getElementById('mf_wfm_mainFrame_btn_gdsDtlSrch')", timeout=60000)
        time.sleep(2)

        # 검색조건: 법원 + 연도 + 사건번호
        if not set_select(page, 'mf_wfm_mainFrame_sbx_rletCortOfc', court):
            print(f"  [경고] 법원 '{court}' 옵션 없음 — 법원명 확인 필요")
        set_select(page, 'mf_wfm_mainFrame_sbx_rletCsYear', year)
        page.evaluate(f"""() => {{const i=document.getElementById('mf_wfm_mainFrame_ibx_rletCsNo');
            i.value='{caseno}'; i.dispatchEvent(new Event('input',{{bubbles:true}}));
            i.dispatchEvent(new Event('change',{{bubbles:true}}));}}""")
        time.sleep(1)
        page.evaluate("() => document.getElementById('mf_wfm_mainFrame_btn_gdsDtlSrch').click()")
        # ⚠️ searchControllerMain 응답은 파이프라인 지연으로 다음 상호작용 때 도착한다.
        #    네트워크 응답이 아니라 결과 그리드 DOM(주소 링크 onclick=moveDtlPage)을 대기한다.
        got_row = False
        for _ in range(25):
            time.sleep(1)
            if page.evaluate("() => { const a=document.querySelector('a[onclick^=\"moveDtlPage\"]'); return !!a; }"):
                got_row = True
                break
        if not got_row:
            browser.close()
            raise RuntimeError(f"검색 결과 없음: {court} {year}타경{caseno} "
                               f"(법원명/사건번호 확인, 또는 사이트 응답 지연)")

        # 상세 진입 (검증된 네비게이션: 주소 링크 onclick=moveDtlPage(idx))
        # ⚠️ 파이프라인 패턴: 첫 moveDtlPage(0)는 지연되어 실제 이동을 안 하는 경우가 많다.
        #    두 번째 호출에서 상세가 로드된다. selectAuctnCsSrchRslt 도착까지 반복 트리거.
        got_detail = False
        for attempt in range(6):
            page.evaluate("() => { try { moveDtlPage(0); } catch(e){} }")
            for _ in range(5):
                time.sleep(1)
                if any('selectAuctnCsSrchRslt' in c['url'] for c in captures):
                    got_detail = True
                    break
            if got_detail:
                break
        if not got_detail:
            browser.close()
            raise RuntimeError("상세 데이터(selectAuctnCsSrchRslt) 캡처 실패")
        time.sleep(2)

        detail = [c for c in captures if 'selectAuctnCsSrchRslt' in c['url']]
        if not detail:
            browser.close()
            raise RuntimeError("상세 데이터(selectAuctnCsSrchRslt) 캡처 실패")
        dma = detail[-1]['body']['data']['dma_result']

        base = dma['csBaseInfo']
        obj = (dma.get('gdsDspslObjctLst') or [{}])[0]
        cort_cd = base.get('cortOfcCd', '')
        user_cs = base.get('userCsNo', f"{year}타경{caseno}")

        # 현황조사서
        curst = page.evaluate(FETCH_JS, ["/pgj/pgj15B/selectCurstExmndc.on",
            {"dma_srchCurstExmn": {"cortOfcCd": cort_cd, "csNo": user_cs,
                                   "auctnInfOriginDvsCd": "2", "ordTsCnt": ""}}])

        # 인근매각 / 인근진행 (동일 시군구·용도 기준)
        near_body = {"csNo": user_cs, "cortOfcCd": cort_cd, "dspslGdsSeq": "1",
                     "rletCarDvsCd": "0",
                     "rprsAdongSdCd": obj.get('rprsAdongSdCd', ''),
                     "rprsAdongSggCd": obj.get('rprsAdongSggCd', ''),
                     "auctnGdsUsgCd": dma.get('dspslGdsDxdyInfo', {}).get('auctnGdsUsgCd', '01')}
        near_sold = page.evaluate(FETCH_JS, ["/pgj/pgjsearch/selectAroundDspslGds.on", near_body])
        near_prog = page.evaluate(FETCH_JS, ["/pgj/pgjsearch/selectAroundProgGds.on", near_body])

        browser.close()

    return {
        'dma_result': dma,
        'curst': (curst or {}).get('json'),
        'near_sold': ((near_sold or {}).get('json') or {}).get('data', {}).get('result', []),
        'near_prog': ((near_prog or {}).get('json') or {}).get('data', {}).get('result', []),
    }


def fetch_myseseo(court, year, caseno, headless=True):
    """매각물건명세서 PDF 텍스트 추출 — **독립 브라우저 세션**(검증된 순서).

    ⚠️ 왜 별도 세션인가: 명세서 버튼 핸들러는 로그 XHR + window.open(뷰어)를 하는데,
       collect()의 상세 세션 안에서 누르면 window.open이 뜨지 않고 로그만 발생하는
       재현 불가한 상태가 있었다. 검색→상세→명세서 클릭만 하는 깨끗한 세션에서는 항상
       뷰어(ecfs getPdf → StreamDocs)가 뜬다. docId 확보 후 /texts/{page} 로 텍스트 추출.

    반환: 미공개(버튼 없음)면 None, 공개인데 추출 실패면 [], 성공하면 페이지 텍스트 list.
    """
    docids = []
    def on_request(r):
        m = re.search(r'/streamdocs/v4/documents/([^/]+)/', r.url)
        if m:
            docids.append(m.group(1))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, args=STEALTH_ARGS)
        ctx = browser.new_context(user_agent=UA, locale="ko-KR",
                                  viewport={"width": 1280, "height": 900})
        ctx.add_init_script(INIT_JS)
        ctx.on("request", on_request)
        page = ctx.new_page()

        page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_function(
            "() => !!document.getElementById('mf_wfm_mainFrame_btn_gdsDtlSrch')", timeout=60000)
        time.sleep(2)
        set_select(page, 'mf_wfm_mainFrame_sbx_rletCortOfc', court)
        set_select(page, 'mf_wfm_mainFrame_sbx_rletCsYear', year)
        page.evaluate(f"""() => {{const i=document.getElementById('mf_wfm_mainFrame_ibx_rletCsNo');
            i.value='{caseno}'; i.dispatchEvent(new Event('input',{{bubbles:true}}));
            i.dispatchEvent(new Event('change',{{bubbles:true}}));}}""")
        time.sleep(1)
        page.evaluate("() => document.getElementById('mf_wfm_mainFrame_btn_gdsDtlSrch').click()")
        got_row = False
        for _ in range(25):
            time.sleep(1)
            if page.evaluate("() => !!document.querySelector('a[onclick^=\"moveDtlPage\"]')"):
                got_row = True
                break
        if not got_row:
            browser.close()
            return []
        # moveDtlPage → 명세서 버튼 출현까지 (버튼 없으면 미공개)
        has_btn = False
        for _ in range(6):
            page.evaluate("() => { try { moveDtlPage(0); } catch(e){} }")
            time.sleep(3)
            has_btn = page.evaluate(
                "() => !!document.getElementById('mf_wfm_mainFrame_btn_dspslGdsSpcfc1')")
            if has_btn:
                break
        if not has_btn:
            browser.close()
            return None   # 매각기일 1주 전 이전 → 명세서 미공개
        # 네이티브 클릭만이 window.open(뷰어)을 띄운다. docId 잡힐 때까지 재시도.
        for _ in range(4):
            try:
                page.locator('#mf_wfm_mainFrame_btn_dspslGdsSpcfc1').click(timeout=5000)
            except Exception:
                page.evaluate("() => { try { $p.getComponentById("
                              "'mf_wfm_mainFrame_btn_dspslGdsSpcfc1').click(); } catch(e){} }")
            for _ in range(12):
                time.sleep(1)
                if docids:
                    break
            if docids:
                break
        if not docids:
            browser.close()
            return []
        docid = docids[-1]
        base = f"https://pvo.scourt.go.kr/streamdocs/v4/documents/{docid}"
        pages, runs0 = [], None
        for i in range(15):
            try:
                r = ctx.request.get(f"{base}/texts/{i}")
            except Exception:
                break
            if r.status != 200:
                break
            try:
                runs = r.json()
            except Exception:
                break
            if i == 0:
                runs0 = runs   # 1페이지 원본 runs(좌표) → 임차인 표 구조화용
            pages.append(''.join(run.get('text', '') for run in runs))
        browser.close()
    return {'texts': pages, 'runs0': runs0 or []}


def build_report(data):
    """캡처 데이터 → 사람이 읽는 요약 dict."""
    dma = data['dma_result']
    base = dma['csBaseInfo']
    dxdy = dma.get('dspslGdsDxdyInfo', {})
    obj = (dma.get('gdsDspslObjctLst') or [{}])[0]
    demn = (dma.get('dstrtDemnInfo') or [{}])[0]

    # 1) 사건상세
    case = {
        '법원': f"{base.get('cortOfcNm','')} {base.get('cortSptNm','')}".strip(),
        '담당계': base.get('cortAuctnJdbnNm',''), '전화': base.get('jdbnTelno',''),
        '사건번호': base.get('userCsNo',''), '사건명': base.get('csNm',''),
        '사건접수': fmt_ymd(base.get('csRcptYmd')), '개시결정': fmt_ymd(base.get('csCmdcYmd')),
        '배당요구종기': fmt_ymd(demn.get('dstrtDemnLstprdYmd')),
        '청구금액': fmt_won(base.get('clmAmt')),
    }
    # 2) 물건
    _gam = int(dxdy.get('aeeEvlAmt') or 0)
    _low = int(dxdy.get('fstPbancLwsDspslPrc') or 0)
    prop = {
        '소재지': obj.get('userPrintSt',''), '단지': obj.get('bldNm',''),
        '동호': obj.get('bldDtlDts',''), '면적': (obj.get('objctArDts') or '').strip(),
        '감정평가액': fmt_won(dxdy.get('aeeEvlAmt')),
        '최저매각가격': fmt_won(dxdy.get('fstPbancLwsDspslPrc')),
        '저감율': f"{round(_low/_gam*100)}%" if _gam and _low else '',
        '유찰횟수': dxdy.get('flbdNcnt',''),
        '매각기일': f"{fmt_ymd(dxdy.get('dspslDxdyYmd'))} {str(dxdy.get('fstDspslHm','')).zfill(4)[:2]}:{str(dxdy.get('fstDspslHm','')).zfill(4)[2:]}",
        '매각장소': dxdy.get('dspslPlcNm',''),
        '매각결정기일': fmt_ymd(dxdy.get('dspslDcsnDxdyYmd')),
        '보증금률': f"{dxdy.get('prchDposRate','')}%",
    }
    # 3) 매각물건명세서 — 요약(dma_result) + PDF 전문(StreamDocs 텍스트 레이어)
    myse = {
        '명세서작성일': fmt_ymd(dxdy.get('gdsSpcfcWrtYmd')),
        '최선순위설정': dxdy.get('tprtyRnkHypthcStngDts',''),
        '배당요구종기': fmt_ymd(demn.get('dstrtDemnLstprdYmd')),
        '비고': (dxdy.get('gdsSpcfcRmk') or '').strip(),
    }
    myse_res = data.get('myse')
    myse_texts = myse_res.get('texts') if isinstance(myse_res, dict) else myse_res
    myse_runs0 = myse_res.get('runs0') if isinstance(myse_res, dict) else None
    if myse_res is None:
        myse['공개여부'] = '미공개 (매각기일 1주 전부터 열람 — 아직 버튼 없음)'
    elif not myse_texts:
        myse['공개여부'] = '공개(버튼 존재) 되었으나 PDF 텍스트 추출 실패 — 재시도 필요'
    else:
        myse['공개여부'] = '공개'
        full = '\n'.join(myse_texts)
        # 임차인 표 구조화 (좌표 기반)
        parsed = parse_tenant_table(myse_runs0 or [], myse.get('최선순위설정', ''))
        if parsed.get('없음'):
            myse['임차인'] = []
            myse['임차인_비고'] = '명세서상 "조사된 임차내역 없음"'
        else:
            myse['임차인'] = parsed['임차인']
            myse['인수위험'] = parsed['인수위험']
            if parsed['인수위험']:
                myse['대항력앞선임차인'] = parsed['대항력앞선임차인']
        # 점유자 표 원문(구조화 실패/검증 대비 항상 병기)
        p0 = myse_texts[0]
        occ = _slice(p0, ['점유자', '점유의', '성  명', '성명'], ['등기된 부동산', '매각에 따라', '※1'])
        myse['점유자_권리_전문'] = re.sub(r'\s{2,}', ' ', occ).strip() if occ else ''
        # 대항력 인수 주의 문구 / 특별매각조건
        m = re.search(r'※\s*최선순위[^※]*?바랍니다\.', full)
        if m: myse['인수주의'] = re.sub(r'\s{2,}', ' ', m.group(0)).strip()
        m = re.search(r'특별매각조건[^\n]*', full)
        if m: myse['특별매각조건'] = re.sub(r'\s{2,}', ' ', m.group(0)).strip()
        myse['_전문'] = myse_texts   # 원본 보존
    # 4) 기일이력
    dxdy_lst = []
    for d in dma.get('gdsDspslDxdyLst', []):
        RSLT = {'002': '유찰', '001': '매각', '003': '변경', '004': '취하', '005': '기각'}
        KND = {'01': '매각기일', '02': '매각결정기일', '03': '대금지급기한'}
        dxdy_lst.append({
            '기일': f"{fmt_ymd(d.get('dxdyYmd'))} {str(d.get('dxdyHm','')).zfill(4)[:2]}:{str(d.get('dxdyHm','')).zfill(4)[2:]}",
            '종류': KND.get(d.get('auctnDxdyKndCd',''), d.get('auctnDxdyKndCd','')),
            '최저가': fmt_won(d.get('tsLwsDspslPrc')) if d.get('tsLwsDspslPrc') else '',
            '결과': RSLT.get(d.get('auctnDxdyRsltCd',''), ''),
        })
    # 5) 감정평가 요항
    ITM = {'00083001':'위치/주위환경','00083003':'교통상황','00083015':'건물구조','00083006':'이용상태',
           '00083017':'설비내역','00083009':'토지형상/이용','00083005':'인접도로','00083011':'공법상제한',
           '00083014':'공부와의차이','00083026':'임대차/기타'}
    aee = [{'항목': ITM.get(a.get('aeeWevlMnpntItmCd',''), a.get('aeeWevlMnpntItmCd','')),
            '내용': (a.get('aeeWevlMnpntCtt') or '').strip()} for a in dma.get('aeeWevlMnpntLst', [])]

    # 3) 현황조사서
    curst_out = {'점유관계': '', '임차인': [], '조사일시': '', '중복사건': []}
    cj = data.get('curst')
    if cj:
        cd = cj.get('data', cj)
        mng = cd.get('dma_curstExmnMngInf', {})
        curst_out['조사일시'] = (mng.get('exmnDtDts') or '').strip()
        for o in cd.get('dlt_ordTsRlet', []):
            if o.get('gdsPossCtt'):
                curst_out['점유관계'] = re.sub(r'<[^>]+>', ' ', o['gdsPossCtt']).strip()
        for l in cd.get('dlt_ordTsLserLtn', []):
            curst_out['임차인'].append({
                '성명': l.get('lseeNm',''), '점유부분': l.get('possPortDts',''),
                '보증금': fmt_won(l.get('scrtAmt')) if l.get('scrtAmt') else '',
                '차임': l.get('mrnt',''), '전입일': fmt_ymd(l.get('mvinYmd')),
                '확정일자': fmt_ymd(l.get('fixtnDt')), '배당요구': l.get('dstrtDemnYn',''),
            })
        for dp in cd.get('dlt_curstExmnDpcnMrg', []):
            curst_out['중복사건'].append(dp.get('userRletCsNo', dp.get('userCsNo','')))
    if not curst_out['임차인']:
        curst_out['임차인_비고'] = "현황조사상 신고·조사된 임차인 내역 없음"

    # 5) 인근매각 사례 (매각완료 = maeAmt 有), 동일 읍면동 우선
    def comp_row(it):
        g = int(it.get('gamevalAmt') or 0); m = int(it.get('maeAmt') or 0)
        return {'사건': it.get('srnSaNo') or '', '읍면동': it.get('hjguDong') or '',
                '단지': it.get('buldNm') or '', '면적': (it.get('pjbBuldList') or '').strip(),
                '감정가': g, '낙찰가': m, '매각가율': round(m/g*100,1) if g and m else None,
                '유찰': it.get('yuchalCnt',''), '매각기일': fmt_ymd(it.get('maeGiil'))}
    sold = [comp_row(it) for it in data.get('near_sold', []) if int(it.get('maeAmt') or 0) > 0]
    same_dong = obj.get('adongEmdNm') or ''
    bld4 = (obj.get('bldNm') or '')[:4]   # 단지명 없는 다세대 등은 None → '' 처리
    near = {
        '조건': f"{obj.get('adongSggNm') or ''} {same_dong} 인근".strip(),
        '전체매각완료건수': len(sold),
        '동일단지사례': [c for c in sold if bld4 and bld4 in c['단지']],
        '동일읍면동사례': [c for c in sold if c['읍면동'] == same_dong][:40],
    }
    if sold:
        rates = [c['매각가율'] for c in sold if c['읍면동'] == same_dong and c['매각가율']]
        if rates:
            near['동일읍면동_평균매각가율'] = round(sum(rates)/len(rates), 1)
            near['동일읍면동_매각가율범위'] = [min(rates), max(rates)]

    return {'사건상세조회': case, '물건개요': prop, '매각물건명세서': myse,
            '기일내역': dxdy_lst, '현황조사서': curst_out, '감정평가서요약': aee,
            '인근매각물건사례': near}


def print_report(rep):
    def line(k, v): print(f"  {k:14}: {v}")
    print("\n" + "="*70)
    print("  법원경매 물건 상세분석")
    print("="*70)

    print("\n■ 물건개요")
    for k, v in rep['물건개요'].items():
        if v and not k.startswith('_'): line(k, v)

    print("\n■ 1. 매각물건명세서")
    m = rep['매각물건명세서']
    for k in ['공개여부', '명세서작성일', '최선순위설정', '배당요구종기', '비고']:
        if m.get(k): line(k, m[k])
    # 구조화 임차인
    if '임차인' in m:
        if not m['임차인']:
            line('임차인', m.get('임차인_비고', '없음'))
        else:
            print(f"  ── 임차인 {len(m['임차인'])}명 (명세서 구조화) ──")
            for t in m['임차인']:
                print(f"    · {t['성명']:<8} 보증금 {t['보증금']:,}원 "
                      f"| 전입 {t['전입신고일'] or '-'} 확정 {t['확정일자'] or '-'} "
                      f"배당요구 {t['배당요구일'] or '-'}")
                print(f"      원문: {t['원문행']}")
            if m.get('인수위험'):
                print(f"  🔴 인수위험: 최선순위설정보다 대항요건 앞선 임차인 → {', '.join(m.get('대항력앞선임차인', []))} "
                      f"(보증금 매수인 인수 가능)")
    if m.get('인수주의'): print("  ⚠️ " + m['인수주의'])
    if m.get('특별매각조건'): print("  ★ " + m['특별매각조건'])

    print("\n■ 2. 사건상세조회")
    for k, v in rep['사건상세조회'].items():
        if v: line(k, v)

    print("\n■ 기일내역")
    for d in rep['기일내역']:
        print(f"    {d['기일']}  {d['종류']:8} {d['최저가']:>16}  {d['결과']}")

    print("\n■ 3. 현황조사서")
    c = rep['현황조사서']
    if c.get('조사일시'): line('조사일시', c['조사일시'])
    if c.get('점유관계'): line('점유관계', c['점유관계'])
    if c.get('중복사건'): line('중복사건', ', '.join(c['중복사건']))
    if c['임차인']:
        for t in c['임차인']:
            print(f"    임차인: {t}")
    else:
        line('임차인', c.get('임차인_비고', '없음'))

    print("\n■ 4. 감정평가서요약")
    for a in rep['감정평가서요약']:
        print(f"    [{a['항목']}] {a['내용']}")

    print("\n■ 5. 인근매각물건사례")
    n = rep['인근매각물건사례']
    line('조건', n['조건'])
    line('매각완료 건수', n['전체매각완료건수'])
    if n.get('동일읍면동_평균매각가율'):
        line('동일읍면동 평균매각가율', f"{n['동일읍면동_평균매각가율']}%  범위 {n['동일읍면동_매각가율범위']}")
    if n['동일단지사례']:
        print("    ▶ 동일단지 사례:")
        for c in n['동일단지사례']:
            print(f"      {c['사건']} {c['단지']} {c['면적']} | 감정 {c['감정가']/1e8:.2f}억 낙찰 {c['낙찰가']/1e8:.2f}억 ({c['매각가율']}%) 유찰{c['유찰']}")
    print(f"    ▶ 동일읍면동 사례 {len(n['동일읍면동사례'])}건 (상세는 JSON 참조)")
    print("\n" + "="*70)
    print("⚠️ 매각물건명세서 임차인 상세는 매각기일 1주 전부터 공개. 등기부·전입세대열람 별도 확인 필수.")
    print("="*70)


def run_with_retry(fn, label, attempts=3, delay=5):
    """사이트 flakiness 대응 — fn()을 최대 attempts회 재시도. 마지막 실패는 그대로 raise."""
    last = None
    for i in range(1, attempts + 1):
        try:
            return fn()
        except Exception as e:
            last = e
            print(f"  [{label}] 시도 {i}/{attempts} 실패: {e}")
            if i < attempts:
                time.sleep(delay)
    raise last


def main():
    ap = argparse.ArgumentParser(description='법원경매 단일 사건 상세분석기')
    ap.add_argument('--court', required=True, help='법원명 (예: 남양주지원, 서울중앙지방법원)')
    ap.add_argument('--case', help="사건번호 (예: '2025타경2412')")
    ap.add_argument('--year', help='사건 연도 (예: 2025)')
    ap.add_argument('--caseno', help='사건번호 숫자 (예: 2412)')
    ap.add_argument('-o', '--output', default=None, help='원본 JSON 저장 경로')
    ap.add_argument('--no-headless', action='store_true', help='브라우저 표시(디버그)')
    args = ap.parse_args()

    year, caseno = parse_case(args)
    hl = not args.no_headless
    print(f"▶ 분석 대상: {args.court} {year}타경{caseno}")
    try:
        data = run_with_retry(lambda: collect(args.court, year, caseno, headless=hl),
                              '4개문서 수집', attempts=3)
    except Exception as e:
        sys.exit(f"❌ 수집 실패(3회 재시도 후): {e}")

    # 매각물건명세서는 별도 세션에서 추출(window.open 뷰어 안정성 위해).
    #   None=미공개, []=추출실패 → []면 1회 더 재시도, 그래도 []면 그대로 둔다(명세서만 실패, 나머지 유지).
    print("▶ 매각물건명세서 추출(별도 세션)...")
    def _myse():
        r = fetch_myseseo(args.court, year, caseno, headless=hl)
        if isinstance(r, dict) and not r.get('texts'):
            raise RuntimeError("명세서 PDF 텍스트 추출 실패")
        if r == []:
            raise RuntimeError("명세서 뷰어 docId 미포착")
        return r
    try:
        data['myse'] = run_with_retry(_myse, '명세서', attempts=2)
    except Exception as e:
        print(f"  명세서 추출 최종 실패({e}) — 나머지 4개 문서로 진행")
        data['myse'] = []
    rep = build_report(data)
    print_report(rep)

    out = args.output or f"case_{year}타경{caseno}.json"
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'raw': data, 'report': rep}, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 원본+리포트 저장 → {out}")


if __name__ == '__main__':
    main()
