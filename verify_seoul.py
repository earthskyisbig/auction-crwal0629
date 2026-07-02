#!/usr/bin/env python3
"""서울 수집 데이터 정합성 검증.

정정된 필드가 맞는지 산술 검증:
  최저가(notifyMinmaePrice1) == 감정가 × (저감율/100)  이어야 함.
  서울 법원은 20% 저감 → 유찰1회 = 80%, 2회 = 64%, 3회 = 51.2% ...
불일치 건이 있으면 필드 매핑에 여전히 문제가 있다는 신호.
"""
import csv, re

SRC = 'auction_서울전체_아파트.csv'

def money(s):
    d = re.sub(r'[^\d]', '', s or ''); return int(d) if d else 0

rows = list(csv.DictReader(open(SRC, encoding='utf-8-sig')))
print(f"서울 아파트 수집: {len(rows)}건\n")

# 저감율 분포
rate_dist = {}
mismatch = []
for r in rows:
    rate = re.sub(r'[^\d]', '', r.get('저감율','') or '')
    rate_dist[rate] = rate_dist.get(rate, 0) + 1
    gam, low = money(r.get('감정가','')), money(r.get('최저가',''))
    if gam == 0 or not rate:
        continue
    expected = round(gam * int(rate) / 100)
    # 원 단위 반올림 오차 허용 (10원)
    if abs(low - expected) > 10:
        mismatch.append((r, gam, low, expected, rate))

print("■ 저감율(%) 분포  — 서울 20%저감 체계면 100/80/64/51/41...")
for rt in sorted(rate_dist, key=lambda x: -int(x or 0)):
    label = {'100':'유찰0회(신건)','80':'유찰1회','64':'유찰2회','51':'유찰3회','41':'유찰4회'}.get(rt,'')
    print(f"   {rt or '(없음)':>4}% : {rate_dist[rt]:3d}건  {label}")

print(f"\n■ 산술 검증: 최저가 == 감정가 × 저감율 ?")
if not mismatch:
    print(f"   ✅ 전체 {len(rows)}건 모두 일치 — notifyMinmaePrice1 필드 정확")
else:
    print(f"   ⚠️ 불일치 {len(mismatch)}건:")
    for r, gam, low, exp, rate in mismatch[:20]:
        print(f"      {r['사건번호']}  감정{gam:,}×{rate}%=기대{exp:,} vs 실제{low:,}")

# 유찰1회 저감율(80%) 교차: yuchalCnt=1 인데 rate≠80 인 이상치
print(f"\n■ 유찰횟수 vs 저감율 교차 (yuchalCnt=1 이면 rate=80 이어야)")
cross = {}
for r in rows:
    y = str(r.get('유찰횟수','')).strip()
    rate = re.sub(r'[^\d]', '', r.get('저감율','') or '')
    cross[(y, rate)] = cross.get((y, rate), 0) + 1
for (y, rate), c in sorted(cross.items(), key=lambda x: (int(x[0][0] or 0), -int(x[0][1] or 0))):
    exp = {'0':'100','1':'80','2':'64','3':'51','4':'41'}.get(y)
    flag = '' if exp == rate else '  ⚠ 불일치'
    print(f"   유찰{y}회 × {rate}%  : {c}건{flag}")
