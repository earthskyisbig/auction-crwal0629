# 법원경매 물건 수집·분석기

법원경매(courtauction.go.kr) 물건을 **① 목록으로 넓게 훑고 → ② 관심 물건을 상세 분석**하는 2단계 도구.

## 2단계 워크플로우

| 단계 | 도구 | 입력 → 출력 | 용도 |
|------|------|-------------|------|
| **① 목록 수집** | `scrape_uijeongbu_apt.py` (스킬: `skill/` = court-auction-scraper) | 검색조건(법원·지역·용도·유찰) → **CSV(다건)** | 후보 스크리닝 |
| **② 상세 분석** | `skill_detail/scripts/analyze_case.py` (스킬: court-auction-detail) | **사건번호 1건** → 5개 법원문서 | 입찰 전 실사 |

②는 사건번호 1건을 상세페이지까지 열어 **매각물건명세서·사건상세조회·현황조사서·감정평가서요약·인근매각물건사례**를 분석한다. 매각물건명세서는 대법원 전자문서(StreamDocs) 텍스트 레이어를 긁어 **임차인(성명·보증금·전입·확정일자·배당요구) + 대항력 인수위험 판정**까지 구조화하고, 이를 바탕으로 **투자분석(예상낙찰가·인수금·취득원가·손익분기가, 시세 입력 시 수익률)** 까지 추정한다.

```bash
# ② 상세 분석 예시
python3 skill_detail/scripts/analyze_case.py --court 서울남부지방법원 --case 2025타경9307
python3 skill_detail/scripts/analyze_case.py --court 남양주지원 --case 2025타경2412 -o out.json

# 투자분석: 예상 매도 시세를 넣으면 순수익·수익률까지
python3 skill_detail/scripts/analyze_case.py --court 남양주지원 --case 2025타경2412 --market 340000000
```

자세한 내용은 `skill_detail/SKILL.md` 참조.

---

## ① 목록 수집기 (아래는 목록 수집 도구)

의정부지방법원 관할 아파트 경매물건 중 유찰 1회 이상인 건을 자동 수집하여 CSV로 저장합니다.

## 수집 항목

사건번호, 물건소재지, 감정가, 최저가, 유찰횟수 → CSV 저장

## 사용법

```bash
pip3 install -r requirements.txt
python3 -m playwright install chromium

# 기본 (의정부지방법원 / 아파트 / 유찰 1회 이상)
python3 scrape_uijeongbu_apt.py

# 법원 변경
python3 scrape_uijeongbu_apt.py --court 서울중앙지방법원

# 유찰 조건 변경
python3 scrape_uijeongbu_apt.py --court 수원지방법원 --flbd-min 3회

# 용도 변경 (대분류 > 중분류 > 소분류)
python3 scrape_uijeongbu_apt.py --lcl 건물 --mcl 주거용건물 --scl 연립다세대

# 전국 / 소분류 전체
python3 scrape_uijeongbu_apt.py --court 전체 --scl 전체

# 출력 파일명 지정
python3 scrape_uijeongbu_apt.py --court 인천지방법원 -o incheon_apt.csv
```

### 옵션

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `-t` / `--template` | — | 템플릿 JSON 파일 경로 |
| `--court` | 의정부지방법원 | 법원명. `전체` 입력 시 전국 검색 |
| `--sido` | — | 시/도 (예: 서울특별시) |
| `--sgg` | — | 시/군/구 (예: 금천구, 양주시) |
| `--lcl` | 건물 | 용도 대분류 |
| `--mcl` | 주거용건물 | 용도 중분류 |
| `--scl` | 아파트 | 용도 소분류. `전체` 입력 시 중분류까지만 적용 |
| `--flbd-min` | 1회 | 유찰횟수 최솟값. `전체` 입력 시 조건 없음 |
| `-o` / `--output` | 자동 생성 | 출력 CSV 파일명 |

출력 파일명 자동 생성 예: `auction_의정부_양주시_아파트_유찰1회.csv`

### 템플릿

자주 쓰는 검색 조건을 `templates/*.json`으로 저장해 재사용할 수 있습니다.
CLI 인자를 함께 쓰면 템플릿 값을 덮어씁니다.

```bash
# 저장된 조건 그대로 실행
python3 scrape_uijeongbu_apt.py -t templates/uijeongbu_apt.json
python3 scrape_uijeongbu_apt.py -t templates/uijeongbu_yangju_apt.json
python3 scrape_uijeongbu_apt.py -t templates/nambu_geumcheon_dasedae.json

# 템플릿 기반으로 일부 조건만 변경
python3 scrape_uijeongbu_apt.py -t templates/uijeongbu_apt.json --sgg 포천시
python3 scrape_uijeongbu_apt.py -t templates/uijeongbu_apt.json --flbd-min 3회
```

**템플릿 추가 방법** — `templates/` 에 JSON 파일 생성:

```json
{
  "court": "수원지방법원",
  "sgg": "수원시",
  "lcl": "건물",
  "mcl": "주거용건물",
  "scl": "아파트",
  "flbd_min": "2회"
}
```

**우선순위**: CLI 인자 > 템플릿 > 기본값

## 프로젝트 구조

```
auction-crwal0629/
├── CLAUDE.md                      # 작업 지침·지도 (Claude Code가 먼저 읽음)
├── requirements.txt               # pip 의존성 (+ python3 -m playwright install chromium)
├── scrape_uijeongbu_apt.py        # ① 목록 수집 진입점 — skill/scripts/scrape_auction_filtered.py 로 위임하는 래퍼
├── filter_listings.py             # 수집 CSV 후처리(저감율 기반 유찰 판정·가격·면적 필터)
├── templates/                     # 검색 조건 템플릿 (skill/scripts/templates/ 와 동일 내용 유지)
├── skill/                         # court-auction-scraper 스킬 원본
│   ├── SKILL.md                   # 올바른 패턴, 드롭다운 체계, API 필드 매핑
│   ├── references/trial-and-error.md
│   └── scripts/
│       ├── scrape_auction_filtered.py   # UI 페이징 수집기 (다중 페이지그룹·수신 시점 중복 제거)
│       ├── collect_api.py               # API 직접 페이징 수집기 v3 (totalCnt 전량 검증, 가격·면적 서버필터)
│       └── scrape_auction.py            # 최소 예제(서울중앙지방법원 고정)
├── skill_detail/                  # court-auction-detail 스킬 원본 (② 상세 분석)
│   └── scripts/analyze_case.py · rights_analysis.py · parse_deungibu.py
├── skills/
│   ├── auction-priority-pipeline/ # 수집→필터→단지보강→실거래 관문→권리분석 오케스트레이션
│   └── seoul-apt-analytics/       # 서울 구별 리포트·아파트 파인더 운영 지침
├── realprice_서울구별/             # 서울 25개 구 실거래 파이프라인 (refresh_all.sh)
├── knowledge-base/                # 정책·세금·법령 근거 + AI 오답노트
├── docs/                          # 강의 자료·개선 기록
└── tests/                         # pytest 단위 테스트 (python3 -m pytest -q tests)
```

`skill/`·`skill_detail/`·`skills/*` 는 `~/.claude/skills/` 에 같은 이름으로 복사되어 Claude Code 스킬로 쓰인다.
이 사이트를 처음 접할 때 반복하기 쉬운 실수들(IP 차단, headless 감지, 파이프라인 딜레이 등)을
사전에 방지하기 위해 시행착오와 해결 패턴을 `references/trial-and-error.md` 에 문서화했다.

### 전량 수집이 중요할 때: `collect_api.py`

UI 페이징 방식은 WebSquare 지연으로 페이지 이동이 씹힐 수 있다. 수집 건수가 사이트 총건수와 일치해야 하면
API 직접 페이징 수집기를 쓴다(검색 폼은 UI로 세팅해 세션을 확보한 뒤, 페이지 번호만 올려 in-page fetch).

```bash
python3 skill/scripts/collect_api.py --court 서울남부지방법원 --sido 서울특별시 --sgg 금천구 \
  --scl 다세대주택 --flbd-min 1회 --max-price 500000000 --area-max 85 -o out.csv
```

## 테스트

```bash
pip install -r requirements.txt
python3 -m pytest -q tests
```

네트워크·브라우저가 필요 없는 순수 로직(권리분석 엔진, 등기부 파서, 유찰 판정, 분석 기간 계산)만 검증한다.

## 기술 스택

- **Playwright** (로컬 브라우저 경유 — 사이트가 외부 IP 직접 호출을 차단함)
- **스텔스 모드** (`--disable-blink-features=AutomationControlled`) — WebSquare 프레임워크의 headless 감지 우회
- **파이프라인 플러시 패턴** — API 응답이 1~2 클릭 뒤에 도착하는 딜레이 처리
