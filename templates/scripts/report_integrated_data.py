# -*- coding: utf-8 -*-
"""경기 비규제 아파트 경매 종합보고서 생성.

입력: _workspace/report_data_0909.json (assemble.py), _workspace/market_recheck.json
출력: 경기비규제_아파트경매_종합보고서.html (repo root) + templates/report_integrated.html
"""
import os, re, json, html

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
DATA = json.load(open(os.path.join(BASE, 'report_data_0909.json'), encoding='utf-8'))

def man(v):
    v = int(v or 0); neg = v < 0; v = abs(v)
    eok, m = v // 100000000, round((v % 100000000) / 10000)
    s = (f'{eok}억 {m:,}만' if m else f'{eok}억') if eok else f'{m:,}만'
    return ('−' if neg else '') + s

def e(s):
    return html.escape(str(s or ''))

# ── 사람이 검증한 물건별 판정 ─────────────────────────────────────────
VERDICT = {
 '2025타경43094': dict(short='안성 롯데캐슬', label='안성 롯데캐슬 130동 1306호', grade='ok', gtext='입찰 검토',
   head='보증기관 확약서로 인수부담 해소 · 2,320세대 최대 표본',
   body='임차인 보증금 2.4억이 최선순위(2025.11.27 경매개시결정)보다 앞서 형식상 인수 대상이지만, 주택도시보증공사가 '
        '2026.06.01자로 <b>“우선변제권만 주장하고 대항력은 포기하며, 전액을 변제받지 못하더라도 임차권등기를 말소하겠다”</b>는 '
        '확약서를 제출해 매수인 인수부담이 사라졌습니다. 전입세대확인서상 등재인이 없어 명도 부담도 낮습니다. '
        '2016년 준공 2,320세대로 12개월 117건이 거래돼 회전율 5.04% — 후보 중 가장 두터운 표본입니다.',
   risk='확약서는 배당요구종기(2026.02.24) 이후인 2026.06.01자 제출입니다. 채권자의 일방적 권리포기라 효력에 문제는 없다고 '
        '보지만, 입찰 전 사건기록에서 확약서 원문과 제출 주체를 직접 확인하세요.'),
 '2025타경65184': dict(short='파주 팜스프링 115㎡', label='파주 팜스프링 126동 2003호', grade='ok', gtext='입찰 검토',
   head='시세 대비 할인폭 최대(55.6%) · 대형 평형 유찰 2회',
   body='115㎡ 대형 평형이 두 번 유찰되며 최저가가 시세(2.67억)의 <b>55.6%</b>인 1.48억까지 내려왔습니다. '
        '임차인 보증금 2.7억은 감정가를 넘지만, 주택도시보증공사가 2026.05.21자 확약서로 <b>대항력 포기 + 잔존 반환청구권 포기 + '
        '임차권등기 말소 동의</b>를 명시해 인수부담이 없습니다. 2,944세대 대단지입니다.',
   risk='대형 평형이라 회전율 3.19%로 후보 중 하위권입니다. 115㎡ 실거래는 12개월 7건·24개월 28건으로 손바뀜이 느려 '
        '매도까지 기간을 길게 잡아야 합니다. 단기 전매 전략에는 부적합합니다.'),
 '2025타경43198': dict(short='안성 공도 주은풍림', label='안성 공도 주은풍림 108동 1001호', grade='ok', gtext='입찰 검토',
   head='환금성 1위(회전율 6.27%) · 절대가격 8,400만원',
   body='서울보증보험이 2026.04.28자 <b>대항력포기확약서</b>를 제출해 임차보증금 1.35억의 인수부담이 없습니다. '
        '2,615세대 대단지로 최근 12개월 164건이 거래돼 회전율 6.27% — 후보 중 환금성 1위입니다. '
        '49.77㎡ 소형이라 절대가격이 8,400만원으로 가장 낮아 진입장벽이 작고, 시세(1.16억) 대비 72.4% 수준입니다.',
   risk='명세서 임차인란의 전입일 표기가 “2025.12.11”로 경매개시(2025.12.12) 직전이고 원문에는 2022년 날짜가 섞여 있어 '
        '파싱이 불안정합니다. 확약서로 인수부담은 해소되나, 전입일 원본은 명세서 정본으로 대조하세요.'),
 '2025타경43222': dict(short='안성 원곡 제일오투', label='안성 원곡 제일오투그란데 308동 504호', grade='ok', gtext='입찰 검토',
   head='임차인 없음 · 2018년 준공 · 권리관계 가장 단순',
   body='최선순위가 2022.03.17 근저당권이고 <b>명세서·현황조사 모두 임차인이 없습니다</b>. 전입세대확인서상 채무자(소유자) 외 '
        '등재인이 없어 소유자 점유로 보이며, 인수할 권리도 명도 대상 임차인도 없는 가장 단순한 구조입니다. '
        '2018년 준공으로 후보 중 가장 신축이고 회전율 6.27%로 환금성도 최상위입니다. 시세 1.8억 대비 73.1%.',
   risk='폐문부재로 실제 점유자를 만나지 못했습니다. 소유자 점유라면 인도명령으로 비교적 빠르게 처리되지만, '
        '점유 실태와 관리비 체납은 현장 확인이 필요합니다.'),
 '2025타경43133': dict(short='평택 청북 이지더원', label='평택 청북 이지더원 101동 1401호', grade='ok', gtext='입찰 검토',
   head='임차인 없음 · 2016년 준공 · 시세 표본 53건',
   body='최선순위 2018.07.13 근저당권, <b>명세서·현황조사 모두 임차인 없음</b>, 전입세대확인서상 채무자 겸 소유자 외 등재자가 '
        '없습니다. 인수·명도 리스크가 모두 낮은 구조입니다. 76.83㎡ 국민평형대이고 24개월 53건이 거래돼 시세(2.47억) 근거가 '
        '탄탄합니다. 최저가 1.84억은 시세의 74.5% 수준입니다.',
   risk='513세대로 대단지는 아니어서 매수 대기 수요층이 얇습니다. 청북읍은 평택 시내권과 떨어진 신도시 외곽이라 '
        '입지 프리미엄보다 가격 메리트로 접근해야 합니다.'),
 '2026타경70505': dict(short='양주 세창리베하우스', label='양주 세창리베하우스 104동 104호', grade='cond', gtext='조건부',
   head='문서 간 불일치 — 명세서엔 임차인 없음, 현황조사엔 전입세대 있음',
   body='최선순위는 2022.12.29 근저당권이고 매각물건명세서에는 <b>임차인이 없다</b>고 기재돼 있습니다. 그러나 현황조사서에는 '
        '<b>“임차인으로 조사한 황태양의 세대가 등재되어 있다”</b>고 적혀 있어 두 문서가 어긋납니다. '
        '권리신고를 하지 않은 임차인이 있을 수 있고, 그의 전입일이 2022.12.29보다 앞서면 보증금이 매수인에게 인수됩니다.',
   risk='이 불일치를 해소하기 전에는 인수금액을 0으로 볼 수 없습니다. <b>전입세대열람원을 직접 발급받아 전입일자를 확인</b>하고, '
        '배당요구종기(2026.06.08)까지 권리신고·배당요구가 있었는지 문건송달내역으로 대조하세요. 확인 전 입찰은 권하지 않습니다.'),
 '2026타경60032': dict(short='파주 그린시티동문', label='파주 그린시티동문 509동 303호', grade='ok', gtext='입찰 검토',
   head='임차인 없음 · 소유자 직접 점유 확인 · 101㎡ 대형',
   body='최선순위 2015.10.19 근저당권이고 명세서상 임차인이 없습니다. 현황조사에서 <b>채무자(소유자) 본인을 직접 만나 '
        '“전부 점유하고 있다”는 진술</b>을 받아, 폐문부재로 점유가 미상인 다른 물건보다 명도 시나리오가 명확합니다. '
        '1,759세대이고 101.66㎡ 대형이 시세(2.24억) 대비 73.4%인 1.65억입니다.',
   risk='회전율 3.41%로 대형 평형 특유의 낮은 손바뀜을 보입니다. 101㎡ 실거래가 24개월 12건뿐이라 시세 밴드(2.0~2.5억)가 '
        '넓습니다. 매도가를 밴드 하단 기준으로 보수적으로 잡으세요.'),
 '2026타경60131': dict(short='파주 동광모닝스카이', label='파주 동광모닝스카이 105동 302호', grade='cond', gtext='조건부',
   head='할인폭은 크지만(57.2%) 단지 규모·표본이 가장 얇음',
   body='최저가 1.03억은 시세(1.8억)의 57.2%로 팜스프링 다음으로 할인폭이 큽니다. 권리 자체는 깨끗합니다 — '
        '임차보증금 2.1억(전입 2022.04.28)이 최선순위 가압류(2025.06.13)보다 앞서지만, 주택도시보증공사가 2026.05.21자로 '
        '<b>대항력 포기 · 임차권등기 말소 동의</b> 확약서를 제출했고 전입세대확인서상 등재자도 없습니다.',
   risk='227세대 소규모 단지이고 12개월 거래가 7건뿐이라 회전율 3.08%로 후보 중 최하위입니다. 시세 근거가 24개월 13건에 '
        '불과해 “시세 1.8억”의 신뢰구간이 넓고, 파주읍 연풍리는 운정·교하 생활권과 떨어진 외곽입니다. '
        '할인폭이 큰 이유가 물건 자체보다 <b>지역 수요 부족</b>일 가능성을 배제하기 어렵습니다.'),
}

ORDER = ['2025타경43094', '2025타경65184', '2025타경43198', '2025타경43222',
         '2025타경43133', '2026타경70505', '2026타경60032', '2026타경60131']

def build_props():
    out = []
    for r in DATA['후보']:
        cn = r.get('_사건')
        if cn not in VERDICT:
            continue
        v = VERDICT[cn]
        g = r.get('_권리') or {}
        t = r.get('_환금성') or {}
        out.append(dict(
            case=cn, court=r['사건번호'].split()[0], addr=r['물건소재지'],
            short=v['short'], label=v['label'], grade=v['grade'], gtext=v['gtext'],
            head=v['head'], body=v['body'], risk=v['risk'],
            area=r['_면적'], hh=r['_세대수n'], built=r['_준공n'],
            apr=r['_감정가'], low=r['_최저가'], mkt=r.get('_시세중앙') or 0,
            samp=r.get('_시세표본') or 0, disc=r.get('_할인율'),
            flbd=r['_유찰'], rate=r['저감율'], date=r['매각기일'],
            turn=t.get('회전율%'), turn_cnt=t.get('12개월거래'),
            waive=g.get('대항력포기확약', False), risk_flag=g.get('인수위험', False),
            tenants=g.get('임차인수', 0), senior=g.get('최선순위설정', ''),
            claim=g.get('청구금액', ''), case_name=g.get('사건명', ''),
            nearby_rate=g.get('읍면동매각가율'), nearby_cnt=g.get('인근매각건수'),
            hist=g.get('기일내역', []),
        ))
    out.sort(key=lambda x: ORDER.index(x['case']) if x['case'] in ORDER else 99)
    return out

PROPS = build_props()
TAX, AGG, REG = DATA['세금'], DATA['집계'], DATA['지역']

# ── 조각 렌더러 ──────────────────────────────────────────────────────
def kpi_row():
    wv = sum(1 for p in PROPS if p['waive'])
    zero = sum(1 for p in PROPS if p['grade'] != 'cond' or not p['risk_flag'])
    zero = len(PROPS) - sum(1 for p in PROPS if p['case'] == '2026타경70505')  # 불일치 1건만 미확정
    tiles = [
        ('비규제 조건부합', f"{AGG['총건수']}", '건', ''),
        ('최저가 중앙값', man(AGG['최저가중앙']).replace(' ', ''), '', ''),
        ('심층 권리분석', f"{len(PROPS)}", '건', ''),
        ('인수금액 0원', f"{zero}", '건', 'good'),
        ('보증기관 확약서', f"{wv}", '건', 'seal'),
    ]
    return '\n'.join(
        f'<div class="kpi {c}"><div class="k">{e(l)}</div><div class="v num">{e(v)}<small>{e(u)}</small></div></div>'
        for l, v, u, c in tiles)

def tax_section():
    rows = [('nonreg_2h', '비규제 · 2주택', False), ('reg_2h', '규제 · 2주택', True),
            ('nonreg_3h', '비규제 · 3주택', False), ('reg_3h', '규제 · 3주택', True)]
    mx = max(abs(TAX[k]['총세금']) for k, _, _ in rows if k in TAX)
    bars, trs = [], []
    for k, lab, isreg in rows:
        d = TAX.get(k)
        if not d:
            continue
        w = round(abs(d['총세금']) / mx * 100)
        net = d['세후순익']
        bars.append(
            f'<div class="tb"><span class="tl">{e(lab)}</span>'
            f'<span class="tbar"><i class="{"reg" if isreg else "non"}" style="width:{w}%"></i></span>'
            f'<span class="tv num">{man(d["총세금"])}</span></div>')
        trs.append(
            f'<tr><td>{e(lab)}</td><td class="r num">{man(d["취득세"])}</td>'
            f'<td class="r num">{man(d["양도세"])}</td><td class="r num"><b>{man(d["총세금"])}</b></td>'
            f'<td class="r num {"pos" if net >= 0 else "neg"}"><b>{man(net)}</b></td>'
            f'<td class="r num {"pos" if net >= 0 else "neg"}">{d["수익률"] * 100:+.1f}%</td></tr>')
    return '\n'.join(bars), '\n'.join(trs)

def funnel():
    steps = [('전국 수집', 682, '유찰 1~3회 · 최저가 2억 이하 · 아파트'),
             ('경기도', 109, '소재지 접두어 사후필터'),
             ('비규제지역', AGG['총건수'], '규제 15개 지역 제외'),
             ('단지스펙 확인', AGG['단지확인'], 'K-apt 세대수·준공 매칭'),
             ('실거래 대조', 14, '국토부 RTMS 동일단지·평형'),
             ('권리분석', len(PROPS), '매각물건명세서·현황조사 직접 열람')]
    mx = steps[0][1]
    return '\n'.join(
        f'<div class="fn"><span class="fl">{e(l)}</span>'
        f'<span class="fbar"><i style="width:{max(3, round(n / mx * 100))}%"></i></span>'
        f'<span class="fv num">{n}</span><span class="fd">{e(d)}</span></div>'
        for l, n, d in steps)

def region_bars():
    items = REG.get('비규제_지역분포', [])[:12]
    mx = items[0][1] if items else 1
    return '\n'.join(
        f'<div class="rg"><span class="rl">{e(name.replace(" None", ""))}</span>'
        f'<span class="rbar"><i style="width:{round(c / mx * 100)}%"></i></span>'
        f'<span class="rv num">{c}</span></div>' for name, c in items)

def prop_tabs():
    return '\n'.join(
        f'<div class="prop{" on" if i == 0 else ""}" data-i="{i}">'
        f'<div class="pn">{e(p["short"])}</div>'
        f'<div class="pm">{e(p["court"])} {e(p["case"])}</div>'
        f'<span class="pv {p["grade"]}">{"✓" if p["grade"] == "ok" else "△"} {e(p["gtext"])}</span></div>'
        for i, p in enumerate(PROPS))

def prop_cards():
    out = []
    for i, p in enumerate(PROPS):
        chips = [f'전용 {p["area"]}㎡', f'{p["hh"]:,}세대', f'{p["built"]}년 준공',
                 f'유찰 {p["flbd"]}회 ({p["rate"]})', f'매각 {p["date"]}']
        if p['case_name']:
            chips.append(p['case_name'])
        rights = ('<span class="rb ok">인수 0원 — 보증기관 대항력 포기 확약</span>' if p['waive'] else
                  '<span class="rb warn">인수 여부 확인 필요</span>' if p['grade'] == 'cond' else
                  '<span class="rb ok">인수 0원 — 명세서상 임차인 없음</span>')
        hist = ''.join(
            f'<tr><td>{e(d)}</td><td>{e(r or "이번 기일")}</td><td class="r num">{man(int(re.sub(chr(92) + "D", "", a)))}</td></tr>'
            for d, a, r in p['hist']) or '<tr><td colspan="3" class="mut">기일 이력 없음</td></tr>'
        disc = f'{p["disc"]}%' if p['disc'] else '—'
        turn = f'{p["turn"]}%' if p['turn'] else '—'
        near = f'{p["nearby_rate"]}%' if p['nearby_rate'] else '—'
        out.append(f'''<div class="pcard{" on" if i == 0 else ""}" data-i="{i}">
  <div class="ph"><span class="pt">{e(p["label"])}</span><span class="rb {p["grade"]}">{e(p["gtext"])}</span></div>
  <p class="phead">{e(p["head"])}</p>
  <div class="chips">{''.join(f'<span class="chip">{e(c)}</span>' for c in chips)}</div>
  <div class="stat4">
    <div class="s"><div class="sk">최저매각가</div><div class="sv num">{man(p["low"])}</div><div class="sd">감정 {man(p["apr"])}</div></div>
    <div class="s"><div class="sk">실거래 시세</div><div class="sv num">{man(p["mkt"])}</div><div class="sd">12개월 {p["samp"]}건 중앙값</div></div>
    <div class="s"><div class="sk">시세 대비</div><div class="sv num seal">{e(disc)}</div><div class="sd">최저가 ÷ 시세</div></div>
    <div class="s"><div class="sk">환금성 회전율</div><div class="sv num">{e(turn)}</div><div class="sd">12개월 {p["turn_cnt"]}건 ÷ 세대수</div></div>
  </div>
  <div class="pbody">{p["body"]}</div>
  <div class="prisk"><b>확인할 것</b> {p["risk"]}</div>
  <div class="pgrid">
    <div><div class="sub">권리 판정</div>{rights}
      <ul class="fl2"><li>최선순위 설정 · {e(p["senior"]) or "미상"}</li>
      <li>명세서 임차인 · {p["tenants"]}명</li><li>청구금액 · {e(p["claim"]) or "—"}</li>
      <li>인근 읍면동 평균 매각가율 · {e(near)} ({p["nearby_cnt"]}건)</li></ul></div>
    <div><div class="sub">기일 이력</div>
      <table class="mini"><thead><tr><th>기일</th><th>결과</th><th class="r">최저가</th></tr></thead>
      <tbody>{hist}</tbody></table></div>
  </div>
</div>''')
    return '\n'.join(out)

def prop_js():
    js = [dict(case=p['case'], short=p['short'], apr=p['apr'] // 10000, low=p['low'] // 10000,
               mkt=p['mkt'] // 10000, area=p['area'], waive=p['waive'], grade=p['grade'])
          for p in PROPS]
    return json.dumps(js, ensure_ascii=False)
