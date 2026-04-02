"""scoring.py のユニットテスト"""

import math

import pandas as pd

from stock_ranking.scoring import _calculate_buy_signal, calculate_total_score


def _make_scoring_fixture() -> pd.DataFrame:
    """ランキング計算用の最小fixtureを作る。"""
    return pd.DataFrame(
        [
            {
                "ticker": "NEM",
                "sector": "Technology",
                "pe_ratio": 13.5,
                "pb_ratio": 1.6,
                "ev_ebitda": 5.5,
                "ps_ratio": 3.6,
                "fcf_yield": 0.13,
                "revenue_growth": 0.44,
                "revenue_growth_calc": 0.48,
                "eps_growth": 0.98,
                "peg_ratio": 0.08,
                "roe": 0.43,
                "gross_margin": 0.81,
                "debt_to_equity": 9.0,
                "fcf_margin": 0.42,
                "avg_surprise_pct": 28.0,
                "eps_revision_90d": 0.27,
                "revenue_acceleration": 0.22,
                "forward_eps_growth": 0.42,
                "piotroski_fscore": 9.0,
                "upside_potential": 0.35,
                "momentum_12_1m": 0.33,
            },
            {
                "ticker": "AVGO",
                "sector": "Technology",
                "pe_ratio": 13.0,
                "pb_ratio": 1.5,
                "ev_ebitda": 5.0,
                "ps_ratio": 3.5,
                "fcf_yield": 0.14,
                "revenue_growth": 0.46,
                "revenue_growth_calc": 0.50,
                "eps_growth": 1.00,
                "peg_ratio": 0.05,
                "roe": 0.45,
                "gross_margin": 0.82,
                "debt_to_equity": 8.0,
                "fcf_margin": 0.45,
                "avg_surprise_pct": 30.0,
                "eps_revision_90d": 0.30,
                "revenue_acceleration": 0.25,
                "forward_eps_growth": 0.45,
                "piotroski_fscore": 8.0,
                "upside_potential": 0.55,
                "momentum_12_1m": 0.35,
            },
            {
                "ticker": "NAVN",
                "sector": "Technology",
                "pe_ratio": math.nan,
                "pb_ratio": 2.5,
                "ev_ebitda": -18.0,
                "ps_ratio": 4.3,
                "fcf_yield": 0.056,
                "revenue_growth": 0.35,
                "revenue_growth_calc": math.nan,
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
                "piotroski_fscore": math.nan,
                "upside_potential": 0.73,
                "momentum_12_1m": 0.45,
            },
            {
                "ticker": "ORCL",
                "sector": "Technology",
                "pe_ratio": 25.0,
                "pb_ratio": 12.0,
                "ev_ebitda": 19.0,
                "ps_ratio": 6.2,
                "fcf_yield": -0.04,
                "revenue_growth": 0.09,
                "revenue_growth_calc": 0.08,
                "eps_growth": 0.18,
                "peg_ratio": 0.70,
                "roe": 0.57,
                "gross_margin": 0.67,
                "debt_to_equity": 415.0,
                "fcf_margin": -0.01,
                "avg_surprise_pct": 10.0,
                "eps_revision_90d": 0.01,
                "revenue_acceleration": -0.01,
                "forward_eps_growth": 0.07,
                "piotroski_fscore": 5.0,
                "upside_potential": 0.20,
                "momentum_12_1m": 0.04,
            },
        ]
    )


class TestCoverageHardCaps:
    def test_navn_like_incomplete_stock_is_capped_and_flagged(self):
        scored = calculate_total_score(_make_scoring_fixture())
        navn = scored.loc[scored["ticker"] == "NAVN"].iloc[0]

        assert navn["valuation_coverage"] == 4
        assert navn["growth_coverage"] == 1
        assert navn["quality_coverage"] == 3
        assert navn["earnings_momentum_coverage"] == 4
        assert bool(navn["is_data_complete"]) is False
        assert "growth" in navn["core_data_warning"]
        assert navn["total_score"] <= 59.9
        assert navn["buy_signal"] <= 54.9

    def test_complete_avgo_like_stock_keeps_uncapped_score(self):
        scored = calculate_total_score(_make_scoring_fixture())
        avgo = scored.loc[scored["ticker"] == "AVGO"].iloc[0]

        assert avgo["valuation_coverage"] == 5
        assert avgo["growth_coverage"] == 3
        assert avgo["quality_coverage"] == 4
        assert avgo["earnings_momentum_coverage"] == 4
        assert bool(avgo["is_data_complete"]) is True
        assert avgo["core_data_warning"] == ""
        assert avgo["total_score"] > 59.9

    def test_complete_orcl_like_stock_stays_low_without_missing_data_cap(self):
        scored = calculate_total_score(_make_scoring_fixture())
        orcl = scored.loc[scored["ticker"] == "ORCL"].iloc[0]

        assert bool(orcl["is_data_complete"]) is True
        assert orcl["core_data_warning"] == ""
        assert orcl["total_score"] < 59.9
        assert round(orcl["total_score"], 1) not in {49.9, 59.9}

    def test_regression_complete_names_rank_above_capped_incomplete_name(self):
        scored = calculate_total_score(_make_scoring_fixture())
        ranked = scored.sort_values("total_score", ascending=False)["ticker"].tolist()
        nem = scored.loc[scored["ticker"] == "NEM"].iloc[0]

        assert ranked.index("AVGO") < ranked.index("NAVN")
        assert bool(nem["is_data_complete"]) is True
        assert nem["core_data_warning"] == ""


class TestBuySignalPenalties:
    def test_missing_auxiliary_components_reduce_buy_signal_instead_of_renormalizing(self):
        df = pd.DataFrame(
            [
                {
                    "total_score": 80.0,
                    "piotroski_fscore": 9.0,
                    "upside_potential": 0.50,
                    "price_momentum_score": 60.0,
                    "core_category_fail_count": 0,
                },
                {
                    "total_score": 80.0,
                    "piotroski_fscore": math.nan,
                    "upside_potential": math.nan,
                    "price_momentum_score": 60.0,
                    "core_category_fail_count": 0,
                },
            ]
        )

        signals = _calculate_buy_signal(df)

        assert signals.iloc[0] > signals.iloc[1]

    def test_core_coverage_failure_caps_buy_signal(self):
        df = pd.DataFrame(
            [
                {
                    "total_score": 90.0,
                    "piotroski_fscore": 9.0,
                    "upside_potential": 0.50,
                    "price_momentum_score": 90.0,
                    "core_category_fail_count": 1,
                }
            ]
        )

        signal = _calculate_buy_signal(df).iloc[0]

        assert signal <= 54.9
