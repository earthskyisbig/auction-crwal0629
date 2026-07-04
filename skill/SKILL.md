---
name: court-auction-scraper
description: 대한민국 법원경매 정보(courtauction.go.kr)에서 경매 물건 목록을 자동 수집하여 CSV로 저장하는 스킬. 사용자가 "법원경매 긁어줘", "courtauction 데이터 수집", "경매 물건 CSV로 뽑아줘", "법원경매정보제공 스크래핑", "강남구 아파트 경매 물건 긁어줘"(지역·용도·유찰횟수 필터 검색 포함) 등을 요청하면 반드시 이 스킬을 먼저 읽어라. 지역(시도/시군구)·용도(아파트/다세대 등)·유찰횟수로 좁혀 검색하려면 scripts/scrape_auction_filtered.py(템플릿 기반)를 쓴다. 사이트가 WebSquare 프레임워크 + IP 차단 + 헤드리스 감지를 사용하므로 일반적인 requests/curl 접근은 전부 실패한다. Playwright 스텔스 모드만 작동한다.
---

# 법원경매 스크래퍼 (courtauction.go.kr)

## ⚠️ 이 스킬이 존재하는 이유

이 사이트를 처음 접할 때 누구나 하는 실수들을 미리 막기 위한 스킬이다.
아래의 "절대 하지 말 것"을 먼저 읽어라.

---

## 절대 하지 말 것 (검증된 실패 패턴)

### ❌ 1. requests / curl 직접 호출
```python
# 이렇게 하면 IP 차단됨 - 절대 시도하지 말 것
import requests
r = requests.post("https://www.courtauction.go.kr/pgj/pgjsearch/searchControllerMain.on", ...)
# → {"message": "해당 IP는 비정상적인 접속으로 보안정책에 의하여 차단되었습니다."}
```
사이트는 외부 IP에서의 직접 POST를 차단한다. 세션 쿠키를 먼저 받아와도 동일하게 차단된다.

### ❌ 2. Playwright 기본 headless 모드 (스텔스 없이)
```python
browser = p.chromium.launch(headless=True)  # 감지됨 → 페이지 렌더링 안 됨
context = browser.new_context(...)  # 버튼이 DOM에 나타나지 않음
```
WebSquare 프레임워크가 headless 감지 후 렌더링을 중단한다.

### ❌ 3. wait_until="networkidle" 또는 고정 sleep으로 초기화 대기
```python
page.goto(url, wait_until="networkidle")  # 일관성 없음
time.sleep(8)                              # 어떤 실행에선 되고 어떤 실행엔 안 됨
```
WebSquare 초기화 시점이 매번 달라서 고정 대기는 불안정하다.

### ❌ 4. Playwright 로케이터로 버튼 클릭
```python
page.click("#mf_wfm_mainFrame_btn_gdsDtlSrch")  # TimeoutError
page.wait_for_selector(...)                       # 60초 후 실패
```
WebSquare가 생성하는 버튼은 Playwright 로케이터로 감지되지 않는다. JS 직접 클릭만 작동한다.

### ❌ 5. 페이지네이션 응답이 즉시 온다고 가정
응답이 1~2 클릭 뒤에 도착하는 파이프라인 패턴이다.
마지막 페이지 클릭 후 루프를 바로 종료하면 마지막 데이터를 놓친다.

---

## 올바른 접근법

### 핵심 원칙 3가지
1. **Playwright + 스텔스 옵션** 필수
2. **`wait_for_function`** 으로 버튼 DOM 출현 대기
3. **`page.evaluate()` JS 클릭** + 파이프라인 플러시 패턴

---

## 사이트 구조 파악

| 항목 | 내용 |
|------|------|
| 프레임워크 | WebSquare (한국 전자정부 JS 프레임워크) |
| 검색 API | `POST /pgj/pgjsearch/searchControllerMain.on` |
| 응답 형식 | `{"data": {"dlt_srchResult": [...]}}` |
| 검색 버튼 ID | `mf_wfm_mainFrame_btn_gdsDtlSrch` |
| 기본 법원 코드 | 서울중앙지방법원 = `B000210` |
| 페이지당 결과 | 10개 (고정) |

### API 응답 필드 → CSV 컬럼 매핑 (2026-07-02 정정: 실제 사이트 대조 검증)

| CSV 컬럼 | API 필드 | 비고 |
|----------|---------|------|
| 사건번호 | `printCsNo` | 중복사건 표기 포함(`<br/>`→공백). fallback `jiwonNm`+`srnSaNo` |
| 물건소재지 | `printSt` | 도로명+단지명+동/호 (㎡ 없음). fallback 조합 |
| 전용면적 | `convAddr`/`areaList`/`pjbBuldList` 의 `㎡` 파싱 | 최댓값 사용 |
| 감정가 | `gamevalAmt` | 원 단위 정수 |
| **최저가** | **`notifyMinmaePrice1`** | ⚠️ **`minmaePrice` 아님!** 아래 경고 참조 |
| 저감율 | `notifyMinmaePriceRate1` | 서울 20%저감→80%, 경기 30%저감→70% |
| 유찰횟수 | ⚠️ `yuchalCnt` 부정확 → 저감율로 역산 | 아래 경고 참조 |
| 매각기일 | `maeGiil` | YYYYMMDD |

> ⚠️ **최저가 함정**: `minmaePrice`는 상당수 물건에서 **최초 최저가(=감정가, 100%)** 를 담고
> 있어 유찰 할인이 반영 안 된다. 현재 최저매각가격은 반드시 **`notifyMinmaePrice1`** 을 쓸 것.
>
> ⚠️ **유찰횟수 함정**: `yuchalCnt` 필드는 신경매/재감정/중복사건에서 이력이 남아 부정확하다.
> 사이트에 직접 확인한 결과(2026-07-02) 사이트의 "유찰횟수"는 **현재 최저가 저감율 기준**이다.
> 예) `yuchalCnt=7`인데 최저가가 감정가의 64%면 사이트는 "유찰 2회"로 취급.
> **실제 유찰횟수 = round 형태로 `notifyMinmaePrice1/gamevalAmt` 비율에서 역산**
> (100%=0회, 70·80%=1회, 49·64%=2회, 34·51%=3회…). 20%/30% 저감을 모두 커버하는 경계로 판정.

---

## 작동하는 코드 패턴

두 스크립트가 있다. **지역·용도를 좁혀 검색하려면 `scrape_auction_filtered.py`(권장)** 를, 조건 없이 전량 훑으려면 `scrape_auction.py`를 쓴다.

### ✅ 필터 검색 (권장) — `scripts/scrape_auction_filtered.py`

법원/시도/시군구/용도(대·중·소분류)/유찰횟수를 **검색 폼에 설정해 서버사이드 필터링**한 뒤, 결과를 `hjguSigu`로 사후 필터링한다. 기본 검색이 지역필터 없이 ~100건만 주는 한계를 해결한다.

```bash
# 템플릿으로 (권장 — 재사용)
python3 scripts/scrape_auction_filtered.py -t scripts/templates/gangnam_apt.json -o out.csv

# CLI 인자로
python3 scripts/scrape_auction_filtered.py \
  --court 서울중앙지방법원 --sido 서울특별시 --sgg 강남구 \
  --lcl 건물 --mcl 주거용건물 --scl 아파트 --flbd-min 전체 -o out.csv
```

- **템플릿**(`scripts/templates/*.json`): `court, sido, sgg, lcl, mcl, scl, flbd_min` 필드. 새 지역은 템플릿만 추가하면 된다.
- **출력 컬럼**: `사건번호, 물건소재지(단지명·동·호 포함), 전용면적, 감정가, 최저가, 저감율, 유찰횟수, 매각기일`.
- `--flbd-min 전체`: 신건(유찰0) 포함 / `1회`·`2회`: 유찰 물건만. `--scl 전체`: 용도 소분류 생략. `--max-price`: 최저가 상한(원).
- 핵심: 법원+용도 서버필터는 `select.value=…; dispatchEvent('change')` + `sleep`으로 확실히 걸린다. 시군구는 사후 `hjguSigu` 필터로 보정한다.

### 조건 없이 전량 — `scripts/scrape_auction.py`

```bash
python3 scrape_auction.py   # → /Users/leomyung/auction_list.csv (지역/용도 필터 없음)
```

---

## 핵심 코드 패턴 (직접 작성 시)

### 1. 스텔스 브라우저 설정 (필수)
```python
browser = p.chromium.launch(
    headless=True,
    args=[
        '--no-sandbox',
        '--disable-blink-features=AutomationControlled',  # ← 핵심
        '--disable-features=site-per-process',
        '--lang=ko-KR',
    ]
)
context = browser.new_context(
    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    locale="ko-KR",
    viewport={"width": 1280, "height": 900},
)
context.add_init_script("""
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
    window.chrome = {runtime: {}};
""")
```

### 2. WebSquare 초기화 대기 (고정 sleep 대신)
```python
page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)

# 검색 버튼이 DOM에 나타날 때까지 대기 (최대 60초)
page.wait_for_function(
    "() => !!document.getElementById('mf_wfm_mainFrame_btn_gdsDtlSrch')",
    timeout=60000
)
```

### 3. 버튼 클릭 (page.click() 대신 JS 사용)
```python
page.evaluate("""
() => {
    const b = document.getElementById('mf_wfm_mainFrame_btn_gdsDtlSrch');
    if(b) b.click();
}
""")
```

### 4. 파이프라인 패턴 - 응답이 1~2 클릭 뒤에 도착
```python
# 페이지네이션 루프
for pg in range(2, max_page + 1):
    response_flag[0] = False
    time.sleep(0.5)
    page.evaluate(f"() => {{ document.getElementById('mf_wfm_mainFrame_pgl_gdsDtlSrchPage_page_{pg}')?.click(); }}")
    
    for _ in range(15):  # 최대 15초 대기
        time.sleep(1)
        if response_flag[0]:
            break

# ← 루프 종료 후 반드시 마지막 페이지 재클릭 (파이프라인 플러시)
page.evaluate(f"() => {{ document.getElementById('mf_wfm_mainFrame_pgl_gdsDtlSrchPage_page_{max_page}')?.click(); }}")

# 잔여 응답 수집 (8초 무응답 시 종료)
no_change = 0
for _ in range(30):
    time.sleep(1)
    if response_flag[0]:
        response_flag[0] = False
        no_change = 0
    else:
        no_change += 1
        if no_change >= 8:
            break
```

---

## 검색 조건 변경 방법

`dma_srchGdsDtlSrchInfo` 의 주요 필드:

| 필드 | 설명 | 예시 |
|------|------|------|
| `cortOfcCd` | 법원 코드 | `B000210` (서울중앙), `""` (전체) |
| `mvprpRletDvsCd` | 부동산/동산 구분 | `00031R` (부동산), `00031M` (동산) |
| `bidBgngYmd` | 입찰 시작일 | `20260629` |
| `bidEndYmd` | 입찰 종료일 | `20260713` |
| `aeeEvlAmtMin` | 감정가 최솟값 | `100000000` (1억) |
| `flbdNcntMin` | 유찰횟수 최솟값 | `1` |

**주의**: `cortOfcCd`를 비워서 전체 법원 검색 시, 반드시 `aeeEvlAmtMin/Max` 또는 `lclDspslGdsLstUsgCd` 중 하나를 설정해야 함 (사이트 규칙).

---

## 용도 드롭다운 체계 (확인 완료)

아파트 검색 시 3단계 select를 순서대로 설정해야 한다. 각 단계 사이 3초 대기 필수.

| 순서 | select ID | 선택값 | 비고 |
|------|-----------|--------|------|
| 1 | `mf_wfm_mainFrame_sbx_rletLclLst` | `건물` | 대분류 (집합건물 없음) |
| 2 | `mf_wfm_mainFrame_sbx_rletMclLst` | `주거용건물` | 중분류 (3초 대기 후) |
| 3 | `mf_wfm_mainFrame_sbx_rletSclLst` | `아파트` | 소분류 (3초 대기 후) |

유찰횟수 select: `mf_wfm_mainFrame_sbx_rletFlbdCntMin` — 옵션값: `1회`, `2회`, ..., `7회`

---

## 트러블슈팅

### 버튼을 못 찾을 때 (`wait_for_function` 타임아웃)
→ 스텔스 옵션이 적용됐는지 확인. `--disable-blink-features=AutomationControlled` 없으면 WebSquare가 렌더링을 거부한다.

### API 응답이 안 올 때
→ `on_response` 콜백이 등록됐는지, `response.url`에 `searchControllerMain`이 있는지 확인.
→ 첫 페이지 응답은 실제로 두 번째 페이지를 클릭할 때 도착하는 경우가 많음 (파이프라인 딜레이).

### 마지막 페이지 데이터 누락
→ 루프 후 마지막 페이지 재클릭(플러시) 패턴을 적용했는지 확인.
→ `browser.close()` 전에 8초 무응답 대기를 거쳤는지 확인.

### 100개 이상 수집 필요 시
→ 현재 구현은 10페이지(100개)가 한 "페이지 그룹". 다음 그룹의 "다음" 버튼(`pgl_gdsDtlSrchPage_next` 계열) 클릭 후 반복해야 함.

---

## 시행착오 기록 (이 스킬을 만들게 된 원인)

`references/trial-and-error.md` 참조 — 세션 중 발생한 15개 실패 패턴과 원인 분석.
