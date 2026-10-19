# -*- coding: utf-8 -*-
"""법원경매 '경매사건검색'(매각기일 2주 창과 무관) → 사건내역·기일내역·문건/송달내역 텍스트 저장.

물건상세검색(analyze_case.py)은 기일 2주 밖 사건에 "검색 결과 없음"을 낸다 — 사건 부존재 아님.
탭 클릭은 상단 헤더 메뉴가 포인터를 가로채므로 JS click 으로 한다.

사용: python court_case_search.py <법원 드롭다운 표기> <연도> <사건번호 숫자> <out_dir>
  예) python court_case_search.py 서울동부지방법원 2025 52539 ./case
"""
import os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
# analyze_case.py 위치: 저장소 안(skills/…/scripts → skill_detail/scripts) 또는 ~/.claude/skills 사본
for _p in (os.path.join(HERE, '..', '..', '..', 'skill_detail', 'scripts'),
           os.path.join(os.path.expanduser('~'), '.claude', 'skills', 'court-auction-detail', 'scripts'),
           os.path.join(os.path.expanduser('~'), 'auction-crawl0629', 'skill_detail', 'scripts')):
    if os.path.exists(os.path.join(_p, 'analyze_case.py')):
        sys.path.insert(0, _p)
        break

TABS = ['사건내역', '기일내역', '문건/송달내역']


def search(court, year, caseno, out):
    from analyze_case import STEALTH_ARGS, UA, INIT_JS, SEARCH_URL
    from playwright.sync_api import sync_playwright
    os.makedirs(out, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, args=STEALTH_ARGS)
        ctx = b.new_context(user_agent=UA, locale="ko-KR", viewport={"width": 1280, "height": 900})
        ctx.add_init_script(INIT_JS)
        page = ctx.new_page()
        page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_function("() => !!document.getElementById('mf_wfm_mainFrame_btn_gdsDtlSrch')", timeout=60000)
        time.sleep(2)
        page.get_by_text('경매사건검색', exact=True).first.click()
        time.sleep(4)
        log = page.evaluate(f"""() => {{ const log=[];
            for (const s of [...document.querySelectorAll('select')].filter(s=>s.offsetParent!==null)) {{
                const o=[...s.options].find(o=>o.text==='{court}'||o.text==='{year}');
                if (o) {{ s.value=o.value; s.dispatchEvent(new Event('change',{{bubbles:true}})); log.push(s.id+'='+o.text); }} }}
            document.querySelectorAll('input').forEach(i=>{{ if(i.offsetParent!==null && /CsNo|csNo/.test(i.id)){{
                i.value='{caseno}'; i.dispatchEvent(new Event('input',{{bubbles:true}}));
                i.dispatchEvent(new Event('change',{{bubbles:true}})); log.push(i.id);}}}});
            return log; }}""")
        print('세팅:', log)
        time.sleep(1)
        page.evaluate("""() => {const b=[...document.querySelectorAll('input[type=button],button')]
            .filter(e=>e.offsetParent!==null && /^검색$/.test((e.value||e.innerText||'').trim())); if(b.length) b[0].click();}""")
        time.sleep(8)
        for tab in TABS:
            try:
                if tab != TABS[0]:
                    page.evaluate('t => [...document.querySelectorAll("a")].find(a => a.textContent.trim() === t).click()', tab)
                    time.sleep(5)
                txt = page.evaluate("() => document.body.innerText")
                open(os.path.join(out, tab.replace('/', '_') + '.txt'), 'w', encoding='utf-8').write(txt)
                print('[%s] %d자 저장' % (tab, len(txt)))
            except Exception as e:
                print('[%s] 실패: %s' % (tab, e))
        b.close()


if __name__ == '__main__':
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    search(*sys.argv[1:])
