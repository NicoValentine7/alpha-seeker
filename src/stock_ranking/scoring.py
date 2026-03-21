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
    QUALITY_WEIGHTS,
    VALUE_TRAP_FILTERS,
    VALUATION_WEIGHTS,
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
    # 成長指標: 計算値があればそちらを優先
    growth_df = pd.DataFrame(index=df.index)

    # 売上成長率
    if "revenue_growth_calc" in df.columns:
        growth_df["revenue_growth"] = df["revenue_growth_calc"].fillna(df.get("revenue_growth"))
    elif "revenue_growth" in df.columns:
        growth_df["revenue_growth"] = df["revenue_growth"]

    # 営業利益成長率
    if "operating_income_growth" in df.columns:
        growth_df["operating_income_growth"] = df["operating_income_growth"]

    # EPS成長率
    if "eps_growth" in df.columns:
        growth_df["eps_growth"] = df["eps_growth"]
    elif "earnings_growth" in df.columns:
        growth_df["eps_growth"] = df["earnings_growth"]

    scores = {}
    mapping = {
        "revenue_growth": "revenue_growth",
        "operating_income_growth": "operating_income_growth",
        "eps_growth": "eps_growth",
    }

    for key, col in mapping.items():
        if col in growth_df.columns:
            scores[key] = _percentile_rank_in_sector(growth_df[col], sector_groups, col, lower_is_better=False)

    # PEG（低いほど割安成長 → lower_is_better）
    if "peg_ratio" in df.columns:
        scores["peg_ratio"] = _percentile_rank_in_sector(df["peg_ratio"], sector_groups, "peg_ratio", lower_is_better=True)

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

    # バリュートラップはスコアにペナルティ（-20点）
    df.loc[is_trap, "total_score"] = df.loc[is_trap, "total_score"] - 20

    return df
