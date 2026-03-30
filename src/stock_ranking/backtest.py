"""バックテスト基盤: IC分析によるファクター予測力の検証

ファクタースコアと将来リターンの順位相関（Information Coefficient）を計算し、
スコアリングモデルの重み付け最適化の根拠を提供する。
"""

import argparse
import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def fetch_returns(tickers: list[str], start_date: str, end_date: str,
                  forward_days: int = 21) -> pd.DataFrame:
    """銘柄群の将来リターンを取得する。

    Args:
        tickers: 銘柄リスト
        start_date: 開始日 (YYYY-MM-DD)
        end_date: 終了日 (YYYY-MM-DD)
        forward_days: 将来リターンの期間（営業日数、デフォルト21日≒1ヶ月）

    Returns:
        columns: ticker, forward_return
    """
    # end_dateからforward_days先まで価格データを取得
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    extended_end = (end_dt + timedelta(days=forward_days * 2)).strftime("%Y-%m-%d")

    results = []
    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(start=start_date, end=extended_end)
            if hist.empty or len(hist) < forward_days + 1:
                continue

            # start_date時点の価格とforward_days後の価格からリターン計算
            # start_dateに最も近い取引日を使用
            start_idx = hist.index.searchsorted(pd.Timestamp(start_date))
            if start_idx >= len(hist):
                continue
            end_idx = min(start_idx + forward_days, len(hist) - 1)

            price_start = hist["Close"].iloc[start_idx]
            price_end = hist["Close"].iloc[end_idx]

            if price_start > 0:
                forward_return = (price_end - price_start) / price_start
                results.append({
                    "ticker": ticker,
                    "forward_return": forward_return,
                })
        except Exception as e:
            logger.debug(f"{ticker}: リターン取得エラー - {e}")

    return pd.DataFrame(results)


def calculate_ic(scores_df: pd.DataFrame, returns_df: pd.DataFrame,
                 factor_cols: list[str]) -> pd.DataFrame:
    """各ファクターのIC（順位相関）を計算する。

    Args:
        scores_df: スコアリング結果（ticker列 + ファクター列を含む）
        returns_df: 将来リターン（ticker列 + forward_return列）
        factor_cols: IC計算対象のファクター列名リスト

    Returns:
        columns: factor, ic, p_value, n_stocks
    """
    merged = scores_df.merge(returns_df, on="ticker", how="inner")

    results = []
    for factor in factor_cols:
        if factor not in merged.columns:
            continue

        # NaN除外
        valid = merged[[factor, "forward_return"]].dropna()
        if len(valid) < 10:
            continue

        # Spearman順位相関
        from scipy import stats
        ic, p_value = stats.spearmanr(valid[factor], valid["forward_return"])

        results.append({
            "factor": factor,
            "ic": ic,
            "p_value": p_value,
            "n_stocks": len(valid),
            "significant": p_value < 0.05,
        })

    df = pd.DataFrame(results)
    if df.empty:
        return df
    return df.sort_values("ic", ascending=False)


def calculate_category_ic(scores_df: pd.DataFrame, returns_df: pd.DataFrame) -> pd.DataFrame:
    """カテゴリスコアのICを計算する。"""
    category_cols = [
        "total_score", "valuation_score", "growth_score",
        "quality_score", "earnings_momentum_score",
    ]
    return calculate_ic(scores_df, returns_df, category_cols)


def calculate_raw_factor_ic(scores_df: pd.DataFrame, returns_df: pd.DataFrame) -> pd.DataFrame:
    """個別ファクター（生データ）のICを計算する。"""
    raw_factors = [
        # バリュエーション
        "pe_ratio", "pb_ratio", "ev_ebitda", "ps_ratio", "fcf_yield",
        # 成長
        "revenue_growth_calc", "operating_income_growth", "eps_growth", "peg_ratio",
        # 質
        "roe", "gross_margin", "debt_to_equity", "fcf_margin",
        # 決算モメンタム
        "avg_surprise_pct", "eps_revision_90d", "revenue_acceleration", "forward_eps_growth",
        # その他
        "piotroski_fscore", "upside_potential",
    ]
    return calculate_ic(scores_df, returns_df, raw_factors)


def quintile_analysis(scores_df: pd.DataFrame, returns_df: pd.DataFrame,
                      factor: str, n_quantiles: int = 5) -> pd.DataFrame:
    """ファクターの五分位分析を実行する。

    ファクタースコアでN分位に分割し、各分位の平均リターンを計算。
    単調なリターン差があるかを検証する。
    """
    merged = scores_df.merge(returns_df, on="ticker", how="inner")
    valid = merged[[factor, "forward_return"]].dropna()

    if len(valid) < n_quantiles * 5:
        return pd.DataFrame()

    valid["quantile"] = pd.qcut(valid[factor], n_quantiles, labels=False, duplicates="drop")

    result = valid.groupby("quantile").agg(
        mean_return=("forward_return", "mean"),
        median_return=("forward_return", "median"),
        count=("forward_return", "count"),
        std_return=("forward_return", "std"),
    ).reset_index()

    result["quantile"] = result["quantile"] + 1  # 1-indexed
    result["factor"] = factor

    return result


def run_backtest(ranking_csv: str, forward_days: int = 21) -> dict:
    """バックテストを実行し、IC分析レポートを返す。

    Args:
        ranking_csv: スコアリング結果CSVのパス
        forward_days: 将来リターンの期間（営業日数）

    Returns:
        分析結果の辞書
    """
    logger.info(f"バックテスト開始: {ranking_csv}")

    # スコアリング結果を読み込み
    scores_df = pd.read_csv(ranking_csv)
    tickers = scores_df["ticker"].tolist()

    # CSVファイル名から日付を推定
    import re
    date_match = re.search(r"(\d{8})", ranking_csv)
    if date_match:
        score_date = datetime.strptime(date_match.group(1), "%Y%m%d").strftime("%Y-%m-%d")
    else:
        score_date = datetime.now().strftime("%Y-%m-%d")

    logger.info(f"スコア日付: {score_date}, 銘柄数: {len(tickers)}, 期間: {forward_days}営業日")

    # 将来リターンを取得
    returns_df = fetch_returns(tickers, score_date, score_date, forward_days)
    logger.info(f"リターン取得完了: {len(returns_df)} 銘柄")

    if len(returns_df) < 30:
        logger.warning("リターンデータが不足しています（30銘柄未満）")
        return {"error": "リターンデータ不足"}

    # IC分析
    category_ic = calculate_category_ic(scores_df, returns_df)
    raw_ic = calculate_raw_factor_ic(scores_df, returns_df)

    # 五分位分析（主要ファクターのみ）
    quintiles = {}
    for factor in ["total_score", "valuation_score", "growth_score", "earnings_momentum_score"]:
        q = quintile_analysis(scores_df, returns_df, factor)
        if not q.empty:
            quintiles[factor] = q

    return {
        "score_date": score_date,
        "forward_days": forward_days,
        "n_stocks": len(returns_df),
        "category_ic": category_ic,
        "raw_factor_ic": raw_ic,
        "quintile_analysis": quintiles,
    }


def print_backtest_report(result: dict):
    """バックテスト結果をコンソールに出力する。"""
    if "error" in result:
        print(f"エラー: {result['error']}")
        return

    print("=" * 80)
    print(f"  IC分析レポート")
    print(f"  スコア日: {result['score_date']}  期間: {result['forward_days']}営業日  銘柄数: {result['n_stocks']}")
    print("=" * 80)

    print("\n--- カテゴリスコアのIC ---")
    cat_ic = result["category_ic"]
    if not cat_ic.empty:
        for _, row in cat_ic.iterrows():
            sig = "***" if row["p_value"] < 0.01 else "**" if row["p_value"] < 0.05 else "*" if row["p_value"] < 0.1 else ""
            print(f"  {row['factor']:30s}  IC={row['ic']:+.4f}  p={row['p_value']:.4f}  n={int(row['n_stocks'])} {sig}")

    print("\n--- 個別ファクターのIC ---")
    raw_ic = result["raw_factor_ic"]
    if not raw_ic.empty:
        for _, row in raw_ic.iterrows():
            sig = "***" if row["p_value"] < 0.01 else "**" if row["p_value"] < 0.05 else "*" if row["p_value"] < 0.1 else ""
            print(f"  {row['factor']:30s}  IC={row['ic']:+.4f}  p={row['p_value']:.4f}  n={int(row['n_stocks'])} {sig}")

    print("\n--- 五分位分析 ---")
    for factor, q_df in result.get("quintile_analysis", {}).items():
        print(f"\n  [{factor}]")
        print(f"  {'Q':>4s}  {'平均リターン':>12s}  {'中央値':>10s}  {'銘柄数':>6s}")
        for _, row in q_df.iterrows():
            print(f"  Q{int(row['quantile']):d}    {row['mean_return']:+.2%}      {row['median_return']:+.2%}    {int(row['count']):4d}")
        # Q1 vs Q5のスプレッド
        if len(q_df) >= 2:
            spread = q_df.iloc[-1]["mean_return"] - q_df.iloc[0]["mean_return"]
            print(f"  スプレッド (Q{int(q_df.iloc[-1]['quantile'])}-Q{int(q_df.iloc[0]['quantile'])}): {spread:+.2%}")

    print("\n" + "=" * 80)


# ============================================================
# 時系列IC分析: 複数日分のCSVを横断してモデルの安定性を検証
# ============================================================

def discover_ranking_csvs(output_dir: str = "output") -> list[str]:
    """output/ディレクトリからranking CSVを日付順に列挙する。"""
    import glob
    import os
    pattern = os.path.join(output_dir, "ranking_*.csv")
    csvs = sorted(glob.glob(pattern))
    return csvs


def run_timeseries_ic(output_dir: str = "output", forward_days: int = 5) -> dict:
    """複数日分のCSVで時系列IC分析を実行する。

    各CSVの日付時点のスコアと、forward_days営業日後のリターンのICを計算し、
    ICの平均・標準偏差・IC>0の割合（Hit Rate）・ICIR を算出する。

    Args:
        output_dir: ranking CSVが格納されたディレクトリ
        forward_days: 将来リターンの期間（営業日数）

    Returns:
        時系列IC分析結果の辞書
    """
    import re

    csvs = discover_ranking_csvs(output_dir)
    if len(csvs) < 2:
        return {"error": f"CSV が {len(csvs)} 件しかありません（2件以上必要）"}

    logger.info(f"時系列IC分析: {len(csvs)} 日分のCSV, forward={forward_days}営業日")

    factor_cols = [
        "total_score", "valuation_score", "growth_score",
        "quality_score", "earnings_momentum_score",
    ]
    raw_factor_cols = [
        "pe_ratio", "pb_ratio", "ev_ebitda", "ps_ratio", "fcf_yield",
        "revenue_growth_calc", "operating_income_growth", "eps_growth", "peg_ratio",
        "roe", "gross_margin", "debt_to_equity", "fcf_margin",
        "avg_surprise_pct", "eps_revision_90d", "revenue_acceleration", "forward_eps_growth",
        "piotroski_fscore", "upside_potential",
    ]
    all_factors = factor_cols + raw_factor_cols

    # 各日付ごとにICを計算
    daily_ics: list[dict] = []

    for csv_path in csvs:
        date_match = re.search(r"(\d{8})", csv_path)
        if not date_match:
            continue
        score_date = datetime.strptime(date_match.group(1), "%Y%m%d").strftime("%Y-%m-%d")

        scores_df = pd.read_csv(csv_path)
        tickers = scores_df["ticker"].tolist()

        returns_df = fetch_returns(tickers, score_date, score_date, forward_days)
        if len(returns_df) < 30:
            logger.warning(f"{score_date}: リターン取得不足 ({len(returns_df)} 銘柄), スキップ")
            continue

        ic_result = calculate_ic(scores_df, returns_df, all_factors)
        if ic_result.empty:
            continue

        ic_dict = {"date": score_date, "n_stocks": len(returns_df)}
        for _, row in ic_result.iterrows():
            ic_dict[row["factor"]] = row["ic"]
        daily_ics.append(ic_dict)

        logger.info(f"{score_date}: IC計算完了 (n={len(returns_df)})")

    if len(daily_ics) < 2:
        return {"error": "有効なIC計算結果が2日分未満です"}

    ic_df = pd.DataFrame(daily_ics)

    # サマリ統計を計算
    summary_rows = []
    for factor in all_factors:
        if factor not in ic_df.columns:
            continue
        series = ic_df[factor].dropna()
        if len(series) < 2:
            continue
        mean_ic = series.mean()
        std_ic = series.std()
        icir = mean_ic / std_ic if std_ic > 0 else 0.0
        hit_rate = (series > 0).mean()
        summary_rows.append({
            "factor": factor,
            "mean_ic": mean_ic,
            "std_ic": std_ic,
            "icir": icir,
            "hit_rate": hit_rate,
            "n_periods": len(series),
        })

    summary_df = pd.DataFrame(summary_rows).sort_values("mean_ic", ascending=False)

    return {
        "forward_days": forward_days,
        "n_periods": len(daily_ics),
        "dates": [d["date"] for d in daily_ics],
        "daily_ics": ic_df,
        "summary": summary_df,
    }


def print_timeseries_report(result: dict):
    """時系列IC分析結果をコンソールに出力する。"""
    if "error" in result:
        print(f"エラー: {result['error']}")
        return

    print("=" * 90)
    print(f"  時系列IC分析レポート")
    print(f"  期間: {result['dates'][0]} ~ {result['dates'][-1]}")
    print(f"  分析日数: {result['n_periods']}日  将来リターン: {result['forward_days']}営業日")
    print("=" * 90)

    summary = result["summary"]

    # カテゴリスコア
    category_factors = {"total_score", "valuation_score", "growth_score",
                        "quality_score", "earnings_momentum_score"}
    cat_summary = summary[summary["factor"].isin(category_factors)]
    raw_summary = summary[~summary["factor"].isin(category_factors)]

    print("\n--- カテゴリスコアの時系列IC ---")
    print(f"  {'ファクター':30s} {'平均IC':>8s} {'Std':>8s} {'ICIR':>8s} {'Hit%':>6s} {'N':>4s}")
    print(f"  {'-'*30} {'-'*8} {'-'*8} {'-'*8} {'-'*6} {'-'*4}")
    for _, row in cat_summary.iterrows():
        quality = "◎" if row["mean_ic"] > 0.05 and row["hit_rate"] >= 0.6 else \
                  "○" if row["mean_ic"] > 0 and row["hit_rate"] >= 0.5 else "△"
        print(f"  {row['factor']:30s} {row['mean_ic']:+8.4f} {row['std_ic']:8.4f} "
              f"{row['icir']:+8.4f} {row['hit_rate']:5.0%} {int(row['n_periods']):4d}  {quality}")

    print("\n--- 個別ファクターの時系列IC ---")
    print(f"  {'ファクター':30s} {'平均IC':>8s} {'Std':>8s} {'ICIR':>8s} {'Hit%':>6s} {'N':>4s}")
    print(f"  {'-'*30} {'-'*8} {'-'*8} {'-'*8} {'-'*6} {'-'*4}")
    for _, row in raw_summary.iterrows():
        quality = "◎" if row["mean_ic"] > 0.05 and row["hit_rate"] >= 0.6 else \
                  "○" if row["mean_ic"] > 0 and row["hit_rate"] >= 0.5 else "△"
        print(f"  {row['factor']:30s} {row['mean_ic']:+8.4f} {row['std_ic']:8.4f} "
              f"{row['icir']:+8.4f} {row['hit_rate']:5.0%} {int(row['n_periods']):4d}  {quality}")

    # 日次ICの推移（total_score）
    ic_df = result["daily_ics"]
    if "total_score" in ic_df.columns:
        print("\n--- total_score 日次IC推移 ---")
        for _, row in ic_df.iterrows():
            ic_val = row.get("total_score", float("nan"))
            if pd.notna(ic_val):
                bar = "+" * int(abs(ic_val) * 100) if ic_val > 0 else "-" * int(abs(ic_val) * 100)
                sign = "▲" if ic_val > 0 else "▼"
                print(f"  {row['date']}  {sign} {ic_val:+.4f}  {bar}")

    print("\n  判定基準: ◎=平均IC>0.05 & Hit≥60%  ○=平均IC>0 & Hit≥50%  △=それ以外")
    print("  ICIR(IC Information Ratio) = 平均IC / IC標準偏差 (高いほど安定)")
    print("=" * 90)


def main():
    parser = argparse.ArgumentParser(description="IC分析バックテスト")
    subparsers = parser.add_subparsers(dest="command")

    # 単発IC分析（既存）
    single = subparsers.add_parser("single", help="単一CSVのIC分析")
    single.add_argument("--csv", required=True, help="スコアリング結果CSVのパス")
    single.add_argument("--days", type=int, default=21, help="将来リターンの期間（営業日数）")

    # 時系列IC分析（新規）
    ts = subparsers.add_parser("timeseries", help="複数CSVの時系列IC分析")
    ts.add_argument("--dir", default="output", help="ranking CSVのディレクトリ (default: output)")
    ts.add_argument("--days", type=int, default=5, help="将来リターンの期間（営業日数、default: 5）")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                        datefmt="%H:%M:%S")

    if args.command == "timeseries":
        result = run_timeseries_ic(args.dir, args.days)
        print_timeseries_report(result)
    elif args.command == "single":
        result = run_backtest(args.csv, args.days)
        print_backtest_report(result)
    else:
        # 後方互換: サブコマンドなしの場合は引数を再パース
        compat = argparse.ArgumentParser()
        compat.add_argument("--csv", required=True)
        compat.add_argument("--days", type=int, default=21)
        compat_args = compat.parse_args()
        result = run_backtest(compat_args.csv, compat_args.days)
        print_backtest_report(result)


if __name__ == "__main__":
    main()
