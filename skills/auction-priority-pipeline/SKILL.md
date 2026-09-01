---
name: auction-priority-pipeline
description: 경매 아파트 물건을 사용자 우선순위 기준으로 걸러 최종 추천까지 뽑는 파이프라인. "경기도/서울 아파트 유찰 물건 추천해줘", "경매 물건 필터링해서 우선순위 매겨줘", "유찰 1~2회 신축 대단지 찾아줘", "실거래량·전세가율로 경매 물건 검증", "통과 물건 권리분석까지" 같은 요청이면 이 스킬을 읽어라. 수집(court-auction-scraper)→기본필터→단지 보강(국토부 K-apt)→실거래 관문(회전율 4%·실거래가>감정가)→권리분석(court-auction-detail) 5단계를 순서대로 오케스트레이션한다. 개별 사건 상세분석만 원하면 court-auction-detail, 목록 수집만 원하면 court-auction-scraper를 직접 써라.
---

# 경매 우선순위 파이프라인

2026-08 경기도 아파트 실전(263건 → 19건 → 5건 → 최종 4건)에서 검증된 5단계 깔때기.
사용자(algo1744)의 우선순위 기준은 메모리 `auction-priority-criteria`에 있다:
**① 연간 실거래량 ≥ 세대수의 4% ② 실거래가 > 감정가 ③ 연식 ④ 역거리 ⑤ 학세권 — 권리분석은 최종 통과분만.**

## 5단계 워크플로

| 단계 | 도구 | 산출 |
|---|---|---|
| 1. 수집 | court-auction-scraper 스킬 (`scrape_auction_filtered.py`) — **법원당 1회 실행**으로 분리 | 법원별 CSV |
| 2. 기본 필터 + 단지 보강 | `scripts/enrich_complex.py` | 유찰 1~2회·전용 59~84㎡ + 세대수·준공 |
| 3. 조건 확정 | (기본값) 준공 10년 이내 + 500세대 이상 — **스크립트 없음, enriched.csv 의 세대수·준공 컬럼으로 수동 선별** | 후보 목록 |
| 4. 실거래 관문 | `scripts/eval_priority.py` | 회전율·동평형 실거래가 → PASS 판정. 역/학교(연식·역거리·학세권)는 **기록만 하고 임계값 없음** — 통과분 중 수동 우선순위 |
| 5. 권리분석 | court-auction-detail 스킬 (`analyze_case.py --auto-market`) 통과분만 순차 | 인수금·투자분석 |

리포트는 algo-design 톤 HTML → Artifact 발행 (artifact-design·dataviz 스킬 먼저 로드).

## 실행 요령

```bash
# 1단계: 법원별 개별 백그라운드 실행 (10분 컷 안에 끝나게)
python3 ~/.claude/skills/court-auction-scraper/scripts/scrape_auction_filtered.py \
  --court 의정부지방법원 --sido 경기도 --lcl 건물 --mcl 주거용건물 --scl 아파트 --flbd-min 1회 -o court_의정부.csv
# 경기 관할: 의정부·고양·수원·성남·안산·안양·부천·평택·여주 (인천지법 본원은 경기 물건 없음)

# 2단계: 병합 CSV → 필터+보강 (프로젝트 루트에서, .env의 PUBLIC_DATA_SERVICE_KEY 필요)
python3 skills/auction-priority-pipeline/scripts/enrich_complex.py merged.csv enriched.csv   # --flbd 1,2 --area 59-84.99 로 조정 가능

# 4단계: 우선순위 평가 — 후보를 items.json 으로 넘긴다 (필드: case,name,tkey,sggs,dong,area,appr,low,flbd,day,built,households)
python3 skills/auction-priority-pipeline/scripts/eval_priority.py --items items.json -o priority_eval.json
#   예) [{"case":"수원 2025타경58196","name":"수원하늘채더퍼스트2단지","tkey":"하늘채더퍼스트","sggs":["41113"],
#        "dong":"곡반정동","area":84.96,"appr":66000,"low":46200,"flbd":1,"day":"8.24","built":"2022.06","households":1833}]
#   (금액은 만원 단위. --items 생략 시 파일 내 ITEMS 상수 사용 — 구방식 호환)
```

## 함정 (전부 실측)

- **PublicDataReader는 이 환경(pandas+py3.14)에서 segfault(exit 139)** — RTMS·K-apt 모두
  requests 직접 호출 + XML/JSON 파싱으로 우회한다. 스크립트가 이미 그렇게 돼 있다.
- **RTMS 429**: data.go.kr 초당 요청제한. 병렬 금지, 호출당 sleep 0.3s + 에러XML(returnReasonCode) 백오프.
- **화성시 분구(2026)**: 시군구코드 41590 → 41591(만세)·41593(효행)·41595(병점)·41597(동탄).
  부천 3구(41192/94/96)도 주의. 스크립트의 SGG_CODES에 반영돼 있다.
- **단지명 매칭 함정**: 경매 표기 ≠ K-apt ≠ RTMS 표기. 정규화(공백·괄호 제거, 이편한세상→e편한세상)
  + 법정동 우선 매칭 + 실패 시 건축년도로 대조. RTMS 예: "목감 호반써밋 더숲"(K-apt) =
  "호반베르디움더숲"(RTMS). 0건이 나오면 이름 변형을 의심하라.
- **유찰 2회 저가 물건은 싼 이유를 먼저 찾아라**: 대항력 임차인이 배당요구를 안 했으면 보증금
  전액 인수(2025타경42667: 2.8억 인수로 -2.5억). 반대로 **HUG가 '대항력 포기 확약서'를 낸 물건**은
  표면상 대항력이 있어도 실질 인수 0원(2025타경53080) — 명세서 비고를 반드시 읽어라.
- **실거래가>감정가 판정**: 동평형(±2㎡) 최근 12개월 최고가 기준(중앙값 병기). 신축(준공 2년 내)은
  거래 이력 0건이라 관문 통과 불가 — 별도 표기.
- 시세 관문의 미확보 데이터(회전율 4% 근소 미달 등)는 탈락 사유와 수치를 함께 보고해
  사용자가 기준 완화 여부를 판단하게 하라.
