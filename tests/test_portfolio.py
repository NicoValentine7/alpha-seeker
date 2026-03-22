"""broker/portfolio.py のユニットテスト"""

from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from stock_ranking.broker.portfolio import fetch_positions, get_portfolio


def _make_moomoo_positions_df() -> pd.DataFrame:
    """moomoo APIが返す形式のダミーポジションDataFrame"""
    return pd.DataFrame({
        "code": ["US.AAPL", "US.MSFT", "US.GOOG"],
        "stock_name": ["Apple Inc", "Microsoft Corp", "Alphabet Inc"],
        "qty": [100, 50, 30],
        "cost_price": [150.0, 350.0, 140.0],
        "nominal_price": [200.0, 400.0, 170.0],
        "market_val": [20000.0, 20000.0, 5100.0],
        "pl_val": [5000.0, 2500.0, 900.0],
        "pl_ratio": [0.33, 0.14, 0.21],
    })


def _make_ranking_df() -> pd.DataFrame:
    """スコアリング済みランキングDataFrame（1始まりindex）"""
    df = pd.DataFrame({
        "ticker": ["NVDA", "AAPL", "MSFT", "AMZN", "META"],
        "name": ["NVIDIA", "Apple", "Microsoft", "Amazon", "Meta"],
        "sector": ["Technology"] * 5,
        "total_score": [90.0, 80.0, 75.0, 70.0, 65.0],
        "valuation_score": [85.0, 70.0, 65.0, 60.0, 55.0],
        "growth_score": [95.0, 85.0, 80.0, 75.0, 70.0],
        "quality_score": [88.0, 78.0, 72.0, 68.0, 62.0],
        "earnings_momentum_score": [92.0, 82.0, 77.0, 72.0, 67.0],
        "current_price": [800.0, 200.0, 400.0, 180.0, 500.0],
    })
    df.index = range(1, len(df) + 1)  # 1始まりindex（rank_in_sp500用）
    return df


class TestFetchPositions:
    """fetch_positions() のテスト"""

    @patch("stock_ranking.broker.portfolio.open_trade_context")
    def test_normal_positions(self, mock_ctx_manager):
        """正常系: moomooからポジションを取得してDataFrameに変換"""
        mock_ret_ok = 0
        mock_ctx = MagicMock()
        mock_ctx.position_list_query.return_value = (
            mock_ret_ok,
            _make_moomoo_positions_df(),
        )
        mock_ctx_manager.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx_manager.return_value.__exit__ = MagicMock(return_value=False)

        with patch("stock_ranking.broker.portfolio.RET_OK", mock_ret_ok, create=True):
            with patch.dict("sys.modules", {
                "moomoo": MagicMock(RET_OK=mock_ret_ok),
            }):
                result = fetch_positions()

        assert not result.empty
        assert "ticker" in result.columns
        assert list(result["ticker"]) == ["AAPL", "MSFT", "GOOG"]

    @patch("stock_ranking.broker.portfolio.open_trade_context")
    def test_ticker_conversion_us_prefix_removed(self, mock_ctx_manager):
        """'US.AAPL' → 'AAPL' のプレフィックス除去"""
        mock_ret_ok = 0
        mock_ctx = MagicMock()
        data = pd.DataFrame({
            "code": ["US.TSLA", "US.AMZN"],
            "qty": [10, 20],
            "cost_price": [250.0, 170.0],
            "nominal_price": [300.0, 180.0],
            "market_val": [3000.0, 3600.0],
            "pl_val": [500.0, 200.0],
            "pl_ratio": [0.20, 0.06],
        })
        mock_ctx.position_list_query.return_value = (mock_ret_ok, data)
        mock_ctx_manager.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx_manager.return_value.__exit__ = MagicMock(return_value=False)

        with patch.dict("sys.modules", {
            "moomoo": MagicMock(RET_OK=mock_ret_ok),
        }):
            result = fetch_positions()

        assert list(result["ticker"]) == ["TSLA", "AMZN"]
        # US.プレフィックスが残っていないことを確認
        assert not result["ticker"].str.contains(r"^US\.", regex=True).any()

    @patch("stock_ranking.broker.portfolio.open_trade_context")
    def test_empty_positions_returns_empty_df(self, mock_ctx_manager):
        """ポジションなしの場合、空のDataFrameを返す"""
        mock_ret_ok = 0
        mock_ctx = MagicMock()
        mock_ctx.position_list_query.return_value = (mock_ret_ok, pd.DataFrame())
        mock_ctx_manager.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx_manager.return_value.__exit__ = MagicMock(return_value=False)

        with patch.dict("sys.modules", {
            "moomoo": MagicMock(RET_OK=mock_ret_ok),
        }):
            result = fetch_positions()

        assert result.empty

    @patch("stock_ranking.broker.portfolio.open_trade_context")
    def test_api_query_failure_returns_empty_df(self, mock_ctx_manager):
        """API応答がRET_OK以外の場合、空のDataFrameを返す"""
        mock_ret_ok = 0
        mock_ret_error = -1
        mock_ctx = MagicMock()
        mock_ctx.position_list_query.return_value = (
            mock_ret_error,
            "サーバーエラー",
        )
        mock_ctx_manager.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx_manager.return_value.__exit__ = MagicMock(return_value=False)

        with patch.dict("sys.modules", {
            "moomoo": MagicMock(RET_OK=mock_ret_ok),
        }):
            result = fetch_positions()

        assert result.empty

    @patch("stock_ranking.broker.portfolio.open_trade_context")
    def test_connection_exception_returns_empty_df(self, mock_ctx_manager):
        """OpenD接続例外時、空のDataFrameを返す（RuntimeError以外）"""
        mock_ctx_manager.return_value.__enter__ = MagicMock(
            side_effect=Exception("ネットワークエラー")
        )
        mock_ctx_manager.return_value.__exit__ = MagicMock(return_value=False)

        with patch.dict("sys.modules", {
            "moomoo": MagicMock(RET_OK=0),
        }):
            result = fetch_positions()

        assert result.empty

    def test_moomoo_not_installed_raises_runtime_error(self):
        """moomoo未インストール時にRuntimeErrorを送出する"""
        import sys
        saved = sys.modules.get("moomoo")
        sys.modules["moomoo"] = None

        try:
            with pytest.raises(RuntimeError, match="moomoo-api"):
                fetch_positions()
        finally:
            if saved is not None:
                sys.modules["moomoo"] = saved
            else:
                sys.modules.pop("moomoo", None)

    @patch("stock_ranking.broker.portfolio.open_trade_context")
    def test_runtime_error_propagates(self, mock_ctx_manager):
        """RuntimeErrorは握りつぶさず伝搬する"""
        mock_ctx_manager.return_value.__enter__ = MagicMock(
            side_effect=RuntimeError("OpenD接続失敗")
        )
        mock_ctx_manager.return_value.__exit__ = MagicMock(return_value=False)

        with patch.dict("sys.modules", {
            "moomoo": MagicMock(RET_OK=0),
        }):
            with pytest.raises(RuntimeError, match="OpenD接続失敗"):
                fetch_positions()


class TestGetPortfolio:
    """get_portfolio() のテスト"""

    @patch("stock_ranking.broker.portfolio.fetch_positions")
    def test_merge_with_ranking(self, mock_fetch):
        """ランキングDFとポジションDFが正しくマージされる"""
        mock_fetch.return_value = pd.DataFrame({
            "ticker": ["AAPL", "MSFT"],
            "quantity": [100, 50],
            "cost_price": [150.0, 350.0],
            "current_price": [200.0, 400.0],
            "market_val": [20000.0, 20000.0],
            "unrealized_pl": [5000.0, 2500.0],
            "unrealized_pl_pct": [0.33, 0.14],
        })

        ranking_df = _make_ranking_df()
        result = get_portfolio(ranking_df)

        assert not result.empty
        assert "total_score" in result.columns
        assert "quantity" in result.columns
        # AAPLのスコア80 > MSFTの75 → AAPLが先（降順ソート）
        assert result.iloc[0]["ticker"] == "AAPL"
        assert result.iloc[1]["ticker"] == "MSFT"

    @patch("stock_ranking.broker.portfolio.fetch_positions")
    def test_sp500_outside_ticker_has_nan_score(self, mock_fetch):
        """S&P500外の銘柄はtotal_scoreがNaNになる"""
        mock_fetch.return_value = pd.DataFrame({
            "ticker": ["AAPL", "ZZZZ"],  # ZZZZはランキングに存在しない
            "quantity": [100, 25],
            "cost_price": [150.0, 50.0],
            "current_price": [200.0, 55.0],
            "market_val": [20000.0, 1375.0],
            "unrealized_pl": [5000.0, 125.0],
            "unrealized_pl_pct": [0.33, 0.10],
        })

        ranking_df = _make_ranking_df()
        result = get_portfolio(ranking_df)

        zzzz_row = result[result["ticker"] == "ZZZZ"]
        assert len(zzzz_row) == 1
        assert pd.isna(zzzz_row.iloc[0]["total_score"])

        # NaN銘柄はソート末尾に来る（na_position="last"）
        assert result.iloc[-1]["ticker"] == "ZZZZ"

    @patch("stock_ranking.broker.portfolio.fetch_positions")
    def test_empty_positions_returns_empty_df(self, mock_fetch):
        """ポジションが空の場合、空のDataFrameを返す"""
        mock_fetch.return_value = pd.DataFrame()

        ranking_df = _make_ranking_df()
        result = get_portfolio(ranking_df)

        assert result.empty

    @patch("stock_ranking.broker.portfolio.fetch_positions")
    def test_rank_in_sp500_column_assigned(self, mock_fetch):
        """rank_in_sp500カラムが正しく付与される"""
        mock_fetch.return_value = pd.DataFrame({
            "ticker": ["AAPL", "MSFT"],
            "quantity": [100, 50],
            "cost_price": [150.0, 350.0],
            "current_price": [200.0, 400.0],
            "market_val": [20000.0, 20000.0],
            "unrealized_pl": [5000.0, 2500.0],
            "unrealized_pl_pct": [0.33, 0.14],
        })

        ranking_df = _make_ranking_df()
        result = get_portfolio(ranking_df)

        assert "rank_in_sp500" in result.columns
        # AAPLはランキングindex=2, MSFTは3
        aapl_rank = result[result["ticker"] == "AAPL"]["rank_in_sp500"].iloc[0]
        msft_rank = result[result["ticker"] == "MSFT"]["rank_in_sp500"].iloc[0]
        assert aapl_rank == 2
        assert msft_rank == 3

    @patch("stock_ranking.broker.portfolio.fetch_positions")
    def test_current_price_uses_moomoo_value(self, mock_fetch):
        """current_priceはmoomoo側の値が優先される"""
        mock_fetch.return_value = pd.DataFrame({
            "ticker": ["AAPL"],
            "quantity": [100],
            "cost_price": [150.0],
            "current_price": [205.0],  # moomoo側: 205
            "market_val": [20500.0],
            "unrealized_pl": [5500.0],
            "unrealized_pl_pct": [0.37],
        })

        ranking_df = _make_ranking_df()  # ランキング側AAPLのcurrent_price=200
        result = get_portfolio(ranking_df)

        aapl_price = result[result["ticker"] == "AAPL"]["current_price"].iloc[0]
        assert aapl_price == 205.0  # moomoo側を採用

    @patch("stock_ranking.broker.portfolio.fetch_positions")
    def test_sort_descending_by_total_score(self, mock_fetch):
        """total_scoreの降順でソートされる"""
        mock_fetch.return_value = pd.DataFrame({
            "ticker": ["META", "NVDA", "AAPL"],
            "quantity": [20, 10, 100],
            "cost_price": [300.0, 500.0, 150.0],
            "current_price": [500.0, 800.0, 200.0],
            "market_val": [10000.0, 8000.0, 20000.0],
            "unrealized_pl": [4000.0, 3000.0, 5000.0],
            "unrealized_pl_pct": [0.67, 0.60, 0.33],
        })

        ranking_df = _make_ranking_df()
        result = get_portfolio(ranking_df)

        scores = result["total_score"].tolist()
        assert scores == sorted(scores, reverse=True)
        assert result.iloc[0]["ticker"] == "NVDA"  # 90点
