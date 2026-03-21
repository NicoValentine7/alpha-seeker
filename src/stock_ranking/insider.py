"""SEC EDGAR Form 4 からインサイダー取引データを取得する

クラスター買い（複数インサイダーの同時購入）は最も強力な買いシグナル。
学術研究: インサイダー購入ポートフォリオは市場を年率10.2%上回る (Seyhun 1986, Jeng et al. 2003)
"""

import json
import logging
import time
from datetime import datetime, timedelta
from urllib.request import Request, urlopen
from xml.etree import ElementTree

import pandas as pd

logger = logging.getLogger(__name__)

SEC_HEADERS = {"User-Agent": "AlphaSeeker/1.0 alpha-seeker@example.com"}
SEC_DELAY = 0.12  # SEC EDGAR rate limit: 10 req/sec


def _sec_request(url: str) -> bytes:
    """SEC EDGAR にリクエストを送信する（rate limit対応）"""
    req = Request(url, headers=SEC_HEADERS)
    time.sleep(SEC_DELAY)
    resp = urlopen(req, timeout=15)
    return resp.read()


def _get_cik_for_ticker(ticker: str) -> str | None:
    """銘柄ティッカーからCIK番号を取得する"""
    try:
        data = json.loads(_sec_request("https://www.sec.gov/files/company_tickers.json"))
        for entry in data.values():
            if entry.get("ticker", "").upper() == ticker.upper():
                return str(entry["cik_str"]).zfill(10)
    except Exception as e:
        logger.debug(f"{ticker}: CIK取得エラー - {e}")
    return None


def _get_form4_accessions(cik: str, days_back: int = 90) -> list[dict]:
    """直近のForm 4アクセション番号リストを取得する"""
    try:
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        data = json.loads(_sec_request(url))

        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])

        cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

        results = []
        for i, form in enumerate(forms):
            if form == "4" and dates[i] >= cutoff:
                results.append({
                    "accession": accessions[i],
                    "filing_date": dates[i],
                })
        return results
    except Exception as e:
        logger.debug(f"CIK {cik}: Form 4一覧取得エラー - {e}")
        return []


def _parse_form4_xml(cik: str, accession: str) -> list[dict]:
    """Form 4 XMLをパースして取引詳細を抽出する"""
    try:
        acc_no_dash = accession.replace("-", "")
        # ファイリングインデックスから実際のXMLファイル名を取得
        index_url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{acc_no_dash}/{accession}-index.htm"
        html = _sec_request(index_url).decode()

        import re
        xml_matches = re.findall(r'href="([^"]+\.xml)"', html)
        # XSL変換版ではなく生XMLを探す
        xml_files = [f for f in xml_matches if "xsl" not in f.lower()]
        if not xml_files:
            return []

        xml_path = xml_files[0]
        if xml_path.startswith("/"):
            xml_url = f"https://www.sec.gov{xml_path}"
        else:
            xml_url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{acc_no_dash}/{xml_path}"

        xml_content = _sec_request(xml_url).decode()
        root = ElementTree.fromstring(xml_content)

        # 名前空間を除去してパース
        def strip_ns(tag):
            return tag.split("}")[-1] if "}" in tag else tag

        # レポーターの情報を取得
        owner_name = ""
        is_officer = False
        is_director = False
        for elem in root.iter():
            tag = strip_ns(elem.tag)
            if tag == "rptOwnerName" and elem.text:
                owner_name = elem.text.strip()
            elif tag == "isOfficer" and elem.text:
                is_officer = elem.text.strip() == "1"
            elif tag == "isDirector" and elem.text:
                is_director = elem.text.strip() == "1"

        # 取引を抽出
        transactions = []
        # nonDerivativeTransaction を探す
        for txn_elem in root.iter():
            tag = strip_ns(txn_elem.tag)
            if tag not in ("nonDerivativeTransaction",):
                continue

            txn = {"owner": owner_name, "is_officer": is_officer, "is_director": is_director}
            for child in txn_elem.iter():
                child_tag = strip_ns(child.tag)
                if child_tag == "transactionDate":
                    for v in child.iter():
                        if strip_ns(v.tag) == "value" and v.text:
                            txn["date"] = v.text.strip()
                elif child_tag == "transactionCode" and child.text:
                    txn["code"] = child.text.strip()
                elif child_tag == "transactionShares":
                    for v in child.iter():
                        if strip_ns(v.tag) == "value" and v.text:
                            try:
                                txn["shares"] = float(v.text.strip())
                            except ValueError:
                                pass
                elif child_tag == "transactionPricePerShare":
                    for v in child.iter():
                        if strip_ns(v.tag) == "value" and v.text:
                            try:
                                txn["price"] = float(v.text.strip())
                            except ValueError:
                                pass
                elif child_tag == "transactionAcquiredDisposedCode":
                    for v in child.iter():
                        if strip_ns(v.tag) == "value" and v.text:
                            txn["acquired_disposed"] = v.text.strip()  # A=取得, D=処分

            if txn.get("code"):
                transactions.append(txn)

        return transactions

    except Exception as e:
        logger.debug(f"Form 4パースエラー ({accession}): {e}")
        return []


def fetch_insider_data(ticker: str, days_back: int = 90, max_filings: int = 20) -> dict:
    """1銘柄のインサイダー取引サマリーを取得する。

    Returns:
        インサイダー取引の集計データ（購入件数、売却件数、クラスター買い等）
    """
    cik = _get_cik_for_ticker(ticker)
    if not cik:
        return {}

    accessions = _get_form4_accessions(cik, days_back)
    if not accessions:
        return {"insider_filings_count": 0}

    # 最新のmax_filings件のみパース（rate limit対策）
    all_transactions = []
    for acc_info in accessions[:max_filings]:
        txns = _parse_form4_xml(cik, acc_info["accession"])
        for txn in txns:
            txn["filing_date"] = acc_info["filing_date"]
        all_transactions.extend(txns)

    if not all_transactions:
        return {"insider_filings_count": len(accessions)}

    # 集計
    purchases = [t for t in all_transactions if t.get("code") == "P"]
    sales = [t for t in all_transactions if t.get("code") == "S"]

    # 購入者のユニーク数（クラスター買い検出用）
    unique_buyers = set(t.get("owner") for t in purchases)

    # 購入金額合計
    purchase_value = sum(
        t.get("shares", 0) * t.get("price", 0)
        for t in purchases
        if t.get("shares") and t.get("price")
    )

    # 売却金額合計
    sale_value = sum(
        t.get("shares", 0) * t.get("price", 0)
        for t in sales
        if t.get("shares") and t.get("price")
    )

    result = {
        "insider_filings_count": len(accessions),
        "insider_purchases": len(purchases),
        "insider_sales": len(sales),
        "insider_unique_buyers": len(unique_buyers),
        "insider_purchase_value": purchase_value,
        "insider_sale_value": sale_value,
        "insider_net_value": purchase_value - sale_value,
        "insider_cluster_buy": len(unique_buyers) >= 3,  # 3人以上が購入
    }

    # 直近の購入詳細（上位5件）
    if purchases:
        result["insider_recent_purchases"] = [
            {
                "owner": t.get("owner", ""),
                "date": t.get("date", ""),
                "shares": t.get("shares", 0),
                "price": t.get("price", 0),
                "value": t.get("shares", 0) * t.get("price", 0),
                "is_officer": t.get("is_officer", False),
            }
            for t in sorted(purchases, key=lambda x: x.get("date", ""), reverse=True)[:5]
        ]

    return result
