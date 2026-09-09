# -*- coding: utf-8 -*-
"""서울 빌라 유찰3회+ 수익성 — auction-analysis-kit profit-analysis 방법론 적용.

kit(out_gyeonggi/profit_calc.py) 상수·산식을 그대로 쓰되 빌라 특성 두 가지를 보정한다.
  · 지하/지층: 비교군(지상 포함) 대비 -30% (반지하 실거래는 지상 1층의 60~70% 수준)
  · 수리비: 빌라는 노후·하자 비중이 커 전용평당 15만(아파트 6~12만)
인수금액은 매각물건명세서에서 확정한 값을 쓴다(확약서 있으면 0).
"""
import os, re, json, glob, math

BASE = os.path.dirname(os.path.abspath(__file__))
MKT = json.load(open(os.path.join(BASE, 'villa_market.json'), encoding='utf-8'))

ACQ_TAX = 0.011
LEGAL   = 600_000
MGMT    = 1_000_000
BROKER  = 0.004
BASEMENT_ADJ = 0.70

def evict(area):
    return round(area / 3.3) * 100_000

def repair(area):
    return round(area / 3.3) * 150_000

def eok(v):
    return '%.2f억' % (v / 1e8)

def parse_log(path):
    t = open(path, encoding='utf-8').read()
    def grab(label):
        m = re.search(r'^\s*%s\s*:\s*(.+)$' % label, t, re.M)
        return m.group(1).strip() if m else ''
    def grab_multi(label):
        m = re.search(r'^\s*%s\s*:\s*(.*(?:\n(?!\s*(?:■|──|⚠️|★|🔴|\S+\s*:)).*)*)' % label, t, re.M)
        return re.sub(r'\s+', ' ', m.group(1)).strip() if m else ''
    remark = grab_multi('비고')
    tenants = re.findall(r'·\s*(\S+)\s+보증금\s+([\d,]+)원\s*\|\s*전입\s*([\d.]+)\s*확정\s*(\S+)\s*배당요구\s*(\S+)', t)
    risk_raw = bool(re.search(r'🔴\s*인수위험', t))
    waive_kw = ('대항력은 포기', '대항력을 포기', '반환청구권을 포기', '임차권등기를 말소',
                '임차권등기 말소', '말소해 주겠다', '말소에 동의', '대항력포기확약',
                '말소하는 것을 조건으로 매각')
    assume_confirmed = bool(re.search(r'인수(?:함|됨|하여야|하게)', remark)) and '포기' not in remark
    waived = (not assume_confirmed) and any(k in remark for k in waive_kw)
    return dict(
        addr=grab('소재지'), apr=grab('감정평가액'), low=grab('최저매각가격'),
        rate=grab('저감율') or grab('최저가율'), flbd=grab('유찰횟수'), date=grab('매각기일'),
        senior=grab('최선순위설정'), claim=grab('청구금액'), casename=grab('사건명'),
        remark=remark, tenants=tenants, risk_raw=risk_raw, waived=waived,
        jibun_share=('지분매각' in t),
        occupy=grab_multi('점유관계')[:200],
        hist=re.findall(r'(\d{4}\.\d{2}\.\d{2})\s+\d{2}:\d{2}\s+매각기일\s+([\d,]+)원\s*(유찰)?', t),
    )

def won(s):
    return int(re.sub(r'[^\d]', '', s or '0'))

LABEL = {
 '2025타경13004': ('강서 화곡동 372-48 지층 비01호', True),
 '2025타경8670':  ('양천 신월동 229-31 지하층 비01호', True),
 '2025타경11168': ('금천 시흥동 3-20 1층 101호', False),
 '2025타경103194':('관악 봉천동 1615-21 4층 401호', False),
 '2025타경52250': ('서대문 연희동 1-64 3층 302호', False),
 '2025타경10752': ('구로 오류동 81-171 해츠빌 2층 202호', False),
 '2025타경12457': ('강서 화곡동 102-26 밀레니엄 3층 302호', False),
 '2023타경108446':('구로 오류동 양지마을 104동 3층 302호', False),
 '2025타경10965': ('강서 화곡동 504-9 누리에스에이치티 2층 201호', False),
}

def main():
    out = {}
    for path in sorted(glob.glob(os.path.join(BASE, 'villa_deep', 'log_*.txt'))):
        case = re.search(r'log_(.+)\.txt$', os.path.basename(path)).group(1)
        if case not in LABEL:
            continue
        g = parse_log(path)
        m = MKT.get(case, {})
        label, is_bsmt = LABEL[case]
        area = m.get('area') or 0
        low = won(g['low']); apr = won(g['apr'])
        adj = BASEMENT_ADJ if is_bsmt else 1.0
        # 빌라 비교군에는 신축 분양 실거래가 섞여 시세를 부풀린다(전세사기 물건의 전형).
        # 반대로 지하/지층은 비교군(지상 포함)보다 실제 가치가 낮다.
        # → 보수 시세 = min(비교군 하위25% × 지하보정, 감정가). 둘 중 낮은 쪽을 택한다.
        con_raw = int((m.get('보수') or 0) * 10000 * adj)
        con = min(con_raw, apr) if con_raw and apr else (con_raw or apr)
        con_basis = '감정가' if (con_raw and apr and apr < con_raw) else '비교군 하위25%'
        neu = int((m.get('중앙') or 0) * 10000 * adj)
        opt = int((m.get('낙관') or 0) * 10000 * adj)
        same = int((m.get('동일지번중앙') or 0) * 10000 * adj)

        # 인수금액: 확약서 있으면 0, 대항력 위험 있으면 보증금 합계(보수적 상한)
        dep = sum(won(x[1]) for x in g['tenants'])
        uniq = {}
        for nm, amt, jeon, hwak, bd in g['tenants']:
            uniq[won(amt)] = (nm, jeon)
        dep_uniq = sum(uniq)          # 동일 보증금 중복(임차인+승계 보증기관) 제거
        takeover = 0 if g['waived'] else (dep_uniq if g['risk_raw'] else 0)

        fixed_side = LEGAL + evict(area) + MGMT + repair(area)
        rows = []
        for tag, bid in [('최저', low), ('+5%', round(low*1.05)), ('+10%', round(low*1.10))]:
            side = round(bid*ACQ_TAX) + fixed_side
            cost = bid + side + takeover
            brk = round(neu*BROKER)
            prof = neu - cost - brk
            rows.append((tag, bid, side, cost, prof, (prof/cost*100) if cost else 0))
        fixed = fixed_side + round(con*BROKER) + takeover
        cap = (con - fixed) / (1 + ACQ_TAX) if con else 0
        cap15 = (con*0.85 - fixed) / (1 + ACQ_TAX) if con else 0

        rate_n = int(re.sub(r'[^\d]', '', g['rate'] or '100') or 100)
        flbd_real = 0 if rate_n >= 98 else max(1, round(math.log(rate_n/100.0)/math.log(0.8)))
        out[case] = dict(label=label, basement=is_bsmt, area=area, apr=apr, low=low,
                         flbd_real=flbd_real,
                         rate=g['rate'], flbd=g['flbd'], date=g['date'], senior=g['senior'],
                         casename=g['casename'], claim=g['claim'], remark=g['remark'][:400],
                         waived=g['waived'], risk_raw=g['risk_raw'], share=g['jibun_share'],
                         deposit=dep_uniq, takeover=takeover, occupy=g['occupy'],
                         con=con, neu=neu, opt=opt, same=same, con_basis=con_basis,
                         comp_n=m.get('비교군건수'), same_n=m.get('동일지번건수'),
                         cap=int(cap), cap15=int(cap15), rows=rows,
                         hist=g['hist'], tenants=g['tenants'])

        print('\n%s\n■ %s' % ('='*80, label))
        print('  감정 %s · 최저 %s (%s, 유찰 %s) · 매각 %s%s' % (
            eok(apr), eok(low), g['rate'], g['flbd'], g['date'],
            ' · 지하/지층' if is_bsmt else ''))
        print('  최선순위 %s | %s | 청구 %s' % (g['senior'] or '-', g['casename'] or '-', g['claim'] or '-'))
        print('  임차인 %d명 보증금합 %s | 확약서 %s | 자동인수위험 %s → 인수금액 %s' % (
            len(g['tenants']), eok(dep_uniq), 'O' if g['waived'] else 'X',
            'O' if g['risk_raw'] else 'X', eok(takeover)))
        print('  시세(비교군 %s건%s) 보수/중앙/낙관: %s / %s / %s%s' % (
            m.get('비교군건수'), ', 지하보정 -30%' if is_bsmt else '',
            eok(con), eok(neu), eok(opt),
            ' | 동일지번 %s (%d건)' % (eok(same), m.get('동일지번건수', 0)) if same else ''))
        print('  보수시세 채택 근거: %s (비교군보수 %s vs 감정 %s)' % (
            con_basis, eok(con_raw), eok(apr)))
        print('  %6s %10s %10s %14s %8s' % ('낙찰가', '취득부대', '총원가', '세전차익(중립)', 'ROI'))
        for tag, bid, side, cost, prof, roi in rows:
            print('  %4s %9s %9s %9s %13s %7.1f%%' % (tag, eok(bid), eok(side), eok(cost), eok(prof), roi))
        flag = '  ⚠️ 최저가가 이미 상한 초과' if low > cap else ''
        print('  → 권장 낙찰상한(보수시세 손익분기): %s%s' % (eok(cap), flag))
        print('  → 안전마진 15%% 상한: %s' % eok(cap15))

    json.dump(out, open(os.path.join(BASE, 'villa_profit.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('\nsaved villa_profit.json (%d건)' % len(out))

if __name__ == '__main__':
    main()
