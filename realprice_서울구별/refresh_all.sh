#!/bin/bash
# 분기 자동 갱신: 원본 CSV 백업 → 재수집(매매 24M·전월세 6M) → 분석 → 리포트 생성
# 수집이 중간에 실패하면 백업을 되돌려 직전 정상 데이터를 보존한다.
# (아파트 파인더 build_app_data.py → build_app.py 는 수동 갱신 — seoul-apt-analytics 스킬 참고)
set -e
cd "$(dirname "$0")"
mkdir -p _prev
rm -f _prev/*.csv
mv sale_*.csv rent_*.csv _prev/ 2>/dev/null || true
rm -f windows_manifest.json
restore() {
  echo "!! 수집 실패 — 직전 데이터 복원"
  rm -f sale_*.csv rent_*.csv
  mv _prev/*.csv . 2>/dev/null || true
}
trap restore ERR
python3 -u collect_seoul.py
python3 -u collect_rent.py
trap - ERR
rm -rf _prev
python3 collect_population.py || echo "인구 갱신 실패(기존값 유지)"
python3 analyze_seoul.py
python3 matched_index.py
python3 compute_jeonse.py
python3 compute_belt_dong.py
python3 build_seoul_report.py
python3 compute_complex.py
python3 build_complex_report.py
python3 build_terrain.py
python3 build_galaxy.py
# 84㎡ 가격 지도(구별 분포·재건축/신축 효과). 실패해도 본 리포트 갱신은 계속한다.
#   rebuild_zones.json 은 jaegaebal DB 스냅샷 — 로컬에서 p84_export_zones.py 로 갱신·커밋
(python3 p84_compute.py && python3 p84_build.py) || echo "84㎡ 지도 갱신 실패(기존 seoul84_report.html 유지)"
echo "REFRESH_DONE"
