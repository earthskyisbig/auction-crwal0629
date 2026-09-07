# templates/ — 경매 보고서·시뮬레이터 템플릿

2026-08-19 세션에서 만든 보고서·웹앱을 재사용 가능한 템플릿으로 정리한 것.
(루트의 `*.json` 파일들은 별개 용도 — `skill/scripts/scrape_auction_filtered.py -t` 용 검색조건 템플릿)

## 공통 디자인 언어

두 계열 모두 "법원 서류" 컨셉:
- **인주(印朱) 레드**를 유일한 강조색으로 (도장·유찰·손실 신호에만)
- 라이트/다크 3-state 테마 (`:root` 라이트 → `@media dark :root:not([data-theme="light"])` → `:root[data-theme]` 토글 오버라이드)
- 금액은 tabular-nums, 만원 단위

## 1) 문서형 스크리닝 보고서 — `report_screening_doc.html`

정적 보고서 (Artifact 게시용). 나눔명조(제목·랭크) + IBM Plex Sans KR(데이터).
구성: 표지 헤더(검색조건 칩) → KPI 4개 → 추천 Top N 랭킹 → 심층분석 카드(판정 배지) → 주의 물건 → 전체 표.

**플레이스홀더** (빌드 스크립트가 주입):
| 자리 | 내용 |
|---|---|
| `{{MEDIAN}}` `{{CNT3}}` `{{HWAGOK}}` | KPI 수치 (조건에 맞게 라벨도 수정) |
| `{{TOP10}}` | 랭킹 리스트 `<div class="rank">…` |
| `{{DEEP}}` | 심층분석 카드 `<div class="deep ok|cond|no">…` |
| `{{ROWS}}` | 전체 목록 `<tr>` 행들 |

**빌드**: `scripts/build_screening_report.py` — 수집 CSV를 읽어 유찰횟수를 저감율로 역산(서울 20% 저감: 80/64/51%, 경기 30%: 70/49/34%)하고, TOP10/DEEP 데이터 블록(파이썬 리스트)만 바꿔서 재사용.
예시 산출물: 루트 `서울_다세대_경매추천_보고서.html`의 초기 버전.

## 2) 수익 시뮬레이터 (웹앱) — `simulator_*.html`

원본 `simulator_original.html` (공유 아티팩트 '경매 낙찰 수익 시뮬레이터'에서 추출)을 물건 다건용으로 확장한 두 변형.
공통: 落札 스탬프 헤더, 물건 선택 탭(판정 배지), 권리분석 배너, ①물건·시나리오(낙찰가율 슬라이더),
②취득구조(개인/매매사업자/법인·LTV·금리), ③8대 필수비용(자동추정+수정), ⑧양도세 산출내역(1년미만 70%·2년미만 60%·누진세율),
우측 고정 세후수익 패널 + KPI + 워터폴.

### `simulator_apt.html` — 아파트형 (실거래 참조)
참조 카드 = 국토부 실거래: 단지 칩 · 4개 통계(건수/중위/범위/최근월) · **월별 거래 막대** · 최근 거래 표 · "중위가 채우기" 버튼.
**데이터 교체 지점** (스크립트 상단):
- `const PROPS = [...]` — 물건별 {감정가, 기본낙찰가, 매도가, 면적, 인수모드, 배너 HTML}
  - `assumeMode`: `'none'`(인수 없음) / `'dividend'`(보증금−배당액 낙찰가 연동 자동계산, `deposit` 필요) / `'full'`(전액 인수)
- `const REFS = {...}` — 단지별 실거래 (cnt/med/min/max/months/recent)
  → `scripts/fetch_market_ref.py`로 생성 (PublicDataReader, `.env`의 `PUBLIC_DATA_SERVICE_KEY`, 프로젝트 루트에서 실행)
예시 산출물: 루트 `평택안성_경매수익성_리포트.html` (이 파일 자체가 4건 예시 포함).

### `simulator_villa.html` — 빌라형 (기일이력 참조)
빌라는 동일평형 실거래 표본이 없으므로 참조 카드를 변형:
월별 실거래 대신 **이 물건의 기일 이력 막대**(회차별 최저가, 이번 기일=초록) + **읍면동 경매 낙찰사례 통계**(법원경매 인근매각사례).
매도가 기본값 = `감정가 × 읍면동 평균 매각가율` (보수적 처분 프록시 — README의 주의 문구 유지할 것).
**데이터 교체 지점**: `const PROPS = [...]` — 물건별 {감정가, 최저가, dong/cnt/avg/rmin/rmax(인근사례), hist(기일이력), 배너}.
플레이스홀더 `{{ROWS58}}` — 전체 스크리닝 목록 (접이식 표). `scripts/build_villa_simulator.py`가 CSV에서 생성·주입.
예시 산출물: 루트 `서울_다세대_경매추천_보고서.html` (현재 버전).

## 3) 데이터 파이프라인 (템플릿에 넣을 데이터 만드는 법)

1. **목록 수집**: `skill/scripts/collect_api.py` (서울 등 단일시도) 또는 `skill_enrich/scripts/collect_region.py` (+ `enrich_apt.py` 세대수·연식)
2. **사건 상세·권리분석**: `skill_detail/scripts/analyze_case.py --court … --case … [--auto-market]`
   → 매각물건명세서(임차인·대항력·특별매각조건), 기일내역, 인근매각사례, 투자분석 — PROPS의 배너/인수모드 근거
3. **실거래 참조**: `templates/scripts/fetch_market_ref.py` (TARGETS 수정) → REFS 블록
4. 빌드 스크립트로 플레이스홀더 주입 → Artifact 게시

## 주의 (템플릿 유지사항)

- 유찰횟수는 사이트 필드가 부정확 — 반드시 저감율 역산 표기 유지
- 시뮬레이터 세율은 "대표 가정값" — ⚠️ 미검증 면책 문구 삭제 금지
- 인수금액 dividend 모드는 "임차인 1순위 배당" 근사 — 배당표 확인 문구 유지
- `<title>`·favicon은 산출물마다 새로 부여 (같은 Artifact 갱신 시엔 유지)
