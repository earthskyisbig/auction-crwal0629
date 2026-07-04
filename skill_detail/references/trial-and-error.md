# 상세분석기 개발 시행착오 기록

이 스킬(court-auction-detail)을 만들며 실제로 부딪힌 실패 → 원인 → 해결. 재구현 시 같은 벽을 다시 넘지 않기 위한 기록.

## 1. Claude-in-Chrome 확장 미연결
- 브라우저 자동화(Claude in Chrome)로 시도 → `tabs_context_mcp`가 3회 연속 "extension not connected".
- 해결: 확장 재연결이 번거로우면 **court-auction-scraper와 동일한 Playwright 스텔스**로 전환. 상세페이지도 동일 방식으로 전부 접근 가능하다.

## 2. 결과 그리드 셀 클릭으로 상세 진입 시도 → 실패
- `grd_gdsDtlSrchResult_cell_0_x`를 mouse click / dispatchEvent / 네이티브 `.click()` 모두 시도 → 상세 안 열림.
- 셀 0_0은 체크박스 컬럼, 실제 진입 링크는 **주소 셀의 `<a onclick="moveDtlPage(0)">`**.
- 그리드 `oncellclick` 핸들러는 `getEventHandler`로 안 잡히고 `userEventList`에 `scwin.grd_..._oncellclick`로 등록됨(참고).
- 해결: `moveDtlPage(idx)` 전역 함수를 직접 호출.

## 3. `moveDtlPage(0)` 첫 호출이 씹힘 (가장 오래 걸린 함정)
- 그리드 렌더 확인 후 `moveDtlPage(0)` 1회 호출 → 반환 `undefined`, 네트워크 요청 0건, 상세 안 열림.
- **두 번째 호출**에서 즉시 `selectAuctnCsSrchRslt.on` 도착.
- 원인: courtauction 특유의 파이프라인 지연(응답이 다음 상호작용 때 도착하는 구조). 첫 호출이 트리거를 "예약"하고 두 번째가 flush.
- 해결: `selectAuctnCsSrchRslt` 캡처될 때까지 `moveDtlPage(0)`를 반복(최대 6회) 호출.

## 4. 검색 응답(searchControllerMain) 게이트로 사용 → 25초 타임아웃
- 검색 버튼 클릭 후 `searchControllerMain.on` 응답을 기다림 → 8초/18초/25초 모두 미도착.
- 그런데 원본 스크립트(고정 sleep 후 moveDtlPage)는 됨 → 응답은 **moveDtlPage 등 다음 상호작용 때** 도착했던 것.
- 해결: 네트워크 응답 대신 **DOM 그리드(`a[onclick^="moveDtlPage"]`) 출현**을 대기.

## 5. 문서 버튼 클릭으로 구조화 데이터 얻으려 함 → PDF 팝업만 열림
- `btn_curstExmndcTop`(현황조사서), `btn_aeeWevl1`(감정평가서) 클릭 → PDF 전자문서 뷰어 팝업(PGJ15BP01.xml). 구조화 JSON 아님.
- 감정평가 요항은 이미 `dma_result.aeeWevlMnpntLst`에 구조화되어 있음(굳이 PDF 불필요).
- 현황조사서 구조화 데이터는 버튼이 내부적으로 치는 `selectCurstExmndc.on`을 **in-page fetch로 직접 호출**해 획득(요청 본문은 네트워크 로그에서 캡처).

## 6. 인근매각물건사례가 "검색결과 없습니다"로 보였으나 실제 데이터는 있었음
- 상세페이지 `tac_aroundGdsExm` 탭(인근매각통계/인근매각물건/인근진행물건) 렌더 텍스트는 "검색결과가 없습니다".
- 그러나 `selectAroundDspslGds.on`/`selectAroundProgGds.on` **원본 응답에는 시군구 전체 아파트 수백 건**이 들어 있었다(화면은 엄격한 유사조건·기간 필터로 비어 보임).
- 해결: 원본 result에서 **매각완료(maeAmt 존재) + 동일 읍면동/동일 단지**로 직접 필터해 비교군을 구성.

## 7. `nearMgakMulSrch()` 직접 호출 → `mapObj is not defined`
- 지도 기반 인근매각 함수는 지도 객체 초기화가 선행되어야 함. 헤드리스에서 불안정.
- 해결: 지도 함수 대신 위 `selectAround*` 엔드포인트를 in-page fetch(함정 6).

## 8. 매각물건명세서 임차인 표 = PDF지만 텍스트 레이어가 있다 (StreamDocs)
- 처음엔 "명세서 임차인은 PDF 전용이라 구조화 불가"로 결론냈으나, 명세서 버튼 클릭 흐름을 끝까지 추적하니:
  버튼 → `insertDspslGdsSpecArtcWdrwInf.on`(로그) → `window.open` → `ecfs.scourt.go.kr/sgvo/.../getPdf.on` → **StreamDocs 뷰어 `pvo.scourt.go.kr`**.
- StreamDocs 뷰어는 **스캔 이미지가 아니라 텍스트 레이어**를 제공: `GET /streamdocs/v4/documents/{docId}/texts/{page}` → 페이지별 텍스트(JSON runs). `run.text` 이어붙이면 명세서 전문 복원.
- 이걸로 점유자성명·임대차기간·보증금·차임·전입·확정일자·배당요구여부/일자 + 인수주의·특별매각조건 전부 추출 가능. (검증: 9307 임차인 변상규/HUG 완전 추출)

## 9. window.open은 '신뢰된 제스처'에서만 — programmatic 클릭 금지
- `$p.getComponentById(btn).click()`(programmatic)이나 `expect_page` 래핑으로 누르면 **로그 XHR만 발생하고 window.open(뷰어)이 안 뜬다**(사용자 제스처로 인정 안 됨).
- 반드시 Playwright **네이티브 `page.locator(id).click()`** 을 써야 뷰어가 뜬다.

## 10. 명세서 추출은 '별도 브라우저 세션'에서 (가장 이상했던 함정)
- collect()의 상세 세션 **안에서** 명세서 버튼을 네이티브 클릭해도 로그만 발생하고 window.open이 안 떴다.
  moveDtlPage 재settle·응답대기 변경·on_response(r.json) 제거 등 다 시도했으나 통합 세션에선 재현 불가하게 실패.
- 반면 **검색→상세→명세서 클릭만 하는 깨끗한 독립 세션**(standalone)에서는 3/3 + 재현 2/2 항상 성공.
- 결론: `fetch_myseseo()`를 **자체 브라우저를 새로 띄우는 독립 함수**로 구현. 사건당 세션 2개(4개 문서용 collect + 명세서용)로 느리지만 안정적. 명세서 실패해도 나머지 4개 문서엔 영향 없음(격리 이점).

## 11. 임차인 표 구조화 — 텍스트 이어붙이면 셀이 뒤섞인다 (좌표로 복원)
- StreamDocs `/texts` 는 run 단위(각 run에 `rect` 좌표)로 오는데, 표 셀이 시각적 위치 순이 아니라 뒤섞여 온다. `.text` 만 이어붙이면 "변상규 전부 주택임..."처럼 열이 엉킨다.
- 해결: `rect.bottom(y)` 로 행 클러스터(±5px) → 행 내 `rect.left(x)` 로 정렬 (`_reconstruct_lines`). 그다음 성명헤더~`<비고>` 밴드에서 날짜+금액 있는 행을 임차인으로 파싱.
- 날짜 라벨링: 보증금 금액 위치 기준 — 앞 날짜=임대차기간시작, 뒤 날짜들=전입/확정/배당요구 순.
- ⚠️ 줄바꿈된 기관명 성명은 조각으로 잡힘(주택도시보증공사→"시보증"). `원문행` 항상 병기로 보완.

## 12. 투자분석(A안) — 매각가율 단일 comp 아웃라이어 주의
- 예상낙찰가 = 감정가 × 매각가율. 처음엔 동일단지 comp가 1건이면 그 값을 썼는데, 특수물건(51% 등) 하나가 잡히면 왜곡. → **동일단지 ≥2건 평균**일 때만 사용, 아니면 동일읍면동 평균, 그것도 없으면 현재 최저가율. 계산값이 현재 최저가 미만이면 최저가 하한.
- 인수금: 특별매각조건에 '반환청구권 포기'(9307) 있으면 0. 취득세는 1주택·비규제 브래킷(다주택 중과는 --acq-tax).

## 13. 시세 자동연동(realprice-flow / 국토부 실거래) 함정
- **PublicDataReader 는 Decoding 키**를 쓴다(Encoding 키 넣으면 인증 실패). `.env` 의 `PUBLIC_DATA_SERVICE_KEY`.
- **verbose=False 필수** — pandas 3.0 + Python 3.14 조합에서 한글 DataFrame print 시 세그폴트(realprice-flow gotcha와 동일). 우리는 iterrows만 하고 print 안 함 + `warnings.filterwarnings('ignore')` 로 ChainedAssignment FutureWarning 억제.
- **`.env` 위치 함정**: `find_dotenv(usecwd=True)` 는 **cwd 상위로만** 탐색한다. 저장소 밖(예: /tmp/scratchpad)에서 실행하면 저장소의 `.env` 를 못 찾아 "키 미설정"으로 뜬다. → **반드시 프로젝트 폴더(auction-crwal0629)에서 실행**하거나 키를 환경변수로 export. (이미 export 돼 있으면 load 후 `os.getenv` 가 잡음.)
- 단지 매칭: 국토부 컬럼 `단지명`(없으면 `아파트`), `전용면적`(±3㎡), `거래금액`(만원 문자열→×10000 원), `해제여부='O'` 제외. 시군구코드 = 경매 `rprsAdongSdCd`+`rprsAdongSggCd`(예 41+360=41360).
- **새 함수 추가 시 상단 import 확인** — `fetch_market_price` 가 쓰는 `os` 를 안 import 해서 NameError 로 조용히 실패했었다.

## 14. 등기부 파싱(B안) — 말소 등기 오분류
- "3번근저당권설정등기말소" 를 `_purpose` 가 "근저당권설정"으로 잡아, 이미 말소된 권리를 살아있는 근저당으로 오인식.
- 해결: `_purpose` 에서 **'말소'를 최우선 판정**(첫 줄에 '말소' 있으면 다른 권리명 포함돼도 '말소' 반환). 그리고 "N번○○등기말소" 참조로 대상 순위번호를 말소여부=True 처리.
- 검증: `parse_deungibu.py --selftest` (합성 등기부 5체크 통과). 엔진은 `rights_analysis.py` (5시나리오 통과).
- ⚠️ **실제 인터넷등기소 PDF 미검증** — 실서식(다단 컬럼·표 테두리·multi-line 등기목적)에서 pdfplumber 추출이 흔들릴 수 있음. 첫 실 PDF는 `--dump-text` 로 포맷 확인 후 파서 튜닝. 스캔본은 OCR 필요.

## 15. 권리분석 엔진 규칙 요약 (rights_analysis.py)
- **말소기준권리** = 소멸성 권리((근)저당·(가)압류·담보가등기·경매개시) 중 접수일 최선순위. 없으면 경매개시결정.
- 말소기준 이후 접수 권리 → 원칙 소멸. 말소기준보다 앞선 **용익물권(전세권·지상권·임차권)·가처분·보전가등기·환매** → 인수.
- 인수금 = 인수 전세권 전세금 + 인수 임차권 보증금 + 대항력 임차인(전입<말소기준) 보증금. 가처분/보전가등기는 금액 아닌 권리 인수 → 경고만.
- 배당요구·배당순위에 따른 전세권/임차권 소멸은 보수적으로 상한 계산(배당표 별도 확인). 유치권·법정지상권 등 등기부 미기재 권리는 대상 밖.

## 검증 사건
- **남양주지원 2025타경2412** (신창현풍림아이원1차, 84.99㎡): 명세서 "조사된 임차내역없음" → 임차인 N (정확). **시세 자동조회: 국토부 실거래 23건 중앙값 3.07억 → 예상낙찰 2.84억(동일단지 5건 79.6%)·수익률 4.7% 산출 확인.**
- **서울남부 2025타경9307** (루체비스타 오피스텔): 명세서 임차인 변상규 보증금 3.15억/전입 2022.3.25/확정 2022.2.28 + HUG 배당요구 2025.3.25, **최선순위(2023.11.7 압류)보다 대항요건 앞서 인수 위험** 전부 추출 (임차인 있는 케이스 검증 완료).
- 3개 법원(서울중앙·남부·북부·남양주) / 아파트·오피스텔·다세대 혼합에서 4개 문서 재현 확인. 8883(다세대·단지명 None) 크래시 수정.
