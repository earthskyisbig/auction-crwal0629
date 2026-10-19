# -*- coding: utf-8 -*-
"""공매(KAMCO 압류재산) 대항력 임차인 물건의 인수 바닥·입찰 상한 계산.

배분 순서(근사): 체납처분비 → 당해세(보수적으로 임차인 앞) → 대항력+확정일자 임차인 → 나머지.
  인수액 = max(0, 보증금 - max(0, 낙찰가 - 선순위))  → 실질원가 = 낙찰가 + 인수액
  ⇒ 실질원가 바닥 = 선순위 + 보증금 (그 아래로 써도 원가는 줄지 않는다)
입찰 상한 = (목표가치 × (1 - 마진) - 부대비용) / (1 + 취득세율 + 법무비율)
공매 예정가: 최초 예정가의 10%씩 체감, 50%까지 (국세징수법 — 회차는 온비드로 재확인).

사용:
  python skills/gongmae-redev-review/scripts/bid_calc.py --appraisal 333500000 --deposit 262500000 \
      --senior 4000000 --value-now 383000000 --value-down 327000000
"""
import argparse, sys

if hasattr(sys.stdout, 'reconfigure'):          # Windows cp949 콘솔에서 한글·기호 깨짐 방지
    sys.stdout.reconfigure(encoding='utf-8')

# 6억 이하·85㎡ 이하·조정대상지역(서울 전역, 2025-10-16 지정) 가정. 비조정·일시적 2주택·공시 1억 이하는 다름 — 개별 확인
TAX = {'1주택 1.1%': 0.011, '2주택 8.4%': 0.084, '3주택+ 12.4%': 0.124}


def assumed(bid, deposit, senior, claimed=True):
    """낙찰가 bid 에서 매수인이 인수하는 보증금 부족분. 배분요구 안 했으면(claimed=False) 전액 인수."""
    if not claimed:
        return deposit
    return max(0, deposit - max(0, bid - senior))


def effective_cost(bid, deposit, senior, claimed=True):
    return bid + assumed(bid, deposit, senior, claimed)


def bid_cap(value, margin, extra, tax, legal=0.003):
    return (value * (1 - margin) - extra) / (1 + tax + legal)


def rounds(appraisal, n=6):
    """공매 회차별 예정가: 최초의 100%, 90%, 80% … 50%."""
    return [round(appraisal * max(0.5, 1 - 0.1 * i)) for i in range(n)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--appraisal', type=int, required=True, help='최초 공매예정가(=감정가)')
    ap.add_argument('--deposit', type=int, required=True, help='대항력 임차보증금')
    ap.add_argument('--senior', type=int, default=0, help='임차인보다 앞서는 배분액(체납처분비+당해세)')
    ap.add_argument('--value-now', type=int, required=True, help='현재 시세(프리미엄 포함)')
    ap.add_argument('--value-down', type=int, required=True, help='하방 가치(프리미엄 소멸, 보통 감정가)')
    ap.add_argument('--extra', type=int, default=13_000_000, help='명도·수리·체납관리비 등')
    ap.add_argument('--no-claim', action='store_true', help='대항력 임차인이 배분요구 안 함 → 보증금 전액 인수')
    a = ap.parse_args()
    claimed = not a.no_claim
    if not claimed:
        print('※ 배분요구 없음: 보증금 %s원 전액 인수 — 아래 상한에서 보증금을 뺀 값이 실제 입찰 상한' % format(a.deposit, ','))
    floor = a.senior + a.deposit
    print('실질원가 바닥(인수 0 되는 낙찰가) = %s원' % format(floor, ','))
    print('회차별 예정가:', ', '.join('%d차 %s' % (i + 1, format(p, ',')) for i, p in enumerate(rounds(a.appraisal))))
    for i, p in enumerate(rounds(a.appraisal)):
        print('  %d차 예정가 낙찰 시 인수 %s원 / 실질원가 %s원' % (i + 1, format(assumed(p, a.deposit, a.senior, claimed), ','),
                                                         format(effective_cost(p, a.deposit, a.senior, claimed), ',')))
    print('\n취득세 구간 | 하방 손익분기 | 현재가 10% 마진 | 현재가 5% 마진')
    less = 0 if claimed else a.deposit
    for k, t in TAX.items():
        print('%s | %s | %s | %s' % (k, *(format(int(round(bid_cap(v, m, a.extra, t), -5)) - less, ',') for v, m in
                                         ((a.value_down, 0), (a.value_now, 0.10), (a.value_now, 0.05)))))
    print('※ 권장 = max(바닥, min(하방 손익분기, 10% 마진)) 근처, 상한 = 5% 마진. 바닥보다 낮은 상한이면 입찰 보류.')


if __name__ == '__main__':
    main()
