"""broker/safety.py のユニットテスト"""

from unittest.mock import patch

import pytest

from stock_ranking.broker.safety import OrderIntent, validate_order


def _make_intent(
    ticker: str = "AAPL",
    quantity: int = 10,
    side: str = "BUY",
    price: float | None = 200.0,
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


class TestOrderIntent:
    """OrderIntentデータクラスのテスト"""

    def test_default_values(self):
        intent = OrderIntent(ticker="AAPL", quantity=10, side="BUY")
        assert intent.price is None
        assert intent.reason == ""

    def test_full_construction(self):
        intent = _make_intent(ticker="MSFT", quantity=5, side="SELL",
                              price=400.0, reason="スコア低下")
        assert intent.ticker == "MSFT"
        assert intent.quantity == 5
        assert intent.side == "SELL"
        assert intent.price == 400.0
        assert intent.reason == "スコア低下"

    def test_equality(self):
        a = _make_intent()
        b = _make_intent()
        assert a == b

    def test_inequality(self):
        a = _make_intent(ticker="AAPL")
        b = _make_intent(ticker="MSFT")
        assert a != b


class TestValidateOrderValid:
    """正常系: バリデーション通過のテスト"""

    @patch("stock_ranking.broker.safety.BROKER_DRY_RUN", True)
    def test_valid_buy_order_dry_run(self):
        intent = _make_intent(side="BUY", quantity=10, price=200.0)
        is_valid, msg = validate_order(intent, total_assets=100_000)

        assert is_valid is True
        assert "dry-run" in msg

    @patch("stock_ranking.broker.safety.BROKER_DRY_RUN", False)
    def test_valid_buy_order_real(self):
        intent = _make_intent(side="BUY", quantity=10, price=200.0)
        is_valid, msg = validate_order(intent, total_assets=100_000)

        assert is_valid is True
        assert "バリデーション通過" in msg

    @patch("stock_ranking.broker.safety.BROKER_DRY_RUN", False)
    def test_valid_sell_order(self):
        intent = _make_intent(side="SELL", quantity=5, price=400.0)
        is_valid, msg = validate_order(intent, total_assets=100_000)

        assert is_valid is True

    @patch("stock_ranking.broker.safety.BROKER_DRY_RUN", False)
    def test_valid_within_position_limit(self):
        # 10株 * $200 = $2,000 → $100,000の2% < 10%上限
        intent = _make_intent(quantity=10, price=200.0)
        is_valid, msg = validate_order(intent, total_assets=100_000)

        assert is_valid is True

    @patch("stock_ranking.broker.safety.BROKER_DRY_RUN", False)
    def test_valid_zero_total_assets_skips_position_check(self):
        # total_assets=0 の場合、ポジション上限チェックをスキップ
        intent = _make_intent(quantity=1000, price=500.0)
        is_valid, msg = validate_order(intent, total_assets=0)

        assert is_valid is True


class TestValidateOrderRejectsInvalid:
    """異常系: バリデーション拒否のテスト"""

    @patch("stock_ranking.broker.safety.BROKER_DRY_RUN", True)
    def test_zero_quantity_rejected(self):
        intent = _make_intent(quantity=0)
        is_valid, msg = validate_order(intent, total_assets=100_000)

        assert is_valid is False
        assert "数量は1以上" in msg

    @patch("stock_ranking.broker.safety.BROKER_DRY_RUN", True)
    def test_negative_quantity_rejected(self):
        intent = _make_intent(quantity=-5)
        is_valid, msg = validate_order(intent, total_assets=100_000)

        assert is_valid is False
        assert "数量は1以上" in msg

    @patch("stock_ranking.broker.safety.BROKER_DRY_RUN", True)
    def test_market_order_rejected(self):
        intent = _make_intent(price=None)
        is_valid, msg = validate_order(intent, total_assets=100_000)

        assert is_valid is False
        assert "成行注文は禁止" in msg

    @patch("stock_ranking.broker.safety.BROKER_DRY_RUN", False)
    @patch("stock_ranking.broker.safety.BROKER_MAX_POSITION_PCT", 0.10)
    def test_oversized_position_rejected(self):
        # 100株 * $200 = $20,000 → $100,000の20% > 10%上限
        intent = _make_intent(quantity=100, price=200.0)
        is_valid, msg = validate_order(intent, total_assets=100_000)

        assert is_valid is False
        assert "ポジション上限超過" in msg

    @patch("stock_ranking.broker.safety.BROKER_DRY_RUN", False)
    @patch("stock_ranking.broker.safety.BROKER_MAX_POSITION_PCT", 0.10)
    def test_exactly_at_limit_passes(self):
        # 50株 * $200 = $10,000 → $100,000の10% == 10%上限（超過していない）
        intent = _make_intent(quantity=50, price=200.0)
        is_valid, msg = validate_order(intent, total_assets=100_000)

        assert is_valid is True

    @patch("stock_ranking.broker.safety.BROKER_DRY_RUN", False)
    @patch("stock_ranking.broker.safety.BROKER_MAX_POSITION_PCT", 0.10)
    def test_slightly_over_limit_rejected(self):
        # 51株 * $200 = $10,200 → $100,000の10.2% > 10%上限
        intent = _make_intent(quantity=51, price=200.0)
        is_valid, msg = validate_order(intent, total_assets=100_000)

        assert is_valid is False
        assert "ポジション上限超過" in msg


class TestDryRunMode:
    """dry-runモードの動作テスト"""

    @patch("stock_ranking.broker.safety.BROKER_DRY_RUN", True)
    def test_dry_run_message_in_response(self):
        intent = _make_intent()
        is_valid, msg = validate_order(intent, total_assets=100_000)

        assert is_valid is True
        assert "dry-run" in msg
        assert "実発注はスキップ" in msg

    @patch("stock_ranking.broker.safety.BROKER_DRY_RUN", False)
    def test_real_mode_message(self):
        intent = _make_intent()
        is_valid, msg = validate_order(intent, total_assets=100_000)

        assert is_valid is True
        assert "バリデーション通過" in msg
        assert "dry-run" not in msg

    @patch("stock_ranking.broker.safety.BROKER_DRY_RUN", True)
    def test_dry_run_still_validates_quantity(self):
        """dry-runでも数量チェックは実行される"""
        intent = _make_intent(quantity=0)
        is_valid, msg = validate_order(intent, total_assets=100_000)

        assert is_valid is False

    @patch("stock_ranking.broker.safety.BROKER_DRY_RUN", True)
    def test_dry_run_still_validates_price(self):
        """dry-runでも指値チェックは実行される"""
        intent = _make_intent(price=None)
        is_valid, msg = validate_order(intent, total_assets=100_000)

        assert is_valid is False
