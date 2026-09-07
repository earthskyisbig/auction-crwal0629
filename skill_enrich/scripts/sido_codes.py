# -*- coding: utf-8 -*-
"""시도명 → (K-apt sidoCode, 주소 접두어들). 경매 물건소재지(printSt) 접두어로 사후필터하고,
K-apt getSidoAptList3(sidoCode) 로 시도 전역 단지 인덱스를 받는다.

⚠️ 지역 드롭다운은 프로그램적 set 이 서버에 등록 안 됨(오늘의 함정 #1). 그래서 경매 수집은
'법원·지역 없이 전국 + 서버 조건필터' 로 받고, 시도는 printSt 접두어로 사후필터한다.
"""

# name: (sidoCode, [주소 접두어 후보])
SIDO = {
    '서울': ('11', ['서울특별시', '서울시', '서울']),
    '부산': ('26', ['부산광역시', '부산시', '부산']),
    '대구': ('27', ['대구광역시', '대구시', '대구']),
    '인천': ('28', ['인천광역시', '인천시', '인천']),
    '광주': ('29', ['광주광역시']),                 # ⚠️ 경기 광주시와 혼동 주의
    '대전': ('30', ['대전광역시', '대전시', '대전']),
    '울산': ('31', ['울산광역시', '울산시', '울산']),
    '세종': ('36', ['세종특별자치시', '세종시', '세종']),
    '경기': ('41', ['경기도']),
    '강원': ('42', ['강원특별자치도', '강원도']),
    '충북': ('43', ['충청북도']),
    '충남': ('44', ['충청남도']),
    '전북': ('45', ['전북특별자치도', '전라북도']),
    '전남': ('46', ['전라남도']),
    '경북': ('47', ['경상북도']),
    '경남': ('48', ['경상남도']),
    '제주': ('50', ['제주특별자치도', '제주도']),
}

def resolve(sido_arg):
    """'경기' / '경기도' / '서울특별시' 무엇이든 (key, sidoCode, [접두어]) 반환. 없으면 None."""
    s = (sido_arg or '').strip()
    for key, (code, prefixes) in SIDO.items():
        if s == key or s in prefixes or any(s in p or p in s for p in prefixes) or s.startswith(key):
            return key, code, prefixes
    return None

def addr_matches(printst, prefixes):
    a = (printst or '').lstrip()
    return any(a.startswith(p) for p in prefixes)
