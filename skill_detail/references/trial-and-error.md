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

## 검증 사건
- **남양주지원 2025타경2412** (신창현풍림아이원1차, 84.99㎡): 명세서 "조사된 임차내역없음" → 임차인 N (정확).
- **서울남부 2025타경9307** (루체비스타 오피스텔): 명세서 임차인 변상규 보증금 3.15억/전입 2022.3.25/확정 2022.2.28 + HUG 배당요구 2025.3.25, **최선순위(2023.11.7 압류)보다 대항요건 앞서 인수 위험** 전부 추출 (임차인 있는 케이스 검증 완료).
- 3개 법원(서울중앙·남부·북부·남양주) / 아파트·오피스텔 혼합에서 4개 문서 재현 확인.
