"""explain.py のユニットテスト"""

import math

import pandas as pd

from stock_ranking.explain import generate_report


def test_incomplete_stock_report_warns_and_avoids_confident_rationale():
    df = pd.DataFrame(
        [
            {
                "ticker": "NAVN",
                "name": "Navan, Inc.",
                "sector": "Technology",
                "total_score": 59.9,
                "valuation_score": 80.0,
                "growth_score": 91.0,
                "quality_score": 48.0,
                "earnings_momentum_score": 97.0,
                "price_momentum_score": 88.0,
                "valuation_coverage": 4,
                "growth_coverage": 1,
                "quality_coverage": 2,
                "earnings_momentum_coverage": 4,
                "core_data_warning": "growth,quality",
                "is_data_complete": False,
                "piotroski_fscore": math.nan,
                "upside_potential": 0.73,
                "recommendation_mean": 1.3,
                "pe_ratio": math.nan,
                "forward_pe": 63.3,
                "pb_ratio": 2.5,
                "ev_ebitda": -18.0,
                "ps_ratio": 4.3,
                "fcf_yield": 0.056,
                "revenue_growth": 0.35,
                "revenue_growth_calc": math.nan,
                "operating_income_growth": math.nan,
                "eps_growth": math.nan,
                "peg_ratio": math.nan,
                "roe": -0.60,
                "gross_margin": 0.71,
                "debt_to_equity": 14.0,
                "fcf_margin": math.nan,
                "avg_surprise_pct": 181.0,
                "eps_revision_90d": 1.03,
                "revenue_acceleration": 0.60,
                "forward_eps_growth": 10.23,
            }
        ]
    )

    report = generate_report(df, top_n=1)

    assert "[警告] データ品質:" in report
    assert "成長力はデータ不足で判定保留" in report
    assert "質・健全性はデータ不足で判定保留" in report
    assert "高い成長率を示している" not in report
    assert "ROE・財務健全性が高く質が良い" not in report
