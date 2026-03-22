"""注文確認フロー・発注実行"""

import logging
from datetime import datetime

from stock_ranking.broker.client import open_trade_context
from stock_ranking.broker.safety import OrderIntent, validate_order
from stock_ranking.config import BROKER_DRY_RUN, SIGNAL_MAX_ORDERS_PER_SESSION

logger = logging.getLogger(__name__)


def execute_orders_with_confirmation(
    intents: list[OrderIntent],
    total_assets: float,
) -> list[dict]:
    """注文一覧を表示し、1件ずつ確認後に発注する。

    Args:
        intents: generate_signals()が生成したOrderIntentリスト
        total_assets: 口座総資産（バリデーション用）

    Returns:
        発注結果のリスト（各dictにticker, side, status, messageを含む）
    """
    if not intents:
        print("\n  売買シグナルはありません。")
        return []

    # セッション制限チェック
    if len(intents) > SIGNAL_MAX_ORDERS_PER_SESSION:
        logger.warning(
            f"シグナル数({len(intents)})がセッション上限"
            f"({SIGNAL_MAX_ORDERS_PER_SESSION})を超過。"
            f"上位{SIGNAL_MAX_ORDERS_PER_SESSION}件に制限します。"
        )
        intents = intents[:SIGNAL_MAX_ORDERS_PER_SESSION]

    # サマリー表示
    _display_order_summary(intents)

    # 一括確認
    proceed = _confirm_all(intents)
    if not proceed:
        print("\n  全注文をキャンセルしました。")
        return []

    # 1件ずつバリデーション→確認→発注
    results = []
    for intent in intents:
        # バリデーション
        is_valid, msg = validate_order(intent, total_assets)
        if not is_valid:
            print(f"  [拒否] {intent.ticker}: {msg}")
            results.append({
                "ticker": intent.ticker,
                "side": intent.side,
                "status": "rejected",
                "message": msg,
            })
            continue

        # 個別確認
        if not _confirm_order(intent):
            print(f"  [スキップ] {intent.ticker}")
            results.append({
                "ticker": intent.ticker,
                "side": intent.side,
                "status": "skipped",
                "message": "ユーザーがスキップ",
            })
            continue

        # 発注実行
        result = _place_single_order(intent)
        results.append(result)

    # 結果サマリー
    _display_results_summary(results)

    return results


def _display_order_summary(intents: list[OrderIntent]):
    """注文一覧のサマリーをコンソール表示する"""
    mode = "[DRY-RUN]" if BROKER_DRY_RUN else "[REAL]"

    print(f"\n{'=' * 80}")
    print(f"  売買提案 {mode}  ({len(intents)}件)")
    print(f"{'=' * 80}")

    buy_signals = [s for s in intents if s.side == "BUY"]
    sell_signals = [s for s in intents if s.side == "SELL"]

    if sell_signals:
        print("\n  【売り提案】")
        for s in sell_signals:
            value = s.quantity * s.price if s.price else 0
            print(f"    {s.ticker:<8} {s.quantity:>6}株 × ${s.price:>10.2f}"
                  f"  = ${value:>12,.0f}  理由: {s.reason}")

    if buy_signals:
        print("\n  【買い提案】")
        for s in buy_signals:
            value = s.quantity * s.price if s.price else 0
            print(f"    {s.ticker:<8} {s.quantity:>6}株 × ${s.price:>10.2f}"
                  f"  = ${value:>12,.0f}  理由: {s.reason}")

    total_buy = sum(s.quantity * (s.price or 0) for s in buy_signals)
    total_sell = sum(s.quantity * (s.price or 0) for s in sell_signals)
    print(f"\n  買い総額: ${total_buy:,.0f}  売り総額: ${total_sell:,.0f}"
          f"  純額: ${total_buy - total_sell:+,.0f}")
    print(f"{'=' * 80}")


def _confirm_all(intents: list[OrderIntent]) -> bool:
    """全注文の一括確認プロンプト"""
    mode = "DRY-RUN（シミュレーション）" if BROKER_DRY_RUN else "REAL（実発注）"
    print(f"\n  モード: {mode}")

    try:
        answer = input("  上記の注文を進めますか？ (y/N): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer == "y"


def _confirm_order(intent: OrderIntent) -> bool:
    """1注文の個別確認プロンプト"""
    value = intent.quantity * intent.price if intent.price else 0
    print(f"\n  {intent.side} {intent.ticker}: "
          f"{intent.quantity}株 × ${intent.price:.2f} = ${value:,.0f}")
    print(f"  理由: {intent.reason}")

    try:
        answer = input("  実行しますか？ (y/N): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer == "y"


def _place_single_order(intent: OrderIntent) -> dict:
    """moomoo APIで1注文を発注する。

    Returns:
        dict: ticker, side, status, message, order_id(成功時)
    """
    result = {
        "ticker": intent.ticker,
        "side": intent.side,
        "quantity": intent.quantity,
        "price": intent.price,
        "timestamp": datetime.now().isoformat(),
    }

    if BROKER_DRY_RUN:
        logger.info(f"[DRY-RUN] 発注シミュレーション: {intent}")
        print(f"  [DRY-RUN] {intent.side} {intent.ticker}: "
              f"{intent.quantity}株 × ${intent.price:.2f} → シミュレーション完了")
        result["status"] = "simulated"
        result["message"] = "dry-runモード: 実発注なし"
        return result

    # 実発注
    try:
        from moomoo import RET_OK, TrdSide, OrderType, TrdEnv

        side = TrdSide.BUY if intent.side == "BUY" else TrdSide.SELL

        with open_trade_context() as ctx:
            # 実取引のアンロック
            ret, data = ctx.unlock_trade(password_md5="")
            if ret != RET_OK:
                result["status"] = "failed"
                result["message"] = f"取引アンロック失敗: {data}"
                return result

            ret, data = ctx.place_order(
                price=intent.price,
                qty=intent.quantity,
                code=f"US.{intent.ticker}",
                trd_side=side,
                order_type=OrderType.NORMAL,
                trd_env=TrdEnv.REAL,
                remark=intent.reason[:64],
            )

            if ret == RET_OK:
                order_id = data["order_id"][0] if not data.empty else "unknown"
                result["status"] = "submitted"
                result["order_id"] = str(order_id)
                result["message"] = f"注文送信成功: order_id={order_id}"
                print(f"  [成功] {intent.side} {intent.ticker}: "
                      f"order_id={order_id}")
            else:
                result["status"] = "failed"
                result["message"] = f"注文送信失敗: {data}"
                print(f"  [失敗] {intent.side} {intent.ticker}: {data}")

    except Exception as e:
        result["status"] = "error"
        result["message"] = str(e)
        logger.error(f"発注エラー: {intent.ticker} - {e}")
        print(f"  [エラー] {intent.side} {intent.ticker}: {e}")

    return result


def _display_results_summary(results: list[dict]):
    """発注結果のサマリーを表示する"""
    if not results:
        return

    print(f"\n{'=' * 80}")
    print("  発注結果サマリー")
    print(f"{'=' * 80}")

    for r in results:
        status_icon = {
            "submitted": "OK",
            "simulated": "SIM",
            "rejected": "NG",
            "skipped": "--",
            "failed": "NG",
            "error": "ERR",
        }.get(r["status"], "?")

        print(f"  [{status_icon}] {r['side']:<4} {r['ticker']:<8} {r['message']}")

    # 集計
    submitted = sum(1 for r in results if r["status"] in ("submitted", "simulated"))
    rejected = sum(1 for r in results if r["status"] in ("rejected", "failed", "error"))
    skipped = sum(1 for r in results if r["status"] == "skipped")
    print(f"\n  実行: {submitted}件  拒否: {rejected}件  スキップ: {skipped}件")
    print(f"{'=' * 80}")
