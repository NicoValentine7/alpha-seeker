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
            "oig": safe(row.get("operating_income_growth"), "pct"),
            "pb": safe(row.get("pb_ratio"), "ratio"),
            "eveb": safe(row.get("ev_ebitda"), "ratio"),
            "psr": safe(row.get("ps_ratio"), "ratio"),
            "fcfm": safe(row.get("fcf_margin"), "pct"),
            "tp": safe(row.get("target_mean_price"), "ratio"),
            "tpHigh": safe(row.get("target_high_price"), "ratio"),
            "tpLow": safe(row.get("target_low_price"), "ratio"),
            "numAnalysts": safe(row.get("num_analysts"), "int"),
            "recMean": safe(row.get("recommendation_mean"), "ratio"),
            "fwdg": safe(row.get("forward_eps_growth"), "pct"),
            "estRevG": safe(row.get("estimated_revenue_growth"), "pct"),
            "revAccel": safe(row.get("revenue_acceleration"), "pct"),
            "epsRev30d": safe(row.get("eps_revision_30d"), "pct"),
            "pioDetails": row.get("piotroski_details", ""),
            "mcap": safe(row.get("market_cap")),
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
thead th {{ position: relative; }}
.th-tip {{ display: none; position: absolute; top: calc(100% + 12px); left: 50%; transform: translateX(-50%); z-index: 100; background: #161b22; border: 1px solid #3d444d; border-radius: 12px; min-width: 340px; max-width: 400px; box-shadow: 0 16px 48px rgba(0,0,0,0.6); white-space: normal; text-transform: none; letter-spacing: normal; font-weight: 400; overflow: hidden; }}
.th-tip::before {{ content: ''; position: absolute; top: -6px; left: 50%; transform: translateX(-50%) rotate(45deg); width: 12px; height: 12px; background: #1f3a5f; border-left: 1px solid #3d444d; border-top: 1px solid #3d444d; }}
thead th:hover .th-tip {{ display: block; }}
.th-tip .tip-top {{ background: #1f3a5f; padding: 14px 20px; }}
.th-tip .tip-title {{ font-weight: 700; font-size: 14px; color: #f0f6fc; margin-bottom: 6px; }}
.th-tip .tip-simple {{ font-size: 13px; color: #a2d2fb; line-height: 1.7; }}
.th-tip .tip-bottom {{ padding: 14px 20px; }}
.th-tip .tip-detail {{ font-size: 12px; color: #8b949e; line-height: 1.8; }}
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
.modal-overlay {{ display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); z-index: 200; justify-content: center; align-items: flex-start; padding: 40px 20px; overflow-y: auto; }}
.modal-overlay.open {{ display: flex; }}
.modal {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; max-width: 700px; width: 100%; padding: 24px; position: relative; }}
.modal-close {{ position: absolute; top: 12px; right: 16px; background: none; border: none; color: #8b949e; font-size: 20px; cursor: pointer; }}
.modal-close:hover {{ color: #f0f6fc; }}
.modal h2 {{ font-size: 18px; color: #f0f6fc; margin-bottom: 4px; }}
.modal .modal-sub {{ color: #8b949e; font-size: 12px; margin-bottom: 16px; }}
.modal-section {{ margin-bottom: 16px; }}
.modal-section h3 {{ font-size: 13px; color: #58a6ff; margin-bottom: 8px; border-bottom: 1px solid #21262d; padding-bottom: 4px; }}
.modal-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px 16px; }}
.modal-item {{ display: flex; justify-content: space-between; padding: 3px 0; }}
.modal-item .label {{ color: #8b949e; font-size: 12px; }}
.modal-item .value {{ color: #c9d1d9; font-size: 12px; font-weight: 600; font-variant-numeric: tabular-nums; }}
.modal-scores {{ display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }}
.modal-score-card {{ background: #0d1117; border: 1px solid #21262d; border-radius: 6px; padding: 8px 12px; text-align: center; min-width: 80px; }}
.modal-score-card .sc-label {{ font-size: 10px; color: #8b949e; text-transform: uppercase; }}
.modal-score-card .sc-val {{ font-size: 20px; font-weight: 700; margin-top: 2px; }}
.modal-rationale {{ background: #0d1117; border: 1px solid #21262d; border-radius: 6px; padding: 12px; font-size: 12px; line-height: 1.6; color: #c9d1d9; }}
.modal-rationale li {{ margin-bottom: 4px; list-style: none; }}
.modal-rationale li::before {{ content: "\\25B6 "; color: #58a6ff; font-size: 8px; }}
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
  <th data-key="total" data-type="num">総合<span class="th-tip"><span class="tip-top"><span class="tip-title">総合スコア (0-100)</span><span class="tip-simple">この株がどれだけ「伸び代のある過小評価株」かを示す総合評価</span></span><span class="tip-bottom"><span class="tip-detail">割安度(25%) + 成長力(30%) + 質(20%) + 決算勢い(25%)の加重平均。セクター内の相対比較。70+は有望、60+は注目、45未満は割高。バリュートラップ銘柄は-20点のペナルティ。</span></span></th>
  <th data-key="val" data-type="num">割安度<span class="th-tip"><span class="tip-top"><span class="tip-title">割安度スコア (0-100)</span><span class="tip-simple">同じセクターの他社と比べて、この株がどれだけ安いか</span></span><span class="tip-bottom"><span class="tip-detail">PER(20%), PBR(15%), EV/EBITDA(20%), PSR(15%), FCF利回り(30%)をセクター内でパーセンタイルランク化。数値が高いほどセクター内で相対的に割安。FCF利回りの重みが最大（30年バックテストで最高リターンの実績）。</span></span></th>
  <th data-key="grw" data-type="num">成長力<span class="th-tip"><span class="tip-top"><span class="tip-title">成長力スコア (0-100)</span><span class="tip-simple">この会社がどれだけ速く成長しているか</span></span><span class="tip-bottom"><span class="tip-detail">売上成長率(30%), 営業利益成長率(25%), EPS成長率(30%), PEGレシオ(15%)で評価。PEGは「成長速度に対して株価が安いか」を測る指標（1.0未満が割安成長）。</span></span></th>
  <th data-key="qlt" data-type="num">質<span class="th-tip"><span class="tip-top"><span class="tip-title">質・健全性スコア (0-100)</span><span class="tip-simple">経営の質と財務の健全性を示す</span></span><span class="tip-bottom"><span class="tip-detail">ROE(30%), 粗利率(20%), D/Eレシオ(25%), FCFマージン(25%)で評価。ROEが高い＝株主資本を効率的に使っている。粗利率が高い＝競争優位性がある。D/Eが低い＝借金が少ない。FCFマージンが高い＝実際にキャッシュを生んでいる。</span></span></th>
  <th data-key="em" data-type="num">決算勢い<span class="th-tip"><span class="tip-top"><span class="tip-title">決算モメンタムスコア (0-100)</span><span class="tip-simple">決算発表で市場の予想を上回り続けているか</span></span><span class="tip-bottom"><span class="tip-detail">決算サプライズ率(25%), アナリストEPS予想の上方修正(25%), 売上成長の加速度(20%), 来期EPS成長予想(30%)で評価。アナリスト予想を連続で上回る銘柄は、まだ市場に正しく評価されていない可能性が高い。</span></span></th>
  <th data-key="fscore" data-type="num">F値<span class="th-tip"><span class="tip-top"><span class="tip-title">Piotroski F-Score (0-9)</span><span class="tip-simple">財務の健全さを9項目でチェックした点数</span></span><span class="tip-bottom"><span class="tip-detail">収益性(ROA, 営業CF, ROA改善, CF&gt;利益)で4点、レバレッジ(負債低下, 流動比率改善, 希薄化なし)で3点、効率(粗利率改善, 資産回転率改善)で2点。7+は優良、4-6は普通、0-3は懸念。F-Score 2以下はバリュートラップとしてペナルティ。</span></span></th>
  <th data-key="pe" data-type="num">PER<span class="th-tip"><span class="tip-top"><span class="tip-title">PER (株価収益率)</span><span class="tip-simple">株価が利益の何倍か。低いほど割安</span></span><span class="tip-bottom"><span class="tip-detail">株価 / 1株あたり利益(EPS)。15以下は割安、20-25は適正、30以上は割高が目安。ただしセクターによって水準が異なるため、同業他社との比較が重要。</span></span></th>
  <th data-key="fpe" data-type="num">予想PE<span class="th-tip"><span class="tip-top"><span class="tip-title">予想PER (Forward PE)</span><span class="tip-simple">来期の予想利益に対する株価の倍率</span></span><span class="tip-bottom"><span class="tip-detail">株価 / 来期予想EPS。現在のPERより低ければ、利益成長が期待されている証拠。PERとの差が大きいほど成長期待が高い。</span></span></th>
  <th data-key="peg" data-type="num">PEG<span class="th-tip"><span class="tip-top"><span class="tip-title">PEGレシオ</span><span class="tip-simple">成長速度に対して株価が安いか高いかを測る</span></span><span class="tip-bottom"><span class="tip-detail">PER / EPS成長率(%)。1.0以下なら成長に対して割安（GARP基準）、0.5以下は非常に割安。Peter Lynchが普及させた指標。ただし赤字企業や低成長企業には使えない。</span></span></th>
  <th data-key="fcfy" data-type="num">FCF利回<span class="th-tip"><span class="tip-top"><span class="tip-title">FCF利回り (%)</span><span class="tip-simple">企業が生み出す余剰キャッシュの利回り</span></span><span class="tip-bottom"><span class="tip-detail">フリーキャッシュフロー / 企業価値(EV)。PERより操作されにくく、30年バックテストで最高リターンを記録した指標。7%以上は魅力的、マイナスは要注意。</span></span></th>
  <th data-key="roe" data-type="num">ROE<span class="th-tip"><span class="tip-top"><span class="tip-title">ROE - 自己資本利益率 (%)</span><span class="tip-simple">株主のお金をどれだけ効率よく利益に変えているか</span></span><span class="tip-bottom"><span class="tip-detail">当期純利益 / 自己資本。15%以上は優秀、20%以上は非常に高い。ただし借入を増やしてもROEは上がるため、D/Eと合わせて評価する必要がある。</span></span></th>
  <th data-key="gm" data-type="num">粗利率<span class="th-tip"><span class="tip-top"><span class="tip-title">粗利率 (Gross Margin %)</span><span class="tip-simple">売上からモノの原価を引いた利益の割合</span></span><span class="tip-bottom"><span class="tip-detail">(売上 - 売上原価) / 売上。高いほど価格決定力や競争優位性がある。ソフトウェア企業は70-80%、製造業は30-40%が目安。Novy-Marx(2013)の研究でリターン予測力が確認された指標。</span></span></th>
  <th data-key="de" data-type="num">D/E<span class="th-tip"><span class="tip-top"><span class="tip-title">D/Eレシオ (負債/自己資本)</span><span class="tip-simple">借金の多さ。低いほど安全</span></span><span class="tip-bottom"><span class="tip-detail">有利子負債 / 自己資本(%)。100以下は健全、200以上は高め、500以上はバリュートラップのリスク。自社株買いで自己資本がマイナスの優良企業（HD, KO等）は異常に高くなることがある。</span></span></th>
  <th data-key="revg" data-type="num">売上成長<span class="th-tip"><span class="tip-top"><span class="tip-title">売上成長率 (前年比 %)</span><span class="tip-simple">売上がどれだけ伸びたか</span></span><span class="tip-bottom"><span class="tip-detail">年次の売上高の前年比成長率。10%以上は高成長、20%以上は急成長。長期的には売上成長がEPS成長の源泉になるため、最も重要な成長指標の一つ。</span></span></th>
  <th data-key="epsg" data-type="num">EPS成長<span class="th-tip"><span class="tip-top"><span class="tip-title">EPS成長率 (前年比 %)</span><span class="tip-simple">1株あたり利益がどれだけ伸びたか</span></span><span class="tip-bottom"><span class="tip-detail">純利益ベースのEPS前年比成長率。株価は長期的にEPS成長に連動する。自社株買いでもEPSは成長するため、売上成長と合わせて評価する。</span></span></th>
  <th data-key="surp" data-type="num">決算サプライズ<span class="th-tip"><span class="tip-top"><span class="tip-title">平均決算サプライズ率 (%)</span><span class="tip-simple">アナリスト予想を実績がどれだけ上回ったか</span></span><span class="tip-bottom"><span class="tip-detail">直近4四半期のEPSサプライズ率の平均。プラスが連続する銘柄は「アナリストがまだ追いついていない」＝過小評価のサイン。PEAD（決算後ドリフト）効果が実証されている。</span></span></th>
  <th data-key="epsrev" data-type="num">EPS修正<span class="th-tip"><span class="tip-top"><span class="tip-title">EPS予想修正率 (90日間 %)</span><span class="tip-simple">アナリストが90日間でEPS予想をどれだけ引き上げたか</span></span><span class="tip-bottom"><span class="tip-detail">90日前のEPS予想と現在の予想の変化率。上方修正が続く銘柄は株価が上昇しやすい。Zacksの研究で予測力が最も高いファクターの一つと確認されている。</span></span></th>
  <th data-key="price" data-type="num">株価</th>
  <th data-key="upside" data-type="num">上昇余地<span class="th-tip"><span class="tip-top"><span class="tip-title">上昇余地 (%)</span><span class="tip-simple">アナリストの目標株価まであとどれだけ上がる余地があるか</span></span><span class="tip-bottom"><span class="tip-detail">(アナリスト目標株価の平均 - 現在株価) / 現在株価。20%以上は十分な上昇余地。ただしアナリスト予想は楽観的な傾向がある点に注意。</span></span></th>
  <th data-key="rec" data-type="str">推奨<span class="th-tip"><span class="tip-top"><span class="tip-title">アナリスト推奨</span><span class="tip-simple">ウォール街のアナリストの総合評価</span></span><span class="tip-bottom"><span class="tip-detail">buy(買い), strong_buy(強い買い), hold(保持), sell(売り)。複数アナリストの評価のコンセンサス。</span></span></th>
  <th data-key="beat" data-type="str">ビート<span class="th-tip"><span class="tip-top"><span class="tip-title">決算ビート率</span><span class="tip-simple">直近4四半期で何回アナリスト予想を上回ったか</span></span><span class="tip-bottom"><span class="tip-detail">例: 4/4 = 4四半期連続でEPS予想を上回った。3/4以上は強い。連続ビートは市場がまだこの会社の実力を正しく評価していない可能性を示す。</span></span></th>
</tr></thead>
<tbody id="tbody"></tbody>
</table>
</div>
<div class="modal-overlay" id="modal">
  <div class="modal">
    <button class="modal-close" id="modalClose">&times;</button>
    <div id="modalContent"></div>
  </div>
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

    // Ticker (clickable)
    var td1 = createCell('td', 'ticker');
    var tickerLink = document.createElement('a');
    tickerLink.textContent = r.ticker;
    tickerLink.href = '#';
    tickerLink.style.cssText = 'color: #58a6ff; text-decoration: none; cursor: pointer;';
    tickerLink.addEventListener('click', (function(row) {{ return function(e) {{ e.preventDefault(); showDetail(row); }}; }})(r));
    td1.appendChild(tickerLink);
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

// Modal logic
var modal = document.getElementById('modal');
document.getElementById('modalClose').addEventListener('click', function() {{ modal.classList.remove('open'); }});
modal.addEventListener('click', function(e) {{ if (e.target === modal) modal.classList.remove('open'); }});

function sv(v, suffix, prefix) {{
  if (v == null) return '-';
  return (prefix || '') + (v > 0 && !prefix ? '+' : '') + v.toFixed(1) + (suffix || '');
}}

function showDetail(r) {{
  var mc = document.getElementById('modalContent');
  while (mc.firstChild) mc.removeChild(mc.firstChild);

  // Title
  var h2 = document.createElement('h2');
  h2.textContent = r.ticker + '  ' + r.name;
  mc.appendChild(h2);
  var sub = document.createElement('div');
  sub.className = 'modal-sub';
  sub.textContent = r.sector + (r.trap ? '  [バリュートラップ: ' + r.trapReason + ']' : '');
  mc.appendChild(sub);

  // Score cards
  var cards = document.createElement('div');
  cards.className = 'modal-scores';
  var scoreData = [
    ['総合', r.total], ['割安度', r.val], ['成長力', r.grw], ['質', r.qlt], ['決算勢い', r.em]
  ];
  scoreData.forEach(function(s) {{
    var card = document.createElement('div');
    card.className = 'modal-score-card';
    var lbl = document.createElement('div');
    lbl.className = 'sc-label';
    lbl.textContent = s[0];
    card.appendChild(lbl);
    var val = document.createElement('div');
    val.className = 'sc-val';
    val.style.color = s[1] != null ? (s[1] >= 65 ? '#3fb950' : s[1] >= 40 ? '#d29922' : '#f85149') : '#484f58';
    val.textContent = s[1] != null ? s[1].toFixed(1) : '-';
    card.appendChild(val);
    cards.appendChild(card);
  }});
  mc.appendChild(cards);

  // Sections
  function addSection(title, items) {{
    var sec = document.createElement('div');
    sec.className = 'modal-section';
    var h3 = document.createElement('h3');
    h3.textContent = title;
    sec.appendChild(h3);
    var grid = document.createElement('div');
    grid.className = 'modal-grid';
    items.forEach(function(item) {{
      var div = document.createElement('div');
      div.className = 'modal-item';
      var lbl = document.createElement('span');
      lbl.className = 'label';
      lbl.textContent = item[0];
      div.appendChild(lbl);
      var val = document.createElement('span');
      val.className = 'value';
      val.textContent = item[1];
      if (typeof item[1] === 'string' && item[1].indexOf('+') === 0) val.style.color = '#3fb950';
      if (typeof item[1] === 'string' && item[1].indexOf('-') === 0) val.style.color = '#f85149';
      div.appendChild(val);
      grid.appendChild(div);
    }});
    sec.appendChild(grid);
    mc.appendChild(sec);
  }}

  addSection('バリュエーション', [
    ['PER', r.pe != null ? r.pe.toFixed(1) : '-'],
    ['予想PER', r.fpe != null ? r.fpe.toFixed(1) : '-'],
    ['PBR', r.pb != null ? r.pb.toFixed(2) : '-'],
    ['EV/EBITDA', r.eveb != null ? r.eveb.toFixed(1) : '-'],
    ['PSR', r.psr != null ? r.psr.toFixed(2) : '-'],
    ['FCF利回り', sv(r.fcfy, '%')],
    ['PEG', r.peg != null ? r.peg.toFixed(2) : '-'],
  ]);

  addSection('成長', [
    ['売上成長率', sv(r.revg, '%')],
    ['営業利益成長率', sv(r.oig, '%')],
    ['EPS成長率', sv(r.epsg, '%')],
    ['来期EPS成長予想', sv(r.fwdg, '%')],
    ['今期売上成長予想', sv(r.estRevG, '%')],
    ['売上加速度', sv(r.revAccel, '%')],
  ]);

  addSection('質・健全性', [
    ['ROE', sv(r.roe, '%')],
    ['粗利率', sv(r.gm, '%')],
    ['FCFマージン', sv(r.fcfm, '%')],
    ['D/Eレシオ', r.de != null ? r.de.toFixed(0) + '%' : '-'],
    ['F-Score', r.fscore != null ? r.fscore + '/9' : '-'],
    ['F-Score詳細', r.pioDetails || '-'],
  ]);

  addSection('決算モメンタム', [
    ['決算サプライズ平均', sv(r.surp, '%')],
    ['EPS修正(90日)', sv(r.epsrev, '%')],
    ['EPS修正(30日)', sv(r.epsRev30d, '%')],
    ['決算ビート', r.beat != null ? r.beat + '/' + r.beatTotal + '四半期' : '-'],
    ['次回決算日', r.nextEd || '-'],
  ]);

  addSection('アナリスト評価', [
    ['現在株価', r.price != null ? '$' + r.price.toFixed(2) : '-'],
    ['TP平均', r.tp != null ? '$' + r.tp.toFixed(0) : '-'],
    ['TP範囲', (r.tpLow != null ? '$' + r.tpLow.toFixed(0) : '?') + ' ~ ' + (r.tpHigh != null ? '$' + r.tpHigh.toFixed(0) : '?')],
    ['上昇余地', sv(r.upside, '%')],
    ['推奨', r.rec || '-'],
    ['アナリスト数', r.numAnalysts != null ? r.numAnalysts + '名' : '-'],
    ['時価総額', r.mcap != null ? '$' + (r.mcap / 1e9).toFixed(0) + 'B' : '-'],
  ]);

  // Rationale
  var rationale = document.createElement('div');
  rationale.className = 'modal-section';
  var rh3 = document.createElement('h3');
  rh3.textContent = 'スコア根拠';
  rationale.appendChild(rh3);
  var rDiv = document.createElement('div');
  rDiv.className = 'modal-rationale';
  var ul = document.createElement('ul');
  var reasons = [];
  if (r.total != null) {{
    if (r.total >= 70) reasons.push('総合スコアが高く、過小評価の可能性が高い');
    else if (r.total >= 60) reasons.push('総合スコアが平均以上で注目に値する');
    else if (r.total < 45) reasons.push('総合スコアが低く、現時点では割高');
  }}
  if (r.val != null && r.val >= 70) reasons.push('セクター内で相対的に割安な水準');
  if (r.grw != null && r.grw >= 70) reasons.push('高い成長率を示している');
  if (r.qlt != null && r.qlt >= 70) reasons.push('ROE・財務健全性が高く質が良い');
  if (r.em != null && r.em >= 70) reasons.push('決算モメンタムが強い（アナリスト予想を連続で上回っている）');
  if (r.beat != null && r.beatTotal != null && r.beat === r.beatTotal && r.beat >= 3) reasons.push('直近' + r.beat + '四半期連続で決算ビート');
  if (r.fscore != null && r.fscore >= 7) reasons.push('F-Score ' + r.fscore + '/9 で財務状態が優良');
  if (r.fscore != null && r.fscore <= 2) reasons.push('[警告] F-Score ' + r.fscore + '/9 で財務状態に懸念');
  if (r.fcfy != null && r.fcfy > 8) reasons.push('FCF利回りが高い（' + r.fcfy.toFixed(1) + '%）');
  if (r.peg != null && r.peg < 1.0) reasons.push('PEG ' + r.peg.toFixed(2) + ' で成長に対して割安');
  if (r.upside != null && r.upside > 20) reasons.push('TP上昇余地が' + r.upside.toFixed(0) + '%');
  if (r.trap) reasons.push('[警告] バリュートラップの可能性: ' + r.trapReason);
  if (reasons.length === 0) reasons.push('データ不足のため根拠を生成できません');
  reasons.forEach(function(reason) {{
    var li = document.createElement('li');
    li.textContent = reason;
    ul.appendChild(li);
  }});
  rDiv.appendChild(ul);
  rationale.appendChild(rDiv);
  mc.appendChild(rationale);

  modal.classList.add('open');
}}

// Initial render
applyFilters();
</script>
</body>
</html>"""
