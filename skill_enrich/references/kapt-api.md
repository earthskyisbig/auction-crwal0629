# K-apt 공동주택 정보 API — 활용신청 · 엔드포인트 · 필드

세대수·준공(사용승인)·동수 등 '단지 스펙'은 국토교통부 공동주택 정보 API에서 온다.
실거래가 API와 **별개로 활용신청** 필요(같은 서비스키, 서비스별 승인). 포맷은 JSON(`_type=json`), 엔드포인트는 V4.

## 활용신청 (사용자가 1회, 둘 다 자동승인)

1. **공동주택 기본 정보제공 서비스 V4** (세대수·준공 등) [필수]
   → https://www.data.go.kr/data/15058453/openapi.do  (AptBasisInfoServiceV4)
2. **공동주택 단지 목록제공 서비스** (단지명↔kaptCode, 시도/시군구 목록) [매칭 필수]
   → https://www.data.go.kr/data/15057332/openapi.do  (AptListService3)

승인 전에는 `403 Forbidden`. `.env` 의 `PUBLIC_DATA_SERVICE_KEY`(Decoding 키) 사용.

## 이 스킬이 쓰는 흐름

1. `AptListService3/getSidoAptList3(sidoCode, pageNo, numOfRows=500)`
   → **시도 전역** 단지 목록. `kaptCode·kaptName·as2(시군구)`. ⭐ 시군구별 조회의 코드 함정을 피하는 핵심.
2. `AptBasisInfoServiceV4/getAphusBassInfoV4(kaptCode)` → 기본정보.

베이스 URL: `https://apis.data.go.kr/1613000/AptListService3` ,
`https://apis.data.go.kr/1613000/AptBasisInfoServiceV4`

## sidoCode (getSidoAptList3)

`11`서울 `26`부산 `27`대구 `28`인천 `29`광주 `30`대전 `31`울산 `36`세종
`41`경기 `42`강원 `43`충북 `44`충남 `45`전북 `46`전남 `47`경북 `48`경남 `50`제주
(scripts/sido_codes.py 에 시도명·주소접두어와 함께 정리)

## 주요 필드 (getAphusBassInfoV4)

| 키 | 뜻 |
|---|---|
| `kaptdaCnt` | 세대수 |
| `kaptUsedate` | 사용승인일(YYYYMMDD) = 준공. 앞 4자리가 준공연도 |
| `kaptDongCnt` | 동수 |
| `kaptTopFloor` | 최고층 |
| `codeHeatNm` / `codeHallNm` | 난방 / 복도유형 |
| `kaptMparea60/85/135/136` | 전용 구간별 세대수(면적 구성) |

## 한계

- **향(방향)은 어떤 API에도 없다.**
- K-apt 등록명 ≠ 경매 표기인 경우가 있다(임대아파트 미등록, 브랜드 상이). 자동매칭 실패는 `*_review.csv` 로 분리 후 수동확인.
- `getSigunguAptList3` 는 구가 있는 시(수원·부천 등)에서 코드가 취약 → `getSidoAptList3` 를 쓸 것.
