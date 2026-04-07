"""スコアリング結果に基づく売買シグナル生成"""

import logging

import pandas as pd

from stock_ranking.broker.safety import OrderIntent
from stock_ranking.config import (
    BROKER_MAX_POSITION_PCT,
    SIGNAL_BUY_MIN_SCORE,
    SIGNAL_BUY_TOP_N,
    SIGNAL_SELL_MAX_SCORE,
    SIGNAL_REBALANCE_THRESHOLD,
)

logger = logging.getLogger(__name__)


def _preferred_buy_score_column(ranking_df: pd.DataFrame) -> str | None:
    for col in ("overlay_buy_signal", "buy_signal", "total_score"):
        if col in ranking_df.columns:
            return col
    return None


def generate_signals(
    ranking_df: pd.DataFrame,
    portfolio_df: pd.DataFrame,
    total_assets: float,
) -> list[OrderIntent]:
    """スコアリング結果とポートフォリオを比較して売買シグナルを生成する。

    Args:
        ranking_df: スコアリング済みランキングDF（total_score列必須、1始まりindex）
        portfolio_df: get_portfolio()の戻り値（保有銘柄+スコア）
        total_assets: 口座総資産（USD）

    Returns:
        OrderIntentのリスト（優先度順: 売り → リバランス → 買い）
    """
    if total_assets <= 0:
        logger.warning("総資産が0以下のためシグナル生成をスキップ")
        return []

    signals: list[OrderIntent] = []

    # 売りシグナルを先に生成（資金確保のため）
    signals.extend(_generate_sell_signals(portfolio_df))

    # リバランスシグナル
    signals.extend(
        _generate_rebalance_signals(portfolio_df, total_assets)
    )

    # 買いシグナル
    held_tickers = set()
    if not portfolio_df.empty and "ticker" in portfolio_df.columns:
        held_tickers = set(portfolio_df["ticker"].tolist())
    signals.extend(
        _generate_buy_signals(ranking_df, held_tickers, total_assets)
    )

    return signals


def _generate_buy_signals(
    ranking_df: pd.DataFrame,
    held_tickers: set[str],
    total_assets: float,
) -> list[OrderIntent]:
    """高スコア未保有銘柄の買いシグナルを生成する。"""
    score_col = _preferred_buy_score_column(ranking_df)
    if score_col is None:
        return []

    # 高スコアかつ未保有の銘柄を抽出
    candidates = ranking_df[
        (ranking_df[score_col] >= SIGNAL_BUY_MIN_SCORE)
        & (~ranking_df["ticker"].isin(held_tickers))
    ].head(SIGNAL_BUY_TOP_N)

    signals = []
    position_budget = total_assets * BROKER_MAX_POSITION_PCT

    for _, row in candidates.iterrows():
        ticker = row["ticker"]
        price = row.get("current_price")
        score = row[score_col]

        if price is None or pd.isna(price) or price <= 0:
            continue

        # ポジション予算から数量を算出（端数切り捨て）
        qty = int(position_budget / price)
        if qty <= 0:
            continue

        score_label = {
            "overlay_buy_signal": "Overlay BUY",
            "buy_signal": "BUY",
            "total_score": "スコア",
        }.get(score_col, score_col)
        signals.append(OrderIntent(
            ticker=ticker,
            quantity=qty,
            side="BUY",
            price=round(price, 2),
            reason=f"{score_label}{score:.1f} ({SIGNAL_BUY_MIN_SCORE}以上、未保有)",
        ))

    return signals


def _generate_sell_signals(
    portfolio_df: pd.DataFrame,
) -> list[OrderIntent]:
    """低スコア保有銘柄・バリュートラップの売りシグナルを生成する。"""
    if portfolio_df.empty:
        return []

    signals = []

    for _, row in portfolio_df.iterrows():
        ticker = row["ticker"]
        score = row.get("total_score")
        is_trap = row.get("is_value_trap", False)
        qty = row.get("quantity", row.get("can_sell_qty", 0))
        price = row.get("current_price")

        if qty is None or pd.isna(qty) or int(qty) <= 0:
            continue
        if price is None or pd.isna(price) or price <= 0:
            continue

        reason = None

        # バリュートラップは最優先で売り
        if is_trap:
            trap_reason = row.get("value_trap_reason", "")
            reason = f"バリュートラップ検出: {trap_reason.rstrip('; ')}"
        # 低スコア銘柄
        elif score is not None and pd.notna(score) and score <= SIGNAL_SELL_MAX_SCORE:
            reason = f"スコア{score:.1f} ({SIGNAL_SELL_MAX_SCORE}以下)"

        if reason:
            signals.append(OrderIntent(
                ticker=ticker,
                quantity=int(qty),
                side="SELL",
                price=round(price, 2),
                reason=reason,
            ))

    return signals


def _generate_rebalance_signals(
    portfolio_df: pd.DataFrame,
    total_assets: float,
) -> list[OrderIntent]:
    """ウェイト調整のリバランスシグナルを生成する。

    スコアに基づく目標ウェイトと現在ウェイトの乖離が
    SIGNAL_REBALANCE_THRESHOLD以上の銘柄について調整シグナルを出す。
    """
    if portfolio_df.empty or total_assets <= 0:
        return []
    if "total_score" not in portfolio_df.columns:
        return []
    if "market_val" not in portfolio_df.columns:
        return []

    # スコアありの銘柄のみ対象
    scored = portfolio_df.dropna(subset=["total_score"]).copy()
    if scored.empty:
        return []

    # スコアベースの目標ウェイト（スコアに比例、上限BROKER_MAX_POSITION_PCT）
    score_sum = scored["total_score"].sum()
    if score_sum <= 0:
        return []

    scored = scored.copy()
    scored["target_weight"] = (
        scored["total_score"] / score_sum
    ).clip(upper=BROKER_MAX_POSITION_PCT)

    # 現在ウェイト
    total_mv = scored["market_val"].sum()
    if total_mv <= 0:
        return []
    scored["current_weight"] = scored["market_val"] / total_mv

    # 乖離チェック
    scored["weight_diff"] = scored["target_weight"] - scored["current_weight"]

    signals = []
    for _, row in scored.iterrows():
        diff = row["weight_diff"]
        if abs(diff) < SIGNAL_REBALANCE_THRESHOLD:
            continue

        ticker = row["ticker"]
        price = row.get("current_price")
        if price is None or pd.isna(price) or price <= 0:
            continue

        # 調整金額と数量
        adjust_value = diff * total_mv
        adjust_qty = int(abs(adjust_value) / price)
        if adjust_qty <= 0:
            continue

        side = "BUY" if diff > 0 else "SELL"
        signals.append(OrderIntent(
            ticker=ticker,
            quantity=adjust_qty,
            side=side,
            price=round(price, 2),
            reason=(
                f"リバランス: 現在{row['current_weight']:.1%} → "
                f"目標{row['target_weight']:.1%} (乖離{diff:+.1%})"
            ),
        ))

    return signals
