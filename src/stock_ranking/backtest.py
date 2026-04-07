"""バックテスト基盤: IC分析によるファクター予測力の検証

ファクタースコアと将来リターンの順位相関（Information Coefficient）を計算し、
スコアリングモデルの重み付け最適化の根拠を提供する。

検証指標:
- IC (Information Coefficient): Spearman順位相関
- ICIR (IC Information Ratio): Mean(IC)/Std(IC) — シグナルの安定性
- IC Hit Rate: IC>0の割合 — 勝率
- 五分位分析: スコア上位vs下位のリターン差（単調性検証）
- ブートストラップ信頼区間: 限られたデータでの統計的信頼性
"""

import argparse
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
from scipy import stats

logger = logging.getLogger(__name__)

# --- 定数 ---
CATEGORY_COLS = [
    "total_score", "valuation_score", "growth_score",
    "quality_score", "earnings_momentum_score", "price_momentum_score",
    "buy_signal", "overlay_buy_signal",
]
SIGNAL_COMPARISON_FACTORS = ["total_score", "buy_signal", "overlay_buy_signal"]

RAW_FACTOR_COLS = [
    "pe_ratio", "pb_ratio", "ev_ebitda", "ps_ratio", "fcf_yield",
    "revenue_growth_calc", "operating_income_growth", "eps_growth", "peg_ratio",
    "roe", "gross_margin", "debt_to_equity", "fcf_margin",
    "avg_surprise_pct", "eps_revision_90d", "revenue_acceleration", "forward_eps_growth",
    "piotroski_fscore", "upside_potential",
    "momentum_12_1m", "momentum_1m",
]

DEFAULT_FORWARD_PERIODS = [1, 5, 10, 21]
BOOTSTRAP_ITERATIONS = 1000
MIN_STOCKS_FOR_IC = 30


def fetch_returns(tickers: list[str], start_date: str,
                  forward_days: int = 21) -> pd.DataFrame:
    """銘柄群の将来リターンを取得する。

    Args:
        tickers: 銘柄リスト
        start_date: 開始日 (YYYY-MM-DD)
        forward_days: 将来リターンの期間（営業日数、デフォルト21日≒1ヶ月）

    Returns:
        columns: ticker, forward_return
    """
    end_dt = datetime.strptime(start_date, "%Y-%m-%d")
    extended_end = (end_dt + timedelta(days=forward_days * 2 + 5)).strftime("%Y-%m-%d")

    results = []
    failed = 0
    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(start=start_date, end=extended_end)
            if hist.empty or len(hist) < 2:
                failed += 1
                continue

            # タイムゾーンを除去して比較可能にする
            hist.index = hist.index.tz_localize(None)

            # 最初の取引日（start_date以降）を基準
            price_start = hist["Close"].iloc[0]

            # forward_days後（またはデータの最終日）
            actual_days = min(forward_days, len(hist) - 1)
            if actual_days < 1:
                failed += 1
                continue
            price_end = hist["Close"].iloc[actual_days]

            if price_start > 0:
                forward_return = (price_end - price_start) / price_start
                results.append({
                    "ticker": ticker,
                    "forward_return": forward_return,
                    "actual_days": actual_days,
                })
        except Exception as e:
            logger.debug(f"{ticker}: リターン取得エラー - {e}")
            failed += 1

    if failed > 0:
        logger.info(f"リターン取得: 成功={len(results)}, 失敗={failed}")

    return pd.DataFrame(results)


def calculate_ic(scores_df: pd.DataFrame, returns_df: pd.DataFrame,
                 factor_cols: list[str]) -> pd.DataFrame:
    """各ファクターのIC（Spearman順位相関）を計算する。"""
    merged = scores_df.merge(returns_df, on="ticker", how="inner")

    results = []
    for factor in factor_cols:
        if factor not in merged.columns:
            continue

        valid = merged[[factor, "forward_return"]].dropna()
        if len(valid) < 10:
            continue

        ic, p_value = stats.spearmanr(valid[factor], valid["forward_return"])

        results.append({
            "factor": factor,
            "ic": ic,
            "p_value": p_value,
            "n_stocks": len(valid),
            "significant": p_value < 0.05,
        })

    if not results:
        return pd.DataFrame()
    return pd.DataFrame(results).sort_values("ic", ascending=False)


def bootstrap_ic(scores_df: pd.DataFrame, returns_df: pd.DataFrame,
                 factor: str, n_iterations: int = BOOTSTRAP_ITERATIONS) -> dict:
    """ブートストラップ法でICの信頼区間を推定する。

    銘柄を復元抽出して再サンプリングし、IC分布の95%信頼区間を算出。
    限られたデータでの統計的信頼性を担保する。
    """
    merged = scores_df.merge(returns_df, on="ticker", how="inner")
    valid = merged[[factor, "forward_return"]].dropna()

    if len(valid) < 20:
        return {"factor": factor, "ci_lower": np.nan, "ci_upper": np.nan,
                "mean_ic": np.nan, "n": len(valid)}

    bootstrap_ics = []
    rng = np.random.default_rng(42)
    for _ in range(n_iterations):
        sample = valid.sample(n=len(valid), replace=True, random_state=rng.integers(0, 2**31))
        ic, _ = stats.spearmanr(sample[factor], sample["forward_return"])
        if not np.isnan(ic):
            bootstrap_ics.append(ic)

    if len(bootstrap_ics) < 100:
        return {"factor": factor, "ci_lower": np.nan, "ci_upper": np.nan,
                "mean_ic": np.nan, "n": len(valid)}

    ci_lower, ci_upper = np.percentile(bootstrap_ics, [2.5, 97.5])
    return {
        "factor": factor,
        "mean_ic": np.mean(bootstrap_ics),
        "std_ic": np.std(bootstrap_ics),
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "ci_excludes_zero": (ci_lower > 0) or (ci_upper < 0),
        "n": len(valid),
    }


def quintile_analysis(scores_df: pd.DataFrame, returns_df: pd.DataFrame,
                      factor: str, n_quantiles: int = 5) -> pd.DataFrame:
    """ファクターの五分位分析を実行する。

    ファクタースコアでN分位に分割し、各分位の平均リターンを計算。
    単調なリターン差があるかを検証する。
    """
    merged = scores_df.merge(returns_df, on="ticker", how="inner")
    valid = merged[[factor, "forward_return", "ticker"]].dropna()

    if len(valid) < n_quantiles * 5:
        return pd.DataFrame()

    valid = valid.copy()
    valid["quantile"] = pd.qcut(valid[factor], n_quantiles, labels=False, duplicates="drop")

    result = valid.groupby("quantile").agg(
        mean_return=("forward_return", "mean"),
        median_return=("forward_return", "median"),
        count=("forward_return", "count"),
        std_return=("forward_return", "std"),
    ).reset_index()

    result["quantile"] = result["quantile"] + 1  # 1-indexed
    result["factor"] = factor

    # Q1 vs Q5のt検定
    if len(result) >= 2:
        q1_returns = valid[valid["quantile"] == 0]["forward_return"]
        q5_returns = valid[valid["quantile"] == valid["quantile"].max()]["forward_return"]
        if len(q1_returns) >= 5 and len(q5_returns) >= 5:
            t_stat, t_pvalue = stats.ttest_ind(q5_returns, q1_returns)
            result.attrs["spread_t_stat"] = t_stat
            result.attrs["spread_p_value"] = t_pvalue

    return result


def multi_period_ic(scores_df: pd.DataFrame, tickers: list[str],
                    score_date: str,
                    periods: list[int] | None = None) -> pd.DataFrame:
    """複数のリターン期間でICを一括計算する。

    短期（1d）から中期（21d）まで一貫してICが正なら信頼性が高い。
    """
    if periods is None:
        periods = DEFAULT_FORWARD_PERIODS

    all_results = []
    for days in periods:
        logger.info(f"  {days}日先リターンを取得中...")
        returns_df = fetch_returns(tickers, score_date, forward_days=days)

        if len(returns_df) < MIN_STOCKS_FOR_IC:
            logger.warning(f"  {days}d: リターンデータ不足 ({len(returns_df)}銘柄)")
            continue

        ic_df = calculate_ic(scores_df, returns_df, CATEGORY_COLS)
        if ic_df.empty:
            continue

        ic_df["forward_days"] = days
        all_results.append(ic_df)

    if not all_results:
        return pd.DataFrame()
    return pd.concat(all_results, ignore_index=True)


def rolling_ic_from_csvs(csv_paths: list[str], forward_days: int = 5) -> pd.DataFrame:
    """複数日のCSVからRolling ICを計算し、ICIRとHit Rateを算出する。

    各CSVの日付でスコア→forward_daysリターンのICを計算し、
    時系列でのIC安定性を評価する。
    """
    daily_ics = []

    for csv_path in sorted(csv_paths):
        date_match = re.search(r"(\d{8})", csv_path)
        if not date_match:
            continue

        score_date = datetime.strptime(date_match.group(1), "%Y%m%d").strftime("%Y-%m-%d")
        logger.info(f"Rolling IC: {score_date} ({csv_path})")

        scores_df = pd.read_csv(csv_path)
        tickers = scores_df["ticker"].tolist()
        returns_df = fetch_returns(tickers, score_date, forward_days=forward_days)

        if len(returns_df) < MIN_STOCKS_FOR_IC:
            logger.warning(f"  スキップ: リターンデータ不足 ({len(returns_df)}銘柄)")
            continue

        ic_df = calculate_ic(scores_df, returns_df, CATEGORY_COLS)
        if ic_df.empty:
            continue

        ic_df["score_date"] = score_date
        ic_df["n_stocks"] = len(returns_df)
        daily_ics.append(ic_df)

    if not daily_ics:
        return pd.DataFrame()
    return pd.concat(daily_ics, ignore_index=True)


def calculate_icir(rolling_ic_df: pd.DataFrame) -> pd.DataFrame:
    """Rolling ICデータからICIR（IC Information Ratio）とHit Rateを算出する。

    ICIR = Mean(IC) / Std(IC)
    Hit Rate = IC > 0 の割合

    ICIR閾値:
    - < 0.3: 弱い
    - 0.3-0.5: まずまず
    - 0.5-1.0: 良好
    - > 1.0: 非常に強い
    """
    if rolling_ic_df.empty:
        return pd.DataFrame()

    results = []
    for factor, group in rolling_ic_df.groupby("factor"):
        ics = group["ic"].dropna()
        n_periods = len(ics)
        if n_periods < 2:
            continue

        mean_ic = ics.mean()
        std_ic = ics.std()
        icir = mean_ic / std_ic if std_ic > 0 else np.nan
        hit_rate = (ics > 0).mean()

        results.append({
            "factor": factor,
            "mean_ic": mean_ic,
            "std_ic": std_ic,
            "icir": icir,
            "hit_rate": hit_rate,
            "n_periods": n_periods,
            "min_ic": ics.min(),
            "max_ic": ics.max(),
        })

    return pd.DataFrame(results).sort_values("icir", ascending=False)


def build_signal_comparison(
    category_ic: pd.DataFrame | None = None,
    icir_df: pd.DataFrame | None = None,
    quintiles: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """total/buy/overlay の優劣を横並びで比較する。"""
    quintiles = quintiles or {}
    cat_map = {}
    if category_ic is not None and not category_ic.empty:
        cat_map = category_ic.set_index("factor").to_dict(orient="index")

    icir_map = {}
    if icir_df is not None and not icir_df.empty:
        icir_map = icir_df.set_index("factor").to_dict(orient="index")

    rows = []
    for factor in SIGNAL_COMPARISON_FACTORS:
        row: dict[str, float | str] = {"factor": factor}
        has_data = False

        if factor in cat_map:
            has_data = True
            row["ic"] = float(cat_map[factor]["ic"])
            row["p_value"] = float(cat_map[factor]["p_value"])

        if factor in icir_map:
            has_data = True
            row["mean_ic"] = float(icir_map[factor]["mean_ic"])
            row["icir"] = float(icir_map[factor]["icir"])
            row["hit_rate"] = float(icir_map[factor]["hit_rate"])
            row["n_periods"] = int(icir_map[factor]["n_periods"])

        quintile_df = quintiles.get(factor)
        if quintile_df is not None and not quintile_df.empty:
            has_data = True
            row["spread"] = float(quintile_df.iloc[-1]["mean_return"] - quintile_df.iloc[0]["mean_return"])
            spread_p = quintile_df.attrs.get("spread_p_value")
            if spread_p is not None:
                row["spread_p_value"] = float(spread_p)

        if has_data:
            rows.append(row)

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


def run_backtest(ranking_csv: str, forward_days: int = 21) -> dict:
    """単一CSVのバックテストを実行し、IC分析レポートを返す。"""
    logger.info(f"バックテスト開始: {ranking_csv}")

    scores_df = pd.read_csv(ranking_csv)
    tickers = scores_df["ticker"].tolist()

    date_match = re.search(r"(\d{8})", ranking_csv)
    score_date = (datetime.strptime(date_match.group(1), "%Y%m%d").strftime("%Y-%m-%d")
                  if date_match else datetime.now().strftime("%Y-%m-%d"))

    logger.info(f"スコア日付: {score_date}, 銘柄数: {len(tickers)}, 期間: {forward_days}営業日")

    returns_df = fetch_returns(tickers, score_date, forward_days)
    logger.info(f"リターン取得完了: {len(returns_df)} 銘柄")

    if len(returns_df) < MIN_STOCKS_FOR_IC:
        logger.warning(f"リターンデータが不足しています（{MIN_STOCKS_FOR_IC}銘柄未満）")
        return {"error": "リターンデータ不足"}

    # IC分析
    category_ic = calculate_ic(scores_df, returns_df, CATEGORY_COLS)
    raw_ic = calculate_ic(scores_df, returns_df, RAW_FACTOR_COLS)

    # ブートストラップ信頼区間（主要カテゴリのみ）
    bootstrap_results = {}
    for factor in CATEGORY_COLS:
        if factor in scores_df.columns:
            bootstrap_results[factor] = bootstrap_ic(scores_df, returns_df, factor)

    # 五分位分析
    quintiles = {}
    for factor in list(dict.fromkeys(SIGNAL_COMPARISON_FACTORS + ["valuation_score", "growth_score", "earnings_momentum_score"])):
        if factor not in scores_df.columns:
            continue
        q = quintile_analysis(scores_df, returns_df, factor)
        if not q.empty:
            quintiles[factor] = q

    signal_comparison = build_signal_comparison(category_ic, quintiles=quintiles)

    return {
        "score_date": score_date,
        "forward_days": forward_days,
        "n_stocks": len(returns_df),
        "category_ic": category_ic,
        "signal_comparison": signal_comparison,
        "raw_factor_ic": raw_ic,
        "bootstrap": bootstrap_results,
        "quintile_analysis": quintiles,
    }


def run_comprehensive_backtest(csv_dir: str = "output",
                               forward_days: int = 5) -> dict:
    """全CSVを使った包括的バックテストを実行する。

    - 各CSVごとのIC分析
    - Rolling IC → ICIR・Hit Rate算出
    - 複数リターン期間での検証
    - ブートストラップ信頼区間
    """
    csv_paths = sorted(Path(csv_dir).glob("ranking_*.csv"))
    if not csv_paths:
        return {"error": f"{csv_dir}にCSVが見つかりません"}

    csv_strs = [str(p) for p in csv_paths]
    logger.info(f"包括的バックテスト: {len(csv_strs)}個のCSV, {forward_days}日先リターン")

    # Rolling IC
    rolling_df = rolling_ic_from_csvs(csv_strs, forward_days=forward_days)

    # ICIR
    icir_df = calculate_icir(rolling_df) if not rolling_df.empty else pd.DataFrame()

    # 最新CSVで複数期間IC
    latest_csv = csv_strs[-1]
    scores_df = pd.read_csv(latest_csv)
    tickers = scores_df["ticker"].tolist()
    date_match = re.search(r"(\d{8})", latest_csv)
    latest_date = (datetime.strptime(date_match.group(1), "%Y%m%d").strftime("%Y-%m-%d")
                   if date_match else datetime.now().strftime("%Y-%m-%d"))

    multi_ic = multi_period_ic(scores_df, tickers, latest_date)

    # 最新CSVのブートストラップ
    returns_df = fetch_returns(tickers, latest_date, forward_days=forward_days)
    latest_category_ic = pd.DataFrame()
    bootstrap_results = {}
    if len(returns_df) >= MIN_STOCKS_FOR_IC:
        latest_category_ic = calculate_ic(scores_df, returns_df, CATEGORY_COLS)
        for factor in CATEGORY_COLS:
            if factor in scores_df.columns:
                bootstrap_results[factor] = bootstrap_ic(scores_df, returns_df, factor)

    # 最新CSVの五分位分析
    quintiles = {}
    if len(returns_df) >= MIN_STOCKS_FOR_IC:
        for factor in list(dict.fromkeys(SIGNAL_COMPARISON_FACTORS + [
            "valuation_score", "growth_score", "earnings_momentum_score",
        ])):
            if factor not in scores_df.columns:
                continue
            q = quintile_analysis(scores_df, returns_df, factor)
            if not q.empty:
                quintiles[factor] = q

    signal_comparison = build_signal_comparison(latest_category_ic, icir_df=icir_df, quintiles=quintiles)

    return {
        "n_csvs": len(csv_strs),
        "csv_dates": [re.search(r"(\d{8})", p).group(1) for p in csv_strs if re.search(r"(\d{8})", p)],
        "forward_days": forward_days,
        "n_stocks": len(returns_df),
        "category_ic": latest_category_ic,
        "signal_comparison": signal_comparison,
        "rolling_ic": rolling_df,
        "icir": icir_df,
        "multi_period_ic": multi_ic,
        "bootstrap": bootstrap_results,
        "quintile_analysis": quintiles,
        "latest_date": latest_date,
    }


def print_backtest_report(result: dict):
    """バックテスト結果をコンソールに出力する。"""
    if "error" in result:
        print(f"エラー: {result['error']}")
        return

    print("=" * 80)
    if "score_date" in result:
        # 単一CSV結果
        print(f"  IC分析レポート")
        print(f"  スコア日: {result['score_date']}  期間: {result['forward_days']}営業日  銘柄数: {result['n_stocks']}")
    else:
        # 包括的バックテスト
        print(f"  包括的IC分析レポート")
        print(f"  CSV数: {result['n_csvs']}  期間: {result['forward_days']}d先リターン")
        print(f"  対象日: {', '.join(result.get('csv_dates', []))}")
    print("=" * 80)

    # ICIR
    icir = result.get("icir")
    if icir is not None and not icir.empty:
        print("\n--- ICIR (IC Information Ratio) ---")
        print(f"  {'ファクター':30s}  {'Mean IC':>8s}  {'Std IC':>8s}  {'ICIR':>6s}  {'Hit%':>5s}  {'N':>3s}  評価")
        for _, row in icir.iterrows():
            rating = (_rate_icir(row["icir"]) if not np.isnan(row["icir"]) else "N/A")
            print(f"  {row['factor']:30s}  {row['mean_ic']:+.4f}  {row['std_ic']:.4f}  "
                  f"{row['icir']:+.2f}  {row['hit_rate']:.0%}  {int(row['n_periods']):3d}  {rating}")

    # カテゴリIC
    cat_ic = result.get("category_ic")
    if cat_ic is not None and not cat_ic.empty:
        print("\n--- カテゴリスコアのIC ---")
        for _, row in cat_ic.iterrows():
            sig = _significance_stars(row["p_value"])
            rating = _rate_ic(row["ic"])
            print(f"  {row['factor']:30s}  IC={row['ic']:+.4f}  p={row['p_value']:.4f}  "
                  f"n={int(row['n_stocks'])} {sig}  {rating}")

    signal_comparison = result.get("signal_comparison")
    if signal_comparison is not None and not signal_comparison.empty:
        print("\n--- Signal Comparison (Total vs BUY vs Overlay BUY) ---")
        print(f"  {'ファクター':22s}  {'IC':>7s}  {'ICIR':>7s}  {'Hit%':>6s}  {'Q5-Q1':>8s}")
        for _, row in signal_comparison.iterrows():
            ic = row.get("ic")
            icir_val = row.get("icir")
            hit_rate = row.get("hit_rate")
            spread = row.get("spread")
            ic_str = f"{ic:+.4f}" if pd.notna(ic) else "   N/A"
            icir_str = f"{icir_val:+.2f}" if pd.notna(icir_val) else "   N/A"
            hit_str = f"{hit_rate:.0%}" if pd.notna(hit_rate) else "  N/A"
            spread_str = f"{spread:+.2%}" if pd.notna(spread) else "   N/A"
            print(f"  {row['factor']:22s}  {ic_str:>7s}  {icir_str:>7s}  {hit_str:>6s}  {spread_str:>8s}")

        factor_map = signal_comparison.set_index("factor").to_dict(orient="index")
        if "buy_signal" in factor_map and "overlay_buy_signal" in factor_map:
            buy_ic = factor_map["buy_signal"].get("ic")
            overlay_ic = factor_map["overlay_buy_signal"].get("ic")
            if buy_ic is not None and overlay_ic is not None:
                print(f"  Overlay - BUY のIC差: {overlay_ic - buy_ic:+.4f}")

    # ブートストラップ
    bootstrap = result.get("bootstrap", {})
    if bootstrap:
        print("\n--- ブートストラップ95%信頼区間 ---")
        for factor, bs in bootstrap.items():
            if np.isnan(bs.get("mean_ic", np.nan)):
                continue
            excludes = "ゼロ含まず" if bs.get("ci_excludes_zero") else "ゼロ含む"
            print(f"  {factor:30s}  IC={bs['mean_ic']:+.4f}  "
                  f"CI=[{bs['ci_lower']:+.4f}, {bs['ci_upper']:+.4f}]  ({excludes})")

    # 個別ファクターIC
    raw_ic = result.get("raw_factor_ic")
    if raw_ic is not None and not raw_ic.empty:
        print("\n--- 個別ファクターのIC ---")
        for _, row in raw_ic.iterrows():
            sig = _significance_stars(row["p_value"])
            print(f"  {row['factor']:30s}  IC={row['ic']:+.4f}  p={row['p_value']:.4f}  "
                  f"n={int(row['n_stocks'])} {sig}")

    # 複数期間IC
    multi_ic = result.get("multi_period_ic")
    if multi_ic is not None and not multi_ic.empty:
        print("\n--- 複数期間IC（リターン期間別） ---")
        pivot = multi_ic.pivot_table(index="factor", columns="forward_days", values="ic")
        print(f"  {'ファクター':30s}", end="")
        for col in sorted(pivot.columns):
            print(f"  {col:>4d}d", end="")
        print("  一貫性")
        for factor in pivot.index:
            print(f"  {factor:30s}", end="")
            ics = []
            for col in sorted(pivot.columns):
                val = pivot.loc[factor, col]
                if pd.notna(val):
                    print(f"  {val:+.3f}", end="")
                    ics.append(val)
                else:
                    print(f"  {'N/A':>6s}", end="")
            # 一貫性: 全期間で同符号
            if ics:
                all_positive = all(ic > 0 for ic in ics)
                all_negative = all(ic < 0 for ic in ics)
                print(f"  {'+++' if all_positive else '---' if all_negative else '混在'}")
            else:
                print()

    # Rolling IC詳細
    rolling = result.get("rolling_ic")
    if rolling is not None and not rolling.empty:
        print("\n--- Rolling IC（日次推移） ---")
        for factor in CATEGORY_COLS:
            factor_data = rolling[rolling["factor"] == factor]
            if factor_data.empty:
                continue
            print(f"  [{factor}]")
            for _, row in factor_data.iterrows():
                sig = _significance_stars(row["p_value"])
                print(f"    {row['score_date']}  IC={row['ic']:+.4f}  n={int(row['n_stocks'])} {sig}")

    # 五分位分析
    quintiles = result.get("quintile_analysis", {})
    if quintiles:
        print("\n--- 五分位分析 ---")
        for factor, q_df in quintiles.items():
            print(f"\n  [{factor}]")
            print(f"  {'Q':>4s}  {'平均リターン':>12s}  {'中央値':>10s}  {'標準偏差':>10s}  {'銘柄数':>6s}")
            for _, row in q_df.iterrows():
                print(f"  Q{int(row['quantile']):d}    {row['mean_return']:+.2%}      "
                      f"{row['median_return']:+.2%}    {row['std_return']:.2%}    {int(row['count']):4d}")
            if len(q_df) >= 2:
                spread = q_df.iloc[-1]["mean_return"] - q_df.iloc[0]["mean_return"]
                t_stat = q_df.attrs.get("spread_t_stat")
                t_p = q_df.attrs.get("spread_p_value")
                t_info = f"  t={t_stat:.2f}, p={t_p:.4f}" if t_stat is not None else ""
                print(f"  スプレッド (Q{int(q_df.iloc[-1]['quantile'])}-Q{int(q_df.iloc[0]['quantile'])}): "
                      f"{spread:+.2%}{t_info}")

    print("\n" + "=" * 80)


def save_ic_record(result: dict, output_path: str = "output/ic_history.json"):
    """IC分析結果をJSON形式で記録する（CI連携用）。

    日次CIで実行し、蓄積することでICIRの信頼性が向上する。
    """
    path = Path(output_path)
    history = []
    if path.exists():
        try:
            history = json.loads(path.read_text())
        except json.JSONDecodeError:
            history = []

    record = {
        "timestamp": datetime.now().isoformat(),
        "score_date": result.get("score_date", result.get("latest_date")),
        "forward_days": result.get("forward_days"),
        "n_stocks": result.get("n_stocks", 0),
    }

    # カテゴリIC
    cat_ic = result.get("category_ic")
    if cat_ic is not None and not cat_ic.empty:
        record["category_ic"] = {
            row["factor"]: {"ic": float(row["ic"]), "p_value": float(row["p_value"])}
            for _, row in cat_ic.iterrows()
        }

    history.append(record)
    path.write_text(json.dumps(history, indent=2, ensure_ascii=False))
    logger.info(f"IC記録を保存: {output_path} (累計{len(history)}件)")


def _significance_stars(p_value: float) -> str:
    if p_value < 0.01:
        return "***"
    if p_value < 0.05:
        return "** "
    if p_value < 0.1:
        return "*  "
    return "   "


def _rate_ic(ic: float) -> str:
    abs_ic = abs(ic)
    if abs_ic > 0.15:
        return "⚠ 過学習?"
    if abs_ic > 0.10:
        return "◎ 非常に強い"
    if abs_ic > 0.05:
        return "○ 良好"
    if abs_ic > 0.02:
        return "△ 弱いが有用"
    return "× ノイズ"


def _rate_icir(icir: float) -> str:
    if icir > 1.0:
        return "◎ 非常に安定"
    if icir > 0.5:
        return "○ 良好"
    if icir > 0.3:
        return "△ まずまず"
    return "× 不安定"


def main():
    parser = argparse.ArgumentParser(description="IC分析バックテスト")
    parser.add_argument("--csv", help="単一CSVのパス（指定時は単体分析）")
    parser.add_argument("--all", action="store_true", help="output/の全CSVで包括的分析")
    parser.add_argument("--days", type=int, default=5, help="将来リターンの期間（営業日数）")
    parser.add_argument("--multi-period", action="store_true",
                        help="複数リターン期間(1d/5d/10d/21d)で分析")
    parser.add_argument("--save", action="store_true", help="IC記録をJSONに保存（CI連携用）")
    parser.add_argument("--output-dir", default="output", help="CSV/JSONの出力ディレクトリ")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                        datefmt="%H:%M:%S")

    if args.all:
        result = run_comprehensive_backtest(args.output_dir, args.days)
    elif args.csv:
        result = run_backtest(args.csv, args.days)
    else:
        parser.error("--csv または --all を指定してください")

    print_backtest_report(result)

    if args.save and "error" not in result:
        save_ic_record(result, f"{args.output_dir}/ic_history.json")


if __name__ == "__main__":
    main()
