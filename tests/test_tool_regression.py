"""tool_regression.py のユニットテスト"""

from pathlib import Path

from stock_ranking.tool_regression import load_cases, run_regression_cases


def test_tool_regression_cases_pass():
    cases_path = Path(__file__).parent / "fixtures" / "tool_regression_cases.json"
    results = run_regression_cases(load_cases(cases_path))

    assert results
    assert all(result["ok"] for result in results), results
