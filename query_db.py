# -*- coding: utf-8 -*-
"""auction.duckdb 조회 예시 — 인자로 준 SQL 실행, 없으면 데모 쿼리."""
import sys, os, duckdb
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'auction.duckdb')
con = duckdb.connect(DB, read_only=True)
if len(sys.argv) > 1:
    con.sql(' '.join(sys.argv[1:])).show(max_rows=100)
else:
    print("① 최종 확정 19건 (세대수 내림차순)")
    con.sql("""SELECT kapt_name 단지, households 세대, built_year 준공,
                      round(area_m2,1) 전용, printf('%.2f억', min_price/1e8) 최저가,
                      yuchal 유찰, sale_date 매각기일
               FROM gyeonggi_final ORDER BY households DESC""").show(max_rows=30)
    print("\n② 임의 조건 검색 예: 세대 1000+ & 준공 2018+")
    con.sql("""SELECT kapt_name, households, built_year, printf('%.2f억',min_price/1e8) min_price
               FROM gyeonggi_final WHERE households>=1000 AND built_year>=2018
               ORDER BY households DESC""").show()
    print("\n③ listings + apt_index 조인 (경기 raw에 세대수 붙이기 예)")
    con.sql("""SELECT l.address[1:30] 주소, a.kapt_name, a.sigungu
               FROM listings l LEFT JOIN apt_index a
                 ON regexp_replace(a.kapt_name,'[ 아파트]','','g')
                    = regexp_replace(regexp_extract(l.address,'[가-힣0-9]+(자이|푸르지오|힐스테이트|캐슬)[가-힣0-9]*',0),'[ 아파트]','','g')
               WHERE l.source='gyeonggi_2026_07' AND a.kapt_name IS NOT NULL
               LIMIT 8""").show()
con.close()
