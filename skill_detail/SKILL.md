---
name: court-auction-detail
description: 대한민국 법원경매(courtauction.go.kr)에서 특정 사건 1건의 상세 문서를 분석하는 스킬. 사용자가 "이 경매물건 상세분석 해줘", "매각물건명세서/현황조사서/감정평가서/사건상세/인근매각물건사례 파악해줘", "2025타경2412 분석", "물건 상세검색해서 권리분석/임차인 분석해줘", "경매 물건 수익률/예상낙찰가/인수금 계산해줘" 등을 요청하면 이 스킬을 먼저 읽어라. 목록 수집(CSV)은 court-auction-scraper 스킬이고, 이 스킬은 단일 사건의 5개 문서(매각물건명세서·사건상세조회·현황조사서·감정평가서요약·인근매각물건사례) 심층 분석 + 권리분석·수익률 추정(투자분석 A안) 전용이다. 사이트가 WebSquare+IP차단+헤드리스감지+파이프라인지연을 사용하므로 검증된 패턴만 작동한다.
---

# 법원경매 단일 사건 상세분석기 (courtauction.go.kr)

목록 스크래핑은 **court-auction-scraper** 스킬이 담당한다. 이 스킬은 **사건번호 하나를 상세페이지까지 열어 5개 문서를 분석**한다.

## 무엇을 뽑아내는가 (사용자 요청 5개 문서)

| # | 문서 | 데이터 출처 | 주요 항목 |
|---|------|------------|----------|
| 1 | **매각물건명세서** | 요약: `selectAuctnCsSrchRslt.on`→`dspslGdsDxdyInfo` / **임차인 표: 명세서 PDF 텍스트레이어(StreamDocs)** | 최선순위설정, 배당요구종기, 작성일, 비고 + **점유자성명·임대차기간·보증금·차임·전입·확정일자·배당요구여부/일자**, 인수주의·특별매각조건 |
| 2 | **사건상세조회** | `selectAuctnCsSrchRslt.on` → `csBaseInfo`,`dstrtDemnInfo` | 법원/담당계/전화, 사건명, 접수·개시일, 배당요구종기, 청구금액, 중복사건 |
| 3 | **현황조사서** | `selectCurstExmndc.on` | 점유관계(`gdsPossCtt`), 임차인목록(`dlt_ordTsLserLtn`), 조사일시, 중복사건 |
| 4 | **감정평가서요약** | `selectAuctnCsSrchRslt.on` → `aeeWevlMnpntLst` | 위치·교통·구조(사용승인일)·이용·설비·토지·도로·공법상제한·임대차 |
| 5 | **인근매각물건사례** | `selectAroundDspslGds.on`(매각) / `selectAroundProgGds.on`(진행) | 동일 시군구·용도 매각완료 사례, 낙찰가·매각가율, 동일단지 사례 |
| 6 | **투자분석(A안)** | 위 1·5 데이터 조합 (외부 데이터 없이) | 예상낙찰가·인수보증금·취득원가·손익분기 매도가, 시세 입력 시 순수익·수익률 |

## 투자분석 (A안 · `compute_investment`)

법원 데이터만으로 "떠안는 돈 + 얼마 남나"를 추정한다. **전부 추정이며 실제 입찰 전 등기부·현장 검증 필수.**

- **예상낙찰가** = 감정가 × 매각가율. 매각가율 우선순위: `--sale-rate` > **동일단지 ≥2건 평균**(단일 comp 아웃라이어 방지) > 동일읍면동 평균 > 현재 최저가율. 계산값이 현재 최저가 미만이면 최저가로 하한.
- **인수보증금(보수적)**: 특별매각조건에 '반환청구권 포기'면 0, 아니면 대항력 임차인(전입<최선순위) 보증금 합계. 배당요구+확정일자 있으면 "배당으로 회수 가능" 주석.
- **취득비용(가정)**: 취득세(1주택·비규제 브래킷 1.1/2.2/3.3%, `--acq-tax`로 중과 조정), 법무등기 0.5%, 명도비 정액(`--evict-cost`).
- **손익분기 매도가** = 총취득원가. `--market <원>` 입력 시 순수익·수익률(중개보수 0.5% 반영) 계산.

- **시세 자동조회** (`--auto-market`): 국토부 아파트 매매 실거래(PublicDataReader)로 **동일 단지·평형(±3㎡)** 최근 12개월 거래 중앙값을 자동으로 `--market`에 넣는다. `fetch_market_price(시군구코드, 단지명, 전용면적)` — 시군구코드는 경매 데이터의 `rprsAdongSdCd+rprsAdongSggCd`, 단지명·면적은 `gdsDspslObjctLst`에서 자동 도출. **realprice-flow/apt-value와 동일하게 `.env`의 `PUBLIC_DATA_SERVICE_KEY` 필요**(data.go.kr '아파트 매매 실거래가' 활용신청). 키 없음/단지명 없음(다세대)/거래 없음이면 안내 후 시세 없이 진행.

```bash
python3 scripts/analyze_case.py --court 남양주지원 --case 2025타경2412 --auto-market   # 시세 자동
python3 scripts/analyze_case.py --court 남양주지원 --case 2025타경2412 --market 340000000  # 시세 수동
python3 scripts/analyze_case.py --court 서울남부지방법원 --case 2025타경9307 --sale-rate 78 --acq-tax 12
```
> ⚠️ 미포함(솔직히 고지): 등기부상 전체 근저당·가압류(→ 정밀 인수금), 양도세·보유비용. 완전 권리분석은 등기사항증명서(인터넷등기소·유료)가 필요 → B안(등기부 업로드 파싱)에서 다룬다.
> ⚠️ `--auto-market` 은 **동일 단지 실거래**가 있어야 정확하다. 소규모/신축/다세대는 표본이 없을 수 있고, 그땐 `--market` 수동 입력이나 `realprice-flow` 지역 리포트를 참고하라.

## ⚠️ 열람 가능 시점 + 매각물건명세서 임차인 추출 (핵심)

사이트 유의사항 원문: **매각물건명세서는 매각기일(입찰기간) 1주 전부터, 현황조사서·감정평가서는 2주 전부터** 매각기일까지 조회 가능.

### ✅ 매각물건명세서 PDF 텍스트 레이어 추출 (검증 완료 2026-07)
매각기일 1주 전이 지나면 상세페이지에 **매각물건명세서 버튼(`btn_dspslGdsSpcfc1/2`)** 이 나타난다. 이 버튼은:
1. `insertDspslGdsSpecArtcWdrwInf.on`(열람 로그) 를 치고,
2. `window.open` 으로 **대법원 전자문서(ecfs.scourt.go.kr `getPdf.on`)** → **StreamDocs 뷰어(pvo.scourt.go.kr)** 를 연다.
3. 뷰어는 스캔 이미지가 아니라 **텍스트 레이어**를 갖는다: `GET https://pvo.scourt.go.kr/streamdocs/v4/documents/{docId}/texts/{page}` → 각 페이지 텍스트(JSON runs).

→ 스크립트는 명세서 버튼을 눌러 docId를 잡고 `/texts/{0..N}` 을 긁어 **점유자성명·임대차기간·보증금·차임·전입신고일·확정일자·배당요구여부/일자 + 인수주의·특별매각조건**을 전부 확보한다. (예: 서울남부 2025타경9307 → 임차인 변상규 보증금 3.15억, 전입 2022.3.25, 확정 2022.2.28, 최선순위 2023.11.7 압류보다 대항요건 앞서 **매수인 인수 위험**까지 추출됨.)

### 임차인 표 구조화 (좌표 기반) + 대항력 자동판정
`/texts` 응답을 그냥 이어붙이면 표 셀이 뒤섞이므로, 각 run의 **rect 좌표로 행을 복원**한다(`_reconstruct_lines`). 그다음 성명 헤더~`<비고>` 밴드에서 날짜+금액이 있는 행을 임차인으로 파싱해 **성명·보증금·전입신고일·확정일자·배당요구일**을 필드로 뽑고(`parse_tenant_table`), **전입신고일 < 최선순위설정일**이면 `인수위험=True`로 자동 판정한다. ⚠️ 성명이 줄바꿈된 기관명(예: 주택도시보증공사→"시보증")은 조각으로 잡힐 수 있어 **`원문행`을 항상 병기**한다(정본 대조용). "조사된 임차내역없음"이면 임차인 0명으로 처리.

### 안정성 — 재시도 래퍼
사이트 flakiness 대응으로 `run_with_retry()`가 collect(4개 문서)는 3회, 명세서 세션은 2회 재시도한다. 명세서만 최종 실패하면 나머지 4개 문서는 그대로 살리고 진행(격리).

### 🔴 반드시 별도 브라우저 세션에서 (검증된 함정)
명세서 버튼 클릭의 `window.open`은 **collect()의 상세 세션 안에서 누르면 로그 XHR만 발생하고 뷰어(getPdf/streamdocs)가 안 뜨는** 재현 불가 상태가 있었다(원인 미상 — moveDtlPage/응답 대기/응답 바디 읽기 모두 배제됨). **검색→상세→명세서 클릭만 하는 깨끗한 독립 세션**에서는 항상 뜬다. 그래서 `fetch_myseseo()`는 자체 브라우저를 새로 띄운다(사건당 세션 2개: 4개 문서용 + 명세서용). 느리지만 안정적이고, 명세서 실패해도 나머지 4개 문서는 영향 없다.

### window.open은 '신뢰된 제스처'에서만
명세서 뷰어는 반드시 Playwright **네이티브 `locator.click()`** 으로 눌러야 뜬다. `$p.getComponentById().click()`(programmatic) 이나 `expect_page` 래핑은 사용자 제스처로 인정 안 돼 로그만 발생한다.

### 미공개 시점 / 현황조사 보조
- 매각기일 1주 전 이전이면 명세서 버튼이 없다 → `fetch_myseseo`가 `None` 반환 → "미공개" 표기. 이때 임차인은 **현황조사서(`dlt_ordTsLserLtn`)** 만으로 보조 판단(폐문부재·전입세대 없음이면 임차인 미확인).
- 명세서·현황조사 두 소스를 교차확인하고, 최종 입찰 전 등기사항증명서·전입세대열람 재확인을 안내.

## 사용법

```bash
python3 scripts/analyze_case.py --court 남양주지원 --case 2025타경2412
python3 scripts/analyze_case.py --court 서울중앙지방법원 --year 2025 --caseno 102237 -o out.json
python3 scripts/analyze_case.py --court 수원지방법원 --case '2024타경12345' --no-headless   # 디버그
```

- `--court` : 법원 **드롭다운 표기 그대로** (지원명도 단독 표기: `남양주지원`, `성남지원`, `고양지원` 등)
- `--case '2025타경2412'` 또는 `--year 2025 --caseno 2412`
- 출력: 콘솔 요약 + `case_<사건번호>.json`(원본 dma_result·현황조사·인근매각 + 정리된 report)

법원명을 모르면 court-auction-scraper의 법원 목록 또는 `sbx_rletCortOfc` 옵션을 참고. 사용자가 사건번호만 주고 법원을 안 주면 **법원을 반드시 물어라**(전국 사건번호는 중복 가능).

## 사이트 동작의 3대 함정 (이 스킬이 존재하는 이유)

이 사이트는 court-auction-scraper의 스텔스 패턴(headless 감지 회피, `wait_for_function`, JS 클릭)을 **그대로 전제**한다. 그 위에 상세페이지 특유의 함정이 셋 더 있다.

### ❌ 함정 1: 검색 응답(searchControllerMain)을 기다리면 멈춘다
검색 버튼 클릭 후 `searchControllerMain.on` **응답은 즉시 오지 않는다**(파이프라인 지연 — 다음 상호작용 때 도착). 그래서 "검색 결과 JSON 도착"을 게이트로 걸면 25초를 기다려도 실패한다.
→ **결과 그리드 DOM**(`a[onclick^="moveDtlPage"]` 링크 출현)을 `wait_for_function`으로 대기하라. 그리드는 응답 이벤트와 무관하게 렌더된다.

### ❌ 함정 2: 상세 진입은 `moveDtlPage(0)`이고, 첫 호출은 씹힌다
결과행 상세진입은 로케이터 클릭이 아니라 주소 링크의 `onclick="moveDtlPage(idx)"` 함수다(idx=행번호, 0부터).
그런데 **첫 `moveDtlPage(0)` 호출은 파이프라인 지연으로 실제 이동을 안 하는 경우가 잦다**(반환 undefined, 네트워크 0). **두 번째 호출에서 상세가 로드**된다.
→ `selectAuctnCsSrchRslt.on` 캡처될 때까지 `moveDtlPage(0)`를 짧은 간격으로 반복 호출하라(스크립트는 최대 6회 반복).

### ❌ 함정 3: 문서 버튼은 WebSquare 팝업/PDF다 — 대신 in-page fetch
현황조사서·감정평가서 버튼(`btn_curstExmndcTop`, `btn_aeeWevl1`)은 클릭 시 PDF 전자문서 팝업을 연다(구조화 데이터 아님).
현황조사·인근매각의 **구조화 JSON은 별도 엔드포인트**를 상세페이지 컨텍스트에서 `fetch(credentials:'include')`로 직접 호출해 받는다(세션 쿠키 재사용). 스크립트의 `FETCH_JS` 참조.
- 현황조사서: `POST /pgj/pgj15B/selectCurstExmndc.on`  body `{"dma_srchCurstExmn":{"cortOfcCd":<Bxxxxxx>,"csNo":"2025타경2412","auctnInfOriginDvsCd":"2","ordTsCnt":""}}`
- 인근매각/진행: `POST /pgj/pgjsearch/selectAroundDspslGds.on` · `selectAroundProgGds.on`  body `{"csNo":"2025타경2412","cortOfcCd":<Bxxxxxx>,"dspslGdsSeq":"1","rletCarDvsCd":"0","rprsAdongSdCd":<시도코드>,"rprsAdongSggCd":<시군구코드>,"auctnGdsUsgCd":"01"}`

> `cortOfcCd`(법원코드, 예 남양주지원=`B214804`), `csNo`(=`userCsNo` "2025타경2412"), `rprsAdongSdCd/SggCd`, `auctnGdsUsgCd`는 모두 상세진입 시 캡처한 `dma_result`에서 꺼낸다. 하드코딩 금지.

## selectAuctnCsSrchRslt.on → dma_result 구조 (핵심 키)

| 키 | 내용 |
|----|------|
| `csBaseInfo` | 사건 기본(법원코드·사건번호·접수/개시일·청구금액·담당계·전화). `userCsNo`=사람이 읽는 사건번호 |
| `dstrtDemnInfo[0]` | `dstrtDemnLstprdYmd`=배당요구종기 |
| `dspslGdsDxdyInfo` | 명세서요약: `tprtyRnkHypthcStngDts`(최선순위설정), `gdsSpcfcWrtYmd`(작성일), `gdsSpcfcRmk`(비고), `aeeEvlAmt`(감정), `fstPbancLwsDspslPrc`(현재최저), `flbdNcnt`(유찰), `dspslDxdyYmd`+`fstDspslHm`(매각기일), `dspslDcsnDxdyYmd`(매각결정), `auctnGdsUsgCd`(용도코드) |
| `gdsDspslDxdyLst` | 기일 이력(일자/종류/최저가/결과 `auctnDxdyRsltCd` 002=유찰) |
| `gdsDspslObjctLst[0]` | 물건: `userPrintSt`(전체주소), `bldNm`(단지), `bldDtlDts`(동호), `objctArDts`(면적), `rprsAdongSdCd/SggCd/EmdNm`(지역코드) |
| `aeeWevlMnpntLst` | 감정평가 요항(항목코드 `aeeWevlMnpntItmCd` → 위치/교통/구조/이용/설비/토지/도로/공법제한/차이/임대차) |
| `csPicLst`,`picDvsIndvdCnt` | 사진 목록/구분개수 |

현황조사(selectCurstExmndc) 응답: `dma_curstExmnMngInf`(조사일시 `exmnDtDts`), `dlt_ordTsRlet[].gdsPossCtt`(점유관계), `dlt_ordTsLserLtn`(임차인 목록), `dlt_curstExmnDpcnMrg`(중복사건).

인근매각(selectAround*) 응답: `data.result[]` 리스트. 매각완료건은 `maeAmt`(낙찰가) 존재. 매각가율=`maeAmt/gamevalAmt`. 동일 `hjguDong`(읍면동)·동일 `buldNm`(단지) 필터로 최적 비교군 추출.

## 결과 해석 가이드 (권리분석 관점)

- **최선순위설정 = 말소기준권리**. 이후 설정 권리는 원칙적으로 소멸, 이전은 인수. 다만 **대항력 임차인·예고등기·법정지상권 등은 명세서 정식 공개 후 확인**.
- **청구금액이 감정가 대비 소액**이면 신청채권자 청구액일 뿐 → 등기부상 총 채무는 별도 등기사항증명서 확인 필요.
- **점유관계 "점유자를 만나지 못함"**(폐문부재) → 명도 난이도·전입세대열람·관리비 체납 현장확인 권고.
- **인근 동일단지·동일평형 낙찰 사례**가 가장 신뢰도 높은 시세 근거. 평균 매각가율로 예상 낙찰가 밴드 제시.
- 항상 마무리에: **① 매각물건명세서(1주 전) ② 등기사항전부증명서 ③ 전입세대열람 ④ 관리비 체납** 재확인을 안내.

## 트러블슈팅

- **"검색 결과 없음"**: 법원명이 드롭다운 표기와 다르거나(지원명 단독), 연도/사건번호 오타. `--no-headless`로 확인.
- **"상세 데이터 캡처 실패"**: `moveDtlPage(0)` 반복 트리거가 적용됐는지 확인(함정 2). 스텔스 옵션 누락 시 그리드 자체가 안 뜬다.
- **임차인이 비어 있음**: 정상일 수 있음(신고 임차인 없음) 또는 명세서 미공개 시점(1주 전 이전). 매각기일과 오늘 날짜를 비교해 어느 쪽인지 판단하라.
- **인근매각 result가 커서 느림**: 시군구 전체 아파트 풀(수백 건)이 온다. 동일 읍면동·매각완료(maeAmt)만 필터해 요약하라.
