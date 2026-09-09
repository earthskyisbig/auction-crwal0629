# -*- coding: utf-8 -*-
"""경기도 경매 목록 → 규제지역/비규제지역 분류.

규제지역(조정대상지역·투기과열지구) 근거:
- 2025-10-16 시행: 과천, 광명, 성남(분당·수정·중원), 수원(영통·장안·팔달),
  안양 동안구, 용인 수지구, 의왕, 하남  (국토부 2025-10-15 주택시장 안정화 대책)
- 2026-07-01 시행: 화성 동탄구, 용인 기흥구, 구리  (국토부 2026-06-29 주정심 의결)
"""
import csv, re, sys, json, collections, os

# (시, 구) — 구가 None 이면 시 전역 규제
REGULATED = {
    ('과천시', None), ('광명시', None), ('의왕시', None), ('하남시', None), ('구리시', None),
    ('성남시', '분당구'), ('성남시', '수정구'), ('성남시', '중원구'),
    ('수원시', '영통구'), ('수원시', '장안구'), ('수원시', '팔달구'),
    ('안양시', '동안구'),
    ('용인시', '수지구'), ('용인시', '기흥구'),
    ('화성시', '동탄구'),
}
CITY_WIDE = {c for c, g in REGULATED if g is None}

ADDR_RE = re.compile(r'경기도\s+(\S+?[시군])\s*(\S+?구)?(?=\s|$)')

def parse_region(addr):
    m = ADDR_RE.match(addr.strip())
    if not m:
        return None, None
    return m.group(1), m.group(2)

def is_regulated(city, gu):
    if city in CITY_WIDE:
        return True
    return (city, gu) in REGULATED

def won(v):
    return int(re.sub(r'[^\d]', '', v or '0'))

def flbd_from_rate(rate):
    """경기 30% 저감: 100%=신건, 70%=1회, 49%=2회, 34%=3회 (근사 경계)"""
    if rate >= 95: return 0
    if rate >= 60: return 1
    if rate >= 42: return 2
    return 3

def main(src, out_non, out_reg, out_json):
    rows = list(csv.DictReader(open(src, encoding='utf-8-sig')))
    non, reg, unknown = [], [], []
    for r in rows:
        city, gu = parse_region(r['물건소재지'])
        if city is None:
            unknown.append(r); continue
        rate = int(re.sub(r'[^\d]', '', r['저감율'] or '0'))
        r['_시'], r['_구'] = city, gu or ''
        r['_지역'] = f"{city} {gu}".strip()
        r['_유찰추정'] = flbd_from_rate(rate)
        r['_최저가원'] = won(r['최저가'])
        r['_감정가원'] = won(r['감정가'])
        (reg if is_regulated(city, gu) else non).append(r)

    cols = list(rows[0].keys()) + ['_시', '_구', '_지역', '_유찰추정', '_최저가원', '_감정가원']
    for path, data in ((out_non, non), (out_reg, reg)):
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(data)

    stat = {
        '총건수': len(rows), '비규제': len(non), '규제': len(reg), '미분류': len(unknown),
        '비규제_지역분포': collections.Counter(x['_지역'] for x in non).most_common(),
        '규제_지역분포': collections.Counter(x['_지역'] for x in reg).most_common(),
        '비규제_유찰분포': collections.Counter(x['_유찰추정'] for x in non).most_common(),
    }
    json.dump(stat, open(out_json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(stat, ensure_ascii=False, indent=1))

if __name__ == '__main__':
    base = os.path.dirname(os.path.abspath(__file__))
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(base, 'data/gg_apt_u1to3_2eok_0909.csv'),
         os.path.join(base, 'data/gg_nonreg_0909.csv'),
         os.path.join(base, 'data/gg_reg_0909.csv'),
         os.path.join(base, 'data/gg_region_stat_0909.json'))
