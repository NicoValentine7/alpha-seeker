"""4カテゴリのスコアリングロジック

各指標をセクター内パーセンタイルランク(0-100)に変換し、
重み付き平均でカテゴリスコア→総合スコアを算出する。
"""

import numpy as np
import pandas as pd

from stock_ranking.config import (
    CATEGORY_WEIGHTS,
    CLIP_LOWER_PERCENTILE,
    CLIP_UPPER_PERCENTILE,
    EARNINGS_MOMENTUM_WEIGHTS,
    GROWTH_WEIGHTS,
    PRICE_MOMENTUM_WEIGHTS,
    QUALITY_WEIGHTS,
    VALUE_TRAP_FILTERS,
    VALUATION_WEIGHTS,
)

CORE_SCORE_CAP = 59.9
SEVERE_CORE_SCORE_CAP = 49.9
BUY_SIGNAL_CAP = 54.9

CATEGORY_MIN_COVERAGE = {
    "valuation": 3,
    "growth": 2,
    "quality": 3,
    "earnings_momentum": 2,
}

CORE_COVERAGE_CATEGORIES = ("valuation", "growth", "quality")
REQUIRED_COVERAGE_CATEGORIES = ("valuation", "growth", "quality", "earnings_momentum")


def _nan_series(index: pd.Index) -> pd.Series:
    """指定indexのNaN Seriesを返す。"""
    return pd.Series(np.nan, index=index)


def _get_series(df: pd.DataFrame, col: str) -> pd.Series:
    """存在しない列はNaN Seriesとして扱う。"""
    if col in df.columns:
        return df[col]
    return _nan_series(df.index)


def _build_growth_inputs(df: pd.DataFrame) -> pd.DataFrame:
    """成長スコア用の実効入力を構築する。"""
    growth_df = pd.DataFrame(index=df.index)
    growth_df["revenue_growth"] = _get_series(df, "revenue_growth_calc").combine_first(
        _get_series(df, "revenue_growth")
    )
    growth_df["eps_growth"] = _get_series(df, "eps_growth").combine_first(
        _get_series(df, "earnings_growth")
    )
    growth_df["peg_ratio"] = _get_series(df, "peg_ratio")
    return growth_df


def _calculate_coverage(df: pd.DataFrame) -> pd.DataFrame:
    """カテゴリごとのデータカバレッジ件数を計算する。"""
    growth_df = _build_growth_inputs(df)
    coverage = pd.DataFrame(index=df.index)

    coverage["valuation_coverage"] = pd.DataFrame(
        {
            "pe_ratio": _get_series(df, "pe_ratio"),
            "pb_ratio": _get_series(df, "pb_ratio"),
            "ev_ebitda": _get_series(df, "ev_ebitda"),
            "ps_ratio": _get_series(df, "ps_ratio"),
            "fcf_yield": _get_series(df, "fcf_yield"),
        }
    ).notna().sum(axis=1)

    coverage["growth_coverage"] = growth_df.notna().sum(axis=1)

    coverage["quality_coverage"] = pd.DataFrame(
        {
            "roe": _get_series(df, "roe"),
            "gross_margin": _get_series(df, "gross_margin"),
            "debt_to_equity": _get_series(df, "debt_to_equity"),
            "fcf_margin": _get_series(df, "fcf_margin"),
        }
    ).notna().sum(axis=1)

    coverage["earnings_momentum_coverage"] = pd.DataFrame(
        {
            "avg_surprise_pct": _get_series(df, "avg_surprise_pct"),
            "eps_revision_90d": _get_series(df, "eps_revision_90d"),
            "revenue_acceleration": _get_series(df, "revenue_acceleration"),
            "forward_eps_growth": _get_series(df, "forward_eps_growth"),
        }
    ).notna().sum(axis=1)

    return coverage


def _category_ok_mask(df: pd.DataFrame, category: str) -> pd.Series:
    """カテゴリの最低カバレッジ閾値を満たすかを返す。"""
    col = f"{category}_coverage"
    min_count = CATEGORY_MIN_COVERAGE[category]
    return df[col] >= min_count


def _build_core_data_warning(df: pd.DataFrame, coverage_ok: pd.DataFrame) -> pd.Series:
    """不足しているカテゴリ名をCSV向け文字列で返す。"""
    return coverage_ok.apply(
        lambda row: ",".join(
            category for category in REQUIRED_COVERAGE_CATEGORIES if not bool(row[category])
        ),
        axis=1,
    )


def _percentile_rank_in_sector(series: pd.Series, sector_groups: pd.api.typing.DataFrameGroupBy,
                                col_name: str, lower_is_better: bool = False) -> pd.Series:
    """セクター内でパーセンタイルランク(0-100)を計算する。

    Args:
        series: 対象の指標値
        sector_groups: セクターでグループ化したDataFrame
        col_name: カラム名（グループ化用）
        lower_is_better: True の場合、値が低いほど高スコア（PER, D/E等）
    """
    result = pd.Series(np.nan, index=series.index)

    for _sector, group_idx in sector_groups.groups.items():
        vals = series.loc[group_idx].dropna()
        if len(vals) < 3:  # セクター内銘柄が少なすぎる場合はスキップ
            continue

        # 外れ値クリッピング
        lower = np.percentile(vals, CLIP_LOWER_PERCENTILE)
        upper = np.percentile(vals, CLIP_UPPER_PERCENTILE)
        clipped = vals.clip(lower, upper)

        # パーセンタイルランク
        ranks = clipped.rank(pct=True) * 100

        if lower_is_better:
            ranks = 100 - ranks

        result.loc[ranks.index] = ranks

    return result


def score_valuation(df: pd.DataFrame, sector_groups) -> pd.Series:
    """バリュエーション割安度スコア (0-100)

    PER, PBR, EV/EBITDA, PSR が低いほど高スコア（セクター内相対）
    """
    scores = {}
    mapping = {
        "pe_ratio": ("pe_ratio", True),
        "pb_ratio": ("pb_ratio", True),
        "ev_ebitda": ("ev_ebitda", True),
        "ps_ratio": ("ps_ratio", True),
        "fcf_yield": ("fcf_yield", False),  # FCF利回りは高いほど良い
    }

    for key, (col, lower_is_better) in mapping.items():
        if col in df.columns:
            scores[key] = _percentile_rank_in_sector(df[col], sector_groups, col, lower_is_better)

    return _weighted_average(scores, VALUATION_WEIGHTS, df.index)


def score_growth(df: pd.DataFrame, sector_groups) -> pd.Series:
    """成長力スコア (0-100)

    成長率が高いほど高スコア。
    yfinance の info と財務諸表計算値を併用（計算値を優先）。
    """
    growth_df = _build_growth_inputs(df)

    scores = {}
    mapping = {
        "revenue_growth": "revenue_growth",
        "eps_growth": "eps_growth",
    }

    for key, col in mapping.items():
        if col in growth_df.columns:
            scores[key] = _percentile_rank_in_sector(growth_df[col], sector_groups, col, lower_is_better=False)

    if "peg_ratio" in growth_df.columns:
        scores["peg_ratio"] = _percentile_rank_in_sector(
            growth_df["peg_ratio"], sector_groups, "peg_ratio", lower_is_better=True
        )

    return _weighted_average(scores, GROWTH_WEIGHTS, df.index)


def score_quality(df: pd.DataFrame, sector_groups) -> pd.Series:
    """質・健全性スコア (0-100)"""
    scores = {}

    if "roe" in df.columns:
        scores["roe"] = _percentile_rank_in_sector(df["roe"], sector_groups, "roe", lower_is_better=False)

    if "gross_margin" in df.columns:
        scores["gross_margin"] = _percentile_rank_in_sector(
            df["gross_margin"], sector_groups, "gross_margin", lower_is_better=False
        )

    if "debt_to_equity" in df.columns:
        scores["debt_to_equity"] = _percentile_rank_in_sector(
            df["debt_to_equity"], sector_groups, "debt_to_equity", lower_is_better=True
        )

    if "fcf_margin" in df.columns:
        scores["fcf_margin"] = _percentile_rank_in_sector(
            df["fcf_margin"], sector_groups, "fcf_margin", lower_is_better=False
        )

    return _weighted_average(scores, QUALITY_WEIGHTS, df.index)


def score_earnings_momentum(df: pd.DataFrame, sector_groups) -> pd.Series:
    """決算モメンタムスコア (0-100)

    決算サプライズ率、EPS予想の上方修正、売上加速度、来期成長予想を評価。
    """
    scores = {}

    if "avg_surprise_pct" in df.columns:
        scores["avg_surprise"] = _percentile_rank_in_sector(
            df["avg_surprise_pct"], sector_groups, "avg_surprise_pct", lower_is_better=False
        )

    if "eps_revision_90d" in df.columns:
        scores["eps_revision_90d"] = _percentile_rank_in_sector(
            df["eps_revision_90d"], sector_groups, "eps_revision_90d", lower_is_better=False
        )

    if "revenue_acceleration" in df.columns:
        scores["revenue_acceleration"] = _percentile_rank_in_sector(
            df["revenue_acceleration"], sector_groups, "revenue_acceleration", lower_is_better=False
        )

    if "forward_eps_growth" in df.columns:
        scores["forward_eps_growth"] = _percentile_rank_in_sector(
            df["forward_eps_growth"], sector_groups, "forward_eps_growth", lower_is_better=False
        )

    return _weighted_average(scores, EARNINGS_MOMENTUM_WEIGHTS, df.index)


def score_price_momentum(df: pd.DataFrame, sector_groups) -> pd.Series:
    """価格モメンタムスコア (0-100)

    12-1ヶ月モメンタム（Jegadeesh & Titman 1993）をセクター内ランク化。
    直近1ヶ月を除外することで短期リバーサル効果を排除。
    """
    scores = {}

    if "momentum_12_1m" in df.columns:
        scores["momentum_12_1m"] = _percentile_rank_in_sector(
            df["momentum_12_1m"], sector_groups, "momentum_12_1m", lower_is_better=False
        )

    return _weighted_average(scores, PRICE_MOMENTUM_WEIGHTS, df.index)


def _weighted_average(scores: dict[str, pd.Series], weights: dict[str, float], index: pd.Index) -> pd.Series:
    """利用可能な指標のみで重み付き平均を計算する（欠損指標は除外して正規化）"""
    result = pd.Series(0.0, index=index)
    total_weight = pd.Series(0.0, index=index)

    for key, weight in weights.items():
        if key in scores:
            s = scores[key]
            mask = s.notna()
            result[mask] += s[mask] * weight
            total_weight[mask] += weight

    # 重みの正規化（利用可能な指標が少ない場合に対応）
    valid = total_weight > 0
    result[valid] /= total_weight[valid]
    result[~valid] = np.nan

    return result


def _detect_value_traps(df: pd.DataFrame) -> pd.Series:
    """バリュートラップを検出する。Trueの銘柄はペナルティを受ける。"""
    is_trap = pd.Series(False, index=df.index)
    reasons = pd.Series("", index=df.index)

    # 四半期売上が連続減少している銘柄を検出
    max_decline = VALUE_TRAP_FILTERS["max_consecutive_revenue_decline"]
    if "quarterly_results" in df.columns:
        for idx, row in df.iterrows():
            qr = row.get("quarterly_results")
            if not qr or not isinstance(qr, list) or len(qr) < max_decline:
                continue
            revenues = [q.get("total_revenue") for q in qr[:max_decline] if q.get("total_revenue")]
            if len(revenues) >= max_decline:
                # 新しい順なので、すべて前の四半期より小さければ連続減少
                all_declining = all(revenues[i] < revenues[i + 1] for i in range(len(revenues) - 1))
                if all_declining:
                    is_trap.loc[idx] = True
                    reasons.loc[idx] += f"売上{max_decline}Q連続減少; "

    # D/E比率が極端に高い
    max_de = VALUE_TRAP_FILTERS["max_debt_to_equity"]
    if "debt_to_equity" in df.columns:
        extreme_debt = df["debt_to_equity"].notna() & (df["debt_to_equity"] > max_de)
        is_trap[extreme_debt] = True
        reasons[extreme_debt] += f"D/E>{max_de}%; "

    # Piotroski F-Score が極端に低い（0-2）
    if "piotroski_fscore" in df.columns:
        low_fscore = df["piotroski_fscore"].notna() & (df["piotroski_fscore"] <= 2)
        is_trap[low_fscore] = True
        reasons[low_fscore] += "F-Score≤2(財務状態悪化); "

    return is_trap, reasons


def calculate_total_score(df: pd.DataFrame) -> pd.DataFrame:
    """全銘柄の総合スコアを計算する。

    Returns:
        元のDFに valuation_score, growth_score, quality_score, total_score を追加したもの
    """
    sector_groups = df.groupby("sector")

    df = df.copy()
    df["valuation_score"] = score_valuation(df, sector_groups)
    df["growth_score"] = score_growth(df, sector_groups)
    df["quality_score"] = score_quality(df, sector_groups)
    df["earnings_momentum_score"] = score_earnings_momentum(df, sector_groups)
    df["price_momentum_score"] = score_price_momentum(df, sector_groups)

    coverage = _calculate_coverage(df)
    for col in coverage.columns:
        df[col] = coverage[col]

    coverage_ok = pd.DataFrame(index=df.index)
    for category in REQUIRED_COVERAGE_CATEGORIES:
        coverage_ok[category] = _category_ok_mask(df, category)

    df["core_data_warning"] = _build_core_data_warning(df, coverage_ok)
    df["is_data_complete"] = coverage_ok[list(REQUIRED_COVERAGE_CATEGORIES)].all(axis=1)
    core_fail_count = (~coverage_ok[list(CORE_COVERAGE_CATEGORIES)]).sum(axis=1)

    # バリュートラップ検出
    is_trap, trap_reasons = _detect_value_traps(df)
    df["is_value_trap"] = is_trap
    df["value_trap_reason"] = trap_reasons

    # 総合スコア（利用可能なカテゴリのみで計算）
    score_cols = {
        "valuation": "valuation_score",
        "growth": "growth_score",
        "quality": "quality_score",
        "earnings_momentum": "earnings_momentum_score",
        "price_momentum": "price_momentum_score",
    }

    df["total_score"] = 0.0
    total_weight = pd.Series(0.0, index=df.index)
    for cat_key, col in score_cols.items():
        weight = CATEGORY_WEIGHTS[cat_key]
        mask = df[col].notna()
        df.loc[mask, "total_score"] += df.loc[mask, col] * weight
        total_weight[mask] += weight

    valid = total_weight > 0
    df.loc[valid, "total_score"] /= total_weight[valid]
    df.loc[~valid, "total_score"] = np.nan

    severe_cap_mask = core_fail_count >= 2
    core_cap_mask = core_fail_count >= 1
    df.loc[core_cap_mask, "total_score"] = df.loc[core_cap_mask, "total_score"].clip(upper=CORE_SCORE_CAP)
    df.loc[severe_cap_mask, "total_score"] = df.loc[severe_cap_mask, "total_score"].clip(upper=SEVERE_CORE_SCORE_CAP)

    # バリュートラップはスコアにペナルティ（-20点）
    df.loc[is_trap, "total_score"] = df.loc[is_trap, "total_score"] - 20

    # Buy Signal Score（総合力 + 市場評価 + 決算実績 + 財務健全性）
    df["_core_category_fail_count"] = core_fail_count
    df["buy_signal"] = _calculate_buy_signal(df)
    df = df.drop(columns=["_core_category_fail_count"])

    return df


def _calculate_buy_signal(df: pd.DataFrame) -> pd.Series:
    """Buy Signal Score (0-100) を計算する。

    学術レビュー(2026-03-30)に基づく再構成:
    - total_score(50%): メインシグナルを主軸化
    - F-Score(20%): 財務健全性の独立チェック（total_scoreに含まれない）
    - upside_potential(15%): アナリスト楽観バイアスを考慮して減額
    - price_momentum(15%): 12-1ヶ月モメンタム（独立したアルファ源）

    旧式から除外:
    - beat_rate: avg_surprise_pctとtotal_score内で二重カウント
    - analyst_rating: 楽観バイアスが大きい（Barber et al. 2001）
    """
    if "total_score" not in df.columns:
        return pd.Series(np.nan, index=df.index)

    total_component = df["total_score"].clip(0, 100)
    fscore_component = (_get_series(df, "piotroski_fscore") / 9 * 100).fillna(0).clip(0, 100)
    upside = _get_series(df, "upside_potential").clip(-0.5, 1.0)
    upside_component = ((upside + 0.5) / 1.5 * 100).fillna(0).clip(0, 100)
    momentum_component = _get_series(df, "price_momentum_score").clip(0, 100).fillna(0)

    result = (
        total_component * 0.50
        + fscore_component * 0.20
        + upside_component * 0.15
        + momentum_component * 0.15
    )

    result[total_component.isna()] = np.nan

    fail_count = None
    for col in ("core_category_fail_count", "_core_category_fail_count"):
        if col in df.columns:
            fail_count = df[col]
            break
    if fail_count is not None:
        fail_mask = fail_count > 0
        result.loc[fail_mask] = result.loc[fail_mask].clip(upper=BUY_SIGNAL_CAP)

    return result
