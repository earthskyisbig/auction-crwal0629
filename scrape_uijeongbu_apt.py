#!/usr/bin/env python3
"""
의정부지방법원 아파트 유찰1회 이상 경매물건 수집
court-auction-scraper 스킬 패턴 적용
"""

import csv
import json
import time
from playwright.sync_api import sync_playwright

TARGET_URL = "https://www.courtauction.go.kr/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ151F00.xml"
OUTPUT = "/Users/leomyung/auction_list.csv"
COLUMNS = ['사건번호', '물건소재지', '감정가', '최저가', '유찰횟수']

def fmt_money(val):
    try:
        return f"{int(val):,}원"
    except Exception:
        return str(val)

def build_address(item):
    parts = [item.get('hjguSido',''), item.get('hjguSigu',''),
             item.get('hjguDong',''), item.get('daepyoLotno','')]
    addr = ' '.join(p for p in parts if p.strip())
    extra = item.get('convAddr','').strip()
    return (addr + (' ' + extra if extra else '')).strip()

def build_case_no(item):
    court = item.get('jiwonNm','').strip()
    case  = item.get('srnSaNo','').strip()
    return f"{court} {case}".strip() if court else case or str(item.get('saNo',''))

def convert_item(item):
    return {
        '사건번호':  build_case_no(item),
        '물건소재지': build_address(item),
        '감정가':    fmt_money(item.get('gamevalAmt','')),
        '최저가':    fmt_money(item.get('minmaePrice','')),
        '유찰횟수':  str(item.get('yuchalCnt','')),
    }

def get_max_page(page):
    return page.evaluate("""
    () => {
        const links = Array.from(document.querySelectorAll('[id*="pgl_gdsDtlSrchPage_page_"]'));
        const nums = links.map(el => { const m = el.id.match(/_page_(\\d+)$/); return m ? +m[1] : 0; });
        return nums.length ? Math.max(...nums) : 0;
    }
    """)

def main():
    all_items = []
    response_flag = [False]

    def on_response(response):
        if 'searchControllerMain' not in response.url:
            return
        try:
            body = response.json()
            items = body.get('data',{}).get('dlt_srchResult',[])
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
        Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
        window.chrome = {runtime: {}};
        """)
        page = context.new_page()
        page.on("response", on_response)

        print("▶ 페이지 로딩...")
        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)

        print("▶ WebSquare 초기화 대기...")
        try:
            page.wait_for_function(
                "() => !!document.getElementById('mf_wfm_mainFrame_btn_gdsDtlSrch')",
                timeout=60000
            )
            print("  버튼 확인됨")
        except Exception as e:
            print(f"  [경고] {e}")
            time.sleep(15)

        time.sleep(2)

        # ── Step 1: 드롭다운 옵션 탐색 ──────────────────────────────────
        print("\n▶ 드롭다운 옵션 탐색...")
        sel_info = page.evaluate("""
        () => {
            const result = {};
            document.querySelectorAll('select').forEach(sel => {
                result[sel.id] = Array.from(sel.options).map(o => o.value + '|' + o.text);
            });
            // 텍스트 input 중 관련 필드 찾기
            const inputs = {};
            document.querySelectorAll('input[type=text], input:not([type])').forEach(el => {
                if (el.id && el.offsetWidth > 0) inputs[el.id] = el.placeholder || '';
            });
            result['__inputs'] = inputs;
            return result;
        }
        """)

        # 법원 선택 옵션 확인
        court_sel_id = None
        court_val = None
        for sel_id, opts in sel_info.items():
            if sel_id == '__inputs':
                continue
            if isinstance(opts, list) and any('의정부' in str(o) for o in opts):
                court_sel_id = sel_id
                # 의정부지방법원 옵션 찾기
                for opt in opts:
                    if '의정부지방법원' in opt:
                        court_val = opt.split('|')[0]
                        print(f"  법원 select: {sel_id} → '{opt}'")
                        break
                break

        # 용도 옵션 확인 (아파트)
        apt_lc_sel = None
        apt_lc_val = None
        apt_mc_sel = None
        apt_mc_val = None
        for sel_id, opts in sel_info.items():
            if sel_id == '__inputs' or not isinstance(opts, list):
                continue
            for opt in opts:
                if '아파트' in opt:
                    print(f"  아파트 option: {sel_id} → '{opt}'")
                    if apt_lc_sel is None:
                        apt_lc_sel = sel_id
                        apt_lc_val = opt.split('|')[0]
                    elif apt_mc_sel is None:
                        apt_mc_sel = sel_id
                        apt_mc_val = opt.split('|')[0]

        # 입력 필드 확인
        inputs = sel_info.get('__inputs', {})
        print(f"\n  전체 select IDs: {[k for k in sel_info if k != '__inputs']}")
        print(f"  전체 input IDs: {list(inputs.keys())}")

        # ── Step 2: 드롭다운 옵션 상세 확인 ─────────────────────────────
        print("\n▶ 유찰횟수 / 용도 드롭다운 옵션 확인...")
        known_ids = [
            'mf_wfm_mainFrame_sbx_rletFlbdCntMin',   # 유찰횟수 최솟값
            'mf_wfm_mainFrame_sbx_rletFlbdCntMax',   # 유찰횟수 최댓값
            'mf_wfm_mainFrame_sbx_rletLclLst',        # 용도 대분류
            'mf_wfm_mainFrame_sbx_rletMclLst',        # 용도 중분류
            'mf_wfm_mainFrame_sbx_rletSclLst',        # 용도 소분류
        ]
        opts_info = page.evaluate("""
        (ids) => {
            const res = {};
            for (const id of ids) {
                const sel = document.getElementById(id);
                if (sel) {
                    res[id] = Array.from(sel.options).map(o => o.value + '|' + o.text);
                }
            }
            return res;
        }
        """, known_ids)
        for sid, opts in opts_info.items():
            print(f"  {sid}: {opts[:8]}")

        # ── Step 3: 조건 설정 ─────────────────────────────────────────
        print("\n▶ 검색 조건 설정...")

        set_result = page.evaluate("""
        () => {
            const result = {};

            // 1) 법원: 의정부지방법원
            const crtSel = document.getElementById('mf_wfm_mainFrame_sbx_rletCortOfc');
            if (crtSel) {
                const opt = Array.from(crtSel.options).find(o => o.text.includes('의정부지방법원'));
                if (opt) {
                    crtSel.value = opt.value;
                    crtSel.dispatchEvent(new Event('change', {bubbles: true}));
                    result.court = opt.text;
                }
            }

            // 2) 유찰횟수 최솟값: 1
            const flbdSel = document.getElementById('mf_wfm_mainFrame_sbx_rletFlbdCntMin');
            if (flbdSel) {
                const opt = Array.from(flbdSel.options).find(o => o.value === '1' || o.text === '1');
                if (opt) {
                    flbdSel.value = opt.value;
                    flbdSel.dispatchEvent(new Event('change', {bubbles: true}));
                    result.flbd = opt.text;
                } else {
                    // 옵션에 '1'이 없으면 첫 번째 숫자 옵션 찾기
                    const numOpt = Array.from(flbdSel.options).find(o => /^[1-9]/.test(o.value));
                    if (numOpt) {
                        flbdSel.value = numOpt.value;
                        flbdSel.dispatchEvent(new Event('change', {bubbles: true}));
                        result.flbd = numOpt.text;
                    }
                }
            }

            return result;
        }
        """)
        print(f"  법원/유찰횟수: {set_result}")

        # 3) 용도 대분류 설정 (아파트는 '건물' 하위)
        time.sleep(1)
        lcl_result = page.evaluate("""
        () => {
            const lclSel = document.getElementById('mf_wfm_mainFrame_sbx_rletLclLst');
            if (!lclSel) return {err: 'not found'};
            const opts = Array.from(lclSel.options);
            // 집합건물 없으면 건물 선택 (아파트가 건물 하위에 있음)
            const target = opts.find(o =>
                o.text.includes('집합건물') ||
                o.value === '건물' || o.text === '건물'
            );
            if (target) {
                lclSel.value = target.value;
                lclSel.dispatchEvent(new Event('change', {bubbles: true}));
                return {set: true, val: target.value, text: target.text,
                        allOpts: opts.map(o => o.value+'|'+o.text)};
            }
            return {set: false, allOpts: opts.map(o => o.value+'|'+o.text)};
        }
        """)
        print(f"  용도 대분류: {lcl_result}")

        # 대분류 변경 후 중분류 드롭다운 업데이트 대기
        time.sleep(3)

        # 4) 용도 중분류: 주거용건물 (아파트의 상위 분류)
        mcl_result = page.evaluate("""
        () => {
            const mclSel = document.getElementById('mf_wfm_mainFrame_sbx_rletMclLst');
            if (!mclSel) return {err: 'not found'};
            const opts = Array.from(mclSel.options);
            const target = opts.find(o =>
                o.text.includes('주거용') || o.text.includes('아파트')
            );
            if (target) {
                mclSel.value = target.value;
                mclSel.dispatchEvent(new Event('change', {bubbles: true}));
                return {set: true, val: target.value, text: target.text,
                        allOpts: opts.map(o => o.value+'|'+o.text)};
            }
            return {set: false, allOpts: opts.map(o => o.value+'|'+o.text)};
        }
        """)
        print(f"  용도 중분류(주거용건물): {mcl_result}")

        # 중분류 변경 후 소분류 드롭다운 업데이트 대기
        time.sleep(3)

        # 5) 용도 소분류: 아파트
        scl_result = page.evaluate("""
        () => {
            const sclSel = document.getElementById('mf_wfm_mainFrame_sbx_rletSclLst');
            if (!sclSel) return {err: 'not found'};
            const opts = Array.from(sclSel.options);
            const aptOpt = opts.find(o => o.text.includes('아파트'));
            if (aptOpt) {
                sclSel.value = aptOpt.value;
                sclSel.dispatchEvent(new Event('change', {bubbles: true}));
                return {set: true, val: aptOpt.value, text: aptOpt.text};
            }
            return {set: false, allOpts: opts.map(o => o.value+'|'+o.text)};
        }
        """)
        print(f"  용도 소분류(아파트): {scl_result}")

        time.sleep(1)

        # 현재 설정 상태 스크린샷
        page.screenshot(path="/tmp/before_uijeongbu_search.png")

        # ── Step 3: 검색 실행 ─────────────────────────────────────────
        print("\n▶ 검색 실행 (의정부지방법원 + 아파트 + 유찰1회 이상)...")
        click_result = page.evaluate("""
        () => {
            const b = document.getElementById('mf_wfm_mainFrame_btn_gdsDtlSrch');
            if(b) { b.click(); return 'ok'; }
            return 'not found';
        }
        """)
        print(f"  클릭: {click_result}")

        # 첫 페이지 응답 대기
        print("▶ 응답 대기...")
        for _ in range(30):
            time.sleep(1)
            if response_flag[0]:
                response_flag[0] = False
                print("  첫 페이지 수신")
                break
        else:
            print("  [경고] 타임아웃")

        time.sleep(2)

        # 페이지 수 확인
        max_page = get_max_page(page)
        print(f"▶ 총 페이지: {max_page} (현재 {len(all_items)}개)")

        if max_page == 0:
            # 결과 없거나 1페이지 이하
            print("  1페이지 이하의 결과")
        else:
            for pg in range(2, max_page + 1):
                response_flag[0] = False
                time.sleep(0.5)
                clicked = page.evaluate(f"""
                () => {{
                    const el = document.getElementById('mf_wfm_mainFrame_pgl_gdsDtlSrchPage_page_{pg}');
                    if(el) {{ el.click(); return true; }}
                    return false;
                }}
                """)
                if not clicked:
                    print(f"  페이지 {pg} 버튼 없음, 중단")
                    break
                for _ in range(15):
                    time.sleep(1)
                    if response_flag[0]:
                        break

            # 파이프라인 플러시
            time.sleep(1)
            response_flag[0] = False
            page.evaluate(f"""
            () => {{
                const el = document.getElementById('mf_wfm_mainFrame_pgl_gdsDtlSrchPage_page_{max_page}');
                if(el) el.click();
            }}
            """)
            print("▶ 마지막 응답 대기 (최대 30초)...")
            no_change = 0
            for _ in range(30):
                time.sleep(1)
                if response_flag[0]:
                    response_flag[0] = False
                    no_change = 0
                    print(f"  응답 수신 (누적 {len(all_items)}개)")
                else:
                    no_change += 1
                    if no_change >= 8:
                        print("  완료")
                        break

        browser.close()

    print(f"\n▶ 최종 수집: {len(all_items)}개")

    if not all_items:
        print("❌ 데이터 없음")
        return

    rows = [convert_item(item) for item in all_items]
    with open(OUTPUT, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ {len(rows)}행 → {OUTPUT}")
    print("\n[미리보기]")
    for r in rows[:10]:
        print(f"  {r['사건번호']} | {r['물건소재지'][:35]} | {r['감정가']} | {r['최저가']} | 유찰{r['유찰횟수']}회")

if __name__ == '__main__':
    main()
