"""スコアの根拠説明を生成するモジュール

定量スコアの内訳 + アナリスト評価 + ニュース をまとめて
銘柄ごとの「なぜこのスコアなのか」レポートを生成する。
"""

import pandas as pd

CATEGORY_LABELS = {
    "valuation": "割安度",
    "growth": "成長力",
    "quality": "質・健全性",
    "earnings_momentum": "決算モメンタム",
}

CATEGORY_COVERAGE_COLUMNS = {
    "valuation": "valuation_coverage",
    "growth": "growth_coverage",
    "quality": "quality_coverage",
    "earnings_momentum": "earnings_momentum_coverage",
}

CATEGORY_MIN_COVERAGE = {
    "valuation": 3,
    "growth": 2,
    "quality": 3,
    "earnings_momentum": 2,
}


def generate_report(
    df: pd.DataFrame, top_n: int = 30, portfolio_df: pd.DataFrame | None = None
) -> str:
    """上位N銘柄の詳細レポートを生成する"""
    lines = []
    lines.append("=" * 100)
    lines.append(f"  過小評価株ランキング 詳細レポート TOP {top_n}")
    lines.append("=" * 100)

    for rank, (_, row) in enumerate(df.head(top_n).iterrows(), 1):
        lines.append("")
        lines.append(f"{'─' * 100}")
        lines.append(f"  #{rank}  {row['ticker']}  {row.get('name', '')}  [{row.get('sector', '')}]")
        lines.append(f"{'─' * 100}")

        # 総合スコア
        total = _fmt_score(row.get("total_score"))
        val = _fmt_score(row.get("valuation_score"))
        grw = _fmt_score(row.get("growth_score"))
        qlt = _fmt_score(row.get("quality_score"))
        em = _fmt_score(row.get("earnings_momentum_score"))
        pm = _fmt_score(row.get("price_momentum_score"))
        lines.append(f"  総合: {total}   割安度: {val}   成長力: {grw}   質: {qlt}   決算モメンタム: {em}   価格モメンタム: {pm}")
        lines.append("")

        data_warning = _data_quality_warning(row)
        if data_warning:
            lines.append(data_warning)
            lines.append("")

        # 定量指標の内訳
        lines.append("  【定量指標】")
        lines.append(_quantitative_breakdown(row))
        lines.append("")

        # 決算情報
        lines.append("  【決算情報】")
        lines.append(_earnings_section(row))
        lines.append("")

        # アナリスト評価
        lines.append("  【アナリスト評価】")
        lines.append(_analyst_section(row))
        lines.append("")

        # 直近アナリストアクション
        actions = row.get("analyst_actions")
        if actions and isinstance(actions, list) and len(actions) > 0:
            lines.append("  【直近アナリストアクション】")
            for a in actions:
                target_str = ""
                if a.get("target_price"):
                    target_str = f"  TP: ${a['target_price']:.0f}"
                    if a.get("prior_target"):
                        target_str += f" (前回: ${a['prior_target']:.0f})"
                lines.append(f"    {a['date']}  {a['firm']}: {a['from_grade']}→{a['to_grade']} ({a['action']}){target_str}")
            lines.append("")

        # ニュース
        news = row.get("news")
        if news and isinstance(news, list) and len(news) > 0:
            lines.append("  【直近ニュース】")
            for n in news:
                lines.append(f"    {n['date']}  {n['title']}")
                if n.get("publisher"):
                    lines.append(f"             {n['publisher']}")
                if n.get("url"):
                    lines.append(f"             {n['url']}")
            lines.append("")

        # スコア根拠サマリー
        lines.append("  【スコア根拠サマリー】")
        lines.append(_score_rationale(row))
        lines.append("")

    lines.append("=" * 100)

    # ポートフォリオセクション（--portfolio指定時）
    if portfolio_df is not None and not portfolio_df.empty:
        lines.append("")
        lines.append(generate_portfolio_section(portfolio_df))

    return "\n".join(lines)


def generate_portfolio_section(portfolio_df: pd.DataFrame) -> str:
    """保有銘柄のスコアと損益をまとめたセクションを生成する"""
    lines = []
    lines.append("=" * 100)
    lines.append("  保有ポートフォリオ vs スコアリング")
    lines.append("=" * 100)
    lines.append("")

    if portfolio_df.empty:
        lines.append("  保有銘柄データが取得できませんでした")
        return "\n".join(lines)

    total_market_val = (
        portfolio_df["market_val"].sum()
        if "market_val" in portfolio_df.columns
        else None
    )

    for _, row in portfolio_df.iterrows():
        ticker = row["ticker"]
        name = row.get("name", row.get("name_moomoo", ""))
        sector = row.get("sector", "")
        total = _fmt_score(row.get("total_score"))
        rank = (
            int(row["rank_in_sp500"])
            if "rank_in_sp500" in row.index and pd.notna(row.get("rank_in_sp500"))
            else None
        )
        rank_str = f"S&P500ランク: #{rank}" if rank else "ランク: スコアなし"

        # 損益
        pl = row.get("unrealized_pl")
        pl_pct = row.get("unrealized_pl_pct")
        pl_str = ""
        if pl is not None and pd.notna(pl):
            pl_str = f"  含み損益: ${pl:+,.0f}"
            if pl_pct is not None and pd.notna(pl_pct):
                pl_str += f" ({pl_pct:+.2f}%)"

        # ウェイト
        mval = row.get("market_val")
        weight_str = ""
        if mval and total_market_val and total_market_val > 0:
            weight_str = f"  ウェイト: {mval / total_market_val:.1%}"

        lines.append(f"  {ticker}  {name}  [{sector}]")
        lines.append(
            f"    総合スコア: {total}  {rank_str}{pl_str}{weight_str}"
        )

        # バリュートラップ警告
        if row.get("is_value_trap"):
            trap_reason = row.get("value_trap_reason", "")
            lines.append(
                f"    [警告] バリュートラップの可能性: {trap_reason.rstrip('; ')}"
            )

        lines.append("")

    lines.append("=" * 100)
    return "\n".join(lines)


def _fmt_score(val) -> str:
    if pd.isna(val):
        return "N/A"
    return f"{val:.1f}"


def _fmt_pct(val) -> str:
    if val is None or pd.isna(val):
        return "N/A"
    return f"{val * 100:+.1f}%"


def _fmt_ratio(val) -> str:
    if val is None or pd.isna(val):
        return "N/A"
    return f"{val:.2f}"


def _quantitative_breakdown(row: pd.Series) -> str:
    """定量指標の内訳テーブルを生成"""
    lines = []

    # バリュエーション
    lines.append("    [バリュエーション]")
    fcf_y = row.get("fcf_yield")
    fcf_y_str = _fmt_pct(fcf_y) if fcf_y and pd.notna(fcf_y) else "N/A"
    peg = row.get("peg_ratio")
    peg_str = _fmt_ratio(peg) if peg and pd.notna(peg) else "N/A"
    lines.append(f"      PER: {_fmt_ratio(row.get('pe_ratio'))}  "
                 f"(Forward: {_fmt_ratio(row.get('forward_pe'))})  "
                 f"PBR: {_fmt_ratio(row.get('pb_ratio'))}  "
                 f"EV/EBITDA: {_fmt_ratio(row.get('ev_ebitda'))}  "
                 f"PSR: {_fmt_ratio(row.get('ps_ratio'))}")
    lines.append(f"      FCF利回り: {fcf_y_str}  PEG: {peg_str}")

    # 成長
    lines.append("    [成長]")
    rev_g = row.get("revenue_growth_calc", row.get("revenue_growth"))
    lines.append(f"      売上成長: {_fmt_pct(rev_g)}  "
                 f"営業利益成長: {_fmt_pct(row.get('operating_income_growth'))}  "
                 f"EPS成長: {_fmt_pct(row.get('eps_growth'))}")

    # 質
    lines.append("    [質・健全性]")
    roe_val = row.get("roe")
    roe_str = _fmt_pct(roe_val) if roe_val and abs(roe_val) < 10 else _fmt_ratio(roe_val)
    gm = row.get("gross_margin")
    gm_str = _fmt_pct(gm) if gm and pd.notna(gm) else "N/A"
    lines.append(f"      ROE: {roe_str}  "
                 f"粗利率: {gm_str}  "
                 f"D/E: {_fmt_ratio(row.get('debt_to_equity'))}  "
                 f"FCFマージン: {_fmt_pct(row.get('fcf_margin'))}")

    return "\n".join(lines)


def _earnings_section(row: pd.Series) -> str:
    """決算情報セクション"""
    lines = []

    # 次回決算日
    next_date = row.get("next_earnings_date")
    if next_date and isinstance(next_date, str) and next_date != "nan":
        lines.append(f"    次回決算日: {next_date}")

    # 決算サプライズ履歴
    surprises = row.get("earnings_surprises")
    if surprises and isinstance(surprises, list) and len(surprises) > 0:
        beat_count = row.get("earnings_beat_count", 0)
        beat_total = row.get("earnings_beat_total", 0)
        avg_surprise = row.get("avg_surprise_pct")
        avg_str = f"{avg_surprise:+.2f}%" if avg_surprise and pd.notna(avg_surprise) else "N/A"
        lines.append(f"    直近{beat_total}四半期: {beat_count}回ビート  平均サプライズ: {avg_str}")

        for s in surprises:
            est = f"${s['eps_estimate']:.2f}" if s.get("eps_estimate") and pd.notna(s["eps_estimate"]) else "N/A"
            act = f"${s['eps_actual']:.2f}" if s.get("eps_actual") and pd.notna(s["eps_actual"]) else "N/A"
            surp = f"{s['surprise_pct']:+.2f}%" if s.get("surprise_pct") and pd.notna(s["surprise_pct"]) else ""
            lines.append(f"      {s['date']}  予想EPS: {est}  実績: {act}  サプライズ: {surp}")

    # EPS予想の修正トレンド
    rev_90d = row.get("eps_revision_90d")
    rev_30d = row.get("eps_revision_30d")
    if rev_90d and pd.notna(rev_90d):
        rev_30d_str = _fmt_pct(rev_30d) if rev_30d and pd.notna(rev_30d) else "N/A"
        lines.append(f"    EPS予想修正: 90日間 {_fmt_pct(rev_90d)}  30日間 {rev_30d_str}")

    # 来期成長予想
    fwd_eps_g = row.get("forward_eps_growth")
    est_rev_g = row.get("estimated_revenue_growth")
    parts = []
    if fwd_eps_g and pd.notna(fwd_eps_g):
        parts.append(f"来期EPS成長予想: {_fmt_pct(fwd_eps_g)}")
    if est_rev_g and pd.notna(est_rev_g):
        parts.append(f"今期売上成長予想: {_fmt_pct(est_rev_g)}")
    if parts:
        lines.append(f"    {'  '.join(parts)}")

    # 売上加速度
    accel = row.get("revenue_acceleration")
    if accel and pd.notna(accel):
        direction = "加速" if accel > 0 else "減速"
        lines.append(f"    売上成長{direction}中 (QoQ変化: {_fmt_pct(accel)})")

    # 四半期売上推移
    quarters = row.get("quarterly_results")
    if quarters and isinstance(quarters, list) and len(quarters) > 0:
        lines.append("    四半期売上推移:")
        for q in quarters:
            rev = q.get("total_revenue")
            oi = q.get("operating_income")
            rev_str = f"${rev/1e9:.1f}B" if rev else "N/A"
            oi_str = f"${oi/1e9:.1f}B" if oi else "N/A"
            lines.append(f"      {q['quarter']}  売上: {rev_str}  営業利益: {oi_str}")

    if not lines:
        lines.append("    決算データなし")

    return "\n".join(lines)


def _analyst_section(row: pd.Series) -> str:
    """アナリスト評価セクション"""
    lines = []
    rating = row.get("analyst_rating", "N/A")
    num = row.get("num_analysts")
    num_str = f"{int(num)}名" if num and pd.notna(num) else "N/A"
    lines.append(f"    コンセンサス: {rating}  (アナリスト数: {num_str})")

    # ターゲット価格
    current = row.get("current_price")
    target_mean = row.get("target_mean_price")
    target_high = row.get("target_high_price")
    target_low = row.get("target_low_price")
    upside = row.get("upside_potential")

    if target_mean and current:
        lines.append(f"    現在価格: ${current:.2f}  "
                     f"ターゲット平均: ${target_mean:.2f}  "
                     f"(${target_low:.0f}〜${target_high:.0f})  "
                     f"上昇余地: {_fmt_pct(upside)}")

    # アップグレード/ダウングレード比
    up = row.get("recent_upgrades")
    down = row.get("recent_downgrades")
    if up is not None and down is not None and pd.notna(up) and pd.notna(down):
        lines.append(f"    直近アクション: アップグレード {int(up)}件 / ダウングレード {int(down)}件")

    return "\n".join(lines)


def _category_has_enough_coverage(row: pd.Series, category: str) -> bool:
    """カテゴリのデータカバレッジ閾値を満たすか判定する。"""
    col = CATEGORY_COVERAGE_COLUMNS.get(category)
    min_count = CATEGORY_MIN_COVERAGE.get(category)
    if col is None or min_count is None or col not in row.index:
        return True

    coverage = row.get(col)
    if coverage is None or pd.isna(coverage):
        return False
    return int(coverage) >= min_count


def _data_quality_warning(row: pd.Series) -> str:
    """データ不足時の警告文を返す。"""
    warning = row.get("core_data_warning")
    if warning is None or pd.isna(warning) or warning == "":
        return ""

    categories = [c.strip() for c in str(warning).split(",") if c.strip()]
    if not categories:
        return ""

    parts = []
    for category in categories:
        label = CATEGORY_LABELS.get(category, category)
        coverage_col = CATEGORY_COVERAGE_COLUMNS.get(category)
        coverage = row.get(coverage_col) if coverage_col else None
        min_count = CATEGORY_MIN_COVERAGE.get(category)
        if coverage is not None and pd.notna(coverage) and min_count is not None:
            parts.append(f"{label}({int(coverage)}/{min_count}+件)")
        else:
            parts.append(label)

    return "  [警告] データ品質: " + "、".join(parts) + " のカバレッジ不足により一部スコアを制限"


def _score_rationale(row: pd.Series) -> str:
    """スコアの根拠を自然言語でサマリーする"""
    reasons = []

    # 割安度の根拠
    val_score = row.get("valuation_score")
    if not _category_has_enough_coverage(row, "valuation"):
        reasons.append("割安度はデータ不足で判定保留")
    elif pd.notna(val_score):
        if val_score >= 70:
            reasons.append("セクター内で割安な水準にある")
        elif val_score >= 40:
            reasons.append("バリュエーションはセクター平均並み")
        else:
            reasons.append("バリュエーションはセクター内で割高")

    # 成長力の根拠
    grw_score = row.get("growth_score")
    if not _category_has_enough_coverage(row, "growth"):
        reasons.append("成長力はデータ不足で判定保留")
    elif pd.notna(grw_score):
        if grw_score >= 70:
            reasons.append("高い成長率を示している")
        elif grw_score >= 40:
            reasons.append("成長率はセクター平均並み")
        else:
            reasons.append("成長率はセクター内で低い")

    # 質の根拠
    qlt_score = row.get("quality_score")
    if not _category_has_enough_coverage(row, "quality"):
        reasons.append("質・健全性はデータ不足で判定保留")
    elif pd.notna(qlt_score):
        if qlt_score >= 70:
            reasons.append("ROE・財務健全性が高く質が良い")
        elif qlt_score >= 40:
            reasons.append("質・健全性はセクター平均並み")
        else:
            reasons.append("質・健全性に懸念あり")

    # 決算モメンタムの根拠
    em_score = row.get("earnings_momentum_score")
    if not _category_has_enough_coverage(row, "earnings_momentum"):
        reasons.append("決算モメンタムはデータ不足で判定保留")
    elif pd.notna(em_score):
        if em_score >= 70:
            reasons.append("決算モメンタムが強い（サプライズ・上方修正・成長加速）")
        elif em_score >= 40:
            reasons.append("決算モメンタムはセクター平均並み")
        else:
            reasons.append("決算モメンタムが弱い")

    beat_count = row.get("earnings_beat_count")
    beat_total = row.get("earnings_beat_total")
    if beat_count and beat_total and pd.notna(beat_count) and pd.notna(beat_total):
        if beat_count == beat_total and beat_total >= 3:
            reasons.append(f"直近{int(beat_total)}四半期連続で決算ビート")
        elif beat_count >= beat_total * 0.75:
            reasons.append(f"直近{int(beat_total)}四半期中{int(beat_count)}回決算ビート")

    # Piotroski F-Score
    fscore = row.get("piotroski_fscore")
    if fscore and pd.notna(fscore):
        fscore = int(fscore)
        details = row.get("piotroski_details", "")
        if fscore >= 7:
            reasons.append(f"Piotroski F-Score {fscore}/9 — 財務状態が優良（{details}）")
        elif fscore >= 4:
            reasons.append(f"Piotroski F-Score {fscore}/9 — 財務状態は普通")
        else:
            reasons.append(f"[警告] Piotroski F-Score {fscore}/9 — 財務状態に懸念")

    # バリュートラップ警告
    is_trap = row.get("is_value_trap")
    trap_reason = row.get("value_trap_reason")
    if is_trap and trap_reason:
        reasons.append(f"[警告] バリュートラップの可能性: {trap_reason.rstrip('; ')}")

    # FCF利回り
    fcf_y = row.get("fcf_yield")
    if fcf_y and pd.notna(fcf_y):
        if fcf_y > 0.08:
            reasons.append(f"FCF利回りが高い（{fcf_y*100:.1f}%）— キャッシュ創出力が強い")
        elif fcf_y < 0:
            reasons.append("FCF利回りがマイナス — キャッシュ燃焼中")

    # PEG
    peg = row.get("peg_ratio")
    if peg and pd.notna(peg):
        if peg < 0.5:
            reasons.append(f"PEG {peg:.2f} — 成長に対して非常に割安")
        elif peg < 1.0:
            reasons.append(f"PEG {peg:.2f} — 成長に対して割安（GARP基準クリア）")
        elif peg > 2.0:
            reasons.append(f"PEG {peg:.2f} — 成長に対して割高")

    # アナリスト評価
    rec_mean = row.get("recommendation_mean")
    if rec_mean and pd.notna(rec_mean):
        if rec_mean <= 2.0:
            reasons.append(f"アナリストは強気（レーティング: {rec_mean:.1f}/5）")
        elif rec_mean <= 3.0:
            reasons.append(f"アナリストは中立〜やや強気（レーティング: {rec_mean:.1f}/5）")
        else:
            reasons.append(f"アナリストは弱気寄り（レーティング: {rec_mean:.1f}/5）")

    # 上昇余地
    upside = row.get("upside_potential")
    if upside and pd.notna(upside):
        if upside > 0.20:
            reasons.append(f"ターゲット価格まで{upside*100:.0f}%の上昇余地")
        elif upside > 0.05:
            reasons.append(f"ターゲット価格まで{upside*100:.0f}%の上昇余地")
        elif upside < -0.05:
            reasons.append(f"現在価格はターゲットを{abs(upside)*100:.0f}%上回っている")

    if not reasons:
        return "    データ不足のため根拠を生成できません"

    return "    " + "。\n    ".join(reasons) + "。"
