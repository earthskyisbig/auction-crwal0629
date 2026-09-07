# -*- coding: utf-8 -*-
"""흩어진 경매 CSV/JSON을 DuckDB(auction.duckdb) 하나로 통합.
테이블:
  apt_index       : K-apt 경기 전역 단지 마스터(code·name·sigungu)
  listings        : 경매 물건 통합(가격·면적 숫자화, source·수집일 태깅)
  gyeonggi_final  : 이번 검색 최종 확정(세대수·준공 보강)
  gyeonggi_review : 조건미달·검토 대상(사유 포함)
재실행 시 항상 새로 빌드(idempotent).
"""
import os, json, datetime
import duckdb
from ingest_to_db import ingest, DDL as LISTINGS_DDL

HERE = os.path.dirname(os.path.abspath(__file__))
DB   = os.path.join(HERE, 'auction.duckdb')
WS   = os.path.join(HERE, '_workspace')

def p(*a): return os.path.join(HERE, *a)

con = duckdb.connect(DB)
con.execute("INSTALL json; LOAD json;")

# ── 1) apt_index (K-apt 경기 단지 마스터) ──
con.execute("DROP TABLE IF EXISTS apt_index;")
con.execute(f"""
CREATE TABLE apt_index AS
SELECT code AS kapt_code, name AS kapt_name, as2 AS sigungu
FROM read_json_auto('{p("_workspace","gyeonggi_apt_index.json").replace(os.sep,"/")}');
""")

# ── 2) listings (경매 물건 통합) — ingest 모듈로 통일 적재 ──
con.execute("DROP TABLE IF EXISTS listings;")
con.execute(LISTINGS_DDL)
con.close()  # ingest가 자체 커넥션을 열므로 잠시 닫음
for path, src in [
    (p('auction_list.csv'),                    'auction_list'),
    (p('auction_yangju_apt.csv'),              'auction_yangju'),
    (p('_workspace', 'gyeonggi_apt_raw.csv'),  'gyeonggi_2026_07'),
]:
    if os.path.exists(path):
        ingest(path, src, DB)
con = duckdb.connect(DB)  # 재연결

# ── 3) gyeonggi_final / gyeonggi_review (보강본) ──
for tbl, fp in [('gyeonggi_final', p('_workspace','gyeonggi_final.csv')),
                ('gyeonggi_review', p('_workspace','gyeonggi_review.csv'))]:
    if not os.path.exists(fp):
        continue
    con.execute(f"DROP TABLE IF EXISTS {tbl};")
    con.execute(f"""
    CREATE TABLE {tbl} AS
    SELECT "사건번호" AS case_no, "물건소재지" AS address,
           TRY_CAST(regexp_replace("전용면적",'[^0-9.]','','g') AS DOUBLE) AS area_m2,
           TRY_CAST(regexp_replace("감정가",'[^0-9]','','g') AS BIGINT) AS appraisal,
           TRY_CAST(regexp_replace("최저가",'[^0-9]','','g') AS BIGINT) AS min_price,
           TRY_CAST(regexp_replace("저감율",'[^0-9]','','g') AS INTEGER) AS discount_rate,
           "_유찰역산" AS yuchal,
           "_시군구" AS sigungu, "_매칭단지" AS kapt_name,
           TRY_CAST("_세대수" AS INTEGER) AS households,
           TRY_CAST("_준공연도" AS INTEGER) AS built_year,
           CAST("매각기일" AS VARCHAR) AS sale_date
           {', "_사유" AS reason' if tbl=='gyeonggi_review' else ''}
    FROM read_csv_auto('{fp.replace(os.sep,"/")}', header=true);
    """)

# ── 메타 (빌드 이력) ──
con.execute("DROP TABLE IF EXISTS _meta;")
con.execute("CREATE TABLE _meta(built_at VARCHAR, note VARCHAR);")
con.execute("INSERT INTO _meta VALUES (?, ?)",
            [datetime.datetime.now().isoformat(timespec='seconds'),
             '경기 아파트 유찰1~2·1~3억·59~85㎡·세대500+·2015+ 검색 (기준 2026-07-13)'])

# ── 요약 ──
print("✅ auction.duckdb 빌드 완료\n")
print("[테이블 · 행수]")
for (name,) in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main' ORDER BY table_name").fetchall():
    cnt = con.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
    print(f"  {name:16s} {cnt:>6,}행")
print("\n[gyeonggi_final 시군구별 건수]")
for sgg, n in con.execute("SELECT sigungu, count(*) FROM gyeonggi_final GROUP BY sigungu ORDER BY 2 DESC").fetchall():
    print(f"  {sgg:12s} {n}건")
con.close()
