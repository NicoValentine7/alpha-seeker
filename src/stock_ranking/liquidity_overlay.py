"""Fed liquidity regime を株式ランキングに重ねる日次 overlay。"""

from __future__ import annotations

from datetime import datetime
from dataclasses import asdict, dataclass
from io import StringIO
import json
import logging
from pathlib import Path
from urllib.request import urlopen

import numpy as np
import pandas as pd

from stock_ranking.config import (
    LIQUIDITY_FRED_TIMEOUT_SEC,
    LIQUIDITY_LIABILITIES_BETA_BASE_BP_PER_BN,
    LIQUIDITY_LIABILITIES_BETA_HIGH_BP_PER_BN,
    LIQUIDITY_LIABILITIES_BETA_LOW_BP_PER_BN,
    LIQUIDITY_OVERLAY_BASELINE_FED_LIABILITIES_BN,
    LIQUIDITY_OVERLAY_BASELINE_IORB,
    LIQUIDITY_OVERLAY_EASING_THRESHOLD_BP,
    LIQUIDITY_OVERLAY_MAX_ADJUSTMENT,
    LIQUIDITY_OVERLAY_PRESSURE_FULL_SCALE_BP,
    LIQUIDITY_OVERLAY_TIGHT_THRESHOLD_BP,
    LIQUIDITY_RATE_BETA_BASE_BP_PER_BP,
    LIQUIDITY_RATE_BETA_HIGH_BP_PER_BP,
    LIQUIDITY_RATE_BETA_LOW_BP_PER_BP,
)

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output"
DEFAULT_CACHE_PATH = DEFAULT_OUTPUT_DIR / "liquidity_regime_latest.json"
DEFAULT_HISTORY_PATH = DEFAULT_OUTPUT_DIR / "liquidity_regime_history.json"

FRED_SERIES = {
    "iorb": "IORB",
    "reserve_balances": "WRESBAL",
    "on_rrp": "WLRRAOL",
}


@dataclass(frozen=True)
class LiquidityRegime:
    """Fed liquidity regime の日次スナップショット。"""

    regime: str
    regime_summary: str
    regime_strength: float
    iorb: float
    iorb_as_of: str
    iorb_delta_bp: float
    reserve_balances_bn: float
    reserve_balances_as_of: str
    on_rrp_bn: float
    on_rrp_as_of: str
    fed_liabilities_bn: float
    fed_liabilities_as_of: str
    fed_liabilities_delta_bn: float
    liquidity_premium_change_low_bp: float
    liquidity_premium_change_base_bp: float
    liquidity_premium_change_high_bp: float

    def to_dict(self) -> dict[str, float | str]:
        return asdict(self)


def _fred_csv_url(series_id: str) -> str:
    return f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"


def _resolve_path(path: str | Path | None, default: Path) -> Path:
    return Path(path) if path is not None else default


def _fetch_latest_fred_value(series_id: str) -> tuple[str, float]:
    """FRED CSV から最新値を取得する。"""
    with urlopen(_fred_csv_url(series_id), timeout=LIQUIDITY_FRED_TIMEOUT_SEC) as response:
        content = response.read().decode("utf-8")

    df = pd.read_csv(StringIO(content))
    date_col = "observation_date" if "observation_date" in df.columns else "DATE"
    if date_col not in df.columns or series_id not in df.columns:
        raise ValueError(f"FRED series format error: {series_id}")

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df[series_id] = pd.to_numeric(df[series_id], errors="coerce")
    latest = df.dropna(subset=[date_col, series_id]).iloc[-1]
    return latest[date_col].date().isoformat(), float(latest[series_id])


def _liquidity_premium_change(
    iorb_delta_bp: float,
    fed_liabilities_delta_bn: float,
    rate_beta: float,
    liabilities_beta: float,
) -> float:
    return (iorb_delta_bp * rate_beta) + (fed_liabilities_delta_bn * liabilities_beta)


def compute_liquidity_regime(
    *,
    iorb: float,
    fed_liabilities_bn: float,
    iorb_as_of: str = "",
    fed_liabilities_as_of: str = "",
    reserve_balances_bn: float | None = None,
    reserve_balances_as_of: str = "",
    on_rrp_bn: float | None = None,
    on_rrp_as_of: str = "",
) -> LiquidityRegime:
    """マクロ入力から liquidity regime を計算する。"""
    iorb_delta_bp = (iorb - LIQUIDITY_OVERLAY_BASELINE_IORB) * 100
    fed_liabilities_delta_bn = fed_liabilities_bn - LIQUIDITY_OVERLAY_BASELINE_FED_LIABILITIES_BN

    lp_low = _liquidity_premium_change(
        iorb_delta_bp,
        fed_liabilities_delta_bn,
        LIQUIDITY_RATE_BETA_LOW_BP_PER_BP,
        LIQUIDITY_LIABILITIES_BETA_LOW_BP_PER_BN,
    )
    lp_base = _liquidity_premium_change(
        iorb_delta_bp,
        fed_liabilities_delta_bn,
        LIQUIDITY_RATE_BETA_BASE_BP_PER_BP,
        LIQUIDITY_LIABILITIES_BETA_BASE_BP_PER_BN,
    )
    lp_high = _liquidity_premium_change(
        iorb_delta_bp,
        fed_liabilities_delta_bn,
        LIQUIDITY_RATE_BETA_HIGH_BP_PER_BP,
        LIQUIDITY_LIABILITIES_BETA_HIGH_BP_PER_BN,
    )

    if lp_base >= LIQUIDITY_OVERLAY_TIGHT_THRESHOLD_BP:
        regime = "tightening"
    elif lp_base <= LIQUIDITY_OVERLAY_EASING_THRESHOLD_BP:
        regime = "easing"
    else:
        regime = "neutral"

    regime_strength = float(np.clip(lp_base / LIQUIDITY_OVERLAY_PRESSURE_FULL_SCALE_BP, -1.0, 1.0))

    direction = {
        "tightening": "資金繰りを締めやすい",
        "neutral": "資金環境はほぼ中立",
        "easing": "資金繰りを緩めやすい",
    }[regime]
    summary = (
        f"Fed liquidity regime: {regime} | IORB {iorb:.2f}% ({iorb_as_of or 'N/A'}) / "
        f"Fed liabilities {fed_liabilities_bn:,.0f}B ({fed_liabilities_as_of or 'N/A'}) | "
        f"推定 liquidity premium 変化 {lp_base:+.2f}bp [{lp_low:+.2f}, {lp_high:+.2f}] | {direction}"
    )

    return LiquidityRegime(
        regime=regime,
        regime_summary=summary,
        regime_strength=round(regime_strength, 4),
        iorb=round(float(iorb), 4),
        iorb_as_of=iorb_as_of,
        iorb_delta_bp=round(float(iorb_delta_bp), 2),
        reserve_balances_bn=round(float(reserve_balances_bn or 0.0), 3),
        reserve_balances_as_of=reserve_balances_as_of,
        on_rrp_bn=round(float(on_rrp_bn or 0.0), 3),
        on_rrp_as_of=on_rrp_as_of,
        fed_liabilities_bn=round(float(fed_liabilities_bn), 3),
        fed_liabilities_as_of=fed_liabilities_as_of,
        fed_liabilities_delta_bn=round(float(fed_liabilities_delta_bn), 3),
        liquidity_premium_change_low_bp=round(float(lp_low), 3),
        liquidity_premium_change_base_bp=round(float(lp_base), 3),
        liquidity_premium_change_high_bp=round(float(lp_high), 3),
    )


def fetch_latest_liquidity_regime() -> LiquidityRegime:
    """FRED 系列から最新の Fed liquidity regime を組み立てる。"""
    return _build_regime_from_fred()


def _build_regime_from_fred() -> LiquidityRegime:
    iorb_as_of, iorb = _fetch_latest_fred_value(FRED_SERIES["iorb"])
    reserve_as_of, reserve_balances = _fetch_latest_fred_value(FRED_SERIES["reserve_balances"])
    on_rrp_as_of, on_rrp = _fetch_latest_fred_value(FRED_SERIES["on_rrp"])

    reserve_balances_bn = reserve_balances / 1_000
    on_rrp_bn = on_rrp / 1_000
    fed_liabilities_bn = reserve_balances_bn + on_rrp_bn
    liabilities_as_of = reserve_as_of if reserve_as_of == on_rrp_as_of else f"{reserve_as_of} / {on_rrp_as_of}"

    return compute_liquidity_regime(
        iorb=iorb,
        fed_liabilities_bn=fed_liabilities_bn,
        iorb_as_of=iorb_as_of,
        fed_liabilities_as_of=liabilities_as_of,
        reserve_balances_bn=reserve_balances_bn,
        reserve_balances_as_of=reserve_as_of,
        on_rrp_bn=on_rrp_bn,
        on_rrp_as_of=on_rrp_as_of,
    )


def load_cached_liquidity_regime(cache_path: str | Path | None = None) -> LiquidityRegime | None:
    """保存済みの最新 regime キャッシュを読む。"""
    path = _resolve_path(cache_path, DEFAULT_CACHE_PATH)
    if not path.exists():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    try:
        return LiquidityRegime(**payload)
    except TypeError:
        return None


def save_liquidity_regime_cache(
    regime: LiquidityRegime,
    cache_path: str | Path | None = None,
) -> Path:
    """最新 regime をキャッシュとして保存する。"""
    path = _resolve_path(cache_path, DEFAULT_CACHE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(regime.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def append_liquidity_regime_history(
    regime: LiquidityRegime,
    *,
    snapshot_date: str | None = None,
    history_path: str | Path | None = None,
) -> Path:
    """日次 regime 履歴を追記する。"""
    path = _resolve_path(history_path, DEFAULT_HISTORY_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    history: list[dict[str, float | str]] = []

    if path.exists():
        try:
            history = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            history = []

    snapshot_date = snapshot_date or datetime.now().strftime("%Y-%m-%d")
    record = {"snapshot_date": snapshot_date, **regime.to_dict()}

    history = [item for item in history if item.get("snapshot_date") != snapshot_date]
    history.append(record)
    history.sort(key=lambda item: item.get("snapshot_date", ""))

    path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def save_liquidity_regime_artifacts(
    regime: LiquidityRegime,
    *,
    snapshot_date: str | None = None,
    output_dir: str | Path | None = None,
) -> tuple[Path, Path]:
    """最新キャッシュと履歴を output 配下に保存する。"""
    out_dir = _resolve_path(output_dir, DEFAULT_OUTPUT_DIR)
    cache_path = out_dir / DEFAULT_CACHE_PATH.name
    history_path = out_dir / DEFAULT_HISTORY_PATH.name
    return (
        save_liquidity_regime_cache(regime, cache_path=cache_path),
        append_liquidity_regime_history(regime, snapshot_date=snapshot_date, history_path=history_path),
    )


def fetch_latest_liquidity_regime_with_fallback(
    cache_path: str | Path | None = None,
) -> LiquidityRegime:
    """FRED 取得に失敗したら最新キャッシュへフォールバックする。"""
    try:
        regime = _build_regime_from_fred()
        save_liquidity_regime_cache(regime, cache_path=cache_path)
        return regime
    except Exception as exc:
        cached = load_cached_liquidity_regime(cache_path=cache_path)
        if cached is not None:
            logger.warning("FRED取得失敗のため cached liquidity regime を利用: %s", exc)
            return cached
        raise


def _mean_available(values: list[float | int | None]) -> float:
    available = [float(v) for v in values if v is not None and not pd.isna(v)]
    if not available:
        return 50.0
    return sum(available) / len(available)


def _style_tilt(row: pd.Series) -> float:
    defensive = _mean_available([row.get("valuation_score"), row.get("quality_score")])
    aggressive = _mean_available([row.get("growth_score"), row.get("price_momentum_score")])
    return float(np.clip((defensive - aggressive) / 100.0, -1.0, 1.0))


def _style_bucket(style_tilt: float) -> str:
    if style_tilt >= 0.10:
        return "quality/value"
    if style_tilt <= -0.10:
        return "growth/momentum"
    return "balanced"


def _overlay_reason(regime: LiquidityRegime, style_tilt: float, adjustment: float) -> str:
    if abs(adjustment) < 0.25:
        return "Fed liquidity regime の影響は小さめ"

    style = _style_bucket(style_tilt)
    if regime.regime == "neutral":
        return "Fed liquidity regime は概ね中立"
    if adjustment > 0:
        return f"{regime.regime} regime がこの銘柄の {style} 傾斜を後押し"
    return f"{regime.regime} regime ではこの銘柄の {style} 傾斜が逆風"


def apply_liquidity_overlay(df: pd.DataFrame, regime: LiquidityRegime) -> pd.DataFrame:
    """銘柄ごとの style tilt に応じて BUY シグナルへ overlay を適用する。"""
    out = df.copy()
    base_signal = (
        out["buy_signal"]
        if "buy_signal" in out.columns
        else out["total_score"] if "total_score" in out.columns
        else pd.Series(np.nan, index=out.index)
    )

    out["liquidity_style_tilt"] = out.apply(_style_tilt, axis=1)
    out["liquidity_overlay_adjustment"] = (
        out["liquidity_style_tilt"]
        * regime.regime_strength
        * LIQUIDITY_OVERLAY_MAX_ADJUSTMENT
    ).clip(lower=-LIQUIDITY_OVERLAY_MAX_ADJUSTMENT, upper=LIQUIDITY_OVERLAY_MAX_ADJUSTMENT)
    out["overlay_buy_signal"] = (base_signal + out["liquidity_overlay_adjustment"]).clip(0, 100)
    out.loc[base_signal.isna(), "overlay_buy_signal"] = np.nan
    out["liquidity_overlay_reason"] = out.apply(
        lambda row: _overlay_reason(regime, row["liquidity_style_tilt"], row["liquidity_overlay_adjustment"]),
        axis=1,
    )

    for key, value in regime.to_dict().items():
        column = {
            "regime": "liquidity_regime",
            "regime_summary": "liquidity_regime_summary",
            "regime_strength": "liquidity_regime_strength",
        }.get(key, key)
        out[column] = value

    out["liquidity_style_tilt"] = out["liquidity_style_tilt"].round(3)
    out["liquidity_overlay_adjustment"] = out["liquidity_overlay_adjustment"].round(2)
    out["overlay_buy_signal"] = out["overlay_buy_signal"].round(2)

    return out


def apply_latest_liquidity_overlay(
    df: pd.DataFrame,
    *,
    cache_path: str | Path | None = None,
) -> tuple[pd.DataFrame, LiquidityRegime | None]:
    """最新 FRED データで overlay を試みる。失敗時は元DFを返す。"""
    try:
        regime = fetch_latest_liquidity_regime_with_fallback(cache_path=cache_path)
    except Exception as exc:
        logger.warning("Fed liquidity regime overlay をスキップ: %s", exc)
        return df, None

    out = apply_liquidity_overlay(df, regime)
    logger.info(regime.regime_summary)
    return out, regime
