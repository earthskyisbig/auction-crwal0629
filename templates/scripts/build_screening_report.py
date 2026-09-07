# -*- coding: utf-8 -*-
"""CSV → HTML 보고서 빌드 (템플릿 플레이스홀더 주입)"""
import csv, re, html, statistics, os

BASE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(BASE, 'seoul_dasedae_u1to3_1eok.csv')
TPL = os.path.join(BASE, 'report_template.html')
OUT = os.path.join(BASE, '서울_다세대_경매추천_보고서.html')

def won(v):  # "88,184,767원" → int
    return int(re.sub(r'[^\d]', '', v))

def man(v, unit=True):  # 원 → "8,384만"
    m = round(v / 10000)
    s = f"{m:,}"
    return s + ('만' if unit else '')

def derive_flbd(rate):
    if rate >= 95: return 0
    if rate >= 70: return 1
    if rate >= 55 or rate in (49,): return 2
    return 3

def flbd2(rate):
    # 20%/30% 저감 모두 커버
    if rate >= 95: return 0
    if rate >= 70: return 1
    if rate >= 45: return 2 if rate >= 55 else 2  # 64, 49
    return 3

rows = []
with open(CSV, encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        rate = int(re.sub(r'[^\d]', '', r['저감율']))
        rows.append({
            'case': r['사건번호'], 'addr': r['물건소재지'], 'area': r['전용면적'],
            'apr': won(r['감정가']), 'low': won(r['최저가']), 'rate': rate,
            'flbd': derive_flbd(rate) if rate not in (49, 34) else (2 if rate == 49 else 3),
            'date': r['매각기일'],
        })

# ── Top10 정의: (매칭 substring, 순위, 짧은 주소, 선정 이유) ──
TOP10 = [
    ('정릉동 318', 1, '성북구 정릉동 318 나동 2층 203호',
     '1억 이하 표본에서 실거주 가능한 60㎡대는 두 건뿐 — 그중 저감율이 좋은 쪽입니다. 단 3개 사건이 병합된 중복사건이라 권리분석 선행이 필수입니다.'),
    ('회기동 103-150 제3층 제303호', 2, '동대문구 회기동 103-150 3층 303호',
     '경희대·외대 도보권 35㎡가 감정가의 51%인 4,649만원. 임대수익률 관점에서 표본 내 최상위입니다.'),
    ('회기동 103-150 제3층 제304호', 3, '동대문구 회기동 103-150 3층 304호',
     '2위와 같은 건물의 옆 호수. 두 호수 동시 입찰로 낙찰 확률을 높이는 전략이 가능합니다.'),
    ('인수봉로29길', 4, '강북구 인수봉로29길 11 1층 2호',
     '30㎡ 1층이 5,171만원(51%). 4·19민주묘지역 인근 주거지로, 절대가격이 낮아 소액 투자에 적합합니다.'),
    ('삼전동 64-7 3층301호', 5, '송파구 삼전동 64-7 3층 301호',
     '표본에서 유일한 송파구 물건. 유찰 1회라 할인폭은 작지만, 잠실 생활권 접근성 대비 7,520만원입니다.'),
    ('화곡동 410-167', 6, '강서구 화곡동 410-167 은하빌라 2층 201호',
     '방 2개급 40㎡가 8,499만원(51%). 화곡동은 표본 최다 지역이라 인근 낙찰가 비교가 쉽습니다.'),
    ('화곡동 56-188', 7, '강서구 화곡동 56-188 1층 102호',
     '표본에서 두 번째로 넓은 지상층 45.4㎡. 1층이라 임대 수요가 안정적이고 64%까지 저감됐습니다.'),
    ('홍은동 265-288', 8, '서대문구 홍은동 265-288 2층 204호',
     '27㎡가 6,656만원(64%). 홍제천·명지대 생활권으로 서북권에서 절대가격이 가장 낮은 지상층입니다.'),
    ('도봉로110아길', 9, '도봉구 도봉로110아길 57-14 4층 401호',
     '표본 최대 면적 93.57㎡. 할인폭(80%)은 작지만 ㎡당 94만원으로 평당가 기준 표본 최저 수준입니다.'),
    ('구의동 201-11 다솜빌 2층204호', 10, '광진구 구의동 201-11 다솜빌 2층 204호',
     '유찰 3회 51%. 같은 건물에서 유사 물건 3건이 동시에 진행 중이라 경쟁이 분산돼 저가 낙찰 여지가 있습니다.'),
]

# ── 심층분석 판정 (2026-08-19 매각물건명세서 확인) ──
# rank → (verdict: ok/cond/no, 배지문구, 본문, facts[(라벨, 값)])
DEEP = {
    1: ('no', '입찰 부적합', '지분매각입니다 — 온전한 소유권이 아니라 공유지분만 매각되며, 공유자 우선매수신고가 1회 허용됩니다. 현황조사상 임차인 송옥희 세대도 등재되어 있습니다. 일반 실수요·투자 목적에는 맞지 않습니다.',
        [('최선순위', '2011.11.29 근저당권'), ('명세서 비고', '지분매각 · 공유자 우선매수 1회'), ('사건', '강제경매 · 중복 3건 병합')]),
    2: ('no', '입찰 부적합', '지분매각입니다 — 감정평가서에 명시된 대로 공유자 정종윤의 지분 5분의 2에 대한 평가·매각이며, 감정가 9,080만원은 지분 가치입니다. 황순영 세대가 전입되어 있어 점유관계 확인도 필요합니다.',
        [('최선순위', '2023.6.12 가압류'), ('명세서 비고', '지분매각 · 공유자 우선매수 1회'), ('지분', '5분의 2 (정종윤)')]),
    3: ('no', '입찰 부적합', '2위와 같은 사건의 옆 호수로, 동일하게 지분 5분의 2 매각입니다. "동시 입찰 전략"은 지분물건이므로 성립하지 않습니다.',
        [('최선순위', '2023.6.12 가압류'), ('명세서 비고', '지분매각 · 공유자 우선매수 1회'), ('지분', '5분의 2 (정종윤)')]),
    4: ('cond', '조건부', '소유권은 온전하지만 대항력 임차인이 있습니다 — 보증금 8,500만원, 전입 2020.1.2로 최선순위 압류(2022.4.19)보다 앞섭니다. 확정일자(2021.8.25)와 배당요구(2025.3.27)가 있어 배당으로 회수될 수 있으나, 낙찰가가 5천만원대면 배당재원이 부족해 미배당 잔액을 매수인이 떠안습니다. 배당표 시뮬레이션 없이 입찰하면 총부담이 감정가를 넘을 수 있습니다.',
        [('대항력 임차인', '보증금 8,500만 · 전입 2020.1.2'), ('예상낙찰가', '6,888만 (수유동 평균 68.2%)'), ('보수적 총부담', '1.60억 (인수 상한 반영)')]),
    5: ('no', '입찰 부적합', '지분매각입니다(청산을 위한 형식적경매). 공유자 우선매수신고 1회 허용 조건이 붙어 있어 낙찰받아도 공유자에게 넘어갈 수 있습니다. 참고로 삼전동 인근 매각가율은 평균 134%로 감정가를 크게 웃돕니다.',
        [('최선순위', '2012.8.16 가압류'), ('명세서 비고', '지분매각 · 공유자 우선매수 1회'), ('인근 매각가율', '평균 134.3% (9건)')]),
    6: ('ok', '입찰 검토', '이번 심층분석에서 가장 안전한 물건입니다. 대항력 임차인(보증금 1.2억)이 있으나 특별매각조건으로 채권자가 미배당 잔액에 대한 보증금 반환청구권을 포기하고 임차권등기를 말소하는 조건이라 매수인 인수 부담이 없습니다. 화곡동 평균 매각가율 70.5% 기준 예상낙찰가 1.17억 — 최저가 8,499만원과의 사이가 입찰 여지입니다. 폐문부재 물건이라 명도 난이도는 현장 확인이 필요합니다.',
        [('인수보증금', '0원 (특별매각조건)'), ('예상낙찰가', '1.17억 (화곡동 70.5%)'), ('총취득원가 추정', '1.24억'), ('사용승인', '2008.9 (비교적 신축)')]),
    7: ('ok', '입찰 검토', '방 3개·거실 구조의 45.4㎡ 1층 — Top 10 중 실사용 가치가 가장 높습니다. 대항력 임차인 3건이 표기되어 있으나 실제로는 동일 임대차(보증금 1.19억)의 승계 관계이고, 특별매각조건으로 서울보증보험이 미배당 잔액 반환청구권을 포기하고 임차권등기를 말소하는 조건이라 인수 부담이 없습니다. 1993년식으로 연식은 오래됐습니다.',
        [('인수보증금', '0원 (특별매각조건)'), ('예상낙찰가', '9,659만 (화곡동 70.5%)'), ('총취득원가 추정', '1.03억'), ('구조', '방3 · 거실주방 · 1993년식')]),
    8: ('ok', '입찰 검토', '신청채권자 서울보증보험이 LH의 임차보증금(8,200만) 반환채권을 양수한 사건으로, 배당으로 전액을 못 받아도 잔존 반환청구권을 포기하고 임차권등기 말소에 동의한다는 확약서를 제출했습니다(2026.4.24). 전입세대도 없어 명도 부담이 낮습니다. 홍은동 평균 매각가율 84% 기준 예상낙찰가 8,736만원. 입찰 전 확약서 원문(사건기록)을 직접 확인하세요.',
        [('인수보증금', '0원 (포기 확약서 · 원문 확인 요망)'), ('예상낙찰가', '8,736만 (홍은동 84.0%)'), ('점유', '전입세대 없음 · 명도 용이')]),
    9: ('no', '입찰 부적합', '지분매각입니다 — 표본 최대 93.57㎡라는 매력은 지분이라는 사실 앞에 무의미합니다. 공유자 우선매수신고 1회 허용. 전입세대주(최동국)도 있어 점유관계 확인이 필요합니다.',
        [('최선순위', '2001.9.27 근저당권'), ('명세서 비고', '지분매각 · 공유자 우선매수 1회'), ('청구금액', '636만원 (소액 강제경매)')]),
    10: ('no', '입찰 부적합', '대항력 임차인의 보증금이 1.5억으로 감정가(1.66억)에 육박하는 깡통 구조입니다. 배당요구는 했지만 낙찰가에서 배당받지 못하는 잔액은 전부 매수인이 인수합니다. 여기에 지분별로 최선순위가 다른 복잡한 권리관계, 토지대장 대지권등록부 미등재 문제까지 겹칩니다.',
        [('대항력 임차인', '보증금 1.5억 · 전입 2022.5.20'), ('추가 리스크', '대지권등록부 미등재'), ('보수적 총부담', '5억 이상 (인수 상한 반영)')]),
}
VERDICT_BADGE = {'ok': ('v-ok', '입찰 검토'), 'cond': ('v-cond', '조건부'), 'no': ('v-no', '입찰 부적합')}

CAUTION_KEYS = ['논현로8길', '신림동 251-214', '하이시티', '다솜빌', '정릉동 318', '지하', '제지']

BADGE = {0: ('b0', '신건 · 100%'), 1: ('b1', '유찰 1회 · {}%'), 2: ('b2', '유찰 2회 · {}%'), 3: ('b3', '유찰 3회 · {}%')}

def badge(r):
    cls, txt = BADGE[r['flbd']]
    return f'<span class="badge {cls}">{txt.format(r["rate"])}</span>'

def find(sub):
    for r in rows:
        if sub in r['addr']:
            return r
    raise KeyError(sub)

# ── Top10 HTML ──
top_html = []
pick_map = {}   # addr → rank
for sub, rank, short, why in TOP10:
    r = find(sub)
    pick_map[r['addr']] = rank
    hot = ' hot' if r['rate'] <= 55 else ''
    vcls, vtxt = VERDICT_BADGE[DEEP[rank][0]]
    top_html.append(f'''  <div class="rank">
    <div class="no{hot} num">{rank}</div>
    <div>
      <div class="addr">{html.escape(short)}</div>
      <div class="meta">{html.escape(r['case'])} · 전용 {r['area']} · 매각 {r['date']}</div>
      <div class="why">{html.escape(why)}</div>
    </div>
    <div class="price">
      <div class="low num">{man(r['low'])}원</div>
      <div class="apprais num">감정 {man(r['apr'])}원</div>
      <div class="badges"><span class="badge {vcls}">{vtxt}</span>{badge(r)}</div>
    </div>
  </div>''')

# ── 심층분석 카드 ──
deep_html = []
for sub, rank, short, why in TOP10:
    v, vtxt, body, facts = DEEP[rank]
    vcls = VERDICT_BADGE[v][0]
    facts_html = ''.join(f'<span>{html.escape(k)} <b>{html.escape(val)}</b></span>' for k, val in facts)
    deep_html.append(f'''  <div class="deep {v}">
    <div class="d-head">
      <span class="d-rank num">{rank}위</span>
      <span class="d-addr">{html.escape(short)}</span>
      <span class="badge {vcls}">{vtxt}</span>
    </div>
    <p class="d-body">{html.escape(body)}</p>
    <div class="d-facts">{facts_html}</div>
  </div>''')

# ── 전체 표 ──
def is_basement(addr):
    return '지하' in addr or '제지' in addr

def is_caution(addr):
    return any(k in addr for k in ['논현로8길', '신림동 251-214', '하이시티']) or is_basement(addr) or '다솜빌' in addr or '정릉동 318' in addr

tr = []
for r in rows:
    marks = ''
    if r['addr'] in pick_map:
        marks += f'<span class="pick">추천 {pick_map[r["addr"]]}</span>'
    if is_caution(r['addr']):
        marks += '<span class="warn-mark">▲</span>'
    base = ' <span class="badge b0">지하</span>' if is_basement(r['addr']) else ''
    addr_cell = f'{marks}{html.escape(r["addr"].replace("서울특별시 ", ""))}{base}<span class="case">{html.escape(r["case"])}</span>'
    tr.append(f'''      <tr>
        <td>{addr_cell}</td>
        <td class="r num">{r['area']}</td>
        <td class="r num">{man(r['apr'], False)}</td>
        <td class="r num"><b>{man(r['low'], False)}</b></td>
        <td class="r num">{r['rate']}%</td>
        <td>{badge(r)}</td>
        <td class="r num">{r['date']}</td>
      </tr>''')

median = statistics.median(r['low'] for r in rows)
cnt3 = sum(1 for r in rows if r['flbd'] == 3)
hwagok = sum(1 for r in rows if '화곡동' in r['addr'])

tpl = open(TPL, encoding='utf-8').read()
out = (tpl.replace('{{MEDIAN}}', f"{round(median/10000):,}")
          .replace('{{CNT3}}', str(cnt3))
          .replace('{{HWAGOK}}', str(hwagok))
          .replace('{{TOP10}}', '\n'.join(top_html))
          .replace('{{DEEP}}', '\n'.join(deep_html))
          .replace('{{ROWS}}', '\n'.join(tr)))
open(OUT, 'w', encoding='utf-8').write(out)
print(f"OK rows={len(rows)} median={round(median/10000):,} cnt3={cnt3} hwagok={hwagok} → {OUT}")
