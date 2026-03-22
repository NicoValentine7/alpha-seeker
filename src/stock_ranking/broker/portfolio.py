"""ポジション取得・スコアリングデータとのマージ"""

import logging

import pandas as pd

from stock_ranking.broker.client import open_trade_context

logger = logging.getLogger(__name__)


def fetch_positions() -> pd.DataFrame:
    """OpenDから米国株ポジション一覧を取得してDataFrameに正規化する。

    Returns:
        columns: ticker, quantity, cost_price, current_price, market_val,
                 unrealized_pl, unrealized_pl_pct
        接続失敗時やポジションなしの場合は空のDataFrame。
    """
    try:
        from moomoo import RET_OK
    except ImportError:
        raise RuntimeError("moomoo-api がインストールされていません。")

    try:
        with open_trade_context() as ctx:
            ret, data = ctx.position_list_query()
            if ret != RET_OK:
                logger.warning(f"ポジション取得失敗: {data}")
                return pd.DataFrame()

            if data.empty:
                logger.info("保有ポジションなし")
                return pd.DataFrame()

            # moomooのカラム名を内部表現にリネーム
            col_map = {
                "code": "ticker_raw",
                "stock_name": "name_moomoo",
                "qty": "quantity",
                "cost_price": "cost_price",
                "nominal_price": "current_price",
                "market_val": "market_val",
                "pl_val": "unrealized_pl",
                "pl_ratio": "unrealized_pl_pct",
            }
            available = {k: v for k, v in col_map.items() if k in data.columns}
            df = data.rename(columns=available)

            # "US.AAPL" → "AAPL" に変換
            if "ticker_raw" in df.columns:
                df["ticker"] = df["ticker_raw"].str.replace(r"^US\.", "", regex=True)
            else:
                logger.warning("code列が見つかりません")
                return pd.DataFrame()

            keep_cols = [v for v in available.values() if v in df.columns]
            keep_cols.append("ticker")
            return df[keep_cols]

    except RuntimeError:
        raise
    except Exception as e:
        logger.warning(f"ポジション取得エラー: {e}")
        return pd.DataFrame()


def get_portfolio(ranking_df: pd.DataFrame) -> pd.DataFrame:
    """保有銘柄をランキングDFとマージして返す。

    Args:
        ranking_df: calculate_total_score()済みのDataFrame（total_score列必須、1始まりindex）

    Returns:
        保有銘柄のみ、ポジション情報とスコアを結合したDataFrame。
        ポジション取得失敗時は空のDataFrame。
    """
    positions = fetch_positions()
    if positions.empty:
        logger.warning("保有ポジションが取得できませんでした")
        return pd.DataFrame()

    # ranking_dfのindexをrank_in_sp500として保存
    rank_df = ranking_df.reset_index().rename(columns={"index": "rank_in_sp500"})

    score_cols = [
        "ticker", "name", "sector",
        "total_score", "valuation_score", "growth_score",
        "quality_score", "earnings_momentum_score",
        "piotroski_fscore", "is_value_trap", "value_trap_reason",
        "current_price", "upside_potential",
        "rank_in_sp500",
    ]
    available = [c for c in score_cols if c in rank_df.columns]
    score_subset = rank_df[available]

    portfolio = positions.merge(
        score_subset, on="ticker", how="left", suffixes=("_moomoo", "")
    )

    # current_priceはmoomoo側を正とする（リアルタイム性が高い）
    if "current_price_moomoo" in portfolio.columns:
        portfolio["current_price"] = portfolio["current_price_moomoo"].fillna(
            portfolio.get("current_price")
        )
        portfolio.drop(columns=["current_price_moomoo"], inplace=True)

    if "total_score" in portfolio.columns:
        not_scored = portfolio["total_score"].isna()
        if not_scored.any():
            missing = portfolio.loc[not_scored, "ticker"].tolist()
            logger.info(f"スコアなし銘柄（S&P500外の可能性）: {missing}")
        return portfolio.sort_values(
            "total_score", ascending=False, na_position="last"
        )

    logger.warning("スコアリングデータとのマージに失敗しました")
    return portfolio
