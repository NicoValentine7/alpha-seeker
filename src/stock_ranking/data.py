"""S&P500銘柄リスト取得 + yfinance からの財務データ取得"""

import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import StringIO
from urllib.request import urlopen

import pandas as pd
import yfinance as yf

from stock_ranking.config import FETCH_DELAY_SEC, FETCH_MAX_WORKERS

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


def fetch_stock_data(ticker: str, max_retries: int = 2) -> dict | None:
    """1銘柄の財務データを yfinance から取得する。

    Returns:
        指標の辞書。取得失敗時はNone。
    """
    for attempt in range(max_retries + 1):
        try:
            return _fetch_stock_data_impl(ticker)
        except Exception as e:
            if attempt < max_retries:
                time.sleep(1 + attempt)
                continue
            logger.warning(f"{ticker}: データ取得失敗（{max_retries+1}回試行） - {e}")
            return None


def _fetch_stock_data_impl(ticker: str) -> dict | None:
    """fetch_stock_data の実装本体"""
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
        balance_sheet = t.balance_sheet
        if financials is not None and financials.shape[1] >= 2:
            _add_financial_growth(data, financials, cashflow)

        # Piotroski F-Score（バリュートラップ検出用）
        _add_piotroski_fscore(data, financials, cashflow, balance_sheet)

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


def _safe_bs_val(bs: pd.DataFrame, key: str, col_idx: int):
    """balance_sheetから安全に値を取得"""
    if bs is None or key not in bs.index or col_idx >= bs.shape[1]:
        return None
    val = bs.loc[key, bs.columns[col_idx]]
    return float(val) if pd.notna(val) else None


def _add_piotroski_fscore(data: dict, financials: pd.DataFrame | None,
                          cashflow: pd.DataFrame | None, balance_sheet: pd.DataFrame | None):
    """Piotroski F-Score (0-9) を計算して data に追加する。

    収益性(4) + レバレッジ/流動性(3) + 運営効率(2) の9項目をバイナリ判定。
    """
    try:
        score = 0
        details = []

        # 年次データが2期分必要
        has_fin = financials is not None and financials.shape[1] >= 2
        has_cf = cashflow is not None and cashflow.shape[1] >= 1
        has_bs = balance_sheet is not None and balance_sheet.shape[1] >= 2

        if not has_fin:
            return

        fin_cols = financials.columns  # 新しい順
        total_assets_curr = _safe_bs_val(balance_sheet, "Total Assets", 0) if has_bs else None
        total_assets_prev = _safe_bs_val(balance_sheet, "Total Assets", 1) if has_bs else None

        # --- 収益性 (4点) ---

        # 1. ROA > 0 (当期純利益 / 総資産)
        ni_key = None
        for key in ["Net Income", "Net Income Common Stockholders"]:
            if key in financials.index:
                ni_key = key
                break
        if ni_key and total_assets_curr and total_assets_curr > 0:
            ni_curr = financials.loc[ni_key, fin_cols[0]]
            if pd.notna(ni_curr) and ni_curr / total_assets_curr > 0:
                score += 1
                details.append("ROA>0")

        # 2. 営業CF > 0
        cfo_curr = None
        if has_cf:
            for key in ["Operating Cash Flow", "Total Cash From Operating Activities"]:
                if key in cashflow.index:
                    val = cashflow.loc[key, cashflow.columns[0]]
                    if pd.notna(val):
                        cfo_curr = float(val)
                        break
        if cfo_curr and cfo_curr > 0:
            score += 1
            details.append("CFO>0")

        # 3. ROA改善 (当期ROA > 前期ROA)
        if ni_key and total_assets_curr and total_assets_prev and total_assets_curr > 0 and total_assets_prev > 0:
            ni_curr = financials.loc[ni_key, fin_cols[0]]
            ni_prev = financials.loc[ni_key, fin_cols[1]]
            if pd.notna(ni_curr) and pd.notna(ni_prev):
                roa_curr = ni_curr / total_assets_curr
                roa_prev = ni_prev / total_assets_prev
                if roa_curr > roa_prev:
                    score += 1
                    details.append("ROA改善")

        # 4. アクルーアル品質 (営業CF > 純利益)
        if cfo_curr and ni_key:
            ni_curr = financials.loc[ni_key, fin_cols[0]]
            if pd.notna(ni_curr) and cfo_curr > float(ni_curr):
                score += 1
                details.append("CFO>NI")

        # --- レバレッジ/流動性 (3点) ---

        # 5. 長期負債比率が前年比低下
        if has_bs:
            ltd_curr = _safe_bs_val(balance_sheet, "Long Term Debt", 0)
            ltd_prev = _safe_bs_val(balance_sheet, "Long Term Debt", 1)
            if ltd_curr is not None and ltd_prev is not None and total_assets_curr and total_assets_prev:
                if total_assets_curr > 0 and total_assets_prev > 0:
                    ratio_curr = ltd_curr / total_assets_curr
                    ratio_prev = ltd_prev / total_assets_prev
                    if ratio_curr <= ratio_prev:
                        score += 1
                        details.append("LTD低下")

        # 6. 流動比率が前年比改善
        if has_bs:
            ca_curr = _safe_bs_val(balance_sheet, "Current Assets", 0)
            cl_curr = _safe_bs_val(balance_sheet, "Current Liabilities", 0)
            ca_prev = _safe_bs_val(balance_sheet, "Current Assets", 1)
            cl_prev = _safe_bs_val(balance_sheet, "Current Liabilities", 1)
            if ca_curr and cl_curr and ca_prev and cl_prev and cl_curr > 0 and cl_prev > 0:
                cr_curr = ca_curr / cl_curr
                cr_prev = ca_prev / cl_prev
                if cr_curr > cr_prev:
                    score += 1
                    details.append("流動比率改善")

        # 7. 新株発行なし (発行済株式数が増えていない)
        if has_bs:
            shares_curr = _safe_bs_val(balance_sheet, "Ordinary Shares Number", 0)
            shares_prev = _safe_bs_val(balance_sheet, "Ordinary Shares Number", 1)
            if shares_curr is None:
                shares_curr = _safe_bs_val(balance_sheet, "Share Issued", 0)
                shares_prev = _safe_bs_val(balance_sheet, "Share Issued", 1)
            if shares_curr and shares_prev and shares_curr <= shares_prev:
                score += 1
                details.append("希薄化なし")

        # --- 運営効率 (2点) ---

        # 8. 粗利率が前年比改善
        gp_key = None
        rev_key = None
        for key in ["Gross Profit"]:
            if key in financials.index:
                gp_key = key
                break
        for key in ["Total Revenue", "Revenue"]:
            if key in financials.index:
                rev_key = key
                break
        if gp_key and rev_key:
            gp_curr = financials.loc[gp_key, fin_cols[0]]
            gp_prev = financials.loc[gp_key, fin_cols[1]]
            rev_curr = financials.loc[rev_key, fin_cols[0]]
            rev_prev = financials.loc[rev_key, fin_cols[1]]
            if all(pd.notna(v) and v != 0 for v in [gp_curr, gp_prev, rev_curr, rev_prev]):
                gm_curr = gp_curr / rev_curr
                gm_prev = gp_prev / rev_prev
                if gm_curr > gm_prev:
                    score += 1
                    details.append("粗利率改善")

        # 9. 資産回転率が前年比改善
        if rev_key and total_assets_curr and total_assets_prev and total_assets_curr > 0 and total_assets_prev > 0:
            rev_curr = financials.loc[rev_key, fin_cols[0]]
            rev_prev = financials.loc[rev_key, fin_cols[1]]
            if pd.notna(rev_curr) and pd.notna(rev_prev):
                at_curr = rev_curr / total_assets_curr
                at_prev = rev_prev / total_assets_prev
                if at_curr > at_prev:
                    score += 1
                    details.append("資産回転率改善")

        data["piotroski_fscore"] = score
        data["piotroski_details"] = "; ".join(details) if details else ""

    except Exception as e:
        logger.debug(f"Piotroski F-Score計算エラー: {e}")


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


def fetch_all_stocks(tickers: list[str], delay: float = FETCH_DELAY_SEC,
                     max_workers: int = FETCH_MAX_WORKERS,
                     batch_size: int = 100) -> pd.DataFrame:
    """複数銘柄のデータをバッチ分割＋並列取得する。

    バッチ間にクールダウンを入れてrate limitを回避。
    失敗銘柄は最後に逐次リトライする。
    """
    results = []
    failed_tickers = []
    total = len(tickers)

    # バッチに分割
    batches = [tickers[i:i + batch_size] for i in range(0, total, batch_size)]
    logger.info(f"取得中: {total} 銘柄（並列数: {max_workers}, {len(batches)}バッチ）")

    for batch_idx, batch in enumerate(batches):
        if batch_idx > 0:
            cooldown = 5
            logger.info(f"バッチ {batch_idx + 1}/{len(batches)} — {cooldown}秒クールダウン")
            time.sleep(cooldown)

        completed = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(fetch_stock_data, t): t for t in batch}
            for future in as_completed(futures):
                ticker = futures[future]
                completed += 1
                try:
                    data = future.result()
                    if data:
                        results.append(data)
                    else:
                        failed_tickers.append(ticker)
                except Exception as e:
                    logger.warning(f"{ticker}: 並列取得エラー - {e}")
                    failed_tickers.append(ticker)

        logger.info(f"バッチ {batch_idx + 1}/{len(batches)} 完了: {len(results)}/{total} 銘柄取得済み")

    # 失敗銘柄の逐次リトライ（rate limit回避のため1銘柄ずつ）
    if failed_tickers:
        logger.info(f"失敗銘柄 {len(failed_tickers)} 件をリトライ中...")
        time.sleep(10)  # クールダウン
        for ticker in failed_tickers:
            time.sleep(1)
            data = fetch_stock_data(ticker)
            if data:
                results.append(data)

    df = pd.DataFrame(results)
    logger.info(f"取得完了: {len(df)}/{total} 銘柄")
    return df
