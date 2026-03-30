"""backtest.py の時系列IC分析のユニットテスト"""

import os
import tempfile

import numpy as np
import pandas as pd
import pytest

from stock_ranking.backtest import (
    calculate_category_ic,
    calculate_ic,
    discover_ranking_csvs,
    quintile_analysis,
    run_timeseries_ic,
)


@pytest.fixture
def sample_scores():
    """スコアリング結果のサンプルデータ"""
    np.random.seed(42)
    n = 50
    return pd.DataFrame({
        "ticker": [f"T{i:03d}" for i in range(n)],
        "total_score": np.random.uniform(30, 90, n),
        "valuation_score": np.random.uniform(20, 80, n),
        "growth_score": np.random.uniform(20, 80, n),
        "quality_score": np.random.uniform(20, 80, n),
        "earnings_momentum_score": np.random.uniform(20, 80, n),
    })


@pytest.fixture
def sample_returns():
    """将来リターンのサンプルデータ"""
    np.random.seed(42)
    n = 50
    return pd.DataFrame({
        "ticker": [f"T{i:03d}" for i in range(n)],
        "forward_return": np.random.normal(0.02, 0.05, n),
    })


def test_calculate_ic_basic(sample_scores, sample_returns):
    """ICが正しく計算されることを確認"""
    result = calculate_ic(sample_scores, sample_returns, ["total_score"])
    assert len(result) == 1
    assert "ic" in result.columns
    assert "p_value" in result.columns
    assert "n_stocks" in result.columns
    assert result.iloc[0]["n_stocks"] == 50


def test_calculate_ic_insufficient_data(sample_scores):
    """データ不足時にスキップされることを確認"""
    returns = pd.DataFrame({
        "ticker": ["T000", "T001"],
        "forward_return": [0.01, 0.02],
    })
    result = calculate_ic(sample_scores, returns, ["total_score"])
    assert len(result) == 0


def test_calculate_category_ic(sample_scores, sample_returns):
    """カテゴリICが5カテゴリ分計算されることを確認"""
    result = calculate_category_ic(sample_scores, sample_returns)
    assert len(result) == 5
    factors = set(result["factor"])
    assert "total_score" in factors
    assert "growth_score" in factors


def test_quintile_analysis(sample_scores, sample_returns):
    """五分位分析が正しく出力されることを確認"""
    result = quintile_analysis(sample_scores, sample_returns, "total_score")
    assert len(result) == 5
    assert result["quantile"].tolist() == [1, 2, 3, 4, 5]
    assert result["count"].sum() == 50


def test_discover_ranking_csvs(tmp_path):
    """CSVファイルの発見が正しく動作することを確認"""
    for date in ["20260321", "20260322", "20260323"]:
        (tmp_path / f"ranking_{date}.csv").write_text("header\n")
    (tmp_path / "other_file.csv").write_text("header\n")

    result = discover_ranking_csvs(str(tmp_path))
    assert len(result) == 3
    assert "ranking_20260321.csv" in result[0]


def test_timeseries_ic_insufficient_csvs(tmp_path):
    """CSVが1件以下の場合エラーになることを確認"""
    result = run_timeseries_ic(str(tmp_path), forward_days=5)
    assert "error" in result


def test_calculate_ic_with_correlated_data():
    """スコアとリターンに正の相関がある場合、ICが正になることを確認"""
    np.random.seed(123)
    n = 100
    scores = np.random.uniform(0, 100, n)
    # スコアに相関したリターン + ノイズ
    returns = scores * 0.001 + np.random.normal(0, 0.01, n)

    scores_df = pd.DataFrame({
        "ticker": [f"T{i:03d}" for i in range(n)],
        "test_factor": scores,
    })
    returns_df = pd.DataFrame({
        "ticker": [f"T{i:03d}" for i in range(n)],
        "forward_return": returns,
    })

    result = calculate_ic(scores_df, returns_df, ["test_factor"])
    assert result.iloc[0]["ic"] > 0.3  # 強い正の相関を確認
