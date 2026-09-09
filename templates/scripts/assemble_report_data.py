# -*- coding: utf-8 -*-
"""보고서용 데이터 조립 — 수집·랭킹·환금성·세금·권리분석 결과를 하나의 JSON으로."""
import os, re, json, csv, glob, statistics

BASE = os.path.dirname(os.path.abspath(__file__))
TAXWS = r'C:\Users\m9938\auction-tax2\_workspace'

def jload(p, default=None):
    try:
        return json.load(open(p, encoding='utf-8'))
    except Exception:
        return default if default is not None else {}

def parse_deep(path):
    """analyze_case.py 콘솔 로그에서 권리분석 핵심 항목 추출."""
    try:
        t = open(path, encoding='utf-8').read()
    except Exception:
        return {}
    def grab(label):
        m = re.search(rf'^\s*{label}\s*:\s*(.+)$', t, re.M)
        return m.group(1).strip() if m else ''

    def grab_multi(label):
        """여러 줄에 걸친 항목(비고 등)을 다음 항목/구획 시작 전까지 통째로."""
        m = re.search(rf'^\s*{label}\s*:\s*(.*(?:\n(?!\s*(?:■|──|⚠️|★|🔴|\S+\s*:)).*)*)',
                      t, re.M)
        return re.sub(r'\s+', ' ', m.group(1)).strip() if m else ''
    out = {
        '소재지': grab('소재지'), '단지': grab('단지'),
        '감정평가액': grab('감정평가액'), '최저매각가격': grab('최저매각가격'),
        '저감율': grab('저감율') or grab('최저가율'), '매각기일': grab('매각기일'),
        '명세서공개': grab('공개여부'), '최선순위설정': grab('최선순위설정'),
        '배당요구종기': grab('배당요구종기'), '비고': grab_multi('비고'),
        '사건명': grab('사건명'), '청구금액': grab('청구금액'),
        '점유관계': grab('점유관계'),
    }
    # 임차인 블록
    out['임차인수'] = 0
    m = re.search(r'──\s*임차인\s*(\d+)명', t)
    if m:
        out['임차인수'] = int(m.group(1))
    elif '조사된 임차내역 없음' in t or grab('임차인') in ('없음',):
        out['임차인수'] = 0
    out['임차인상세'] = re.findall(r'·\s*(\S+)\s+보증금\s+([\d,]+)원\s*\|\s*전입\s*([\d.]+)\s*확정\s*([\d.]+)\s*배당요구\s*(\S+)', t)
    out['인수위험_원시'] = bool(re.search(r'🔴\s*인수위험', t))
    m = re.search(r'★\s*특별매각조건\s*:?\s*(.+)', t)
    out['특별매각조건'] = m.group(1).strip()[:400] if m else ''
    out['지분매각'] = ('지분매각' in t)

    # 구버전 analyze_case.py 로그용 폴백 — 자동 '인수위험'이 명세서 비고의 확약서
    # (대항력 포기·임차권등기 말소)를 읽지 못해 오탐이 난다.
    # (2026-09-09 이후 analyze_case.py 는 is_deposit_waived() 로 상류에서 처리한다.)
    blob = (out['비고'] or '') + ' ' + (out['특별매각조건'] or '')
    waive_kw = ('대항력은 포기', '대항력을 포기', '반환청구권을 포기', '임차권등기를 말소',
                '임차권등기 말소', '말소해 주겠다', '말소에 동의', '대항력포기확약')
    # 비고에는 반대로 '전액을 매수인이 인수함' 같은 인수 확정 문구도 들어간다 —
    # '포기' 없이 인수 문구만 있으면 확약으로 보지 않는다(upstream is_deposit_waived 와 동일 가드).
    assume_confirmed = bool(re.search(r'인수(?:함|됨|하여야|하게)', blob)) and '포기' not in blob
    out['대항력포기확약'] = (not assume_confirmed) and any(k in blob for k in waive_kw)
    out['인수위험'] = out['인수위험_원시'] and not out['대항력포기확약']
    out['확약문구'] = blob.strip()[:500] if out['대항력포기확약'] else ''
    # 인근매각
    m = re.search(r'동일읍면동 평균매각가율\s*:\s*([\d.]+)%\s*범위\s*\[([\d.]+),\s*([\d.]+)\]', t)
    if m:
        out['읍면동매각가율'] = float(m.group(1))
        out['매각가율범위'] = [float(m.group(2)), float(m.group(3))]
    m = re.search(r'매각완료 건수\s*:\s*(\d+)', t)
    out['인근매각건수'] = int(m.group(1)) if m else 0
    out['동일단지사례'] = re.findall(r'(\d{4}타경\d+)\s+(\S+)\s+\S*?\s*([\d.]+)㎡\s*\|\s*감정\s*([\d.]+)억\s*낙찰\s*([\d.]+)억\s*\(([\d.]+)%\)\s*유찰(\d)', t)
    # 기일내역
    out['기일내역'] = re.findall(r'(\d{4}\.\d{2}\.\d{2})\s+\d{2}:\d{2}\s+매각기일\s+([\d,]+)원\s*(유찰)?', t)
    return out

def main():
    ranked = jload(os.path.join(BASE, 'ranked_0909.json'), {'all': [], 'top': []})
    turn = jload(os.path.join(BASE, 'turnover_0909.json'), {})
    stat = jload(os.path.join(BASE, 'data/gg_region_stat_0909.json'), {})

    # 세금 비교
    tax = {}
    for c in ('nonreg_2h', 'reg_2h', 'nonreg_3h', 'reg_3h'):
        d = jload(os.path.join(TAXWS, f'result_{c}.json'))
        if d:
            tax[c] = {
                '취득세': d.get('acquisition', {}).get('total'),
                '양도세': d.get('transfer', {}).get('total'),
                '총세금': d.get('summary', {}).get('total_tax'),
                '세후순익': d.get('summary', {}).get('net_profit_after_tax'),
                '수익률': d.get('summary', {}).get('net_yield_on_cost'),
                'verify': d.get('verify', []),
            }

    # 권리분석
    deep = {}
    for p in sorted(glob.glob(os.path.join(BASE, 'deep0909', 'log_*.txt'))):
        case = re.search(r'log_(.+)\.txt$', os.path.basename(p)).group(1)
        deep[case] = parse_deep(p)

    # top 후보에 환금성·권리 붙이기
    LABEL = {
        '2025타경43094': '안성롯데캐슬', '2025타경65184': '팜스프링', '2025타경43198': '공도주은풍림',
        '2025타경43222': '원곡제일오투', '2026타경60032': '그린시티동문', '2025타경43133': '청북이지더원',
        '2026타경70505': '세창리베하우스', '2026타경60131': '동광모닝스카이',
    }
    merged = []
    for r in ranked['top']:
        cn = re.search(r'(\d{4}타경\d+)', r['사건번호'])
        cn = cn.group(1) if cn else ''
        lab = LABEL.get(cn)
        m = dict(r)
        m['_사건'] = cn
        m['_환금성'] = turn.get(lab, {}) if lab else {}
        m['_권리'] = deep.get(cn, {})
        merged.append(m)

    # 비규제 전체 통계
    allrows = ranked['all']
    prices = [x['_최저가'] for x in allrows if x.get('_최저가')]
    agg = {
        '총건수': len(allrows),
        '최저가중앙': int(statistics.median(prices)) if prices else 0,
        '최저가최소': min(prices) if prices else 0,
        '최저가최대': max(prices) if prices else 0,
        '유찰분포': {str(k): sum(1 for x in allrows if x.get('_유찰') == k) for k in (1, 2, 3)},
        '단지확인': sum(1 for x in allrows if x.get('_세대수n')),
        '1000세대이상': sum(1 for x in allrows if (x.get('_세대수n') or 0) >= 1000),
        '10년이내': sum(1 for x in allrows if (x.get('_준공n') or 0) >= 2016),
    }

    out = {'집계': agg, '지역': stat, '세금': tax, '환금성': turn, '후보': merged}
    json.dump(out, open(os.path.join(BASE, 'report_data_0909.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('집계:', json.dumps(agg, ensure_ascii=False))
    print('세금:', json.dumps(tax, ensure_ascii=False)[:400])
    print('권리분석 파싱:', len(deep), '건')
    for k, v in deep.items():
        print(f"  {k}: 지분={v.get('지분매각')} 임차인={v.get('임차인수')} 인수위험={v.get('인수위험')} "
              f"매각가율={v.get('읍면동매각가율')} 특별조건={'Y' if v.get('특별매각조건') else 'N'}")

if __name__ == '__main__':
    main()
