# auction-crwal0629 — 작업 지침 (Claude Code)

한국 부동산 **경매 물건 수집·분석 + 서울 아파트 실거래 분석** 개인 워크스페이스. 언어는 한국어, 스크립트는 Python 3 단일 파일 스크립트 모음(패키지 아님).

## 지도 (어디에 무엇이 있나)

| 경로 | 역할 | 진입점 |
|---|---|---|
| `skill/` | 법원경매 **목록 수집** (court-auction-scraper 스킬 원본) | `skill/scripts/scrape_auction_filtered.py` (UI 페이징), `skill/scripts/collect_api.py` (API 직접 페이징, totalCnt 검증) |
| `scrape_uijeongbu_apt.py` | 위 filtered 스크립트의 **호환 래퍼** (README·강의자료 명령 유지용). 구현은 여기 두지 말 것 | — |
| `skill_detail/` | **사건 1건 상세 분석** (court-auction-detail 스킬 원본): 5개 법원문서 + 권리분석 + 투자분석 | `skill_detail/scripts/analyze_case.py --court … --case …` |
| `skill_detail/scripts/rights_analysis.py` | 등기부 권리분석 엔진(순수 함수) | `analyze_rights(entries, 경매개시일, 명세서임차인)` |
| `skill_detail/scripts/parse_deungibu.py` | 등기부 PDF → 권리 목록 | `--selftest` 로 합성 검증 |
| `skills/auction-priority-pipeline/` | 수집→필터→단지보강→실거래 관문→권리분석 5단계 오케스트레이션 | `scripts/enrich_complex.py`, `scripts/eval_priority.py` |
| `skills/seoul-apt-analytics/` | 서울 25개 구 분석 자산 **운영 지침**(원본은 아래 디렉터리) | — |
| `realprice_서울구별/` | 서울 구별 평당가 리포트 + 아파트 파인더 파이프라인 | `bash refresh_all.sh` (리포트), `build_app_data.py → build_app.py` (파인더) |
| `filter_listings.py` | 수집 CSV 후처리 필터(저감율 기반 유찰 판정) | `python3 filter_listings.py in.csv out.csv` |
| `templates/` = `skill/scripts/templates/` | 검색 조건 템플릿(두 디렉터리 **내용 동일 유지**) | — |
| `knowledge-base/` | 정책·세금·법령 근거 저장소 + AI 오답노트 | `knowledge-base/README.md` |
| `docs/` | 강의 자료(서문·슬라이드·실습 가이드) | — |
| `tests/` | pytest 단위 테스트(순수 로직만, 네트워크 없음) | `python3 -m pytest -q tests` |

`~/.claude/skills/{court-auction-scraper, court-auction-detail, auction-priority-pipeline, seoul-apt-analytics}` 는 이 저장소 `skill/`, `skill_detail/`, `skills/*` 의 **사본**이다. 어느 한쪽을 고치면 반대쪽도 맞춰라(`diff -rq` 로 확인). 저장소가 단일 진실 원천.

## 실행 전제

- 국토부 API 키: `.env` 의 `PUBLIC_DATA_SERVICE_KEY` (Decoding 키). `.env.example` 참고. 키를 쓰는 스크립트는 **프로젝트 루트에서 실행**해야 `find_dotenv` 가 잡는다.
- 의존성: `pip install -r requirements.txt` 후 `python3 -m playwright install chromium`.
- 법원경매 사이트는 IP 차단·헤드리스 감지·WebSquare 파이프라인 지연이 있다. `requests/curl` 직접 호출은 전부 실패하며 Playwright 스텔스만 동작한다. 세부 함정은 `skill/references/trial-and-error.md`, `skill_detail/references/trial-and-error.md`.
- 국토부 RTMS·K-apt: **PublicDataReader 금지**(이 환경에서 segfault). requests 직접 호출, 병렬 금지, 호출당 sleep 0.3~0.35s + 에러 XML 백오프.

## 코드 규칙

- 새 로직은 **함수로 감싸고 `if __name__ == '__main__':` 가드**를 둔다. 모듈 import 만으로 네트워크 호출·파일 쓰기가 일어나면 테스트할 수 없다.
- 순수 로직(파싱·판정·계산)을 바꾸면 `tests/` 에 케이스를 추가하고 `python3 -m pytest -q tests` 를 통과시킨다. 네트워크·브라우저가 필요한 코드는 테스트 대상이 아니다.
- CSV 출력은 `utf-8-sig`(엑셀 호환). 금액은 원 단위 정수, RTMS `dealAmount` 만 **만원 단위**임에 주의.
- 통계 원칙(realprice-flow): 해제거래(`cdealType == 'O'`) 제외, 상·하위 1% 컷, 단일 월 비교 금지, 기간은 `realprice_서울구별/windows.py` 만 참조(하드코딩 금지, 지난달 종료). 실거래 CSV 는 `sales_io.load_sales()` 로만 읽는다(해제 쌍둥이 행 제거).
- 세법·규제 수치(취득세율, 소액임차인 기준 등)를 코드에 넣을 때는 시행일과 출처를 주석에 남기고 `knowledge-base/` 에 근거를 적는다. AI가 틀렸던 사례는 `knowledge-base/09_AI오답노트/` 에 날짜별로 기록한다.

## 커밋하지 않는 것

`.env`, `auction_*.csv`(auction_list.csv 제외), `raw_*.json`, `case_*.json`, `realprice_서울구별/{sale,rent}_*.csv`, `hh_*.json`, `shot*.png`, `priority_eval.json`. 전부 `.gitignore` 에 있다. `purmi_*.json` 두 개(약 3.7MB)는 과거에 커밋된 원본 덤프이며, 양주푸르지오 보고서 재현용으로만 남겨 둔다.

## 운영 자산 (외부)

- 서울 구별 리포트·아파트 파인더 아티팩트 URL, 분기 자동 갱신 루틴 ID: `skills/seoul-apt-analytics/SKILL.md`.
- 개선 이력: `docs/개선기록_2026-09-02.md`.
