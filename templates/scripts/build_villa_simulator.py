# -*- coding: utf-8 -*-
import csv, re, html, os
BASE = os.path.dirname(os.path.abspath(__file__))
def won(v): return int(re.sub(r'[^\d]', '', v))
def man(v): return f"{round(v/10000):,}"

PICKS = {  # top10 매칭 substring → rank
    '정릉동 318':1, '회기동 103-150 제3층 제303호':2, '회기동 103-150 제3층 제304호':3,
    '인수봉로29길':4, '삼전동 64-7 3층301호':5, '화곡동 410-167':6, '화곡동 56-188':7,
    '홍은동 265-288':8, '도봉로110아길':9, '구의동 201-11 다솜빌 2층204호':10,
}
def flbd(rate):
    if rate >= 95: return '신건'
    if rate >= 70: return f'1회 ({rate}%)'
    if rate >= 55: return f'2회 ({rate}%)'
    return f'3회 ({rate}%)'

rows = []
with open(os.path.join(BASE, 'seoul_dasedae_u1to3_1eok.csv'), encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        rate = int(re.sub(r'[^\d]', '', r['저감율']))
        addr = r['물건소재지'].replace('서울특별시 ', '')
        pick = ''
        for k, v in PICKS.items():
            if k in r['물건소재지']:
                pick = f'<span class="pickchip">{v}위</span>'; break
        rows.append(f'''          <tr><td>{pick}{html.escape(addr)}<span style="display:block;font-size:10px;color:var(--muted)">{html.escape(r['사건번호'])} · 매각 {r['매각기일']}</span></td>
            <td>{r['전용면적']}</td><td>{flbd(rate)}</td><td>{man(won(r['최저가']))}만</td></tr>''')

tpl = open(os.path.join(BASE, 'seoul_sim_template.html'), encoding='utf-8').read()
out_path = os.path.join(BASE, '서울_다세대_경매추천_보고서.html')
open(out_path, 'w', encoding='utf-8').write(tpl.replace('{{ROWS58}}', '\n'.join(rows)))
print('OK', len(rows), '→', out_path)
