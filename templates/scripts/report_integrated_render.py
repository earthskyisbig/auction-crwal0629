# -*- coding: utf-8 -*-
"""경기 비규제 아파트 경매 종합보고서 — HTML 렌더러."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_report_0909 import (PROPS, TAX, AGG, REG, ROOT, man, e,
                               kpi_row, tax_section, funnel, region_bars,
                               prop_tabs, prop_cards, prop_js)

BARS, TRS = tax_section()

def turn_rows():
    rows = []
    for p in PROPS:
        t = p['turn'] or 0
        interp = ('손바뀜 활발 — 매도 대기 짧음' if t >= 5 else
                  '보통' if t >= 4 else '손바뀜 느림 — 출구 좁음')
        rows.append('<tr><td>%s</td><td class="r num">%s</td><td class="r num">%s</td>'
                    '<td class="r num"><b>%s%%</b></td><td class="mut">%s</td></tr>'
                    % (e(p['short']), format(p['hh'] or 0, ','), p['turn_cnt'], t, interp))
    return '\n'.join(rows)

HEAD = '''<meta charset="utf-8">
<title>경기 비규제 아파트 경매</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Nanum+Myeongjo:wght@400;700;800&family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap">
<style>
:root{
  --seal:#c0392b; --seal-deep:#8f2a1f; --ink:#1b2432;
  --bg:#efe9dd; --card:#fff; --fg:#1b2432; --sub:#5b6472; --muted:#79828f;
  --line:#d8d0bf; --line-soft:#e6e0d2; --field:#fbf9f4;
  --gain:#1f7a4d; --gain-soft:#e4efe9; --loss:#b23b2e; --loss-soft:#f7e8e5;
  --amber:#9a6410; --amber-soft:#f5ecdc;
  --shadow:0 1px 2px rgba(27,36,50,.06),0 8px 30px rgba(27,36,50,.07);
  --mono:"SF Mono",ui-monospace,"JetBrains Mono",Consolas,monospace;
  --sans:"IBM Plex Sans KR",-apple-system,"Malgun Gothic",sans-serif;
  --serif:"Nanum Myeongjo",serif;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --seal:#e0644f; --seal-deep:#c0392b; --ink:#e8eaf0;
  --bg:#10141b; --card:#1a212c; --fg:#e8eaf0; --sub:#9aa3b2; --muted:#7f8896;
  --line:#2b3342; --line-soft:#232b38; --field:#141a23;
  --gain:#4ecf8f; --gain-soft:#1a2f26; --loss:#e9705f; --loss-soft:#33211e;
  --amber:#d9a05b; --amber-soft:#332920;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 34px rgba(0,0,0,.5);
}}
:root[data-theme="dark"]{
  --seal:#e0644f; --seal-deep:#c0392b; --ink:#e8eaf0;
  --bg:#10141b; --card:#1a212c; --fg:#e8eaf0; --sub:#9aa3b2; --muted:#7f8896;
  --line:#2b3342; --line-soft:#232b38; --field:#141a23;
  --gain:#4ecf8f; --gain-soft:#1a2f26; --loss:#e9705f; --loss-soft:#33211e;
  --amber:#d9a05b; --amber-soft:#332920;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 34px rgba(0,0,0,.5);
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font-family:var(--sans);
  font-size:15px;line-height:1.65;-webkit-font-smoothing:antialiased}
.num{font-variant-numeric:tabular-nums}
.wrap{max-width:1060px;margin:0 auto;padding:32px 22px 90px}
.mut{color:var(--muted)} .pos{color:var(--gain)} .neg{color:var(--loss)}
header{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;
  border-bottom:1px solid var(--line);padding-bottom:24px;margin-bottom:22px}
.brand{display:flex;gap:15px;align-items:center}
.stamp{width:50px;height:50px;flex:none;border-radius:9px;border:2px solid var(--seal);color:var(--seal);
  display:grid;place-items:center;font-family:var(--serif);font-weight:800;font-size:13px;
  transform:rotate(-6deg);position:relative;letter-spacing:1px}
.stamp::after{content:"";position:absolute;inset:4px;border:1px solid var(--seal);border-radius:5px;opacity:.5}
h1{font-family:var(--serif);font-weight:800;font-size:clamp(24px,4.4vw,34px);margin:0;letter-spacing:-.4px;text-wrap:balance}
.eyebrow{font-size:11.5px;letter-spacing:.13em;text-transform:uppercase;color:var(--muted);font-weight:700;margin:0 0 7px}
.themebtn{border:1px solid var(--line);background:var(--card);color:var(--sub);border-radius:8px;
  padding:7px 11px;font-size:12px;cursor:pointer;font-family:inherit;flex:none}
.conds{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:26px}
.cond{border:1px solid var(--line);background:var(--card);border-radius:20px;padding:4px 12px;font-size:12.5px;color:var(--sub)}
.cond b{color:var(--fg);font-weight:650;margin-left:5px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(158px,1fr));gap:1px;background:var(--line);
  border:1px solid var(--line);border-radius:12px;overflow:hidden;margin-bottom:36px}
.kpi{background:var(--card);padding:16px 17px 14px}
.kpi .k{font-size:11.5px;color:var(--muted);font-weight:600}
.kpi .v{font-family:var(--serif);font-weight:800;font-size:24px;line-height:1.15;margin-top:5px}
.kpi .v small{font-family:var(--sans);font-size:12.5px;font-weight:500;color:var(--muted);margin-left:3px}
.kpi.good .v{color:var(--gain)} .kpi.seal .v{color:var(--seal)}
section{margin-bottom:44px}
h2{font-family:var(--serif);font-weight:800;font-size:21px;margin:0 0 5px;text-wrap:balance}
.lede{color:var(--sub);font-size:13.5px;margin:0 0 20px;max-width:72ch}
h3{font-size:14px;margin:22px 0 10px;font-weight:700}
.card{background:var(--card);border:1px solid var(--line);border-radius:13px;box-shadow:var(--shadow);padding:20px 22px}
.verdict{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--seal);
  border-radius:0 12px 12px 0;padding:18px 22px;box-shadow:var(--shadow)}
.verdict p{margin:0 0 11px;max-width:80ch} .verdict p:last-child{margin-bottom:0}
.tb{display:flex;align-items:center;gap:12px;margin:9px 0;font-size:13px}
.tb .tl{flex:none;width:118px;color:var(--sub)}
.tb .tbar{flex:1;height:20px;background:var(--field);border-radius:4px;overflow:hidden}
.tb .tbar i{display:block;height:100%;border-radius:4px}
.tb .tbar i.non{background:var(--gain)} .tb .tbar i.reg{background:var(--seal)}
.tb .tv{flex:none;width:96px;text-align:right;font-family:var(--mono);font-size:12.5px}
table{border-collapse:collapse;width:100%;font-size:13px}
.tw{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--card)}
.tw table{min-width:600px}
thead th{text-align:left;font-size:11px;letter-spacing:.05em;color:var(--muted);font-weight:700;
  padding:10px 12px;border-bottom:2px solid var(--ink);white-space:nowrap;background:var(--card)}
tbody td{padding:9px 12px;border-bottom:1px solid var(--line-soft);vertical-align:top}
tbody tr:last-child td{border-bottom:0}
td.r,th.r{text-align:right;white-space:nowrap}
.fn{display:flex;align-items:center;gap:12px;margin:8px 0;font-size:13px}
.fn .fl{flex:none;width:104px;font-weight:600}
.fn .fbar{flex:none;width:200px;height:16px;background:var(--field);border-radius:4px;overflow:hidden}
.fn .fbar i{display:block;height:100%;background:var(--seal);opacity:.82;border-radius:4px}
.fn .fv{flex:none;width:44px;text-align:right;font-family:var(--mono);font-weight:700}
.fn .fd{flex:1;color:var(--muted);font-size:12px}
@media(max-width:660px){.fn{flex-wrap:wrap}.fn .fd{width:100%;padding-left:116px}}
.rg{display:flex;align-items:center;gap:10px;margin:6px 0;font-size:12.5px}
.rg .rl{flex:none;width:112px;color:var(--sub)}
.rg .rbar{flex:1;height:14px;background:var(--field);border-radius:3px;overflow:hidden}
.rg .rbar i{display:block;height:100%;background:var(--ink);opacity:.42;border-radius:3px}
.rg .rv{flex:none;width:28px;text-align:right;font-family:var(--mono)}
.props{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:16px}
@media(max-width:880px){.props{grid-template-columns:repeat(2,1fr)}}
.prop{border:1px solid var(--line);border-radius:11px;background:var(--card);padding:10px 12px;cursor:pointer;
  user-select:none;box-shadow:var(--shadow)}
.prop.on{border-color:var(--seal);outline:2px solid var(--seal);outline-offset:-1px}
.prop .pn{font-size:12.5px;font-weight:700;letter-spacing:-.2px}
.prop .pm{font-size:10.5px;color:var(--muted);margin-top:2px;font-family:var(--mono)}
.prop .pv{display:inline-block;margin-top:7px;font-size:10px;font-weight:700;border-radius:5px;padding:1px 6px;border:1px solid}
.pv.ok,.rb.ok{color:var(--gain);border-color:var(--gain);background:var(--gain-soft)}
.pv.cond,.rb.cond{color:var(--amber);border-color:var(--amber);background:var(--amber-soft)}
.rb{display:inline-block;font-size:11px;font-weight:700;border-radius:5px;padding:2px 8px;border:1px solid}
.rb.warn{color:var(--amber);border-color:var(--amber);background:var(--amber-soft)}
.pcard{display:none;background:var(--card);border:1px solid var(--line);border-radius:13px;
  padding:20px 22px;box-shadow:var(--shadow)}
.pcard.on{display:block}
.ph{display:flex;flex-wrap:wrap;align-items:baseline;gap:10px;margin-bottom:6px}
.pt{font-family:var(--serif);font-weight:800;font-size:18px}
.phead{color:var(--seal);font-size:13.5px;font-weight:650;margin:0 0 12px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px}
.chip{font-size:11.5px;background:var(--field);border:1px solid var(--line);border-radius:20px;padding:3px 10px;color:var(--sub)}
.stat4{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);border:1px solid var(--line);
  border-radius:10px;overflow:hidden;margin-bottom:16px}
@media(max-width:620px){.stat4{grid-template-columns:repeat(2,1fr)}}
.stat4 .s{background:var(--card);padding:11px 13px}
.stat4 .sk{font-size:10.5px;color:var(--muted);font-weight:600}
.stat4 .sv{font-family:var(--serif);font-weight:800;font-size:17px;margin-top:3px}
.stat4 .sv.seal{color:var(--seal)}
.stat4 .sd{font-size:10.5px;color:var(--muted);margin-top:2px}
.pbody{font-size:13.5px;max-width:80ch;margin-bottom:14px}
.prisk{font-size:12.5px;color:var(--sub);background:var(--field);border:1px solid var(--line-soft);
  border-left:3px solid var(--amber);border-radius:0 8px 8px 0;padding:11px 14px;margin-bottom:16px}
.prisk b{color:var(--amber);margin-right:6px}
.pgrid{display:grid;grid-template-columns:1fr 1fr;gap:22px}
@media(max-width:720px){.pgrid{grid-template-columns:1fr}}
.sub{font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);font-weight:700;margin-bottom:8px}
.fl2{margin:9px 0 0;padding-left:17px;font-size:12.5px;color:var(--sub)}
.fl2 li{margin:4px 0}
table.mini{font-size:12px}
table.mini th{border-bottom:1px solid var(--line);padding:5px 7px;font-size:10.5px}
table.mini td{padding:5px 7px;border-bottom:1px solid var(--line-soft)}
.simg{display:grid;grid-template-columns:1fr 1fr;gap:20px 26px}
@media(max-width:720px){.simg{grid-template-columns:1fr}}
.ctl{margin-bottom:14px}
.ctl label{display:block;font-size:12px;color:var(--sub);font-weight:600;margin-bottom:5px}
.ctl input[type=range]{width:100%;accent-color:var(--seal)}
.ctl .val{font-family:var(--serif);font-weight:800;font-size:20px}
.ctl .hint{font-size:11px;color:var(--muted);margin-top:2px}
.segs{display:flex;gap:6px;flex-wrap:wrap}
.seg{flex:1;min-width:64px;text-align:center;padding:7px 5px;border:1px solid var(--line);border-radius:8px;
  background:var(--field);color:var(--sub);font-size:12px;cursor:pointer;user-select:none}
.seg.on{border-color:var(--seal);color:var(--seal);background:var(--loss-soft);font-weight:650}
.out{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;align-content:start}
.out .o{border:1px solid var(--line-soft);background:var(--field);border-radius:8px;padding:10px 12px}
.out .o .ol{font-size:10.5px;color:var(--muted);font-weight:600}
.out .o .ov{font-family:var(--serif);font-weight:800;font-size:17px;margin-top:3px;white-space:nowrap}
.law td:first-child{font-weight:600;white-space:nowrap}
.src{font-family:var(--mono);font-size:11px;color:var(--muted)}
footer{border-top:1px solid var(--line);padding-top:22px;font-size:12px;color:var(--muted);max-width:84ch}
footer p{margin:0 0 9px} footer b{color:var(--sub)}
</style>
'''

BODY = '''<div class="wrap">
<header>
  <div class="brand">
    <div class="stamp">落札</div>
    <div>
      <p class="eyebrow">경매 종합보고서 · 실사 · 법률 · 입지 · 세금 통합 · 2026. 09. 09.</p>
      <h1>경기 비규제 아파트 경매</h1>
    </div>
  </div>
  <button class="themebtn" id="tt">◐ 테마</button>
</header>

<div class="conds">
  <span class="cond">지역<b>경기도 비규제지역</b></span>
  <span class="cond">용도<b>아파트</b></span>
  <span class="cond">유찰<b>1 ~ 3회</b></span>
  <span class="cond">최저매각가<b>2억원 이하</b></span>
  <span class="cond">매각기일<b>2026.09.09 ~ 09.23</b></span>
</div>

<div class="kpis">__KPI__</div>

<section>
  <h2>결론</h2>
  <div class="verdict">
    <p>조건에 맞는 경기도 <b>비규제지역 아파트는 100건</b>입니다. 이 가운데 단지 규모·연식·실거래 표본으로 압축한 8건의
    매각물건명세서와 현황조사서를 직접 열람한 결과, <b>8건 모두 지분매각이 아니었고 7건은 매수인이 떠안을 인수금액이 0원</b>입니다.
    같은 방식으로 검증한 서울 빌라에서 상위 10건 중 5건이 지분매각이었던 것과 대조적입니다.</p>
    <p>핵심 발견은 따로 있습니다. 8건 중 <b>4건이 주택도시보증공사·서울보증보험이 대위변제 후 신청한 경매</b>이고, 이들 보증기관은
    낙찰을 촉진하려고 <b>“대항력을 포기하고 임차권등기를 말소하겠다”는 확약서</b>를 제출해 두었습니다. 겉보기에는 보증금 2억대가
    선순위로 걸린 위험 물건이지만 실제로는 인수부담 없이 시세의 55~75%에 살 수 있는 물건이고,
    <b>자동 수집 스크립트는 이 확약서를 읽지 못해 네 건 모두 “인수위험”으로 잘못 표시</b>했습니다.</p>
    <p>여기에 비규제라는 조건이 세금에서 결정적으로 작동합니다. 동일한 물건·동일한 차익 4,000만원을 가정해도
    <b>비규제 2주택자의 세후 순익은 2,702만원(17.2%)인 반면 규제지역 3주택자는 65만원 적자</b>입니다. 물건을 고르는 일보다
    어느 지역에서 몇 번째 주택으로 사느냐가 수익을 더 크게 가릅니다.</p>
    <p>다만 8건 중 <b>입찰을 권할 수 있는 것은 6건</b>입니다. 양주 세창리베하우스는 명세서와 현황조사의 임차인 기재가 어긋나
    전입세대열람 전에는 인수금액을 확정할 수 없고, 파주 동광모닝스카이는 권리가 깨끗한데도 227세대·연 7건 거래에 그쳐
    <b>할인폭이 큰 이유가 물건이 아니라 지역 수요 부족일 가능성</b>을 배제하기 어렵습니다.</p>
  </div>
</section>

<section>
  <h2>비규제지역이 만드는 세금 차이</h2>
  <p class="lede">같은 물건(낙찰 1.5억 · 2년 보유 · 매도 1.9억 · 차익 4,000만원)을 규제 여부와 주택수만 바꿔 계산했습니다.
  수치는 auction-tax2 세금엔진이 <span class="src">data/tax-rates.yaml</span>의 법령별 세율표를 읽어 산출한 값이며 암산·추정치가 아닙니다.</p>
  <div class="card">
    __TAXBARS__
    <div style="height:16px"></div>
    <div class="tw"><table>
      <thead><tr><th>시나리오</th><th class="r">취득세</th><th class="r">양도세</th><th class="r">총 세금</th><th class="r">세후 순익</th><th class="r">수익률</th></tr></thead>
      <tbody>__TAXROWS__</tbody>
    </table></div>
    <h3>왜 이렇게 벌어지나</h3>
    <ul class="fl2" style="font-size:13px">
      <li><b>취득세</b> — 비규제지역은 <b>3주택까지 일반세율(1~3%)</b>이고 4주택부터 12% 중과입니다. 규제지역은 2주택에서 이미 8%,
      3주택부터 12%입니다. 같은 2주택자가 1.5억을 낙찰받으면 비규제 165만원 vs 규제 1,260만원으로 <b>7.6배</b> 차이입니다.
      <span class="src">지방세법 §13의2①</span></li>
      <li><b>양도세 다주택 중과</b> — 조정대상지역 주택에만 2주택 +20%p, 3주택 이상 +30%p가 붙고 장기보유특별공제가 배제됩니다.
      비규제지역 주택은 이 중과 대상이 아닙니다. <span class="src">소득세법 §104⑦</span></li>
      <li><b>단기양도 중과는 지역과 무관</b> — 1년 미만 70%, 2년 미만 60%는 비규제에서도 그대로 적용됩니다.
      비규제의 이점은 “빨리 팔아도 된다”가 아니라 <b>“주택수를 늘려도 벌칙이 작다”</b>입니다. <span class="src">소득세법 §104①2·3</span></li>
    </ul>
  </div>
</section>

<section>
  <h2>어떻게 100건으로 좁혔나</h2>
  <p class="lede">법원경매정보 전국 검색에서 시작해 단계마다 조건을 걸었습니다. 각 단계는 실제로 실행한 스크립트 한 개에 대응합니다.</p>
  <div class="card">__FUNNEL__</div>
  <h3>비규제 100건은 어디에 몰려 있나</h3>
  <div class="card">__REGIONS__
    <p class="lede" style="margin:16px 0 0">의정부·파주·양주·평택·안성이 전체의 56%를 차지합니다. 규제지역 15곳(과천·광명·성남 전역·수원 3개 구·
    안양 동안구·용인 수지구·용인 기흥구·의왕·하남·구리·화성 동탄구)을 빼고 나면 남는 것은 경기 북부와 남부 외곽입니다.
    <b>비규제는 세제 혜택인 동시에 “규제할 만큼 과열되지 않은 지역”이라는 뜻</b>이기도 하다는 점을 기억해야 합니다.</p>
  </div>
</section>

<section>
  <h2>핵심 발견 — 보증기관이 대항력을 포기한 물건들</h2>
  <div class="card">
    <p style="margin:0 0 12px;max-width:80ch">심층 분석한 8건 중 4건에서 같은 구조가 나왔습니다. 전세보증금 반환보증에 가입한 임차인이
    보증사고를 당하자 <b>주택도시보증공사(HUG) 또는 서울보증보험이 보증금을 대신 지급하고 임차인의 채권을 넘겨받아</b> 경매를 신청한 사건입니다.</p>
    <p style="margin:0 0 12px;max-width:80ch">문제는 이 임차인의 전입일이 근저당·가압류보다 앞선다는 점입니다. 원칙대로면
    <span class="src">주택임대차보호법 §3의5 단서</span>에 따라 배당에서 못 받은 보증금 잔액을 매수인이 인수해야 하고, 보증금이 2억대라
    아무도 입찰하지 않습니다. 그래서 보증기관은 <b>“우선변제권만 주장하고 대항력은 포기하며, 전액을 못 받아도 임차권등기를 말소하겠다”</b>는
    확약서를 법원에 제출합니다. 이 확약서가 들어오는 순간 인수부담은 0원이 되고, 이미 한두 번 저감된 최저가만 남습니다.</p>
    <div class="tw"><table>
      <thead><tr><th>물건</th><th>보증기관</th><th class="r">보증금</th><th>확약서 제출일</th><th class="r">최저가 ÷ 시세</th></tr></thead>
      <tbody>
        <tr><td>안성 롯데캐슬 1306호</td><td>주택도시보증공사</td><td class="r num">2억 4,000만</td><td>2026.06.01</td><td class="r num">74.9%</td></tr>
        <tr><td>파주 팜스프링 2003호</td><td>주택도시보증공사</td><td class="r num">2억 7,000만</td><td>2026.05.21</td><td class="r num">55.6%</td></tr>
        <tr><td>안성 공도 주은풍림 1001호</td><td>서울보증보험</td><td class="r num">1억 3,500만</td><td>2026.04.28</td><td class="r num">72.4%</td></tr>
        <tr><td>파주 동광모닝스카이 302호</td><td>주택도시보증공사</td><td class="r num">2억 1,000만</td><td>2026.05.21</td><td class="r num">57.2%</td></tr>
      </tbody>
    </table></div>
    <p class="lede" style="margin:16px 0 0"><b>주의</b> — 확약서는 사건기록에 편철된 문서이지 등기부에 공시되는 권리가 아닙니다.
    매각물건명세서 비고란의 원문과 사건기록의 확약서 실물을 직접 확인하고, 제출 주체가 현재의 채권자와 일치하는지 대조하세요.</p>
  </div>
</section>

<section>
  <h2>물건별 심층분석</h2>
  <p class="lede">탭을 눌러 물건을 전환하면 권리 판정·시세·환금성·기일 이력이 함께 바뀌고, 아래 시뮬레이터도 그 물건 기준으로 다시 계산됩니다.
  유찰횟수는 사이트 필드가 부정확해 저감율로 역산했습니다(경기 30% 저감 기준 70%=1회, 49%=2회, 34%=3회).</p>
  <div class="props">__TABS__</div>
  __CARDS__
</section>

<section>
  <h2>세후 수익 시뮬레이터</h2>
  <p class="lede">선택한 물건에 낙찰가·매도가·보유기간·주택수·규제여부를 적용해 세후 순익을 계산합니다.
  세율 체계는 세금엔진과 동일합니다(취득세 비규제 3주택까지 일반세율, 단기양도 70/60%, 지방소득세 10%, 기본공제 250만원).
  <b>“규제 가정”으로 바꿔 보면 같은 물건에서 비규제가 만드는 차이가 바로 보입니다.</b></p>
  <div class="card">
    <div class="simg">
      <div>
        <div class="ctl">
          <label for="bid">낙찰가</label>
          <input type="range" id="bid" min="0" max="100" value="0">
          <div class="val num" id="bidv">—</div>
          <div class="hint" id="bidh"></div>
        </div>
        <div class="ctl">
          <label for="sell">예상 매도가</label>
          <input type="range" id="sell" min="0" max="100" value="50">
          <div class="val num" id="sellv">—</div>
          <div class="hint" id="sellh"></div>
        </div>
        <div class="ctl"><label>보유기간</label>
          <div class="segs" id="segMonths">
            <div class="seg" data-v="6">6개월</div><div class="seg" data-v="18">1.5년</div>
            <div class="seg on" data-v="30">2.5년</div><div class="seg" data-v="60">5년</div>
          </div></div>
        <div class="ctl"><label>취득 후 보유 주택수</label>
          <div class="segs" id="segHouses">
            <div class="seg on" data-v="1">1주택</div><div class="seg" data-v="2">2주택</div>
            <div class="seg" data-v="3">3주택</div><div class="seg" data-v="4">4주택</div>
          </div></div>
        <div class="ctl"><label>지역 규제 (비교용)</label>
          <div class="segs" id="segReg">
            <div class="seg on" data-v="0">비규제 (실제)</div><div class="seg" data-v="1">규제 가정</div>
          </div></div>
      </div>
      <div class="out" id="out"></div>
    </div>
    <p class="lede" style="margin:16px 0 0">비용 가정: 법무등기 낙찰가 0.5%, 명도비 300만원, 수리비 전용면적×20만원, 중개보수 매도가 0.5%.
    대출이자·보유세·인수금액은 미반영이라 실제 수익률은 이보다 낮을 수 있습니다.</p>
  </div>
</section>

<section>
  <h2>판정에 쓴 법적 근거</h2>
  <p class="lede">아래 조문·판례는 auction-law 워크스페이스의 사전 검증된 지식베이스에서 가져왔으며,
  각 항목은 국가법령정보(law.go.kr) 원문 조회로 확인된 것입니다.</p>
  <div class="tw"><table class="law">
    <thead><tr><th>쟁점</th><th>근거</th><th>이 보고서에서의 적용</th></tr></thead>
    <tbody>
      <tr><td>말소기준권리</td><td class="src">민사집행법 §91② ③ ④<br>시행 2026.02.01</td>
        <td>“말소기준권리”는 법률 용어가 아닙니다. ②는 <b>모든 저당권이 순위와 무관하게 소멸</b>한다고 정하고,
        ③④는 용익권·등기임차권이 저당권·압류·가압류에 대항할 수 있는지로 소멸과 인수를 가릅니다.
        이번 8건의 최선순위는 근저당 5건·가압류 1건·경매개시결정 2건이었습니다.</td></tr>
      <tr><td>대항력 임차인 인수</td><td class="src">주택임대차보호법 §3의5 단서<br>대법원 99다9981</td>
        <td>대항력은 인도와 전입신고를 마친 <b>다음 날 0시</b>에 발생하고, 보증금이 전액 변제되지 않은 대항력 있는 임차권은
        경락으로 소멸하지 않습니다. 확약서 4건은 이 보호를 채권자가 <b>스스로 포기</b>한 경우입니다.</td></tr>
      <tr><td>지분매각</td><td class="src">민사집행법 §140<br>대법원 2023다217916</td>
        <td>공유자는 매각기일 종결 고지 전까지 최고가와 같은 값으로 <b>우선매수</b>할 수 있어 낙찰이 뒤집힐 수 있고,
        “싸게 받아 공유물분할로 전체를 경매에 부친다”는 기대는 판례가 부정합니다(대금분할은 예외적 방법).
        이번 8건에는 지분매각이 없었습니다.</td></tr>
      <tr><td>유치권</td><td class="src">민사집행법 §91⑤</td>
        <td>유치권은 순위 논리 밖의 인수 항목이라 권리분석이 완벽해도 별도 부담이 남습니다.
        8건 모두 유치권 신고는 확인되지 않았으나 등기부에 공시되지 않으므로 현장 확인이 필요합니다.</td></tr>
      <tr><td>인수금액과 명도는 별개</td><td class="src">auction-due-deligence 실무 원칙</td>
        <td>확약서로 인수금액이 0이 되어도 점유자가 자동으로 나가지는 않습니다. “권리는 깨끗한데 못 들어가는 물건”이
        가장 흔한 함정입니다. 8건 중 6건이 폐문부재로 점유가 미상이고, 전입세대 등재인이 없는 4건은 명도가 비교적 수월할 것으로 봅니다.</td></tr>
    </tbody>
  </table></div>
</section>

<section>
  <h2>환금성을 어떻게 쟀나</h2>
  <div class="card">
    <p style="margin:0 0 14px;max-width:80ch">apt-location-kit은 경매 물건에서 <b>입지 점수보다 환금성이 1차 지표</b>라고 규정합니다.
    같은 워크스페이스의 실측(은계 13개 단지, 스피어만 상관 −0.14)은 역세권 순위가 실제 손바뀜을 거의 설명하지 못한다는 것을 보여줍니다.
    그래서 이 보고서는 입지 점수를 매기는 대신 국토부 실거래로 <b>회전율 = 최근 12개월 거래건수 ÷ 세대수</b>를 직접 계산했습니다.</p>
    <div class="tw"><table>
      <thead><tr><th>단지</th><th class="r">세대수</th><th class="r">12개월 거래</th><th class="r">회전율</th><th>해석</th></tr></thead>
      <tbody>__TURNROWS__</tbody>
    </table></div>
    <p class="lede" style="margin:14px 0 0">회전율 5% 이상이면 연간 스무 채 중 한 채가 손바뀜한다는 뜻으로 낙찰 후 매도 대기가 짧습니다.
    3%대는 대형 평형이나 소규모 단지에서 나타나며, 할인폭이 커도 출구가 좁다는 신호입니다.
    할인폭 1·2위인 팜스프링 115㎡와 동광모닝스카이가 모두 회전율 하위권이라는 점은 우연이 아닙니다.</p>
  </div>
</section>

<section>
  <h2>입찰 전 반드시 확인할 것</h2>
  <div class="card">
    <ul class="fl2" style="font-size:13.5px;color:var(--fg)">
      <li><b>확약서 원문</b> — 4건의 인수 0원 판정은 전적으로 확약서에 의존합니다. 사건기록 열람으로 실물과 제출 주체를 확인하세요.</li>
      <li><b>전입세대열람원</b> — 세창리베하우스는 명세서와 현황조사가 어긋납니다. 전입일자를 확인하기 전에는 입찰하지 마세요.</li>
      <li><b>등기사항전부증명서</b> — 이 보고서는 등기부를 열람하지 않았습니다. 전체 근저당·가압류·가처분은 등기부로만 확정됩니다.</li>
      <li><b>관리비 체납</b> — 공용부분 체납액은 매수인이 인수합니다. 관리사무소에 직접 확인하세요.</li>
      <li><b>주택수 확정</b> — 세액은 취득 후 주택수에 따라 완전히 달라집니다. 분양권·입주권·오피스텔 포함 여부를 세무 상담으로 확정하세요.</li>
      <li><b>규제지역 재확인</b> — 지정은 수시로 바뀝니다. 잔금일 기준으로 국토교통부 고시를 다시 확인하세요.</li>
    </ul>
  </div>
</section>

<footer>
  <p><b>데이터 출처</b> · 법원경매정보(courtauction.go.kr) 2026.09.09 수집 및 매각물건명세서·현황조사서 직접 열람 ·
  국토교통부 아파트 매매 실거래가(RTMS) 최근 12~24개월 · 한국부동산원 공동주택 기본정보(K-apt) 세대수·준공연도 ·
  국가법령정보(law.go.kr) 조문·판례 원문 · 규제지역은 국토교통부 2025.10.15 대책과 2026.06.29 주거정책심의위원회 의결 기준.</p>
  <p><b>통합한 워크스페이스</b> · auction-crawl0629(수집·단지보강) · auction-due-deligence(실사 원칙·문서 교차검증) ·
  auction-law(조문·판례 지식베이스) · apt-location-kit(환금성 방법론) · auction-tax2(세금엔진).</p>
  <p><b>한계</b> · 등기부등본을 열람하지 않아 권리분석은 매각물건명세서·현황조사서 기준입니다(정밀 인수금액이 아닙니다).
  세액은 대표 가정값 기반 추정이며, 종합부동산세는 다른 보유주택 공시가격을 반영하지 않아 과소계산됐을 수 있습니다.
  다주택 양도세 중과의 시행 상태(유예·부활)는 양도 시점에 재확인이 필요합니다.
  실거래 표본이 10건 미만인 평형은 시세 신뢰구간이 넓고, 회전율은 동일 단지 전 평형 기준입니다.</p>
  <p><b>이 보고서는 투자 권유가 아니라 스크리닝 참고자료입니다.</b> 최종 판단 전 변호사·법무사·세무사 상담을 권합니다.</p>
</footer>
</div>
'''

SCRIPT = '''<script>
const PROPS = __PROPJS__;
const won = n => Math.round(n).toLocaleString('ko-KR');
const asEok = n => { const neg = n < 0; n = Math.abs(n);
  const k = Math.floor(n / 10000), m = Math.round(n % 10000);
  return (neg ? '−' : '') + (k > 0 ? (m ? k + '억 ' + won(m) + '만' : k + '억') : won(m) + '만'); };
let cur = 0, months = 30, houses = 1, regulated = 0;
const BR = [[1400,.06,0],[5000,.15,126],[8800,.24,576],[15000,.35,1544],
            [30000,.38,1994],[50000,.40,2594],[100000,.42,3594],[Infinity,.45,6594]];
function prog(b){ for (const x of BR) if (b <= x[0]) return Math.max(0, Math.round(b * x[1] - x[2])); return 0; }
function acqRate(price, h, reg){
  if (reg) { if (h >= 3) return .12; if (h === 2) return .08; }
  else     { if (h >= 4) return .12; if (h === 3) return .08; }
  if (price <= 60000) return .01;
  if (price >= 90000) return .03;
  return (price * 2 / 30000 - 3) / 100;
}
function calc(){
  const p = PROPS[cur];
  const bid = +document.getElementById('bid').dataset.v;
  const sell = +document.getElementById('sell').dataset.v;
  const ar = acqRate(bid, houses, regulated);
  const acq = Math.round(bid * ar * 1.1);
  const costs = Math.round(bid * 0.005) + 300 + Math.round(p.area * 20) + Math.round(sell * 0.005);
  const gain = sell - bid - acq - costs;
  const taxable = Math.max(0, gain - 250);
  let nat = 0, label = '양도차익 없음';
  if (taxable > 0) {
    if (months < 12) { nat = Math.round(taxable * .70); label = '1년 미만 단기양도 70% 중과'; }
    else if (months < 24) { nat = Math.round(taxable * .60); label = '2년 미만 단기양도 60% 중과'; }
    else {
      nat = prog(taxable); label = '기본세율 누진';
      if (regulated && houses >= 2) {
        const add = houses >= 3 ? .30 : .20;
        nat += Math.round(taxable * add);
        label += ' + 조정지역 ' + (houses >= 3 ? '3주택' : '2주택') + ' +' + (add * 100) + '%p 중과';
      }
    }
  }
  const capTax = nat + Math.round(nat * .1);
  const net = gain - capTax;
  const invest = bid + acq + costs;
  const roi = invest > 0 ? net / invest * 100 : 0;
  const cls = net >= 0 ? 'pos' : 'neg';
  document.getElementById('out').innerHTML =
    '<div class="o"><div class="ol">취득세 (' + (ar * 100).toFixed(1) + '% + 지방교육세)</div><div class="ov num">' + asEok(acq) + '</div></div>' +
    '<div class="o"><div class="ol">기타 비용</div><div class="ov num">' + asEok(costs) + '</div></div>' +
    '<div class="o"><div class="ol">양도차익</div><div class="ov num">' + asEok(gain) + '</div></div>' +
    '<div class="o"><div class="ol">양도세 + 지방소득세</div><div class="ov num">' + asEok(capTax) + '</div></div>' +
    '<div class="o"><div class="ol">세후 순익</div><div class="ov num ' + cls + '">' + asEok(net) + '</div></div>' +
    '<div class="o"><div class="ol">투자원금 대비</div><div class="ov num ' + cls + '">' + (net >= 0 ? '+' : '') + roi.toFixed(1) + '%</div></div>' +
    '<div class="o" style="grid-column:1/-1"><div class="ol">적용 양도세율</div><div class="ov" style="font-size:13px;font-family:var(--sans);font-weight:600;white-space:normal">' + label + '</div></div>';
}
function syncSliders(){
  const p = PROPS[cur];
  const bs = document.getElementById('bid'), ss = document.getElementById('sell');
  const bv = Math.round(p.low + (p.apr - p.low) * (bs.value / 100));
  bs.dataset.v = bv;
  document.getElementById('bidv').textContent = asEok(bv);
  document.getElementById('bidh').textContent =
    '최저 ' + asEok(p.low) + ' ~ 감정 ' + asEok(p.apr) + ' · 감정가의 ' + (bv / p.apr * 100).toFixed(1) + '%';
  const slo = Math.round(p.mkt * 0.8), shi = Math.round(p.mkt * 1.1);
  const sv = Math.round(slo + (shi - slo) * (ss.value / 100));
  ss.dataset.v = sv;
  document.getElementById('sellv').textContent = asEok(sv);
  document.getElementById('sellh').textContent =
    '실거래 중앙값 ' + asEok(p.mkt) + ' 대비 ' + (sv / p.mkt * 100).toFixed(0) + '%';
  calc();
}
function selectProp(i){
  cur = i;
  document.querySelectorAll('.prop').forEach((x, j) => x.classList.toggle('on', j === i));
  document.querySelectorAll('.pcard').forEach((x, j) => x.classList.toggle('on', j === i));
  document.getElementById('bid').value = 0;
  document.getElementById('sell').value = 67;
  syncSliders();
}
document.querySelectorAll('.prop').forEach((el, i) => el.addEventListener('click', () => selectProp(i)));
['bid', 'sell'].forEach(id => document.getElementById(id).addEventListener('input', syncSliders));
function seg(boxId, fn){
  document.querySelectorAll('#' + boxId + ' .seg').forEach(s => s.addEventListener('click', () => {
    document.querySelectorAll('#' + boxId + ' .seg').forEach(x => x.classList.remove('on'));
    s.classList.add('on'); fn(+s.dataset.v); calc();
  }));
}
seg('segMonths', v => months = v); seg('segHouses', v => houses = v); seg('segReg', v => regulated = v);
const root = document.documentElement;
document.getElementById('tt').addEventListener('click', () => {
  const c = root.getAttribute('data-theme') || (matchMedia('(prefers-color-scheme:dark)').matches ? 'dark' : 'light');
  root.setAttribute('data-theme', c === 'dark' ? 'light' : 'dark');
});
selectProp(0);
</script>
'''

def main():
    body = (BODY.replace('__KPI__', kpi_row())
                .replace('__TAXBARS__', BARS)
                .replace('__TAXROWS__', TRS)
                .replace('__FUNNEL__', funnel())
                .replace('__REGIONS__', region_bars())
                .replace('__TABS__', prop_tabs())
                .replace('__CARDS__', prop_cards())
                .replace('__TURNROWS__', turn_rows()))
    script = SCRIPT.replace('__PROPJS__', prop_js())
    out = HEAD + body + script
    dst = os.path.join(ROOT, '경기비규제_아파트경매_종합보고서.html')
    open(dst, 'w', encoding='utf-8').write(out)
    print('OK ->', dst)
    print(len(out), 'bytes /', len(PROPS), 'props')
    for tok in ('__KPI__', '__TAXBARS__', '__FUNNEL__', '__TABS__', '__CARDS__', '__PROPJS__', '{{'):
        if tok in out:
            print('  !! 미치환 토큰 남음:', tok)

if __name__ == '__main__':
    main()
