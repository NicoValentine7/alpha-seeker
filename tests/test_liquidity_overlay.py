"""liquidity_overlay.py のユニットテスト"""

import json

import pandas as pd

from stock_ranking.liquidity_overlay import (
    append_liquidity_regime_history,
    apply_liquidity_overlay,
    compute_liquidity_regime,
    load_cached_liquidity_regime,
    save_liquidity_regime_cache,
)


def test_compute_liquidity_regime_classifies_tightening():
    regime = compute_liquidity_regime(
        iorb=5.40,
        fed_liabilities_bn=3000.0,
        iorb_as_of="2026-04-07",
        fed_liabilities_as_of="2026-04-02",
    )

    assert regime.regime == "tightening"
    assert regime.liquidity_premium_change_base_bp > 1.0
    assert regime.regime_strength > 0


def test_apply_liquidity_overlay_favors_defensive_names_in_tightening():
    regime = compute_liquidity_regime(
        iorb=5.40,
        fed_liabilities_bn=3000.0,
        iorb_as_of="2026-04-07",
        fed_liabilities_as_of="2026-04-02",
    )
    df = pd.DataFrame(
        [
            {
                "ticker": "QUAL",
                "buy_signal": 70.0,
                "valuation_score": 80.0,
                "quality_score": 85.0,
                "growth_score": 40.0,
                "price_momentum_score": 30.0,
            },
            {
                "ticker": "MOMO",
                "buy_signal": 70.0,
                "valuation_score": 30.0,
                "quality_score": 40.0,
                "growth_score": 85.0,
                "price_momentum_score": 80.0,
            },
        ]
    )

    overlaid = apply_liquidity_overlay(df, regime)
    qual = overlaid.loc[overlaid["ticker"] == "QUAL"].iloc[0]
    momo = overlaid.loc[overlaid["ticker"] == "MOMO"].iloc[0]

    assert qual["liquidity_overlay_adjustment"] > 0
    assert momo["liquidity_overlay_adjustment"] < 0
    assert qual["overlay_buy_signal"] > qual["buy_signal"]
    assert momo["overlay_buy_signal"] < momo["buy_signal"]


def test_apply_liquidity_overlay_carries_regime_columns():
    regime = compute_liquidity_regime(
        iorb=5.40,
        fed_liabilities_bn=3500.0,
        iorb_as_of="2026-04-07",
        fed_liabilities_as_of="2026-04-02",
    )
    df = pd.DataFrame([{"ticker": "AAPL", "buy_signal": 70.0}])

    overlaid = apply_liquidity_overlay(df, regime)
    row = overlaid.iloc[0]

    assert row["liquidity_regime"] == "neutral"
    assert row["liquidity_regime_summary"]
    assert row["fed_liabilities_bn"] == 3500.0


def test_cache_and_history_persist_regime(tmp_path):
    regime = compute_liquidity_regime(
        iorb=3.65,
        fed_liabilities_bn=3029.0,
        iorb_as_of="2026-04-07",
        fed_liabilities_as_of="2026-04-01",
    )
    cache_path = tmp_path / "liquidity_regime_latest.json"
    history_path = tmp_path / "liquidity_regime_history.json"

    save_liquidity_regime_cache(regime, cache_path=cache_path)
    cached = load_cached_liquidity_regime(cache_path=cache_path)
    append_liquidity_regime_history(regime, snapshot_date="2026-04-07", history_path=history_path)
    append_liquidity_regime_history(regime, snapshot_date="2026-04-07", history_path=history_path)

    history = json.loads(history_path.read_text(encoding="utf-8"))

    assert cached == regime
    assert len(history) == 1
    assert history[0]["snapshot_date"] == "2026-04-07"
