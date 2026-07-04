# -*- coding: utf-8 -*-
"""등기사항전부증명서(등기부) PDF → 구조화 권리 목록 → 권리분석 (B안).

사용:
  python parse_deungibu.py 등기부.pdf                 # 파싱 + 권리분석 출력
  python parse_deungibu.py 등기부.pdf --dump-text     # 원문 텍스트 덤프(포맷 확인/튜닝용)
  python parse_deungibu.py 등기부.pdf --started 20250625   # 경매개시일 지정

⚠️ 인터넷등기소 발급/열람 PDF는 대개 텍스트 레이어가 있다(스캔이면 OCR 필요 → --dump-text 로 확인).
   파서는 표준 등기부 서식 기준 휴리스틱이며, 실제 샘플로 검증·튜닝해야 한다.
"""
import re, sys, argparse

# 등기목적 → 표준 키워드 (엔진의 _MALSO_BASE/_INSU_IF_SENIOR 와 호환)
_AMT_KEYS = ('채권최고액', '전세금', '청구금액', '보증금', '금')
_DATE_RE = re.compile(r'(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일')
_AMT_RE = re.compile(r'금?\s*([\d,]{4,})\s*원')
_RANK_RE = re.compile(r'^\s*(\d+(?:-\d+)?)\s')           # 순위번호(1, 2-1 등)
_MALSO_TARGET_RE = re.compile(r'(\d+(?:-\d+)?)\s*번.*?(?:등기)?말소')


def extract_pages(pdf_path):
    import pdfplumber
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for pg in pdf.pages:
            pages.append(pg.extract_text() or '')
    return pages


def _find_amount(text):
    """항목 텍스트에서 대표 금액(채권최고액/전세금/보증금/청구금액) 추출."""
    for key in ('채권최고액', '전세금', '임차보증금', '보증금', '청구금액'):
        m = re.search(key + r'\s*금?\s*([\d,]{4,})\s*원', text)
        if m:
            return int(m.group(1).replace(',', ''))
    # 키워드 없으면 가장 큰 '금 N원'
    amts = [int(a.replace(',', '')) for a in _AMT_RE.findall(text)]
    return max(amts) if amts else None


def _purpose(text):
    """등기목적 표준화 — 첫 줄에서 키워드 추출. '말소'는 최우선(다른 권리명 포함돼도 말소로)."""
    head = (text.strip().split('\n')[0] if text.strip() else '')[:40]
    if '말소' in head:               # 'N번근저당권설정등기말소' → 근저당 아님, 말소로 분류
        return '말소'
    for kw in ('근저당권설정', '저당권설정', '전세권설정', '지상권설정', '지역권설정',
               '주택임차권', '임차권설정', '가압류', '압류', '가처분', '가등기',
               '소유권이전청구권', '환매특약', '강제경매개시결정', '임의경매개시결정',
               '경매개시결정', '소유권이전', '소유권보존'):
        if kw in text:
            return kw
    return (text.strip().split('\n')[0][:20] if text.strip() else '미상')


def parse_deungibu(pdf_path):
    """PDF → {'갑구':[entry...], '을구':[entry...], '전체':[...]}. entry는 엔진 스키마."""
    full = '\n'.join(extract_pages(pdf_path))
    # 【갑구】/【을구】 섹션 분리
    def section(name_variants):
        for nm in name_variants:
            i = full.find(nm)
            if i != -1:
                return i
        return -1
    i_gap = section(['【 갑 구 】', '【갑구】', '갑구 ]', '[ 갑 구 ]'])
    i_eul = section(['【 을 구 】', '【을구】', '을구 ]', '[ 을 구 ]'])
    gap_txt = full[i_gap:i_eul] if i_gap != -1 and i_eul != -1 else (full[i_gap:] if i_gap != -1 else '')
    eul_txt = full[i_eul:] if i_eul != -1 else ''

    def parse_section(sec_txt, gubun):
        entries, cur = [], None
        for line in sec_txt.split('\n'):
            m = _RANK_RE.match(line)
            if m and any(k in line for k in ('설정', '경매', '압류', '가처분', '이전', '보존', '가등기', '말소', '환매')):
                if cur:
                    entries.append(cur)
                cur = {'구분': gubun, '순위번호': m.group(1), '_text': line}
            elif cur is not None:
                cur['_text'] += '\n' + line
        if cur:
            entries.append(cur)
        # 필드 추출
        out = []
        for e in entries:
            t = e['_text']
            dm = _DATE_RE.search(t)
            out.append({
                '구분': gubun, '순위번호': e['순위번호'], '등기목적': _purpose(t),
                '접수일': (int(dm.group(1)), int(dm.group(2)), int(dm.group(3))) if dm else None,
                '금액': _find_amount(t),
                '권리자': _extract_person(t),
                '말소여부': ('말소' in _purpose(t)),
                '_원문': re.sub(r'\s{2,}', ' ', t).strip()[:200],
            })
        return out

    gap = parse_section(gap_txt, '갑구')
    eul = parse_section(eul_txt, '을구')
    # 말소 처리: "N번...말소" 항목이 있으면 해당 순위 권리를 말소여부=True
    allrows = gap + eul
    malso_targets = set()
    for e in allrows:
        mt = _MALSO_TARGET_RE.search(e['_원문'])
        if mt:
            malso_targets.add((e['구분'], mt.group(1)))
    for e in allrows:
        if (e['구분'], e['순위번호']) in malso_targets:
            e['말소여부'] = True
    # 말소 항목 자체는 분석에서 제외
    live = [e for e in allrows if '말소' not in e['등기목적']]
    return {'갑구': gap, '을구': eul, '전체': allrows, '분석대상': live}


def _extract_person(text):
    m = re.search(r'(?:권리자|근저당권자|전세권자|가처분권자|채권자|소유자|임차권자)\s*[:：]?\s*([가-힣A-Za-z0-9()\s]{2,20})', text)
    return m.group(1).strip() if m else ''


_SYNTH = """【 갑 구 】 ( 소유권에 관한 사항 )
1 소유권보존 2009년7월2일 제12345호 소유자 김철수
3 가압류 2023년5월1일 제9999호 채권자 우리은행 청구금액 금50,000,000원
4 임의경매개시결정 2025년6월25일 제11111호 채권자 국민은행
【 을 구 】 ( 소유권 이외의 권리에 관한 사항 )
1 전세권설정 2019년3월1일 제3333호 전세금 금200,000,000원 전세권자 박전세
2 근저당권설정 2020년11월4일 제7777호 채권최고액 금120,000,000원 근저당권자 국민은행
3 근저당권설정 2018년1월5일 제1111호 채권최고액 금300,000,000원 근저당권자 신한은행
4 3번근저당권설정등기말소 2021년6월1일 제2222호 2021년5월30일 해지
"""


def _selftest():
    """합성 등기부 텍스트로 파싱+엔진 검증(pdfplumber 우회)."""
    global extract_pages
    orig = extract_pages
    extract_pages = lambda p: [_SYNTH]
    try:
        d = parse_deungibu('synthetic')
    finally:
        extract_pages = orig
    from rights_analysis import analyze_rights
    r = analyze_rights(d['분석대상'], 경매개시일=(2025, 6, 25))
    checks = {
        '말소기준=근저당2020.11.4': r['말소기준일'] == (2020, 11, 4),
        '전세권 인수 2억': r['정밀인수금'] == 200000000,
        '말소된 2018근저당 제외': all(e['접수일'] != (2018, 1, 5) for e in
                                [x for x in d['분석대상'] if not x['말소여부']]),
        '말소등기 자체 제외': all('말소' not in e['등기목적'] for e in d['분석대상']),
        '인수권리=전세권1건': [x['등기목적'] for x in r['인수권리']] == ['전세권설정'],
    }
    print("=== parse_deungibu 자체검증(합성) ===")
    for k, v in checks.items():
        print(f"  [{'✅' if v else '❌'}] {k}")
    print("전체:", "통과 ✅" if all(checks.values()) else "실패 ❌")
    return all(checks.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf', nargs='?', help='등기부 PDF 경로 (--selftest 시 생략)')
    ap.add_argument('--dump-text', action='store_true', help='원문 텍스트 덤프(포맷 확인)')
    ap.add_argument('--selftest', action='store_true', help='합성 데이터로 파싱+엔진 검증')
    ap.add_argument('--started', help='경매개시일 YYYYMMDD')
    a = ap.parse_args()

    if a.selftest:
        _selftest(); return
    if not a.pdf:
        ap.error('pdf 경로가 필요합니다 (또는 --selftest)')

    if a.dump_text:
        for i, p in enumerate(extract_pages(a.pdf)):
            print(f"\n===== PAGE {i} =====\n{p}")
        return

    parsed = parse_deungibu(a.pdf)
    print("=== 파싱된 권리 (분석대상) ===")
    for e in parsed['분석대상']:
        d = e['접수일']
        접수 = f'{d[0]}.{d[1]}.{d[2]}' if d else '?'
        금액 = f"{e['금액']:,}원" if e['금액'] else '-'
        print(f"  [{e['구분']} {e['순위번호']}] {e['등기목적']} | 접수 {접수} | 금액 {금액} | {e['권리자']}")

    started = None
    if a.started and len(a.started) == 8:
        started = (int(a.started[:4]), int(a.started[4:6]), int(a.started[6:8]))
    from rights_analysis import analyze_rights
    r = analyze_rights(parsed['분석대상'], 경매개시일=started)
    print("\n=== 권리분석 ===")
    print("  말소기준권리:", r['말소기준권리'])
    print("  인수권리:")
    for x in r['인수권리']:
        print(f"    · [{x['구분']} {x['순위번호']}] {x['등기목적']} — {x['사유']}")
    if not r['인수권리']:
        print("    (없음 — 등기부상 인수권리 없음)")
    print(f"  정밀 인수금(등기부 기준): {r['정밀인수금']:,}원")
    print("  ⚠️", r['_주의'])


if __name__ == '__main__':
    sys.path.insert(0, __file__.rsplit('/', 1)[0])
    main()
