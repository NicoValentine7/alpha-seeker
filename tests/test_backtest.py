"""backtest.py のユニットテスト"""

import pandas as pd

from stock_ranking.backtest import build_signal_comparison


def test_build_signal_comparison_includes_overlay_metrics():
    category_ic = pd.DataFrame(
        [
            {"factor": "total_score", "ic": 0.04, "p_value": 0.10, "n_stocks": 100},
            {"factor": "buy_signal", "ic": 0.05, "p_value": 0.05, "n_stocks": 100},
            {"factor": "overlay_buy_signal", "ic": 0.07, "p_value": 0.02, "n_stocks": 100},
        ]
    )
    icir_df = pd.DataFrame(
        [
            {"factor": "buy_signal", "mean_ic": 0.03, "std_ic": 0.02, "icir": 1.5, "hit_rate": 0.7, "n_periods": 10},
            {"factor": "overlay_buy_signal", "mean_ic": 0.04, "std_ic": 0.02, "icir": 2.0, "hit_rate": 0.8, "n_periods": 10},
        ]
    )
    overlay_quintile = pd.DataFrame(
        [
            {"quantile": 1, "mean_return": -0.01},
            {"quantile": 5, "mean_return": 0.03},
        ]
    )
    overlay_quintile.attrs["spread_p_value"] = 0.04

    comparison = build_signal_comparison(
        category_ic=category_ic,
        icir_df=icir_df,
        quintiles={"overlay_buy_signal": overlay_quintile},
    )

    overlay_row = comparison.loc[comparison["factor"] == "overlay_buy_signal"].iloc[0]

    assert set(comparison["factor"]) == {"total_score", "buy_signal", "overlay_buy_signal"}
    assert overlay_row["ic"] == 0.07
    assert overlay_row["icir"] == 2.0
    assert round(float(overlay_row["spread"]), 4) == 0.04
