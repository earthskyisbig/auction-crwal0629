#!/usr/bin/env python3
"""법원경매 물건 수집기 — 호환용 진입점.

실제 구현은 skill/scripts/scrape_auction_filtered.py 한 곳에만 둔다(단일 진실 원천).
이 파일은 README·강의자료의 `python3 scrape_uijeongbu_apt.py ...` 명령이 계속 동작하도록
인자를 그대로 넘겨 실행하는 얇은 래퍼다.

  python3 scrape_uijeongbu_apt.py -t templates/uijeongbu_apt.json
  python3 scrape_uijeongbu_apt.py --court 서울중앙지방법원 --sido 서울특별시 --sgg 강남구 --scl 아파트 --flbd-min 전체

(2026-09-02: 7월판 단독 구현을 폐기하고 래퍼로 전환 — 다중 페이지그룹 수집·수신 시점 중복 제거·
 물건번호 컬럼 등 8월 버그픽스가 루트 사본에 반영되지 않던 드리프트 해소)
"""
import os
import runpy
import sys

_IMPL = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'skill', 'scripts', 'scrape_auction_filtered.py')

if __name__ == '__main__':
    if not os.path.exists(_IMPL):
        sys.exit(f'구현 파일이 없습니다: {_IMPL}')
    sys.argv[0] = _IMPL
    runpy.run_path(_IMPL, run_name='__main__')
