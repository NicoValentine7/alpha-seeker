"""broker/signal.py のユニットテスト"""

import pandas as pd
import pytest

from stock_ranking.broker.safety import OrderIntent
from stock_ranking.broker.signal import (
    generate_signals,
    _generate_buy_signals,
    _generate_sell_signals,
    _generate_rebalance_signals,
)


def _make_ranking_df(rows: list[dict]) -> pd.DataFrame:
    """テスト用のランキングDFを作成する"""
    df = pd.DataFrame(rows)
    df.index = range(1, len(df) + 1)
    return df


def _make_portfolio_df(rows: list[dict]) -> pd.DataFrame:
    """テスト用のポートフォリオDFを作成する"""
    return pd.DataFrame(rows)


class TestGenerateBuySignals:
    def test_high_score_unowned_generates_buy(self):
        ranking = _make_ranking_df([
            {"ticker": "AAPL", "total_score": 85.0, "current_price": 200.0},
            {"ticker": "MSFT", "total_score": 72.0, "current_price": 400.0},
            {"ticker": "GOOG", "total_score": 50.0, "current_price": 150.0},
        ])
        held = set()
        signals = _generate_buy_signals(ranking, held, total_assets=100_000)

        assert len(signals) == 2  # AAPL(85), MSFT(72) >= 70
        assert all(s.side == "BUY" for s in signals)
        assert signals[0].ticker == "AAPL"
        assert signals[1].ticker == "MSFT"

    def test_already_held_excluded(self):
        ranking = _make_ranking_df([
            {"ticker": "AAPL", "total_score": 85.0, "current_price": 200.0},
        ])
        held = {"AAPL"}
        signals = _generate_buy_signals(ranking, held, total_assets=100_000)

        assert len(signals) == 0

    def test_low_score_excluded(self):
        ranking = _make_ranking_df([
            {"ticker": "AAPL", "total_score": 60.0, "current_price": 200.0},
        ])
        signals = _generate_buy_signals(ranking, set(), total_assets=100_000)

        assert len(signals) == 0

    def test_quantity_calculation(self):
        ranking = _make_ranking_df([
            {"ticker": "AAPL", "total_score": 80.0, "current_price": 200.0},
        ])
        # total_assets=100k, max_position=10% → budget=10k, qty=10k/200=50
        signals = _generate_buy_signals(ranking, set(), total_assets=100_000)

        assert len(signals) == 1
        assert signals[0].quantity == 50
        assert signals[0].price == 200.0

    def test_zero_price_skipped(self):
        ranking = _make_ranking_df([
            {"ticker": "AAPL", "total_score": 80.0, "current_price": 0.0},
        ])
        signals = _generate_buy_signals(ranking, set(), total_assets=100_000)

        assert len(signals) == 0

    def test_nan_price_skipped(self):
        ranking = _make_ranking_df([
            {"ticker": "AAPL", "total_score": 80.0, "current_price": float("nan")},
        ])
        signals = _generate_buy_signals(ranking, set(), total_assets=100_000)

        assert len(signals) == 0

    def test_top_n_limit(self):
        rows = [
            {"ticker": f"T{i}", "total_score": 90.0 - i, "current_price": 100.0}
            for i in range(10)
        ]
        ranking = _make_ranking_df(rows)
        signals = _generate_buy_signals(ranking, set(), total_assets=100_000)

        # SIGNAL_BUY_TOP_N = 5
        assert len(signals) == 5


class TestGenerateSellSignals:
    def test_low_score_generates_sell(self):
        portfolio = _make_portfolio_df([
            {"ticker": "BAD", "total_score": 20.0, "current_price": 50.0,
             "quantity": 100, "is_value_trap": False},
        ])
        signals = _generate_sell_signals(portfolio)

        assert len(signals) == 1
        assert signals[0].side == "SELL"
        assert signals[0].ticker == "BAD"
        assert signals[0].quantity == 100

    def test_value_trap_generates_sell(self):
        portfolio = _make_portfolio_df([
            {"ticker": "TRAP", "total_score": 60.0, "current_price": 100.0,
             "quantity": 50, "is_value_trap": True,
             "value_trap_reason": "売上3Q連続減少; "},
        ])
        signals = _generate_sell_signals(portfolio)

        assert len(signals) == 1
        assert "バリュートラップ" in signals[0].reason

    def test_high_score_no_sell(self):
        portfolio = _make_portfolio_df([
            {"ticker": "GOOD", "total_score": 80.0, "current_price": 200.0,
             "quantity": 30, "is_value_trap": False},
        ])
        signals = _generate_sell_signals(portfolio)

        assert len(signals) == 0

    def test_zero_quantity_skipped(self):
        portfolio = _make_portfolio_df([
            {"ticker": "BAD", "total_score": 10.0, "current_price": 50.0,
             "quantity": 0, "is_value_trap": False},
        ])
        signals = _generate_sell_signals(portfolio)

        assert len(signals) == 0

    def test_empty_portfolio(self):
        signals = _generate_sell_signals(pd.DataFrame())

        assert len(signals) == 0


class TestGenerateRebalanceSignals:
    def test_overweight_generates_sell(self):
        portfolio = _make_portfolio_df([
            {"ticker": "A", "total_score": 50.0, "current_price": 100.0,
             "market_val": 8000, "quantity": 80},
            {"ticker": "B", "total_score": 50.0, "current_price": 100.0,
             "market_val": 2000, "quantity": 20},
        ])
        signals = _generate_rebalance_signals(portfolio, total_assets=10_000)

        # A: 80%→50%, B: 20%→50% → 大きな乖離
        assert len(signals) >= 1

    def test_balanced_no_signals(self):
        # 10銘柄で均等保有 → 各10%ウェイト → clip(10%)と一致 → シグナルなし
        rows = [
            {"ticker": f"T{i}", "total_score": 50.0, "current_price": 100.0,
             "market_val": 1000, "quantity": 10}
            for i in range(10)
        ]
        portfolio = _make_portfolio_df(rows)
        signals = _generate_rebalance_signals(portfolio, total_assets=10_000)

        assert len(signals) == 0

    def test_empty_portfolio(self):
        signals = _generate_rebalance_signals(pd.DataFrame(), total_assets=10_000)

        assert len(signals) == 0


class TestGenerateSignals:
    def test_integration_sell_before_buy(self):
        ranking = _make_ranking_df([
            {"ticker": "GOOD", "total_score": 85.0, "current_price": 200.0},
            {"ticker": "BAD", "total_score": 15.0, "current_price": 50.0},
        ])
        portfolio = _make_portfolio_df([
            {"ticker": "BAD", "total_score": 15.0, "current_price": 50.0,
             "quantity": 100, "market_val": 5000, "is_value_trap": False,
             "rank_in_sp500": 400},
        ])

        signals = generate_signals(ranking, portfolio, total_assets=100_000)

        # 売りシグナルが先に来る
        sell_signals = [s for s in signals if s.side == "SELL"]
        buy_signals = [s for s in signals if s.side == "BUY"]
        assert len(sell_signals) >= 1
        assert len(buy_signals) >= 1

        # 売りは買いより前にある
        first_sell_idx = next(i for i, s in enumerate(signals) if s.side == "SELL")
        first_buy_idx = next(i for i, s in enumerate(signals) if s.side == "BUY")
        assert first_sell_idx < first_buy_idx

    def test_zero_assets_returns_empty(self):
        ranking = _make_ranking_df([
            {"ticker": "AAPL", "total_score": 85.0, "current_price": 200.0},
        ])
        signals = generate_signals(ranking, pd.DataFrame(), total_assets=0)

        assert len(signals) == 0

    def test_all_order_intents_have_price(self):
        ranking = _make_ranking_df([
            {"ticker": "AAPL", "total_score": 85.0, "current_price": 200.0},
        ])
        signals = generate_signals(ranking, pd.DataFrame(), total_assets=100_000)

        for s in signals:
            assert s.price is not None
            assert s.price > 0
