# -*- coding: utf-8 -*-
"""jaegaebal 정비구역 DB → rebuild_zones.json 스냅샷 (로컬 전용).

클라우드 분기 루틴에는 jaegaebal DB가 없으므로, 재건축 추진 구역 목록을 저장소에 스냅샷으로 둔다.
로컬에서 DB 단계가 바뀌었을 때 이 스크립트를 다시 돌리고 rebuild_zones.json 을 커밋한다.
  python3 p84_export_zones.py [DB경로]   (기본 ~/jaegaebal/redev_zones.db)
"""
import json, os, re, sqlite3, sys
from datetime import date

W = os.path.dirname(os.path.abspath(__file__))
DB = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/jaegaebal/redev_zones.db')
STAGES = ('구역지정전', '추진위', '구역지정', '조합설립', '사업시행인가', '관리처분')   # 기존 건물이 아직 거래되는 단계

if not os.path.exists(DB):
    sys.exit(f'DB 없음: {DB} — 기존 rebuild_zones.json 유지')
con = sqlite3.connect(DB)
rows = con.execute(f"""select id, gu, dong, name, stage, type, ifnull(note,'') from zones
    where (type like '%재건축%' or ifnull(subtype,'') like '%재건축%') and stage in {STAGES}""").fetchall()
zones = []
for zid, gu, dong, name, stage, typ, note in rows:
    m = re.search(r'대표지번:\s*(\S+)\s+(\d+)(?:-(\d+))?', note)
    zones.append({'id': zid, 'gu': gu, 'dong': dong, 'name': name, 'stage': stage, 'type': typ,
                  'jb_dong': m.group(1) if m else None,
                  'bonbun': int(m.group(2)) if m else None,
                  'bubun': int(m.group(3)) if m and m.group(3) else None})
json.dump({'exported': date.today().isoformat(), 'source': 'jaegaebal/redev_zones.db', 'stages': STAGES, 'zones': zones},
          open(os.path.join(W, 'rebuild_zones.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print(f'rebuild_zones.json: {len(zones)}개 구역 (대표지번 {sum(1 for z in zones if z["bonbun"])}개)')
