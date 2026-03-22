"""broker/client.py のユニットテスト"""

from unittest.mock import patch, MagicMock

import pytest


class TestOpenTradeContext:
    """open_trade_context() のテスト"""

    @patch("stock_ranking.broker.client.BROKER_HOST", "127.0.0.1")
    @patch("stock_ranking.broker.client.BROKER_PORT", 11111)
    def test_normal_open_and_close(self):
        """コンテキストマネージャが正常にopen/closeする"""
        mock_ctx = MagicMock()
        mock_open_sec = MagicMock(return_value=mock_ctx)
        mock_trd_market = MagicMock()
        mock_trd_market.US = "US"

        with patch.dict("sys.modules", {
            "moomoo": MagicMock(
                OpenSecTradeContext=mock_open_sec,
                TrdMarket=mock_trd_market,
            ),
        }):
            from importlib import reload
            import stock_ranking.broker.client as client_mod
            reload(client_mod)

            with client_mod.open_trade_context() as ctx:
                assert ctx is mock_ctx

            mock_ctx.close.assert_called_once()

    def test_moomoo_not_installed_raises_runtime_error(self):
        """moomoo未インストール時にRuntimeErrorを送出する"""
        import sys
        # moomooモジュールを一時的に除去してImportErrorを発生させる
        saved = sys.modules.get("moomoo")
        sys.modules["moomoo"] = None  # Noneにするとimportでエラー

        try:
            from importlib import reload
            import stock_ranking.broker.client as client_mod
            reload(client_mod)

            with pytest.raises(RuntimeError, match="moomoo-api"):
                with client_mod.open_trade_context() as ctx:
                    pass
        finally:
            if saved is not None:
                sys.modules["moomoo"] = saved
            else:
                sys.modules.pop("moomoo", None)

    @patch("stock_ranking.broker.client.BROKER_HOST", "127.0.0.1")
    @patch("stock_ranking.broker.client.BROKER_PORT", 11111)
    def test_opend_connection_failure_raises_runtime_error(self):
        """OpenD接続失敗時にRuntimeErrorを送出する"""
        mock_trd_market = MagicMock()
        mock_trd_market.US = "US"

        def raise_conn_error(**kwargs):
            raise ConnectionRefusedError("接続拒否")

        with patch.dict("sys.modules", {
            "moomoo": MagicMock(
                OpenSecTradeContext=raise_conn_error,
                TrdMarket=mock_trd_market,
            ),
        }):
            from importlib import reload
            import stock_ranking.broker.client as client_mod
            reload(client_mod)

            with pytest.raises(RuntimeError, match="OpenDに接続できません"):
                with client_mod.open_trade_context() as ctx:
                    pass

    @patch("stock_ranking.broker.client.BROKER_HOST", "127.0.0.1")
    @patch("stock_ranking.broker.client.BROKER_PORT", 11111)
    def test_close_called_even_on_exception(self):
        """with内で例外が発生してもcloseが呼ばれる"""
        mock_ctx = MagicMock()
        mock_open_sec = MagicMock(return_value=mock_ctx)
        mock_trd_market = MagicMock()
        mock_trd_market.US = "US"

        with patch.dict("sys.modules", {
            "moomoo": MagicMock(
                OpenSecTradeContext=mock_open_sec,
                TrdMarket=mock_trd_market,
            ),
        }):
            from importlib import reload
            import stock_ranking.broker.client as client_mod
            reload(client_mod)

            with pytest.raises(ValueError):
                with client_mod.open_trade_context() as ctx:
                    raise ValueError("テスト例外")

            mock_ctx.close.assert_called_once()
