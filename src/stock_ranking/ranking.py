"""メインエントリポイント: データ取得→スコアリング→ランキング出力"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from stock_ranking.config import TOP_N_DISPLAY
from stock_ranking.data import fetch_all_stocks, fetch_sp500_tickers
from stock_ranking.explain import generate_report
from stock_ranking.scoring import calculate_total_score

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output"


def run(
    tickers: list[str] | None = None,
    top_n: int = TOP_N_DISPLAY,
    portfolio_mode: bool = False,
) -> pd.DataFrame:
    """ランキングを実行する。

    Args:
        tickers: 対象ティッカーリスト。Noneの場合はS&P500全銘柄。
        top_n: コンソールに表示する上位N件。
        portfolio_mode: Moomoo保有ポジションをスコアと照合する。
    """
    # S&P500銘柄リスト取得
    if tickers is None:
        logger.info("S&P500銘柄リストを取得中...")
        sp500 = fetch_sp500_tickers()
        ticker_list = sp500["ticker"].tolist()
        sector_map = sp500.set_index("ticker")[["name", "sector"]]
    else:
        ticker_list = tickers
        sector_map = None

    # 財務データ取得
    logger.info(f"{len(ticker_list)} 銘柄のデータを取得中...")
    df = fetch_all_stocks(ticker_list)

    if df.empty:
        logger.error("データが取得できませんでした")
        return df

    # sector_map から補完（yfinance の sector が欠損している場合）
    if sector_map is not None:
        for col in ["name", "sector"]:
            mask = df[col].isna()
            if mask.any():
                df.loc[mask, col] = df.loc[mask, "ticker"].map(sector_map[col])

    # セクターが取れなかった銘柄は除外
    before = len(df)
    df = df.dropna(subset=["sector"])
    if len(df) < before:
        logger.info(f"セクター情報なし: {before - len(df)} 銘柄を除外")

    # スコアリング
    logger.info("スコアリング実行中...")
    df = calculate_total_score(df)

    # ランキング
    df = df.sort_values("total_score", ascending=False).reset_index(drop=True)
    df.index = df.index + 1  # 1始まり

    # ポートフォリオモード: 保有銘柄をスコアと照合
    portfolio_df = None
    if portfolio_mode:
        from stock_ranking.broker import get_portfolio

        logger.info("Moomooポートフォリオを取得中...")
        portfolio_df = get_portfolio(df)
        if not portfolio_df.empty:
            _print_portfolio(portfolio_df)

    # 出力
    _print_ranking(df, top_n)
    _save_csv(df)
    _save_report(df, top_n, portfolio_df=portfolio_df)

    return df


def _print_ranking(df: pd.DataFrame, top_n: int):
    """ランキングをコンソールに出力する"""
    display_cols = ["ticker", "name", "sector", "total_score", "valuation_score", "growth_score", "quality_score", "earnings_momentum_score", "piotroski_fscore"]
    available = [c for c in display_cols if c in df.columns]
    top = df.head(top_n)[available].copy()

    # スコアを小数点1桁に
    score_cols = [c for c in available if c.endswith("_score")]
    for col in score_cols:
        top[col] = top[col].round(1)

    print("\n" + "=" * 100)
    print(f"  過小評価株ランキング TOP {top_n}")
    print("=" * 100)
    print(top.to_string())
    print("=" * 100 + "\n")


def _save_csv(df: pd.DataFrame):
    """全銘柄のスコアをCSVに保存する"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    path = OUTPUT_DIR / f"ranking_{date_str}.csv"

    # リスト/辞書型カラムはCSV向けに文字列化
    df_csv = df.copy()
    for col in df_csv.columns:
        if df_csv[col].apply(lambda x: isinstance(x, (list, dict))).any():
            df_csv[col] = df_csv[col].apply(str)

    df_csv.to_csv(path, index=True, index_label="rank")
    logger.info(f"CSV保存: {path}")


def _print_portfolio(portfolio_df: pd.DataFrame):
    """ポートフォリオをコンソールに出力する"""
    from stock_ranking.explain import generate_portfolio_section

    print(generate_portfolio_section(portfolio_df))


def _save_report(
    df: pd.DataFrame, top_n: int, portfolio_df: pd.DataFrame | None = None
):
    """詳細レポートをテキストファイルに保存する"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    path = OUTPUT_DIR / f"report_{date_str}.txt"

    report = generate_report(df, top_n, portfolio_df=portfolio_df)
    path.write_text(report, encoding="utf-8")
    print(report)
    logger.info(f"レポート保存: {path}")


def main():
    parser = argparse.ArgumentParser(description="過小評価株ランキング")
    parser.add_argument("--tickers", nargs="*", help="対象ティッカー（省略時はS&P500全銘柄）")
    parser.add_argument("--top", type=int, default=TOP_N_DISPLAY, help="表示する上位N件")
    parser.add_argument("--portfolio", action="store_true", help="Moomoo保有ポジションをスコアと照合")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    tickers = args.tickers if args.tickers else None
    run(tickers=tickers, top_n=args.top, portfolio_mode=args.portfolio)


if __name__ == "__main__":
    main()
