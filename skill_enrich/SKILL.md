---
name: court-auction-enrich
description: 법원경매 물건 목록을 지역(시도) 조건으로 수집한 뒤, 국토부 K-apt 공동주택 기본정보로 세대수·준공연도를 붙여 조건 필터하고 DuckDB에 누적 저장하는 스킬. 사용자가 "경기도 아파트 유찰1~2회·최저가·면적·세대수 500이상·2015년 이후 물건 검색해줘", "경매 목록에 세대수/준공연도 붙여줘", "지역 조건으로 여러 물건 걸러줘", "수집한 경매 물건 DB에 쌓아줘", "세대수·연식으로 필터해줘" 등 여러 물건을 지역·단지스펙 조건으로 스크리닝하려 하면 이 스킬을 먼저 읽어라. 단건 상세분석은 court-auction-detail, 원시 목록 수집만은 court-auction-scraper 이고, 이 스킬은 그 사이 "대량 수집→세대수/연식 보강→조건필터→DB적재" 파이프라인 전용이다. courtauction.go.kr 지역검색의 함정과 K-apt 매칭 함정을 검증된 방식으로 우회한다.
---

# 경매 목록 지역수집 · 세대수/연식 보강 · DuckDB 적재

**court-auction-scraper**(원시 목록 수집)와 **court-auction-detail**(단건 심층분석) 사이를 잇는다.
경매 목록에는 **세대수·준공연도·향·정확한 유찰횟수가 없다.** 이 스킬은 그걸 국토부 공공데이터로
보강해서 "세대 500+·2015년 이후" 같은 **단지스펙 조건으로 여러 물건을 스크리닝**하고, 결과를
DuckDB에 누적한다.

## 파이프라인 3단계

```
① collect_region.py   전국 조건검색 + 시도 사후필터 → 목록 CSV
② enrich_apt.py       K-apt로 세대수·준공 보강 → *_final.csv / *_review.csv
③ ingest_to_db.py     (수집기가 자동 호출) → auction.duckdb  (query_db.py로 조회)
```

```bash
# ① 수집 (예: 경기 아파트, 유찰1~2·최저가1~3억·전용59~85 — 전부 서버사이드 필터)
python skill_enrich/scripts/collect_region.py --sido 경기 \
    --min-price 100000000 --max-price 300000000 --area-min 59 --area-max 85 \
    --flbd-min 1 --flbd-max 2 -o out.csv

# ② 세대수·준공 보강 + 조건 필터
python skill_enrich/scripts/enrich_apt.py out.csv --sido 경기 \
    --min-households 500 --min-built-year 2015

# ③ 조회 (수집 시 자동 적재됨)
python query_db.py "SELECT * FROM listings WHERE collected_at > '2026-07'"
```

---

## 절대 하지 말 것 (오늘 검증된 실패 패턴)

### ❌ 1. 법원별로 순회 수집 → 느리고 페이지네이션이 무너진다
경기 전체를 8개 법원으로 순회하면 한 프로세스가 너무 길어 중단되고, 클릭 페이지네이션 지연으로
법원당 절반만 수집된다(의정부 72건 중 32건). **CSV는 마지막에 한 번 쓰므로 중단 시 전량 유실.**
→ **법원을 아예 비우고(cortOfcCd='') 전국을 조건으로 좁힌 뒤 시도 주소로 사후필터**하라.

### ❌ 2. 검색 폼의 지역 드롭다운을 프로그램적으로 set → 서버에 등록 안 됨
```python
sset(page, 'mf_wfm_mainFrame_sbx_rletAdongSdS', '경기도')  # 서버가 무시!
# → 검색하면 결과가 전국(서울 강남 등)으로 나옴. totalCnt 1987(전국)
```
시/도·시/군/구 드롭다운은 **실제 사용자 클릭의 AJAX**로만 서버 세션에 등록된다. 헤드리스 자동
set은 무시된다. 게다가 드롭다운 value 는 코드가 아니라 텍스트('경기도')라 API 본문에 넣어도 안 걸린다.
→ 지역은 **결과의 `printSt` 접두어("경기도…")로 사후필터**하는 게 유일하게 안정적이다.

### ❌ 3. K-apt를 시/군/구 목록(getSigunguAptList3)으로 조회 → 코드가 취약
```python
# 수원시 코드 41110(상위) → 0건. 실제로는 41111/41113/41115/41117 하위 구가 따로.
# 부천시는 2016년 구 폐지 → 41190 이 0건, 소사구는 41194·41197 복수코드.
```
구가 있는 시(수원·성남·안양·안산·고양·용인·부천)에서 시군구코드 해석이 전부 실패한다.
→ **시도 전역 목록 `getSidoAptList3(sidoCode)` 로 한 번에 받아라**(경기=41 → 5,646개). 코드 문제가 사라진다.
동명이 단지는 응답의 **`as2`(시군구)로 구분**한다.

### ❌ 4. 유찰횟수를 `yuchalCnt` 그대로 신뢰 → 부정확
신경매·재감정·중복사건에서 이력이 남아 틀린다.
→ **저감율로 역산**: 100%→0, 70·80%→1, 49·64%→2, 34·51%→3회 (경계 근사 매핑).

### ❌ 5. 단지명을 주소 끝 토큰 하나로 추출 → 매칭 실패
"경기도 평택시 현덕면 인광리 573 **이안 평택안중역아파트** 103동" 처럼 단지명이 공백 포함
다어절이거나, "소사3지구4블록 평택뉴비전엘크루"처럼 앞에 주소요소가 붙거나, "(용이동,금호어울림)"
괄호 안에 있다.
→ 괄호 "(동명,단지명)" 우선 → 동/층/호 마커 앞까지 자른 뒤 **주소요소를 만나면 리셋**하고 남은
어절 묶음을 단지명으로. (`enrich_apt.py` 의 `parse_name`)

---

## 올바른 접근법 — API 조건검색 + 시도 사후필터

### 핵심: 검색 API 요청 본문에 서버사이드 조건을 직접 주입

`searchControllerMain.on` 의 `dma_srchGdsDtlSrchInfo` 에는 지역·조건 필드가 전부 있다.
UI로 **용도만** 설정해 세션·용도코드를 확보하고 요청 본문을 캡처한 뒤, 아래를 주입한다:

| 필드 | 의미 | 예 |
|------|------|-----|
| `cortOfcCd` | 법원코드 | `''` (비우면 전국) |
| `lwsDspslPrcMin` / `Max` | 최저가 하한/상한(원) | `100000000` / `300000000` |
| `objctArDtsMin` / `Max` | 전용면적 하한/상한(㎡) | `59` / `85` |
| `flbdNcntMin` / `Max` | 유찰횟수 하한/상한 | `1` / `2` |
| `rprsAdongSdCd` 등 | 지역코드 | ⚠️ **이 API 모드에선 무시됨** → printSt 사후필터 |

> ⚠️ 법원을 비우면 반드시 용도 또는 감정가/최저가 조건 중 하나는 있어야 한다(사이트 규칙). 용도(아파트)를 UI로 걸면 충족.

### 결정론적 완전수집 — pageNo 직접 페이징
클릭 페이지네이션(파이프라인 지연으로 씹힘) 대신, 캡처한 본문의 `dma_pageInfo.pageNo` 를 1..N 으로
올려 **in-page `fetch(credentials:'include')`** 로 직접 호출한다. `pageSize ≤ 40`(초과 시 서버 500).
`totalCnt` 와 수집 고유건수를 대조해 누락을 검증한다.

**효과(2026-07-13 실측)**: 전국 아파트 유찰1↑ 1987 → +유찰상한2 1268 → +최저가1~3억 599 → +면적59~85 **423건**
→ 11페이지 결정론적 수집 → 경기 사후필터 **89건**.

### 검증된 최저가/주소 필드
- 최저가 = **`notifyMinmaePrice1`** (`minmaePrice`는 최초가=감정가인 함정)
- 주소 = `printSt` (도로명+단지명+동/호). 시도 사후필터는 `printSt.startswith('경기도')`

---

## K-apt 공동주택 기본정보 — 세대수·준공 보강

두 서비스 모두 `PUBLIC_DATA_SERVICE_KEY`(Decoding)로 쓰지만 **각각 data.go.kr 활용신청 필요**(미신청 403).
자세한 엔드포인트·필드는 `references/kapt-api.md`.

1. **`getSidoAptList3(sidoCode)`** — 시도 전역 단지 목록 → `kaptCode·kaptName·as2`. **이름 매칭용 인덱스**.
2. **`getAphusBassInfoV4(kaptCode)`** — `kaptdaCnt`(세대수)·`kaptUsedate`(사용승인=준공, YYYYMMDD).

매칭: 경매 주소에서 시군구·단지명 추출 → 인덱스에서 norm(공백/구분점/`아파트`·`단지`·`차` 제거) 정확/포함
매칭, `as2` 시군구 일치 시 가산점. 실패건은 버리지 말고 `*_review.csv` 로 분리(수동확인).

> ⚠️ K-apt 등록명과 경매 표기가 근본적으로 다른 경우가 있다(임대아파트 미등록, 브랜드 상이).
> 자동매칭 100%는 불가 — `*_review.csv` 의 매칭실패 중 신축 대단지로 보이는 건은 단지명으로 직접 재확인하라.

---

## DuckDB 적재 (자동)

수집 스크립트가 CSV 저장 직후 `ingest_to_db.ingest(csv, source)` 를 호출해 **자동 적재**한다(프로젝트 루트의
`ingest_to_db.py`). `(사건번호, 물건소재지)` upsert 라 재수집 시 가격·유찰·기일이 최신화되고 중복이 안 쌓인다.
`source`·`collected_at` 태깅으로 배치·수집일 이력을 남긴다.

| 스크립트(루트) | 역할 |
|---|---|
| `ingest_to_db.py` | CSV → `listings` upsert (수집기가 자동 호출) |
| `build_db.py` | 전체 재빌드(idempotent) — listings·apt_index·검색결과 스냅샷 |
| `query_db.py` | `python query_db.py "<SQL>"` 조회 |

```bash
python query_db.py "SELECT l.*, a.kapt_name FROM listings l
  LEFT JOIN apt_index a ON ... WHERE l.min_price < 200000000"
```

---

## 환경 함정 (Windows)

- **bash 의 `python` 은 이 환경에서 import 단계 세그폴트(exit 139)**가 난다. **PowerShell 의 python 을 써라.**
  출력 한글이 콘솔에서 깨지므로 `$env:PYTHONIOENCODING='utf-8'` + `Out-File -Encoding utf8` 로 파일에 받아 확인.
- `.env` 는 `find_dotenv(usecwd=True)` 로 찾으므로 **프로젝트 폴더에서 실행**해야 키가 잡힌다.
- 항목별 처리는 `try/except` 로 감싼다(한 건 오류가 전체 루프를 죽이지 않게).

## 시행착오 전체 기록
`references/trial-and-error-today.md` — 오늘 세션의 접근 전환(법원순회→전국조건→시도필터), K-apt 매칭
5차 개선, DuckDB 통합까지의 실패·해결 로그.
