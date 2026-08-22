#!/bin/bash
# 분기 자동 갱신: 원본 CSV 삭제 → 재수집(매매 24M·전월세 6M) → 분석 → 리포트 생성
set -e
cd "$(dirname "$0")"
rm -f sale_*.csv rent_*.csv
python3 -u collect_seoul.py
python3 -u collect_rent.py
python3 collect_population.py || echo "인구 갱신 실패(기존값 유지)"
python3 analyze_seoul.py
python3 matched_index.py
python3 compute_jeonse.py
python3 compute_belt_dong.py
python3 build_seoul_report.py
echo "REFRESH_DONE"
