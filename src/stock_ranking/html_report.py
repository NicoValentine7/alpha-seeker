"""S&P500ランキングのインタラクティブHTMLビューアを生成する"""

import json
import math
from pathlib import Path

import pandas as pd


def generate_html(df: pd.DataFrame, output_path: str | Path) -> Path:
    """ランキングDataFrameからインタラクティブHTMLを生成する。

    Args:
        df: calculate_total_scoreで計算済みのDataFrame（rankインデックス付き）
        output_path: 出力先HTMLファイルパス

    Returns:
        出力ファイルのPath
    """
    output_path = Path(output_path)

    # JSON用データ準備
    rows = []
    for idx, row in df.iterrows():
        def safe(val, fmt=None):
            if val is None or (isinstance(val, float) and math.isnan(val)):
                return None
            if fmt == "pct":
                return round(val * 100, 1)
            if fmt == "score":
                return round(val, 1)
            if fmt == "ratio":
                return round(val, 2)
            if fmt == "int":
                return int(val)
            return val

        rows.append({
            "rank": int(idx),
            "ticker": row.get("ticker", ""),
            "name": row.get("name", ""),
            "sector": row.get("sector", ""),
            "total": safe(row.get("total_score"), "score"),
            "val": safe(row.get("valuation_score"), "score"),
            "grw": safe(row.get("growth_score"), "score"),
            "qlt": safe(row.get("quality_score"), "score"),
            "em": safe(row.get("earnings_momentum_score"), "score"),
            "fscore": safe(row.get("piotroski_fscore"), "int"),
            "pe": safe(row.get("pe_ratio"), "ratio"),
            "fpe": safe(row.get("forward_pe"), "ratio"),
            "pb": safe(row.get("pb_ratio"), "ratio"),
            "eveb": safe(row.get("ev_ebitda"), "ratio"),
            "psr": safe(row.get("ps_ratio"), "ratio"),
            "fcfy": safe(row.get("fcf_yield"), "pct"),
            "peg": safe(row.get("peg_ratio"), "ratio"),
            "roe": safe(row.get("roe"), "pct"),
            "gm": safe(row.get("gross_margin"), "pct"),
            "de": safe(row.get("debt_to_equity"), "ratio"),
            "fcfm": safe(row.get("fcf_margin"), "pct"),
            "revg": safe(row.get("revenue_growth_calc", row.get("revenue_growth")), "pct"),
            "epsg": safe(row.get("eps_growth"), "pct"),
            "surp": safe(row.get("avg_surprise_pct"), "ratio"),
            "epsrev": safe(row.get("eps_revision_90d"), "pct"),
            "fwdg": safe(row.get("forward_eps_growth"), "pct"),
            "price": safe(row.get("current_price"), "ratio"),
            "tp": safe(row.get("target_mean_price"), "ratio"),
            "upside": safe(row.get("upside_potential"), "pct"),
            "rec": row.get("recommendation_key", ""),
            "trap": bool(row.get("is_value_trap", False)),
            "trapReason": row.get("value_trap_reason", ""),
            "beat": safe(row.get("earnings_beat_count"), "int"),
            "beatTotal": safe(row.get("earnings_beat_total"), "int"),
            "nextEd": str(row.get("next_earnings_date", "")) if pd.notna(row.get("next_earnings_date")) else "",
        })

    # セクター一覧
    sectors = sorted(df["sector"].dropna().unique().tolist())

    data_json = json.dumps(rows, ensure_ascii=False)
    sectors_json = json.dumps(sectors, ensure_ascii=False)

    html = _build_html(data_json, sectors_json, len(rows))
    output_path.write_text(html, encoding="utf-8")
    return output_path


def _escape(text: str) -> str:
    """HTML特殊文字をエスケープする"""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _build_html(data_json: str, sectors_json: str, total_count: int) -> str:
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Alpha Seeker - S&amp;P500 Ranking</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0e17; color: #c9d1d9; font-size: 13px; }}
.header {{ background: linear-gradient(135deg, #0d1117 0%, #161b22 100%); border-bottom: 1px solid #21262d; padding: 16px 24px; }}
.header h1 {{ font-size: 20px; font-weight: 600; color: #f0f6fc; }}
.header .subtitle {{ color: #8b949e; font-size: 12px; margin-top: 4px; }}
.controls {{ background: #0d1117; border-bottom: 1px solid #21262d; padding: 12px 24px; display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }}
.control-group {{ display: flex; align-items: center; gap: 6px; }}
.control-group label {{ color: #8b949e; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap; }}
input[type="text"], select {{ background: #161b22; border: 1px solid #30363d; color: #c9d1d9; padding: 6px 10px; border-radius: 4px; font-size: 13px; }}
input[type="text"] {{ width: 200px; }}
select {{ cursor: pointer; }}
input[type="text"]:focus, select:focus {{ outline: none; border-color: #58a6ff; }}
.stats {{ color: #8b949e; font-size: 12px; margin-left: auto; white-space: nowrap; }}
.table-wrap {{ overflow-x: auto; padding: 0 24px 24px; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
thead th {{ position: sticky; top: 0; background: #161b22; border-bottom: 2px solid #30363d; padding: 8px 6px; text-align: left; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: #8b949e; cursor: pointer; user-select: none; white-space: nowrap; }}
thead th:hover {{ color: #58a6ff; }}
thead th.sorted-asc::after {{ content: " \\25B2"; color: #58a6ff; }}
thead th.sorted-desc::after {{ content: " \\25BC"; color: #58a6ff; }}
tbody tr {{ border-bottom: 1px solid #21262d; transition: background 0.1s; }}
tbody tr:hover {{ background: #161b22; }}
tbody tr.trap {{ opacity: 0.5; }}
td {{ padding: 7px 6px; white-space: nowrap; }}
td.ticker {{ font-weight: 700; color: #58a6ff; }}
td.name {{ color: #8b949e; max-width: 180px; overflow: hidden; text-overflow: ellipsis; }}
td.sector {{ font-size: 11px; }}
.score {{ display: inline-block; min-width: 36px; text-align: right; padding: 2px 6px; border-radius: 3px; font-weight: 600; font-variant-numeric: tabular-nums; }}
.score.total {{ font-size: 14px; }}
.s-high {{ background: #0d3321; color: #3fb950; }}
.s-mid {{ background: #2a1f00; color: #d29922; }}
.s-low {{ background: #3d1214; color: #f85149; }}
.s-na {{ color: #484f58; }}
.val {{ text-align: right; font-variant-numeric: tabular-nums; }}
.pos {{ color: #3fb950; }}
.neg {{ color: #f85149; }}
.na {{ color: #484f58; }}
.badge {{ display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 10px; font-weight: 600; }}
.badge-buy {{ background: #0d3321; color: #3fb950; }}
.badge-hold {{ background: #2a1f00; color: #d29922; }}
.badge-sell {{ background: #3d1214; color: #f85149; }}
.badge-trap {{ background: #3d1214; color: #f85149; }}
.fscore {{ font-weight: 700; }}
.fs-high {{ color: #3fb950; }}
.fs-mid {{ color: #d29922; }}
.fs-low {{ color: #f85149; }}
.beat {{ font-size: 11px; }}
.eval-tag {{ display: inline-block; padding: 1px 5px; border-radius: 3px; font-size: 10px; font-weight: 600; margin-left: 4px; vertical-align: middle; }}
.eval-excellent {{ background: #0d3321; color: #3fb950; }}
.eval-good {{ background: #143620; color: #56d364; }}
.eval-fair {{ background: #2a1f00; color: #d29922; }}
.eval-poor {{ background: #3d1214; color: #f85149; }}
@media (max-width: 768px) {{
  .controls {{ flex-direction: column; align-items: stretch; }}
  .stats {{ margin-left: 0; }}
  input[type="text"] {{ width: 100%; }}
}}
</style>
</head>
<body>
<div class="header">
  <h1>Alpha Seeker</h1>
  <div class="subtitle">S&amp;P500 過小評価グロース株ランキング &mdash; {total_count}銘柄をスコアリング</div>
</div>
<div class="controls">
  <div class="control-group">
    <label>検索</label>
    <input type="text" id="search" placeholder="ティッカー / 銘柄名...">
  </div>
  <div class="control-group">
    <label>セクター</label>
    <select id="sectorFilter"><option value="">すべて</option></select>
  </div>
  <div class="control-group">
    <label>スコア</label>
    <select id="scoreFilter">
      <option value="">すべて</option>
      <option value="70">70+ (有望)</option>
      <option value="60">60+ (注目)</option>
      <option value="50">50+ (平均以上)</option>
    </select>
  </div>
  <div class="control-group">
    <label>財務健全性</label>
    <select id="fscoreFilter">
      <option value="">すべて</option>
      <option value="7">F7+ (優良)</option>
      <option value="5">F5+ (普通)</option>
      <option value="0-3">F0-3 (懸念)</option>
    </select>
  </div>
  <div class="control-group">
    <label>罠フィルター</label>
    <select id="trapFilter">
      <option value="">すべて</option>
      <option value="no">バリュートラップ除外</option>
      <option value="only">バリュートラップのみ</option>
    </select>
  </div>
  <div class="stats" id="stats"></div>
</div>
<div class="table-wrap">
<table>
<thead><tr>
  <th data-key="rank" data-type="num">#</th>
  <th data-key="ticker" data-type="str">銘柄</th>
  <th data-key="name" data-type="str">企業名</th>
  <th data-key="sector" data-type="str">セクター</th>
  <th data-key="total" data-type="num">総合</th>
  <th data-key="val" data-type="num">割安度</th>
  <th data-key="grw" data-type="num">成長力</th>
  <th data-key="qlt" data-type="num">質</th>
  <th data-key="em" data-type="num">決算勢い</th>
  <th data-key="fscore" data-type="num">F値</th>
  <th data-key="pe" data-type="num">PER</th>
  <th data-key="fpe" data-type="num">予想PE</th>
  <th data-key="peg" data-type="num">PEG</th>
  <th data-key="fcfy" data-type="num">FCF利回</th>
  <th data-key="roe" data-type="num">ROE</th>
  <th data-key="gm" data-type="num">粗利率</th>
  <th data-key="de" data-type="num">D/E</th>
  <th data-key="revg" data-type="num">売上成長</th>
  <th data-key="epsg" data-type="num">EPS成長</th>
  <th data-key="surp" data-type="num">決算サプライズ</th>
  <th data-key="epsrev" data-type="num">EPS修正</th>
  <th data-key="price" data-type="num">株価</th>
  <th data-key="upside" data-type="num">上昇余地</th>
  <th data-key="rec" data-type="str">推奨</th>
  <th data-key="beat" data-type="str">ビート</th>
</tr></thead>
<tbody id="tbody"></tbody>
</table>
</div>
<script>
const DATA = {data_json};
const SECTORS = {sectors_json};
const TOTAL = {total_count};

// Populate sector filter
const sf = document.getElementById('sectorFilter');
SECTORS.forEach(function(s) {{
  var o = document.createElement('option');
  o.value = s;
  o.textContent = s;
  sf.appendChild(o);
}});

var sortKey = 'rank', sortDir = 1;

function escapeHtml(str) {{
  var div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}}

function scoreClass(v) {{
  if (v == null) return 's-na';
  if (v >= 65) return 's-high';
  if (v >= 40) return 's-mid';
  return 's-low';
}}

function createScoreEl(v, isTotal) {{
  var span = document.createElement('span');
  span.className = 'score ' + scoreClass(v) + (isTotal ? ' total' : '');
  span.textContent = v != null ? v.toFixed(1) : '-';
  if (isTotal && v != null) {{
    var tag = document.createElement('span');
    tag.className = 'eval-tag ';
    if (v >= 70) {{ tag.className += 'eval-excellent'; tag.textContent = '有望'; }}
    else if (v >= 60) {{ tag.className += 'eval-good'; tag.textContent = '注目'; }}
    else if (v >= 45) {{ tag.className += 'eval-fair'; tag.textContent = '普通'; }}
    else {{ tag.className += 'eval-poor'; tag.textContent = '割高'; }}
    var frag = document.createDocumentFragment();
    frag.appendChild(span);
    frag.appendChild(tag);
    return frag;
  }}
  return span;
}}

function createValEl(v, suffix) {{
  var span = document.createElement('span');
  span.className = 'val' + (v != null ? (v > 0 ? ' pos' : v < 0 ? ' neg' : '') : ' na');
  if (v != null) {{
    span.textContent = (v > 0 ? '+' : '') + v.toFixed(1) + (suffix || '');
  }} else {{
    span.textContent = '-';
  }}
  return span;
}}

function createFscoreEl(v) {{
  var span = document.createElement('span');
  if (v == null) {{
    span.className = 'val na';
    span.textContent = '-';
  }} else {{
    span.className = 'fscore ' + (v >= 7 ? 'fs-high' : v >= 4 ? 'fs-mid' : 'fs-low');
    span.textContent = v;
  }}
  return span;
}}

function createRecEl(v) {{
  if (!v) return document.createTextNode('');
  var span = document.createElement('span');
  var cls = {{ strong_buy: 'buy', buy: 'buy', hold: 'hold', sell: 'sell', strong_sell: 'sell' }};
  span.className = 'badge badge-' + (cls[v] || 'hold');
  span.textContent = v.replace('_', ' ');
  return span;
}}

function createCell(tag, className) {{
  var td = document.createElement(tag || 'td');
  if (className) td.className = className;
  return td;
}}

function render(data) {{
  var tbody = document.getElementById('tbody');
  // Clear safely
  while (tbody.firstChild) tbody.removeChild(tbody.firstChild);

  var frag = document.createDocumentFragment();
  data.forEach(function(r) {{
    var tr = document.createElement('tr');
    if (r.trap) tr.className = 'trap';

    // #
    var td0 = createCell('td');
    td0.textContent = r.rank;
    tr.appendChild(td0);

    // Ticker
    var td1 = createCell('td', 'ticker');
    td1.textContent = r.ticker;
    if (r.trap) {{
      var vt = document.createElement('span');
      vt.className = 'badge badge-trap';
      vt.textContent = 'VT';
      vt.title = r.trapReason || '';
      td1.appendChild(document.createTextNode(' '));
      td1.appendChild(vt);
    }}
    tr.appendChild(td1);

    // Name
    var td2 = createCell('td', 'name');
    td2.textContent = r.name;
    td2.title = r.name;
    tr.appendChild(td2);

    // Sector
    var td3 = createCell('td', 'sector');
    td3.textContent = r.sector;
    tr.appendChild(td3);

    // Scores
    var scores = [
      [r.total, true], [r.val, false], [r.grw, false], [r.qlt, false], [r.em, false]
    ];
    scores.forEach(function(s) {{
      var td = createCell('td');
      td.appendChild(createScoreEl(s[0], s[1]));
      tr.appendChild(td);
    }});

    // F-Score
    var tdf = createCell('td');
    tdf.appendChild(createFscoreEl(r.fscore));
    tr.appendChild(tdf);

    // PER, Fwd PE, PEG
    [r.pe, r.fpe, r.peg].forEach(function(v) {{
      var td = createCell('td', 'val');
      td.textContent = v != null ? v.toFixed(v === r.peg ? 2 : 1) : '-';
      tr.appendChild(td);
    }});

    // FCF%, ROE, GM%
    [r.fcfy, r.roe, r.gm].forEach(function(v) {{
      var td = createCell('td');
      td.appendChild(createValEl(v, '%'));
      tr.appendChild(td);
    }});

    // D/E
    var tde = createCell('td', 'val');
    tde.textContent = r.de != null ? r.de.toFixed(0) : '-';
    tr.appendChild(tde);

    // Rev G, EPS G
    [r.revg, r.epsg].forEach(function(v) {{
      var td = createCell('td');
      td.appendChild(createValEl(v, '%'));
      tr.appendChild(td);
    }});

    // Surp%, EPS Rev
    [r.surp, r.epsrev].forEach(function(v) {{
      var td = createCell('td');
      td.appendChild(createValEl(v, '%'));
      tr.appendChild(td);
    }});

    // Price
    var tdp = createCell('td', 'val');
    tdp.textContent = r.price != null ? '$' + r.price.toFixed(0) : '-';
    tr.appendChild(tdp);

    // Upside
    var tdu = createCell('td');
    tdu.appendChild(createValEl(r.upside, '%'));
    tr.appendChild(tdu);

    // Rec
    var tdr = createCell('td');
    tdr.appendChild(createRecEl(r.rec));
    tr.appendChild(tdr);

    // Beat
    var tdb = createCell('td');
    if (r.beat != null && r.beatTotal != null) {{
      var bs = document.createElement('span');
      bs.className = 'beat';
      bs.textContent = r.beat + '/' + r.beatTotal;
      tdb.appendChild(bs);
    }} else {{
      tdb.className = 'val na';
      tdb.textContent = '-';
    }}
    tr.appendChild(tdb);

    frag.appendChild(tr);
  }});
  tbody.appendChild(frag);
  document.getElementById('stats').textContent = data.length + ' / ' + TOTAL + ' 銘柄';
}}

function applyFilters() {{
  var q = document.getElementById('search').value.toLowerCase();
  var sec = document.getElementById('sectorFilter').value;
  var minScore = document.getElementById('scoreFilter').value;
  var fscoreF = document.getElementById('fscoreFilter').value;
  var trapF = document.getElementById('trapFilter').value;

  var filtered = DATA.filter(function(r) {{
    if (q && r.ticker.toLowerCase().indexOf(q) === -1 && (r.name||'').toLowerCase().indexOf(q) === -1) return false;
    if (sec && r.sector !== sec) return false;
    if (minScore && (r.total == null || r.total < +minScore)) return false;
    if (fscoreF === '0-3' && (r.fscore == null || r.fscore > 3)) return false;
    if (fscoreF && fscoreF !== '0-3' && (r.fscore == null || r.fscore < +fscoreF)) return false;
    if (trapF === 'no' && r.trap) return false;
    if (trapF === 'only' && !r.trap) return false;
    return true;
  }});

  filtered.sort(function(a, b) {{
    var va = a[sortKey], vb = b[sortKey];
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    if (typeof va === 'string') return va.localeCompare(vb) * sortDir;
    return (va - vb) * sortDir;
  }});

  render(filtered);
}}

// Sort headers
document.querySelectorAll('thead th').forEach(function(th) {{
  th.addEventListener('click', function() {{
    var key = th.dataset.key;
    if (sortKey === key) {{ sortDir *= -1; }}
    else {{ sortKey = key; sortDir = th.dataset.type === 'num' ? -1 : 1; }}
    document.querySelectorAll('thead th').forEach(function(t) {{
      t.classList.remove('sorted-asc', 'sorted-desc');
    }});
    th.classList.add(sortDir === 1 ? 'sorted-asc' : 'sorted-desc');
    applyFilters();
  }});
}});

// Filter events
['search', 'sectorFilter', 'scoreFilter', 'fscoreFilter', 'trapFilter'].forEach(function(id) {{
  document.getElementById(id).addEventListener(id === 'search' ? 'input' : 'change', applyFilters);
}});

// Initial render
applyFilters();
</script>
</body>
</html>"""
