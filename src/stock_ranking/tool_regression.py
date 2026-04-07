"""OpenTools の発想を借りた最小の内部ツール回帰テスト基盤。"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from stock_ranking.liquidity_overlay import apply_liquidity_overlay, compute_liquidity_regime

ToolHandler = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler


_REGISTRY: dict[str, ToolSpec] = {}


def register_tool(spec: ToolSpec) -> None:
    _REGISTRY[spec.name] = spec


def get_registry() -> dict[str, ToolSpec]:
    ensure_builtin_tools()
    return dict(_REGISTRY)


def invoke_tool(name: str, payload: dict[str, Any]) -> Any:
    ensure_builtin_tools()
    if name not in _REGISTRY:
        raise KeyError(f"unknown tool: {name}")
    return _REGISTRY[name].handler(payload)


def ensure_builtin_tools() -> None:
    if _REGISTRY:
        return

    register_tool(
        ToolSpec(
            name="compute_liquidity_regime",
            description="IORB と Fed liabilities から日次 liquidity regime を計算する",
            input_schema={
                "type": "object",
                "required": ["iorb", "fed_liabilities_bn"],
                "properties": {
                    "iorb": {"type": "number"},
                    "fed_liabilities_bn": {"type": "number"},
                },
            },
            handler=_tool_compute_liquidity_regime,
        )
    )
    register_tool(
        ToolSpec(
            name="apply_liquidity_overlay",
            description="銘柄群に Fed liquidity overlay を適用する",
            input_schema={
                "type": "object",
                "required": ["iorb", "fed_liabilities_bn", "stocks"],
                "properties": {
                    "iorb": {"type": "number"},
                    "fed_liabilities_bn": {"type": "number"},
                    "stocks": {"type": "array"},
                    "output_columns": {"type": "array"},
                },
            },
            handler=_tool_apply_liquidity_overlay,
        )
    )


def _tool_compute_liquidity_regime(payload: dict[str, Any]) -> dict[str, Any]:
    regime = compute_liquidity_regime(
        iorb=float(payload["iorb"]),
        fed_liabilities_bn=float(payload["fed_liabilities_bn"]),
        iorb_as_of=str(payload.get("iorb_as_of", "")),
        fed_liabilities_as_of=str(payload.get("fed_liabilities_as_of", "")),
        reserve_balances_bn=payload.get("reserve_balances_bn"),
        reserve_balances_as_of=str(payload.get("reserve_balances_as_of", "")),
        on_rrp_bn=payload.get("on_rrp_bn"),
        on_rrp_as_of=str(payload.get("on_rrp_as_of", "")),
    )
    return regime.to_dict()


def _tool_apply_liquidity_overlay(payload: dict[str, Any]) -> dict[str, Any]:
    regime = compute_liquidity_regime(
        iorb=float(payload["iorb"]),
        fed_liabilities_bn=float(payload["fed_liabilities_bn"]),
        iorb_as_of=str(payload.get("iorb_as_of", "")),
        fed_liabilities_as_of=str(payload.get("fed_liabilities_as_of", "")),
        reserve_balances_bn=payload.get("reserve_balances_bn"),
        reserve_balances_as_of=str(payload.get("reserve_balances_as_of", "")),
        on_rrp_bn=payload.get("on_rrp_bn"),
        on_rrp_as_of=str(payload.get("on_rrp_as_of", "")),
    )
    df = pd.DataFrame(payload["stocks"])
    overlaid = apply_liquidity_overlay(df, regime)
    columns = payload.get(
        "output_columns",
        ["ticker", "liquidity_overlay_adjustment", "overlay_buy_signal", "liquidity_regime"],
    )
    return {"stocks": overlaid[columns].to_dict(orient="records")}


def load_cases(path: str | Path) -> list[dict[str, Any]]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _compare(expected: Any, actual: Any, *, tolerance: float, path: str = "$") -> list[str]:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path}: expected dict, got {type(actual).__name__}"]
        diffs: list[str] = []
        for key, expected_value in expected.items():
            if key not in actual:
                diffs.append(f"{path}.{key}: missing")
                continue
            diffs.extend(_compare(expected_value, actual[key], tolerance=tolerance, path=f"{path}.{key}"))
        return diffs

    if isinstance(expected, list):
        if not isinstance(actual, list):
            return [f"{path}: expected list, got {type(actual).__name__}"]
        if len(expected) != len(actual):
            return [f"{path}: expected len {len(expected)}, got {len(actual)}"]
        diffs: list[str] = []
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual, strict=False)):
            diffs.extend(_compare(expected_item, actual_item, tolerance=tolerance, path=f"{path}[{index}]"))
        return diffs

    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if math.isnan(float(expected)) and math.isnan(float(actual)):
            return []
        if abs(float(expected) - float(actual)) > tolerance:
            return [f"{path}: expected {expected}, got {actual}"]
        return []

    if expected != actual:
        return [f"{path}: expected {expected!r}, got {actual!r}"]
    return []


def run_regression_cases(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for case in cases:
        actual = invoke_tool(case["tool"], case["input"])
        diffs = _compare(
            case["expected"],
            actual,
            tolerance=float(case.get("tolerance", 0.0)),
        )
        results.append(
            {
                "name": case["name"],
                "tool": case["tool"],
                "ok": not diffs,
                "diffs": diffs,
                "actual": actual,
            }
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="内部ツールの回帰テストを実行する")
    parser.add_argument("cases", type=Path, help="回帰ケースJSON")
    args = parser.parse_args()

    results = run_regression_cases(load_cases(args.cases))
    failed = [result for result in results if not result["ok"]]

    for result in results:
        status = "PASS" if result["ok"] else "FAIL"
        print(f"[{status}] {result['name']} ({result['tool']})")
        for diff in result["diffs"]:
            print(f"  - {diff}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
