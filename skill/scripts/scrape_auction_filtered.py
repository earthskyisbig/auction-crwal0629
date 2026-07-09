#!/usr/bin/env python3
"""
법원경매 물건 수집기 (courtauction.go.kr) — 템플릿/파라미터 기반 지역·용도 서버사이드 필터 검색.
court-auction-scraper 스킬의 스텔스 + WebSquare 패턴을 기반으로, 법원/시도/시군구/용도(대·중·소분류)/유찰횟수
필터를 검색 폼에 설정한 뒤 결과를 hjguSigu 로 사후 필터링해 정확한 목록을 CSV로 낸다.

사용 예:
  python3 scrape_auction_filtered.py -t templates/gangnam_apt.json -o _workspace/01_listings.csv
  python3 scrape_auction_filtered.py -t templates/uijeongbu_yangju_apt.json
  python3 scrape_auction_filtered.py --court 서울중앙지방법원 --sido 서울특별시 --sgg 강남구 --scl 아파트 --flbd-min 전체
  python3 scrape_auction_filtered.py -t templates/gangnam_apt.json --sgg 서초구

출력 컬럼: 사건번호, 물건소재지(단지명·동·호 포함), 전용면적, 감정가, 최저가, 저감율, 유찰횟수, 매각기일

수집: 다중 페이지그룹 순회로 100건(10페이지) 한도를 넘어 수집한다(nextPage_btn).

⚠️ 한계 — 시/군/구(sgg) 서버 필터 미적용:
  법원/용도/유찰은 서버에 등록되나, 시/군/구 cascade는 프로그램적 설정으로
  서버 세션에 등록되지 않는다(실제 사이트는 사용자 클릭 시 발생하는 AJAX로 등록).
  따라서 --sgg 는 결과를 hjguSigu 로 '사후 필터'할 뿐, 서버는 해당 법원 관할 전체를
  반환한다. 관할 물건이 매우 많으면(수백 건) 다중 그룹 수집에도 특정 시/군/구 물건이
  누락될 수 있다. 소규모 시/군/구 정밀·완전 검색이 필요하면 사이트 자체 검색이 정답이다.
  (넓은 범위 스윕/모니터링 용도로는 적합)
"""

import argparse
import csv
import json
import os
import re
import time
from playwright.sync_api import sync_playwright

TARGET_URL = "https://www.courtauction.go.kr/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ151F00.xml"
COLUMNS = ['사건번호', '물건소재지', '전용면적', '감정가', '최저가', '저감율', '유찰횟수', '매각기일']
AREA_RE = re.compile(r'([\d,]+(?:\.\d+)?)\s*㎡')

# 법원 그룹 — 여러 법원을 한 번에 순차 검색
COURT_GROUPS = {
    '서울전체': [
        '서울중앙지방법원', '서울동부지방법원', '서울남부지방법원',
        '서울북부지방법원', '서울서부지방법원',
    ],
    '경기전체': [
        '의정부지방법원', '수원지방법원', '인천지방법원',
        '성남지원', '부천지원', '고양지원', '안산지원', '안양지원',
    ],
}


DEFAULTS = {
    'court':     '의정부지방법원',
    'sido':      None,
    'sgg':       None,
    'lcl':       '건물',
    'mcl':       '주거용건물',
    'scl':       '아파트',
    'flbd_min':  '1회',
    'max_price': None,
    'output':    None,
}


def parse_args():
    parser = argparse.ArgumentParser(description='법원경매 물건 수집기')
    parser.add_argument('-t', '--template', default=None,        help='템플릿 JSON 파일 경로 (templates/*.json)')
    parser.add_argument('--court',          default=None,        help='법원명 ("전체" 입력 시 전국)')
    parser.add_argument('--sido',           default=None,        help='시/도 (예: 서울특별시)')
    parser.add_argument('--sgg',            default=None,        help='시/군/구 (예: 금천구)')
    parser.add_argument('--lcl',            default=None,        help='용도 대분류')
    parser.add_argument('--mcl',            default=None,        help='용도 중분류')
    parser.add_argument('--scl',            default=None,        help='용도 소분류 ("전체" 입력 시 생략)')
    parser.add_argument('--flbd-min',       default=None,        help='유찰횟수 최솟값 ("전체" 입력 시 생략)')
    parser.add_argument('--max-price',      default=None, type=int, help='최저가 상한 (원 단위, 예: 500000000)')
    parser.add_argument('-o', '--output',   default=None,        help='출력 CSV 파일명 (기본: 자동 생성)')
    args = parser.parse_args()

    # 우선순위: CLI 인자 > 템플릿 > 기본값
    merged = dict(DEFAULTS)
    if args.template:
        tpl_path = args.template
        if not os.path.isabs(tpl_path):
            tpl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), tpl_path)
        with open(tpl_path, encoding='utf-8') as f:
            merged.update(json.load(f))
        print(f"▶ 템플릿 로드: {args.template}")
    for key in ['court', 'sido', 'sgg', 'lcl', 'mcl', 'scl', 'output', 'max_price']:
        if getattr(args, key) is not None:
            merged[key] = getattr(args, key)
    if args.flbd_min is not None:
        merged['flbd_min'] = args.flbd_min

    # argparse Namespace로 변환
    for key, val in merged.items():
        setattr(args, key, val)
    return args


def make_output_path(args):
    if args.output:
        return args.output
    court = args.court.replace('지방법원', '').replace('전체', '전국')
    # --sido가 쉼표로 여러 지역일 경우 축약
    if args.sido:
        sido_parts = [s.strip().replace('특별시','').replace('광역시','').replace('특별자치도','').replace('도','') for s in args.sido.split(',')]
        area = '+'.join(sido_parts)
    else:
        area = args.sgg or ''
    scl   = args.scl if args.scl != '전체' else args.mcl
    flbd  = args.flbd_min.replace('전체', '전체유찰')
    price = f'최저{args.max_price//100000000}억이하' if args.max_price else ''
    parts = [p for p in [court, area, scl, f'유찰{flbd}', price] if p]
    name  = f"auction_{'_'.join(parts)}.csv"
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), name)


def fmt_money(val):
    try:
        return f"{int(val):,}원"
    except Exception:
        return str(val)


def build_address(item):
    parts = [item.get('hjguSido', ''), item.get('hjguSigu', ''),
             item.get('hjguDong', ''), item.get('daepyoLotno', '')]
    addr  = ' '.join(p for p in parts if p.strip())
    extra = item.get('convAddr', '').strip()
    full  = (addr + (' ' + extra if extra else '')).strip()
    return ' '.join(full.split())


def build_case_no(item):
    # printCsNo 는 중복사건(<br/>...(중복))까지 포함한 완전한 표기
    p = item.get('printCsNo', '')
    if p:
        return ' '.join(p.replace('<br/>', ' ').split())
    court = item.get('jiwonNm', '').strip()
    case  = item.get('srnSaNo', '').strip()
    return f"{court} {case}".strip() if court else case or str(item.get('saNo', ''))


def low_price(item):
    """현재 최저매각가격. notifyMinmaePrice1 이 정답(minmaePrice 는 최초가=감정가인 경우가 많음)."""
    v = item.get('notifyMinmaePrice1') or item.get('minmaePrice') or 0
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def fmt_giil(v):
    s = str(v or '')
    return f"{s[:4]}.{s[4:6]}.{s[6:]}" if len(s) == 8 else s


def parse_area(item):
    """전용면적(㎡) — convAddr/areaList/pjbBuldList 의 ㎡ 값 중 최댓값."""
    src = ' '.join(str(item.get(k, '') or '') for k in ('convAddr', 'areaList', 'pjbBuldList'))
    vals = [float(m.replace(',', '')) for m in AREA_RE.findall(src)]
    return max(vals) if vals else None


def convert_item(item):
    rate = item.get('notifyMinmaePriceRate1', '')
    area = parse_area(item)
    return {
        '사건번호':   build_case_no(item),
        '물건소재지': (item.get('printSt', '') or '').strip() or build_address(item),
        '전용면적':   f"{area:g}㎡" if area else '',
        '감정가':     fmt_money(item.get('gamevalAmt', '')),
        '최저가':     fmt_money(low_price(item)),
        '저감율':     f"{rate}%" if rate not in (None, '') else '',
        '유찰횟수':   str(item.get('yuchalCnt', '')),
        '매각기일':   fmt_giil(item.get('maeGiil', '')),
    }


def get_max_page(page):
    return page.evaluate("""
    () => {
        const links = Array.from(document.querySelectorAll('[id*="pgl_gdsDtlSrchPage_page_"]'));
        const nums  = links.map(el => { const m = el.id.match(/_page_(\\d+)$/); return m ? +m[1] : 0; });
        return nums.length ? Math.max(...nums) : 0;
    }
    """)


def set_select(page, el_id, value):
    result = page.evaluate(f"""
    () => {{
        const sel = document.getElementById('{el_id}');
        if (!sel) return {{ok: false, err: 'not found'}};
        const opts = Array.from(sel.options);
        const opt  = opts.find(o => o.value === '{value}' || o.text === '{value}' || o.text.includes('{value}'));
        if (!opt) return {{ok: false, opts: opts.map(o => o.text)}};
        sel.value = opt.value;
        sel.dispatchEvent(new Event('change', {{bubbles: true}}));
        return {{ok: true, text: opt.text}};
    }}
    """)
    if not result.get('ok'):
        print(f"  [경고] {el_id} 에서 '{value}' 없음. 옵션: {result.get('opts', [])}")
    return result.get('ok', False)


def load_search_form(page):
    """검색 폼 페이지 로드 + WebSquare 초기화 대기 (매 검색 전 폼 리셋용)."""
    page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_function(
            "() => !!document.getElementById('mf_wfm_mainFrame_btn_gdsDtlSrch')",
            timeout=60000
        )
    except Exception as e:
        print(f"  [경고] 초기화 대기 실패: {e}")
        time.sleep(15)
    time.sleep(2)


def _unique_count(all_items):
    return len({build_case_no(it) for it in all_items})


def _click_and_wait_for_growth(page, response_flag, all_items, click_js, max_retries=3, wait_secs=15):
    """클릭 → 응답 대기 → '고유 건수가 실제로 늘었는지' 검증. 안 늘면 재시도.
    반환: (응답_수신여부, 신규건수_증가여부)"""
    before = _unique_count(all_items)
    for attempt in range(1, max_retries + 1):
        response_flag[0] = False
        page.evaluate(click_js)
        got_response = False
        for _ in range(wait_secs):
            time.sleep(1)
            if response_flag[0]:
                got_response = True
                break
        time.sleep(0.3)
        after = _unique_count(all_items)
        if after > before:
            return True, True
        if attempt < max_retries:
            print(f"    [재시도 {attempt}/{max_retries - 1}] 응답={got_response} 신규건수 증가 없음 → 재클릭")
            time.sleep(1.5)
    return got_response, False


def run_search(page, args, court, response_flag, all_items, total_cnt_holder):
    """단일 법원에 대해 검색 조건 설정 → 검색 실행 → 다중 페이지그룹 수집(검증·재시도 포함)."""
    # 검색 후 폼이 결과 화면으로 바뀌므로 매 법원마다 폼을 새로 로드
    load_search_form(page)

    print(f"\n▶ [{court or '전체'}] 검색 조건 설정...")

    # 법원
    if court and court != '전체':
        set_select(page, 'mf_wfm_mainFrame_sbx_rletCortOfc', court)
        print(f"  법원: {court}")

    # 유찰횟수
    if args.flbd_min != '전체':
        set_select(page, 'mf_wfm_mainFrame_sbx_rletFlbdCntMin', args.flbd_min)
        print(f"  유찰횟수: {args.flbd_min} 이상")

    # 지역 (시/도 → 시/군/구 순서)
    if args.sido:
        set_select(page, 'mf_wfm_mainFrame_sbx_rletAdongSdS', args.sido)
        time.sleep(2)
        print(f"  시/도: {args.sido}")
    if args.sgg:
        set_select(page, 'mf_wfm_mainFrame_sbx_rletAdongSggS', args.sgg)
        print(f"  시/군/구: {args.sgg}")
        time.sleep(1)

    # 용도 대분류 > 중분류 > 소분류
    set_select(page, 'mf_wfm_mainFrame_sbx_rletLclLst', args.lcl)
    time.sleep(3)
    set_select(page, 'mf_wfm_mainFrame_sbx_rletMclLst', args.mcl)
    time.sleep(3)
    if args.scl != '전체':
        set_select(page, 'mf_wfm_mainFrame_sbx_rletSclLst', args.scl)
    print(f"  용도: {args.lcl} > {args.mcl}" + (f" > {args.scl}" if args.scl != '전체' else ''))
    time.sleep(1)

    # 검색 실행
    print("▶ 검색 실행...")
    total_cnt_holder[0] = None
    response_flag[0] = False
    page.evaluate("() => { document.getElementById('mf_wfm_mainFrame_btn_gdsDtlSrch').click(); }")
    for _ in range(30):
        time.sleep(1)
        if response_flag[0]:
            response_flag[0] = False
            break
    time.sleep(2)

    if total_cnt_holder[0] is not None:
        print(f"  ▶ 사이트 보고 총건수(totalCnt): {total_cnt_holder[0]}")
    else:
        print("  [경고] totalCnt를 응답에서 못 읽음 — 정합성 검증 불가")

    # 페이지네이션 — 다중 페이지그룹 수집 (100건/10페이지 한도 극복)
    # WebSquare 페이저는 그룹마다 페이지 라벨(1~10)을 재사용하므로, 그룹 내 라벨 순회 →
    # 다음그룹(nextPage_btn) 클릭을 반복한다.
    # ⚠️ 파이프라인 지연 때문에 클릭→응답이 와도 실제로는 '이전 페이지의 지연 응답'일 수 있어
    #    응답 수신만으로는 페이지 이동을 신뢰할 수 없다. 그래서 클릭마다 '고유 건수가
    #    실제로 늘었는지'를 검증하고, 안 늘면 같은 자리에서 재클릭한다(_click_and_wait_for_growth).
    def _labels():
        return page.evaluate("""() => [...document.querySelectorAll('[id*="pgl_gdsDtlSrchPage_page_"]')]
            .map(e => { const m = e.id.match(/_page_(\\d+)$/); return m ? +m[1] : 0; })
            .filter(x => x > 1)""")
    group, dry, failed_clicks = 0, 0, []
    while group < 60:
        # 단일 페이지(다음 페이지·그룹 없음)면 즉시 종료
        if not _labels() and page.evaluate("""() => {
            const e = document.getElementById('mf_wfm_mainFrame_pgl_gdsDtlSrchPage_nextPage_btn');
            return !e || /last|disabled|end/.test(e.className); }"""):
            break
        before = _unique_count(all_items)
        remaining_target = total_cnt_holder[0] is None or _unique_count(all_items) < total_cnt_holder[0]
        for n in sorted(set(_labels())):
            if not remaining_target:
                break
            click_js = f"() => {{ const e = document.getElementById('mf_wfm_mainFrame_pgl_gdsDtlSrchPage_page_{n}'); if (e) e.click(); }}"
            got_resp, grew = _click_and_wait_for_growth(page, response_flag, all_items, click_js)
            if not grew:
                # 마지막 페이지라 정말 신규가 없는 경우일 수도 있으니 totalCnt로만 판단
                if total_cnt_holder[0] is not None and _unique_count(all_items) < total_cnt_holder[0]:
                    failed_clicks.append(f"그룹{group}-페이지{n}")
                    print(f"    [경고] 그룹{group} 페이지{n}: 재시도 후에도 신규 없음 (누적 {_unique_count(all_items)}/{total_cnt_holder[0]})")
            remaining_target = total_cnt_holder[0] is None or _unique_count(all_items) < total_cnt_holder[0]
        # 다음 페이지그룹으로 이동
        state = page.evaluate("""() => {
            const e = document.getElementById('mf_wfm_mainFrame_pgl_gdsDtlSrchPage_nextPage_btn');
            if (!e) return 'none';
            if (/last|disabled|end/.test(e.className)) return 'last';
            return 'movable';
        }""")
        if state in ('none', 'last'):
            break
        move_js = """() => { const e = document.getElementById('mf_wfm_mainFrame_pgl_gdsDtlSrchPage_nextPage_btn');
            const a = e && e.querySelector('a'); if (e) (a || e).click(); }"""
        got_resp, grew = _click_and_wait_for_growth(page, response_flag, all_items, move_js)
        if not grew and total_cnt_holder[0] is not None and _unique_count(all_items) < total_cnt_holder[0]:
            print(f"    [경고] 그룹{group}→다음그룹 이동: 재시도 후에도 신규 없음 (누적 {_unique_count(all_items)}/{total_cnt_holder[0]})")
            failed_clicks.append(f"그룹{group}-다음그룹")
        group += 1
        dry = dry + 1 if _unique_count(all_items) == before else 0
        if dry >= 3:   # 세 그룹 연속 신규 없음 → 종료 (totalCnt 미달이어도 무한루프 방지)
            break
    print(f"▶ 페이지그룹 {group + 1}개 순회 (누적 고유 {_unique_count(all_items)}건)")
    if failed_clicks:
        print(f"  [경고] 재시도에도 실패한 클릭 {len(failed_clicks)}건: {failed_clicks[:10]}{'...' if len(failed_clicks) > 10 else ''}")
    return total_cnt_holder[0]


def main():
    args   = parse_args()
    output = make_output_path(args)

    # 법원 그룹 확장 (서울전체 / 경기전체) 또는 쉼표 구분 다중 법원
    if args.court in COURT_GROUPS:
        courts = COURT_GROUPS[args.court]
        print(f"▶ 법원 그룹 '{args.court}' → {len(courts)}개 법원 순차 검색")
    elif args.court and ',' in args.court:
        courts = [c.strip() for c in args.court.split(',')]
    else:
        courts = [args.court]

    all_items       = []
    response_flag   = [False]
    total_cnt_holder = [None]

    def on_response(response):
        if 'searchControllerMain' not in response.url:
            return
        try:
            body  = response.json()
            data  = body.get('data', {})
            items = data.get('dlt_srchResult', [])
            page_info = data.get('dma_pageInfo') or {}
            if page_info.get('totalCnt') is not None:
                try:
                    total_cnt_holder[0] = int(page_info['totalCnt'])
                except (TypeError, ValueError):
                    pass
            if items:
                all_items.extend(items)
                response_flag[0] = True
                print(f"  [+{len(items)}] 누적 {len(all_items)}개")
        except Exception:
            pass

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-features=site-per-process',
                '--lang=ko-KR',
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="ko-KR",
            viewport={"width": 1280, "height": 900},
        )
        context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins',  {get: () => [1,2,3,4,5]});
        window.chrome = {runtime: {}};
        """)
        page = context.new_page()
        page.on("response", on_response)

        # ── 법원별 순차 검색 (각 검색 전 폼 리로드, 정합성 미달 시 재시도) ──
        shortfall_courts = []
        for court in courts:
            before_idx = len(all_items)
            max_attempts = 2
            for attempt in range(1, max_attempts + 1):
                run_search(page, args, court, response_flag, all_items, total_cnt_holder)
                court_unique = len({build_case_no(it) for it in all_items[before_idx:]})
                expected = total_cnt_holder[0]
                if expected is None:
                    print(f"  [정합성검증 불가] {court}: totalCnt 미확인 (수집 {court_unique}건)")
                    break
                if court_unique >= expected:
                    print(f"  [정합성검증 통과] {court}: {court_unique}/{expected}건")
                    break
                print(f"  [정합성검증 실패] {court}: {court_unique}/{expected}건 — "
                      f"{'재시도' if attempt < max_attempts else '재시도 소진'}")
                if attempt >= max_attempts:
                    shortfall_courts.append((court, court_unique, expected))

        browser.close()

    # 사건번호 기준 중복 제거 (그룹 검색 시 안전장치)
    seen, deduped = set(), []
    for it in all_items:
        key = build_case_no(it)
        if key and key in seen:
            continue
        seen.add(key)
        deduped.append(it)
    if len(deduped) < len(all_items):
        print(f"  중복 제거: {len(all_items)}개 → {len(deduped)}개")
    all_items = deduped

    print(f"\n▶ 최종 수집: {len(all_items)}개")

    if shortfall_courts:
        print("\n❌ 정합성 검증 실패 — 아래 법원은 사이트 totalCnt보다 적게 수집되었습니다(누락 가능성):")
        for court, got, expected in shortfall_courts:
            print(f"   - {court}: {got}/{expected}건 (누락 {expected - got}건)")
        print("   ⚠️ 결과 CSV를 그대로 신뢰하지 말고, 위 법원은 재실행하거나 사이트에서 직접 재확인하세요.\n")

    if not all_items:
        print("❌ 데이터 없음")
        return

    # 후처리 필터
    filtered = all_items
    if args.sido:
        sidos = [s.strip() for s in args.sido.split(',')]
        filtered = [i for i in filtered if any(s in i.get('hjguSido', '') for s in sidos)]
        if len(filtered) < len(all_items):
            print(f"  시/도 필터: {len(all_items)}개 → {len(filtered)}개 ({args.sido})")
    if args.sgg:
        before = len(filtered)
        filtered = [i for i in filtered if args.sgg in i.get('hjguSigu', '')]
        if len(filtered) < before:
            print(f"  시/군/구 필터: {before}개 → {len(filtered)}개 ({args.sgg})")
    if args.max_price:
        before = len(filtered)
        filtered = [i for i in filtered if low_price(i) <= args.max_price]
        print(f"  최저가 필터: {before}개 → {len(filtered)}개 (≤ {args.max_price:,}원)")

    rows = [convert_item(item) for item in filtered]
    with open(output, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ {len(rows)}행 → {output}")

    if shortfall_courts:
        warn_path = output.rsplit('.', 1)[0] + '.WARNING.txt'
        with open(warn_path, 'w', encoding='utf-8') as f:
            f.write("정합성 검증 실패 — 이 CSV는 누락된 물건이 있을 수 있습니다.\n\n")
            for court, got, expected in shortfall_courts:
                f.write(f"- {court}: {got}/{expected}건 수집 (누락 {expected - got}건)\n")
        print(f"⚠️  경고 파일 생성: {warn_path}")

    print("\n[미리보기]")
    for i, r in enumerate(rows[:10], 1):
        print(f"  [{i:02d}] 사건번호: {r['사건번호']}")
        print(f"       소재지:   {r['물건소재지']}")
        print(f"       감정가:   {r['감정가']}  /  최저가: {r['최저가']} ({r['저감율']})  /  유찰: {r['유찰횟수']}회  /  매각: {r['매각기일']}")
        print()


if __name__ == '__main__':
    main()
