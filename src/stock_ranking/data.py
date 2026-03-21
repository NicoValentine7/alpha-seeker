"""S&P500銘柄リスト取得 + yfinance からの財務データ取得"""

import time
import logging
from io import StringIO
from urllib.request import urlopen

import pandas as pd
import yfinance as yf

from stock_ranking.config import FETCH_DELAY_SEC

logger = logging.getLogger(__name__)


def fetch_sp500_tickers() -> pd.DataFrame:
    """WikipediaからS&P500銘柄リストを取得する。

    Returns:
        columns: ticker, name, sector
    """
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    from urllib.request import Request
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    html = urlopen(req).read().decode("utf-8")
    tables = pd.read_html(StringIO(html))
    df = tables[0][["Symbol", "Security", "GICS Sector"]].copy()
    df.columns = ["ticker", "name", "sector"]
    # BRK.B → BRK-B（yfinance形式）
    df["ticker"] = df["ticker"].str.replace(".", "-", regex=False)
    return df


def _safe_get(d: dict, *keys, default=None):
    """ネストされた辞書から安全に値を取得する"""
    for key in keys:
        if isinstance(d, dict):
            d = d.get(key, default)
        else:
            return default
    return d


def _calc_fcf_yield(info: dict) -> float | None:
    """FCF利回り = Free Cash Flow / Enterprise Value"""
    fcf = info.get("freeCashflow")
    ev = info.get("enterpriseValue")
    if fcf and ev and ev > 0:
        return fcf / ev
    return None


def _calc_peg(info: dict) -> float | None:
    """PEG = Forward PE / 来期EPS成長率(%)"""
    fpe = info.get("forwardPE")
    growth = info.get("earningsGrowth")
    if fpe and growth and growth > 0:
        return fpe / (growth * 100)
    return None


def fetch_stock_data(ticker: str) -> dict | None:
    """1銘柄の財務データを yfinance から取得する。

    Returns:
        指標の辞書。取得失敗時はNone。
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}

        # 財務諸表（年次）
        financials = t.financials
        cashflow = t.cashflow

        data = {
            "ticker": ticker,
            # バリュエーション指標
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "pb_ratio": info.get("priceToBook"),
            "ev_ebitda": info.get("enterpriseToEbitda"),
            "ps_ratio": info.get("priceToSalesTrailing12Months"),
            # FCF利回り (FCF / Enterprise Value)
            "fcf_yield": _calc_fcf_yield(info),
            # 成長率
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            # PEG (Forward PE / EPS成長予想)
            "peg_ratio": _calc_peg(info),
            # 質指標
            "roe": info.get("returnOnEquity"),
            "gross_margin": info.get("grossMargins"),
            "debt_to_equity": info.get("debtToEquity"),
            # アナリスト評価
            "analyst_rating": info.get("averageAnalystRating"),  # e.g. "1.9 - Buy"
            "recommendation_mean": info.get("recommendationMean"),  # 1=Strong Buy, 5=Sell
            "recommendation_key": info.get("recommendationKey"),  # buy/hold/sell
            "num_analysts": info.get("numberOfAnalystOpinions"),
            "target_mean_price": info.get("targetMeanPrice"),
            "target_median_price": info.get("targetMedianPrice"),
            "target_high_price": info.get("targetHighPrice"),
            "target_low_price": info.get("targetLowPrice"),
            "current_price": info.get("currentPrice"),
            # その他
            "market_cap": info.get("marketCap"),
            "sector": info.get("sector"),
            "name": info.get("shortName"),
        }

        # ターゲット価格と現在価格から上昇余地を計算
        if data["target_mean_price"] and data["current_price"]:
            data["upside_potential"] = (data["target_mean_price"] - data["current_price"]) / data["current_price"]

        # 財務諸表から成長率を計算
        if financials is not None and financials.shape[1] >= 2:
            _add_financial_growth(data, financials, cashflow)

        # 決算データ（サプライズ・四半期推移・EPS予想トレンド）
        _add_earnings_data(data, t)

        # アナリストの直近アクション（アップグレード/ダウングレード）
        _add_analyst_actions(data, t)

        # ニュース
        _add_news(data, t)

        return data

    except Exception as e:
        logger.warning(f"{ticker}: データ取得失敗 - {e}")
        return None


def _add_financial_growth(data: dict, financials: pd.DataFrame, cashflow: pd.DataFrame | None):
    """財務諸表から成長率とFCFマージンを計算して data に追加する"""
    try:
        cols = financials.columns  # 新しい順

        # 売上成長率（financials から）
        rev_key = None
        for key in ["Total Revenue", "Revenue"]:
            if key in financials.index:
                rev_key = key
                break
        if rev_key and pd.notna(financials.loc[rev_key, cols[0]]) and pd.notna(financials.loc[rev_key, cols[1]]):
            prev = financials.loc[rev_key, cols[1]]
            if prev != 0:
                data["revenue_growth_calc"] = (financials.loc[rev_key, cols[0]] - prev) / abs(prev)

        # 営業利益成長率
        oi_key = None
        for key in ["Operating Income", "EBIT"]:
            if key in financials.index:
                oi_key = key
                break
        if oi_key and pd.notna(financials.loc[oi_key, cols[0]]) and pd.notna(financials.loc[oi_key, cols[1]]):
            prev = financials.loc[oi_key, cols[1]]
            if prev != 0:
                data["operating_income_growth"] = (financials.loc[oi_key, cols[0]] - prev) / abs(prev)

        # EPS成長率（純利益ベースで代替）
        ni_key = None
        for key in ["Net Income", "Net Income Common Stockholders"]:
            if key in financials.index:
                ni_key = key
                break
        if ni_key and pd.notna(financials.loc[ni_key, cols[0]]) and pd.notna(financials.loc[ni_key, cols[1]]):
            prev = financials.loc[ni_key, cols[1]]
            if prev != 0:
                data["eps_growth"] = (financials.loc[ni_key, cols[0]] - prev) / abs(prev)

        # フリーCFマージン
        if cashflow is not None and rev_key:
            fcf_key = None
            for key in ["Free Cash Flow"]:
                if key in cashflow.index:
                    fcf_key = key
                    break
            if fcf_key and pd.notna(cashflow.loc[fcf_key, cashflow.columns[0]]):
                revenue = financials.loc[rev_key, cols[0]]
                if revenue and revenue != 0:
                    data["fcf_margin"] = cashflow.loc[fcf_key, cashflow.columns[0]] / abs(revenue)

    except Exception as e:
        logger.debug(f"財務成長率計算エラー: {e}")


def _add_earnings_data(data: dict, ticker_obj: yf.Ticker):
    """決算データを追加する: サプライズ率・四半期推移・EPS予想トレンド"""
    try:
        # --- 1. 決算サプライズ（EPS予想vs実績） ---
        ed = ticker_obj.earnings_dates
        if ed is not None and len(ed) > 0:
            # 実績が出ている決算のみ（Reported EPS が非NaN）
            reported = ed[ed["Reported EPS"].notna()]
            if len(reported) > 0:
                surprises = []
                for date_idx, row in reported.head(4).iterrows():
                    surprises.append({
                        "date": str(date_idx)[:10],
                        "eps_estimate": row.get("EPS Estimate"),
                        "eps_actual": row.get("Reported EPS"),
                        "surprise_pct": row.get("Surprise(%)"),
                    })
                data["earnings_surprises"] = surprises

                # 直近4四半期のビート回数
                surprise_vals = reported.head(4)["Surprise(%)"].dropna()
                data["earnings_beat_count"] = int((surprise_vals > 0).sum())
                data["earnings_beat_total"] = len(surprise_vals)
                data["avg_surprise_pct"] = float(surprise_vals.mean()) if len(surprise_vals) > 0 else None

            # 次回決算日
            upcoming = ed[ed["Reported EPS"].isna()]
            if len(upcoming) > 0:
                data["next_earnings_date"] = str(upcoming.index[0])[:10]

    except Exception as e:
        logger.debug(f"決算サプライズ取得エラー: {e}")

    try:
        # --- 2. 四半期売上・利益の推移 ---
        qf = ticker_obj.quarterly_financials
        if qf is not None and qf.shape[1] >= 2:
            quarters = []
            for col in qf.columns[:4]:  # 直近4四半期
                q_data = {"quarter": str(col)[:10]}
                for key in ["Total Revenue", "Operating Income", "Net Income", "Gross Profit"]:
                    if key in qf.index and pd.notna(qf.loc[key, col]):
                        q_data[key.lower().replace(" ", "_")] = float(qf.loc[key, col])
                quarters.append(q_data)
            data["quarterly_results"] = quarters

            # 四半期売上の加速度（直近QoQ vs 前回QoQ）
            rev_key = "Total Revenue" if "Total Revenue" in qf.index else None
            if rev_key and qf.shape[1] >= 3:
                vals = [qf.loc[rev_key, c] for c in qf.columns[:3] if pd.notna(qf.loc[rev_key, c])]
                if len(vals) >= 3 and vals[1] != 0 and vals[2] != 0:
                    recent_qoq = (vals[0] - vals[1]) / abs(vals[1])
                    prev_qoq = (vals[1] - vals[2]) / abs(vals[2])
                    data["revenue_acceleration"] = recent_qoq - prev_qoq

    except Exception as e:
        logger.debug(f"四半期決算取得エラー: {e}")

    try:
        # --- 3. EPS予想の上方修正トレンド ---
        eps_trend = ticker_obj.eps_trend
        if eps_trend is not None and len(eps_trend) > 0:
            # 今期（0y）のトレンド
            if "0y" in eps_trend.index:
                row = eps_trend.loc["0y"]
                current = row.get("current")
                d90 = row.get("90daysAgo")
                d30 = row.get("30daysAgo")
                if current and d90 and d90 != 0:
                    data["eps_revision_90d"] = (current - d90) / abs(d90)
                if current and d30 and d30 != 0:
                    data["eps_revision_30d"] = (current - d30) / abs(d30)

        # --- 4. 来期の成長予想 ---
        earnings_est = ticker_obj.earnings_estimate
        if earnings_est is not None and len(earnings_est) > 0:
            if "+1y" in earnings_est.index:
                data["forward_eps_growth"] = earnings_est.loc["+1y"].get("growth")

        revenue_est = ticker_obj.revenue_estimate
        if revenue_est is not None and len(revenue_est) > 0:
            if "0y" in revenue_est.index:
                data["estimated_revenue_growth"] = revenue_est.loc["0y"].get("growth")

    except Exception as e:
        logger.debug(f"EPS予想トレンド取得エラー: {e}")


def _add_analyst_actions(data: dict, ticker_obj: yf.Ticker):
    """直近のアナリストアクション（アップグレード/ダウングレード）を追加"""
    try:
        ud = ticker_obj.upgrades_downgrades
        if ud is not None and len(ud) > 0:
            recent = ud.head(10)
            upgrades = len(recent[recent["Action"].isin(["up", "upgrade"])])
            downgrades = len(recent[recent["Action"].isin(["down", "downgrade"])])
            data["recent_upgrades"] = upgrades
            data["recent_downgrades"] = downgrades
            data["upgrade_ratio"] = upgrades / max(upgrades + downgrades, 1)

            # 直近のアクション詳細（上位5件、日付付き）
            actions = []
            for grade_date, row in recent.head(5).iterrows():
                date_str = str(grade_date)[:10] if hasattr(grade_date, 'strftime') else str(grade_date)[:10]
                actions.append({
                    "date": date_str,
                    "firm": row.get("Firm", ""),
                    "from_grade": row.get("FromGrade", ""),
                    "to_grade": row.get("ToGrade", ""),
                    "action": row.get("Action", ""),
                    "target_price": row.get("currentPriceTarget"),
                    "prior_target": row.get("priorPriceTarget"),
                })
            data["analyst_actions"] = actions
    except Exception as e:
        logger.debug(f"アナリストアクション取得エラー: {e}")


def _add_news(data: dict, ticker_obj: yf.Ticker):
    """直近のニュースタイトルとURLを追加"""
    try:
        news = ticker_obj.news
        if news:
            headlines = []
            for n in news[:5]:
                content = n.get("content", {})
                title = content.get("title", "")
                url_info = content.get("canonicalUrl", {})
                url = url_info.get("url", "")
                publisher = content.get("provider", {}).get("displayName", "")
                pub_date = content.get("pubDate", "")[:10]
                if title:
                    headlines.append({
                        "title": title,
                        "url": url,
                        "publisher": publisher,
                        "date": pub_date,
                    })
            data["news"] = headlines
    except Exception as e:
        logger.debug(f"ニュース取得エラー: {e}")


def fetch_all_stocks(tickers: list[str], delay: float = FETCH_DELAY_SEC) -> pd.DataFrame:
    """複数銘柄のデータを一括取得する"""
    results = []
    total = len(tickers)
    for i, ticker in enumerate(tickers):
        if (i + 1) % 50 == 0 or i == 0:
            logger.info(f"取得中: {i+1}/{total} ({ticker})")
        data = fetch_stock_data(ticker)
        if data:
            results.append(data)
        if delay > 0:
            time.sleep(delay)

    df = pd.DataFrame(results)
    logger.info(f"取得完了: {len(df)}/{total} 銘柄")
    return df
