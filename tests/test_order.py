"""broker/order.py のユニットテスト"""

import io
from unittest.mock import patch, MagicMock

import pytest

from stock_ranking.broker.safety import OrderIntent


def _make_intent(
    ticker: str = "AAPL",
    quantity: int = 10,
    side: str = "BUY",
    price: float = 200.0,
    reason: str = "スコア80超",
) -> OrderIntent:
    """テスト用のOrderIntentを作成する"""
    return OrderIntent(
        ticker=ticker,
        quantity=quantity,
        side=side,
        price=price,
        reason=reason,
    )


class TestDisplayOrderSummary:
    """_display_order_summary のテスト"""

    @patch("stock_ranking.broker.order.BROKER_DRY_RUN", True)
    def test_buy_intent_displayed(self, capsys):
        from stock_ranking.broker.order import _display_order_summary

        intents = [_make_intent(side="BUY", ticker="AAPL", price=200.0, quantity=10)]
        _display_order_summary(intents)

        captured = capsys.readouterr().out
        assert "[DRY-RUN]" in captured
        assert "買い提案" in captured
        assert "AAPL" in captured
        assert "1件" in captured

    @patch("stock_ranking.broker.order.BROKER_DRY_RUN", False)
    def test_sell_intent_displayed(self, capsys):
        from stock_ranking.broker.order import _display_order_summary

        intents = [_make_intent(side="SELL", ticker="MSFT", price=400.0, quantity=5)]
        _display_order_summary(intents)

        captured = capsys.readouterr().out
        assert "[REAL]" in captured
        assert "売り提案" in captured
        assert "MSFT" in captured

    @patch("stock_ranking.broker.order.BROKER_DRY_RUN", True)
    def test_mixed_buy_sell(self, capsys):
        from stock_ranking.broker.order import _display_order_summary

        intents = [
            _make_intent(side="BUY", ticker="AAPL", price=200.0, quantity=10),
            _make_intent(side="SELL", ticker="MSFT", price=400.0, quantity=5),
        ]
        _display_order_summary(intents)

        captured = capsys.readouterr().out
        assert "買い提案" in captured
        assert "売り提案" in captured
        assert "買い総額" in captured
        assert "売り総額" in captured


class TestDisplayResultsSummary:
    """_display_results_summary のテスト"""

    @patch("stock_ranking.broker.order.BROKER_DRY_RUN", True)
    def test_simulated_result(self, capsys):
        from stock_ranking.broker.order import _display_results_summary

        results = [
            {"ticker": "AAPL", "side": "BUY", "status": "simulated",
             "message": "dry-runモード"},
        ]
        _display_results_summary(results)

        captured = capsys.readouterr().out
        assert "[SIM]" in captured
        assert "実行: 1件" in captured

    def test_mixed_statuses(self, capsys):
        from stock_ranking.broker.order import _display_results_summary

        results = [
            {"ticker": "AAPL", "side": "BUY", "status": "submitted",
             "message": "注文送信成功"},
            {"ticker": "MSFT", "side": "SELL", "status": "rejected",
             "message": "数量不正"},
            {"ticker": "GOOG", "side": "BUY", "status": "skipped",
             "message": "ユーザーがスキップ"},
        ]
        _display_results_summary(results)

        captured = capsys.readouterr().out
        assert "[OK]" in captured
        assert "[NG]" in captured
        assert "[--]" in captured
        assert "実行: 1件" in captured
        assert "拒否: 1件" in captured
        assert "スキップ: 1件" in captured

    def test_empty_results_no_output(self, capsys):
        from stock_ranking.broker.order import _display_results_summary

        _display_results_summary([])
        captured = capsys.readouterr().out
        assert captured == ""

    def test_error_status(self, capsys):
        from stock_ranking.broker.order import _display_results_summary

        results = [
            {"ticker": "AAPL", "side": "BUY", "status": "error",
             "message": "接続エラー"},
        ]
        _display_results_summary(results)

        captured = capsys.readouterr().out
        assert "[ERR]" in captured


class TestExecuteOrdersWithConfirmation:
    """execute_orders_with_confirmation のテスト"""

    @patch("stock_ranking.broker.order.BROKER_DRY_RUN", True)
    @patch("stock_ranking.broker.order.validate_order", return_value=(True, "dry-runモード"))
    @patch("stock_ranking.broker.order._confirm_order", return_value=True)
    @patch("stock_ranking.broker.order._confirm_all", return_value=True)
    def test_dry_run_no_api_calls(self, mock_confirm_all, mock_confirm_order,
                                   mock_validate, capsys):
        from stock_ranking.broker.order import execute_orders_with_confirmation

        intents = [_make_intent()]
        results = execute_orders_with_confirmation(intents, total_assets=100_000)

        assert len(results) == 1
        assert results[0]["status"] == "simulated"
        assert "dry-run" in results[0]["message"]

    @patch("stock_ranking.broker.order.BROKER_DRY_RUN", True)
    @patch("stock_ranking.broker.order._confirm_all", return_value=False)
    def test_user_cancels_all(self, mock_confirm_all, capsys):
        from stock_ranking.broker.order import execute_orders_with_confirmation

        intents = [_make_intent()]
        results = execute_orders_with_confirmation(intents, total_assets=100_000)

        assert results == []
        captured = capsys.readouterr().out
        assert "キャンセル" in captured

    @patch("stock_ranking.broker.order.BROKER_DRY_RUN", True)
    @patch("stock_ranking.broker.order.validate_order", return_value=(True, "OK"))
    @patch("stock_ranking.broker.order._confirm_order", return_value=False)
    @patch("stock_ranking.broker.order._confirm_all", return_value=True)
    def test_user_skips_individual_order(self, mock_confirm_all, mock_confirm_order,
                                         mock_validate, capsys):
        from stock_ranking.broker.order import execute_orders_with_confirmation

        intents = [_make_intent()]
        results = execute_orders_with_confirmation(intents, total_assets=100_000)

        assert len(results) == 1
        assert results[0]["status"] == "skipped"

    @patch("stock_ranking.broker.order.BROKER_DRY_RUN", True)
    @patch("stock_ranking.broker.order.validate_order",
           return_value=(False, "数量は1以上を指定してください"))
    @patch("stock_ranking.broker.order._confirm_all", return_value=True)
    def test_validation_rejection(self, mock_confirm_all, mock_validate, capsys):
        from stock_ranking.broker.order import execute_orders_with_confirmation

        intents = [_make_intent(quantity=0)]
        results = execute_orders_with_confirmation(intents, total_assets=100_000)

        assert len(results) == 1
        assert results[0]["status"] == "rejected"

    def test_empty_intents(self, capsys):
        from stock_ranking.broker.order import execute_orders_with_confirmation

        results = execute_orders_with_confirmation([], total_assets=100_000)
        assert results == []
        captured = capsys.readouterr().out
        assert "シグナルはありません" in captured


class TestSessionLimit:
    """セッション上限のテスト"""

    @patch("stock_ranking.broker.order.BROKER_DRY_RUN", True)
    @patch("stock_ranking.broker.order.SIGNAL_MAX_ORDERS_PER_SESSION", 3)
    @patch("stock_ranking.broker.order.validate_order", return_value=(True, "OK"))
    @patch("stock_ranking.broker.order._confirm_order", return_value=True)
    @patch("stock_ranking.broker.order._confirm_all", return_value=True)
    def test_exceeding_session_limit_truncates(self, mock_confirm_all,
                                                mock_confirm_order,
                                                mock_validate, capsys):
        from stock_ranking.broker.order import execute_orders_with_confirmation

        intents = [_make_intent(ticker=f"T{i}") for i in range(5)]
        results = execute_orders_with_confirmation(intents, total_assets=100_000)

        # 5件 → 3件に制限される
        assert len(results) == 3

    @patch("stock_ranking.broker.order.BROKER_DRY_RUN", True)
    @patch("stock_ranking.broker.order.SIGNAL_MAX_ORDERS_PER_SESSION", 10)
    @patch("stock_ranking.broker.order.validate_order", return_value=(True, "OK"))
    @patch("stock_ranking.broker.order._confirm_order", return_value=True)
    @patch("stock_ranking.broker.order._confirm_all", return_value=True)
    def test_within_session_limit_no_truncation(self, mock_confirm_all,
                                                 mock_confirm_order,
                                                 mock_validate, capsys):
        from stock_ranking.broker.order import execute_orders_with_confirmation

        intents = [_make_intent(ticker=f"T{i}") for i in range(3)]
        results = execute_orders_with_confirmation(intents, total_assets=100_000)

        assert len(results) == 3


class TestConfirmAll:
    """_confirm_all のテスト"""

    @patch("stock_ranking.broker.order.BROKER_DRY_RUN", True)
    @patch("builtins.input", return_value="y")
    def test_confirm_yes(self, mock_input):
        from stock_ranking.broker.order import _confirm_all

        result = _confirm_all([_make_intent()])
        assert result is True

    @patch("stock_ranking.broker.order.BROKER_DRY_RUN", True)
    @patch("builtins.input", return_value="n")
    def test_confirm_no(self, mock_input):
        from stock_ranking.broker.order import _confirm_all

        result = _confirm_all([_make_intent()])
        assert result is False

    @patch("stock_ranking.broker.order.BROKER_DRY_RUN", True)
    @patch("builtins.input", side_effect=EOFError)
    def test_confirm_eof(self, mock_input):
        from stock_ranking.broker.order import _confirm_all

        result = _confirm_all([_make_intent()])
        assert result is False


class TestConfirmOrder:
    """_confirm_order のテスト"""

    @patch("builtins.input", return_value="y")
    def test_confirm_individual_yes(self, mock_input):
        from stock_ranking.broker.order import _confirm_order

        result = _confirm_order(_make_intent())
        assert result is True

    @patch("builtins.input", return_value="N")
    def test_confirm_individual_no(self, mock_input):
        from stock_ranking.broker.order import _confirm_order

        result = _confirm_order(_make_intent())
        assert result is False


class TestPlaceSingleOrder:
    """_place_single_order のテスト（dry-run）"""

    @patch("stock_ranking.broker.order.BROKER_DRY_RUN", True)
    def test_dry_run_returns_simulated(self, capsys):
        from stock_ranking.broker.order import _place_single_order

        result = _place_single_order(_make_intent())

        assert result["status"] == "simulated"
        assert result["ticker"] == "AAPL"
        assert "dry-run" in result["message"]
        captured = capsys.readouterr().out
        assert "[DRY-RUN]" in captured
