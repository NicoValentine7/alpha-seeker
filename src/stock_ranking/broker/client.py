"""OpenDゲートウェイへの接続管理"""

import logging
from contextlib import contextmanager
from typing import Generator

from stock_ranking.config import BROKER_HOST, BROKER_PORT

logger = logging.getLogger(__name__)


@contextmanager
def open_trade_context() -> Generator:
    """米国株取引コンテキストを開き、finally節で確実にcloseする。

    Usage:
        with open_trade_context() as ctx:
            ret, data = ctx.position_list_query()

    Raises:
        RuntimeError: moomoo-api未インストールまたはOpenD接続不可
    """
    try:
        from moomoo import OpenSecTradeContext, TrdMarket
    except ImportError as e:
        raise RuntimeError(
            "moomoo-api がインストールされていません。"
            "`uv add moomoo-api` を実行してください。"
        ) from e

    logger.info(f"OpenD接続中: {BROKER_HOST}:{BROKER_PORT}")
    try:
        ctx = OpenSecTradeContext(
            filter_trdmarket=TrdMarket.US,
            host=BROKER_HOST,
            port=BROKER_PORT,
        )
    except Exception as e:
        raise RuntimeError(
            f"OpenDに接続できません ({BROKER_HOST}:{BROKER_PORT})。"
            "OpenDが起動しているか確認してください。"
        ) from e

    try:
        yield ctx
    finally:
        ctx.close()
        logger.info("OpenD接続クローズ")
