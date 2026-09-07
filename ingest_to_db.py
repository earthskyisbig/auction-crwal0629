# -*- coding: utf-8 -*-
"""경매 수집 CSV를 auction.duckdb의 listings 테이블에 upsert(자동 적재).

- 표준 8컬럼(사건번호·물건소재지·전용면적·감정가·최저가·저감율·유찰횟수·매각기일)과
  최소 5컬럼(면적/저감율/기일 없음) 모두 지원 — 헤더 존재 여부로 판단.
- 금액/면적/저감율을 숫자로 정규화, source·collected_at 태깅.
- (case_no, address) 동일 물건은 replace(최신 상태로 갱신) → 재수집 시 가격·유찰·기일 최신화.

CLI:   python ingest_to_db.py <csv> --source gyeonggi_2026_07
모듈:  from ingest_to_db import ingest;  ingest("out.csv", "some_batch")
"""
import os, csv, re, argparse, datetime
import duckdb

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'auction.duckdb')

DDL = """
CREATE TABLE IF NOT EXISTS listings (
    source        VARCHAR,
    case_no       VARCHAR,
    address       VARCHAR,
    area_m2       DOUBLE,
    appraisal     BIGINT,
    min_price     BIGINT,
    discount_rate INTEGER,
    fail_count    VARCHAR,
    sale_date     VARCHAR,
    collected_at  VARCHAR
);
"""

def _num(s):
    d = re.sub(r'[^0-9]', '', str(s or ''))
    return int(d) if d else None

def _area(s):
    m = re.search(r'([\d.]+)', str(s or ''))
    return float(m.group(1)) if m else None

def _rate(s):
    d = re.sub(r'[^0-9]', '', str(s or ''))
    return int(d) if d else None

def _norm_row(r, source, now):
    g = lambda *ks: next((r[k] for k in ks if k in r and r[k] not in (None, '')), '')
    return {
        'source': source,
        'case_no': g('사건번호', 'case_no').strip(),
        'address': g('물건소재지', 'address').strip(),
        'area_m2': _area(g('전용면적', 'area_m2')),
        'appraisal': _num(g('감정가', 'appraisal')),
        'min_price': _num(g('최저가', 'min_price')),
        'discount_rate': _rate(g('저감율', 'discount_rate')),
        'fail_count': str(g('유찰횟수', 'fail_count') or '').strip(),
        'sale_date': str(g('매각기일', 'sale_date') or '').strip(),
        'collected_at': now,
    }

COLS = ['source', 'case_no', 'address', 'area_m2', 'appraisal', 'min_price',
        'discount_rate', 'fail_count', 'sale_date', 'collected_at']

def ingest(csv_path, source, db=DB):
    now = datetime.datetime.now().isoformat(timespec='seconds')
    with open(csv_path, encoding='utf-8-sig') as f:
        rows = [_norm_row(r, source, now) for r in csv.DictReader(f)]
    rows = [r for r in rows if r['case_no']]
    if not rows:
        print(f"⚠️  {csv_path}: 적재할 행 없음")
        return 0
    con = duckdb.connect(db)
    con.execute(DDL)
    # upsert: (case_no,address) 동일 물건 삭제 후 삽입
    keys = list({(r['case_no'], r['address']) for r in rows})
    con.executemany("DELETE FROM listings WHERE case_no=? AND address=?", keys)
    con.executemany(
        f"INSERT INTO listings ({','.join(COLS)}) VALUES ({','.join(['?']*len(COLS))})",
        [[r[c] for c in COLS] for r in rows])
    total = con.execute("SELECT count(*) FROM listings").fetchone()[0]
    con.close()
    print(f"✅ 적재 {len(rows)}건 (source={source}) → listings 총 {total:,}행")
    return len(rows)

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('csv')
    ap.add_argument('--source', required=True, help='배치 식별자 (예: gyeonggi_2026_07)')
    ap.add_argument('--db', default=DB)
    a = ap.parse_args()
    ingest(a.csv, a.source, a.db)
