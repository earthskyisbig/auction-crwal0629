# -*- coding: utf-8 -*-
"""토지이음(eum.go.kr) 토지이용계획 열람 — 지번별 「지역·지구등 지정여부」 자동 조회.

경매 물건 지번이 정비구역(재개발·재건축·소규모주택정비 등)으로 **지정 고시**되었는지를
법적 근거와 함께 확인한다.

⚠️ 함정 (직접 검증함):
  - luLandDet.jsp 에 pnu 를 GET/POST 로 넣으면 무시되고 매번 다른 '샘플 지번'이 돌아온다
    (서대문구 북가좌동 → 마포구 공덕동). 200 이 떠도 내 지번이 아니다.
  - 시도/시군구/읍면동 셀렉트 + 본번/부번을 세팅하고 fn_searchAct() 를 호출하면 서버가 500 을 낸다.
    → 작동하는 경로는 **지번 검색창에 "시흥동 820-17" 형태로 입력하고 Enter** 하나뿐이다.
  - 그래서 조회 결과의 '소재지'가 요청한 지번과 일치하는지 **매 건 검증**한다(mismatch 시 실패 처리).
  - 토지이용계획확인원에는 **지정 고시가 끝난 구역만** 표시된다. 후보지 선정·정비계획 수립 중
    단계는 안 나오며, 그것이 '구역이 아니다'라는 뜻은 아니다.

사용:
  python skill_enrich/scripts/check_landuse.py <입력.json> -o <출력.json> [--limit N]
  입력 JSON: [{"주소": "...금천구 시흥동 820-17 ...", ...}, ...]
"""
import argparse, json, re, time
from playwright.sync_api import sync_playwright

URL = "https://www.eum.go.kr/web/ar/lu/luLandDet.jsp"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 정비사업 관련 키워드 — 「지역·지구등 지정여부」 원문에서 탐지
JEONGBI_KW = ['정비구역', '정비예정구역', '재개발', '재건축', '주거환경개선', '가로주택',
              '소규모주택정비', '소규모재건축', '모아타운', '도시개발구역', '지구단위계획구역']


def search_key(addr):
    """검색창에 넣을 문자열을 만든다. 지번 우선, 없으면 도로명.
    반환: (검색어, 종류) — 종류는 '지번' | '도로명'"""
    m = re.search(r'금천구\s+(\S+?동)\s+(\d+)(?:-(\d+))?', addr)
    if m:
        s = f"{m.group(1)} {m.group(2)}"
        if m.group(3):
            s += f"-{m.group(3)}"
        return s, '지번'
    m = re.search(r'금천구\s+(\S+?(?:로|길)\S*)\s+([\d-]+)', addr)
    if m:
        return f"{m.group(1)} {m.group(2)}", '도로명'
    return None, None


def set_select(page, el_id, want):
    """옵션을 텍스트/값으로 찾아 선택하고 change 이벤트 발생. 선택된 텍스트 반환."""
    return page.evaluate("""([id, want]) => {
        const s = document.getElementById(id);
        if (!s) return null;
        const o = [...s.options].find(o => o.text.trim() === want || o.value === want)
               || [...s.options].find(o => o.text.includes(want));
        if (!o) return null;
        s.value = o.value;
        s.dispatchEvent(new Event('change', {bubbles: true}));
        return o.text.trim();
    }""", [el_id, want])


def wait_options(page, el_id, timeout=15):
    """하위 셀렉트가 ajax로 채워질 때까지 대기."""
    for _ in range(timeout * 2):
        if page.evaluate(f"() => {{const s=document.getElementById('{el_id}'); return s ? s.options.length : 0;}}") > 1:
            return True
        time.sleep(0.5)
    return False


def extract(page):
    """조회 결과에서 소재지 / 지목·면적 / 지역·지구등 지정여부 원문 추출."""
    return page.evaluate("""() => {
        const clean = t => (t || '').replace(/\\s+/g, ' ').trim();
        const all = clean(document.body.innerText);
        const grab = (label, next) => {
            const i = all.indexOf(label);
            if (i < 0) return '';
            const j = next ? all.indexOf(next, i + label.length) : -1;
            return clean(all.slice(i + label.length, j > 0 ? j : i + label.length + 700));
        };
        const zone = (() => {
            const i = all.indexOf('지역지구등 지정여부', all.indexOf('개별공시지가'));
            if (i < 0) return '';
            const rest = all.slice(i);
            const end = ['확인도면', '행위제한', '「토지이용규제 기본법 시행령」']
                .map(k => rest.indexOf(k)).filter(x => x > 0);
            return clean(rest.slice(0, end.length ? Math.min(...end) : 1400));
        })();
        return {
            소재지: (all.match(/소재지\\s+(\\S+(?:특별시|광역시|도)\\s+\\S+\\s+\\S+\\s+[\\d-]+번지)/) || [])[1] || '',
            지역지구: zone,
        };
    }""")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input')
    ap.add_argument('-o', '--output', required=True)
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--sido', default='서울특별시')
    ap.add_argument('--sgg', default='금천구')
    args = ap.parse_args()

    rows = json.load(open(args.input, encoding='utf-8'))
    if args.limit:
        rows = rows[:args.limit]

    out = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, args=['--no-sandbox'])
        ctx = b.new_context(user_agent=UA, locale='ko-KR', viewport={'width': 1400, 'height': 1000})
        page = ctx.new_page()

        for n, r in enumerate(rows, 1):
            want, kind = search_key(r['주소'])
            if not want:
                out.append(dict(r, 조회='실패', 조회사유='검색어 생성 불가'))
                print(f"[{n:02d}] 실패 — 검색어 없음 | {r['주소'][:46]}"); continue
            try:
                page.goto(URL, wait_until='domcontentloaded', timeout=60000)
                time.sleep(2.5)
                box = page.locator("input[placeholder*='지번(00동']").first
                # ⚠️ 시군구를 안 붙이면 동명이동이 후보로 섞인다(금천구 시흥동 ↔ 성남시 수정구 시흥동)
                box.fill(f"{args.sgg} {want}"); time.sleep(0.8); box.press("Enter"); time.sleep(4)
                d = extract(page)
                # 후보가 여러 필지면 목록이 뜬다(도로명 건물이 2필지에 걸친 경우 등) → 첫 후보 선택
                cands = []
                if not d['소재지']:
                    cands = page.evaluate("""() => [...document.querySelectorAll('a.ico01')]
                        .filter(e => /\\(서울특별시/.test(e.innerText || ''))
                        .map(e => (e.innerText || '').trim())""")
                    if cands:
                        page.locator('a.ico01').first.click()
                        time.sleep(4.5)
                        d = extract(page)
                if kind == '지번':
                    ok = want.replace(' ', '') in d['소재지'].replace(' ', '')
                else:
                    ok = bool(d['소재지']) and '금천구' in d['소재지']
                hits = sorted({k for k in JEONGBI_KW if k in d['지역지구']})
                out.append(dict(r,
                    조회=('성공' if ok else '실패'),
                    조회사유=('' if ok else f"소재지 불일치(요청 {want} / 응답 {d['소재지'] or '없음'})"),
                    검색어=want, 검색종류=kind, 후보목록=cands,
                    확인_소재지=d['소재지'],
                    지역지구원문=d['지역지구'][:900],
                    정비키워드=hits))
                print(f"[{n:02d}] {'OK ' if ok else 'NG '} {d['소재지'] or '(응답없음)':34s} | 정비={hits or '없음'}")
            except Exception as e:
                out.append(dict(r, 조회='실패', 조회사유=f'{type(e).__name__}: {e}'))
                print(f"[{n:02d}] 실패 — {type(e).__name__}: {e}")
            time.sleep(0.8)
        b.close()

    json.dump(out, open(args.output, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    ok = sum(1 for x in out if x.get('조회') == '성공')
    print(f"\n조회 성공 {ok}/{len(out)} → {args.output}")


if __name__ == '__main__':
    main()
