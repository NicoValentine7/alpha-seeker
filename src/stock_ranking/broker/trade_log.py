"""発注履歴ログの永続化"""

import csv
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

LOG_DIR = Path(__file__).resolve().parent.parent.parent.parent / "output"
LOG_FILE = "trade_log.csv"

COLUMNS = [
    "timestamp",
    "ticker",
    "side",
    "quantity",
    "price",
    "order_value",
    "status",
    "order_id",
    "reason",
    "message",
    "mode",
]


def log_trade(result: dict, dry_run: bool = True):
    """発注結果を trade_log.csv に追記する。

    Args:
        result: _place_single_order() の戻り値
        dry_run: dry-runモードか否か
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / LOG_FILE

    # ファイルが存在しなければヘッダー付きで作成
    write_header = not path.exists()

    qty = result.get("quantity", 0)
    price = result.get("price", 0)

    row = {
        "timestamp": result.get("timestamp", datetime.now().isoformat()),
        "ticker": result.get("ticker", ""),
        "side": result.get("side", ""),
        "quantity": qty,
        "price": price,
        "order_value": qty * price if qty and price else 0,
        "status": result.get("status", ""),
        "order_id": result.get("order_id", ""),
        "reason": result.get("reason", ""),
        "message": result.get("message", ""),
        "mode": "DRY-RUN" if dry_run else "REAL",
    }

    try:
        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            if write_header:
                writer.writeheader()
            writer.writerow(row)
        logger.info(f"取引ログ記録: {row['ticker']} {row['side']} → {row['status']}")
    except Exception as e:
        logger.warning(f"取引ログ書き込み失敗: {e}")


def get_trade_history(limit: int = 50) -> list[dict]:
    """直近の取引履歴を取得する。

    Args:
        limit: 取得する最大件数（最新から）

    Returns:
        取引ログのリスト（新しい順）
    """
    path = LOG_DIR / LOG_FILE
    if not path.exists():
        return []

    try:
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        return rows[-limit:][::-1]  # 最新順
    except Exception as e:
        logger.warning(f"取引ログ読み込み失敗: {e}")
        return []
