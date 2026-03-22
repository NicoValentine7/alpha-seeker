"""発注安全チェック（Phase 1: dry-run検証のみ、Phase 2/3で実発注ガードとして使用）"""

import logging
from dataclasses import dataclass

from stock_ranking.config import BROKER_DRY_RUN, BROKER_MAX_POSITION_PCT

logger = logging.getLogger(__name__)


@dataclass
class OrderIntent:
    """発注意図を表すデータクラス"""

    ticker: str
    quantity: int
    side: str  # "BUY" or "SELL"
    price: float | None = None  # Noneは成行（原則禁止）
    reason: str = ""  # スコアベースの発注根拠


def validate_order(
    intent: OrderIntent, total_assets: float = 0.0
) -> tuple[bool, str]:
    """発注前バリデーション。

    Returns:
        (is_valid, message): バリデーション結果とメッセージ
    """
    # 数量チェック（dry-run含め常に実行）
    if intent.quantity <= 0:
        return False, "数量は1以上を指定してください"

    # 指値必須チェック
    if intent.price is None:
        return False, "成行注文は禁止です。指値を指定してください"

    # ポジション上限チェック
    if total_assets > 0 and intent.price:
        order_value = intent.quantity * intent.price
        position_pct = order_value / total_assets
        if position_pct > BROKER_MAX_POSITION_PCT:
            return False, (
                f"ポジション上限超過: {position_pct:.1%} > "
                f"{BROKER_MAX_POSITION_PCT:.1%}"
            )

    # dry-runモードの場合は実発注をスキップ
    if BROKER_DRY_RUN:
        logger.info(f"[DRY-RUN] {intent}")
        return True, "dry-runモード: 実発注はスキップ"

    return True, "バリデーション通過"
