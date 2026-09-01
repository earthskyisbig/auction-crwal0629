---
name: seoul-apt-analytics
description: 서울 25개 구 아파트 실거래 분석 자산 운영·확장 스킬. "서울 구별 평당가 리포트 갱신/수정해줘", "아파트 파인더 앱 업데이트", "서울 리포트에 섹션 추가", "분기 루틴 상태 확인", "다른 지역(경기 등)으로 같은 리포트 만들어줘" 같은 요청이면 이 스킬을 읽어라. 원본 파이프라인은 저장소 auction-crwal0629/realprice_서울구별/ 에 있고, 결과물은 고정 URL 아티팩트 2개(구별 리포트·아파트 파인더)와 분기 클라우드 루틴으로 운영된다. 한 지역의 신규 심층 분석은 realprice-flow, 단지 하나 분석은 apt-value를 쓰고, 이 스킬은 이미 구축된 서울 자산의 운영·확장 전용이다.
---

# 서울 아파트 분석 자산 (2026-08 구축)

원본은 전부 **`/Users/leomyung/auction-crwal0629/realprice_서울구별/`** (GitHub earthskyisbig/auction-crwal0629, main).
스킬에는 사본을 두지 않는다 — 저장소가 단일 진실 원천.

## 자산 목록

| 자산 | 위치/URL | 갱신 방법 |
|---|---|---|
| 구별 평당가 리포트 (지도·히트맵·버블·벨트 동별·전세가율) | https://claude.ai/code/artifact/49f6f0eb-0c9f-490e-b382-2f44eb107ff1 | `bash refresh_all.sh` → `Artifact(url=위 URL)` |
| 아파트 파인더 (3,435개 단지 검색+분석기) | https://claude.ai/code/artifact/706eb608-7d2c-46a9-9a88-415c478eab26 | `build_app_data.py` → `build_app.py` → `Artifact(url=위 URL)` |
| 분기 자동 갱신 루틴 | trig_019RU1R2bHGnkBpvQmovieE2 (1·4·7·10월 15일 09:17 KST) | RemoteTrigger로 관리, 삭제는 claude.ai/code/routines |

## 파이프라인 구조 (실행 순서 = refresh_all.sh)

```
collect_seoul.py   매매 24개월 (RTMS XML 직접, 구별 sale_*.csv)
collect_rent.py    전월세 6개월 (rent_*.csv)
collect_population.py  행안부 주민등록 인구 (statMonth.do POST, sltOrgType=2)
analyze_seoul.py   월별 중앙값+3개월 이동중앙값, 양끝6개월 변화 → seoul_gu_insights.json
matched_index.py   동일 단지·평형 매칭 지수 (구성편향 보정) → seoul_gu_matched.json
compute_jeonse.py  전세가율 (동일 단지·평형 전세÷매매) → jeonse_ratio.json
compute_belt_dong.py  한강벨트 5개 구 법정동 분해 → belt_dong.json
build_seoul_report.py  charts_extra.py(지도·히트맵·버블·벨트·전세맵) → seoul_report.html
```
- 날짜는 전부 `windows.py`(롤링 24개월, **지난달 종료** — 이번 달은 신고 지연으로 제외) 기준. `collect_seoul.py` 가 전 구 수집을 마치면 `windows_manifest.json` 에 기간을 기록하고, 분석 스크립트는 그 기간을 그대로 써서 달이 바뀌어도 CSV 와 어긋나지 않는다(refresh_all.sh 가 시작 시 삭제).
- 리포트의 기간·전세가율·벨트 동·착시 사례 문장은 전부 데이터에서 생성한다(2026-09-02 하드코딩 제거). 축 범위도 데이터로 계산.
- 해제거래는 `sales_io.load_sales()` 가 원본행+해제행 쌍을 통째로 버린다(O행만 버리면 원본이 남아 약 5% 해제 거래가 통계에 섞였음). 매매·전세 매칭 키는 (법정동, 단지, 면적) — 동명 단지 혼입 방지. 전세가율은 신규 계약만(갱신 제외).
- `refresh_all.sh` 는 기존 CSV 를 `_prev/` 로 옮겨 두고 수집하며, 실패 시 되돌린다.
- 파인더: `collect_kapt_detail.py`(K-apt 프로파일, kapt_*.json) → `build_app_data.py` → `app_template.html` 주입.
- 정적 데이터: `apt_households.json`(K-apt 세대수 합), `seoul_geo.json`(구 경계), 종사자수는 build 스크립트 내 5개 구만(나머지 KOSIS 수동 필요). `population_202607.json` 은 파일명 고정이며 내용에 `asof`(기준월)를 담는다.

## 원칙과 함정 (실측)

- **PublicDataReader 금지** — 이 환경에서 segfault. RTMS/K-apt 모두 requests 직접 호출.
- **RTMS 초당 제한(429)**: 병렬 금지. sleep 0.3~0.35s + 에러XML(returnReasonCode) 백오프. 수집은
  10분 백그라운드 컷 안에 끝나게 배치 분할.
- **통계 원칙**(realprice-flow gotchas 준수): 해제거래 제외, 상하위 1% 컷, 단일월 비교 금지.
  단순 중앙값은 구성편향(서초 −5.4% 착시)이 있으니 **헤드라인은 매칭 지수**로.
- **RTMS·K-apt 단지명 표기 상이**: 정규화+법정동+건축년도 대조. 신축은 거래 0건이 정상.
- 아티팩트 갱신 시 **반드시 url 파라미터** — 없으면 새 아티팩트가 생긴다. 다른 세션이 갱신했다면
  409 절차(라이브 읽기→병합→재발행)를 따르라.
- 디자인: algo-design 톤, 차트는 dataviz 원칙(단일축·검증 팔레트 #cf6a48/#3f7fb8/#4f7d3a/#8a6bb8/#b0893a).

## 분기 루틴 운영

- 클라우드 환경 "기본값"(env_01JZSJ5gSkt2E1o35pNSY1W6)에 **PUBLIC_DATA_SERVICE_KEY 환경변수** +
  **Network access = All** 이 설정돼 있어야 한다(2026-08-23 검증 완료). 실패 시 흔한 원인이 이 둘.
- 디버그: `RemoteTrigger list_runs → get_run_log`. 수집만 55분쯤 걸리니 완료 판정은 서두르지 말 것.
- 루틴이 커밋한 뒤에는 로컬에서 `git pull` 로 동기화.

## 다른 지역으로 확장할 때

`collect_seoul.py`·`collect_rent.py`의 GUS 딕셔너리(시군구명→법정동코드 5자리)만 교체하면
같은 파이프라인이 그대로 돈다. 경기도 코드는 auction-priority-pipeline 스킬의 enrich_complex.py 참조
(화성 분구 41591/93/95/97 주의). 지도는 southkorea/*-maps GeoJSON을 받아 charts_extra.choropleth 재사용.
