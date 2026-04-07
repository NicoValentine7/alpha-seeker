"""スコアリングの重み付け・設定値"""

import os

# --- カテゴリ別の総合スコアへの重み ---
# IC分析(2026-03-30)と学術レビューに基づく調整:
# - バリュエーション: ICIR +3.26（最強）→ 維持
# - 質: ブートストラップCIが正方向 → 30%に増量（Fama-French 5F, AQR QMJ）
# - 成長: ICIR -1.41（逆シグナル）→ 20%に減量、冗長指標整理
# - 決算モメンタム: ICIR -3.43 → 15%に減量（短期ミーンリバージョン疑い）
# - 価格モメンタム: 新規追加（Jegadeesh & Titman 1993、最も堅牢なアノマリー）
CATEGORY_WEIGHTS = {
    "valuation": 0.25,
    "growth": 0.20,
    "quality": 0.30,
    "earnings_momentum": 0.15,
    "price_momentum": 0.10,
}

# --- バリュエーション割安度の指標別重み ---
VALUATION_WEIGHTS = {
    "pe_ratio": 0.20,
    "pb_ratio": 0.15,
    "ev_ebitda": 0.20,
    "ps_ratio": 0.15,
    "fcf_yield": 0.30,  # FCF利回り（30年バックテストで最高リターン）
}

# --- 成長力の指標別重み ---
# 営業利益成長を削除（売上・EPSと高相関で冗長）、PEGを30%に強化
GROWTH_WEIGHTS = {
    "revenue_growth": 0.35,
    "eps_growth": 0.35,
    "peg_ratio": 0.30,  # GARP: 成長と価格のバランス。Lynch(1989)の核心指標
}

# --- 質・健全性の指標別重み ---
# ROEはレバレッジ効果で歪むため25%に抑制、FCFマージンを強化
QUALITY_WEIGHTS = {
    "roe": 0.25,
    "gross_margin": 0.20,  # 粗利率（モート/コスト優位性のプロキシ）
    "debt_to_equity": 0.25,
    "fcf_margin": 0.30,  # キャッシュ生成力の直接測定
}

# --- バリュートラップフィルター閾値 ---
VALUE_TRAP_FILTERS = {
    "max_consecutive_revenue_decline": 3,  # 四半期連続売上減少の上限
    "max_debt_to_equity": 500,             # D/E比率の上限(%)
}

# --- 決算モメンタムの指標別重み ---
EARNINGS_MOMENTUM_WEIGHTS = {
    "avg_surprise": 0.25,       # 決算サプライズ率の平均
    "eps_revision_90d": 0.25,   # EPS予想の90日間上方修正率
    "revenue_acceleration": 0.20,  # 売上成長の加速度
    "forward_eps_growth": 0.30, # 来期EPS成長予想
}

# --- 価格モメンタムの指標別重み ---
# Jegadeesh & Titman (1993): 12-1ヶ月モメンタムが最も堅牢
PRICE_MOMENTUM_WEIGHTS = {
    "momentum_12_1m": 1.0,  # 12ヶ月リターン（直近1ヶ月除外）
}

# --- 外れ値クリッピング ---
CLIP_LOWER_PERCENTILE = 5
CLIP_UPPER_PERCENTILE = 95

# --- データ取得設定 ---
FETCH_DELAY_SEC = 0.15  # yfinance APIへのリクエスト間隔（逐次取得時）
FETCH_MAX_WORKERS = int(os.environ.get("FETCH_MAX_WORKERS", "8"))  # 並列取得のワーカー数
TOP_N_DISPLAY = 30  # コンソールに表示するランキング数

# --- Moomoo証券ブローカー設定 ---
BROKER_HOST = os.environ.get("BROKER_HOST", "127.0.0.1")
BROKER_PORT = int(os.environ.get("BROKER_PORT", "11111"))
BROKER_DRY_RUN = os.environ.get("BROKER_DRY_RUN", "true").lower() == "true"
BROKER_MAX_POSITION_PCT = 0.10  # 1銘柄の上限: 総資産の10%

# --- 売買シグナル設定 ---
SIGNAL_BUY_MIN_SCORE = 70         # 買い検討の最低スコア
SIGNAL_BUY_TOP_N = 5              # 買いシグナルの最大銘柄数
SIGNAL_SELL_MAX_SCORE = 30        # 売り検討の最高スコア
SIGNAL_REBALANCE_THRESHOLD = 0.03  # リバランス発動の乖離率(3%)
SIGNAL_MAX_ORDERS_PER_SESSION = 10  # 1セッションの最大注文数

# --- Fed liquidity regime overlay 設定 ---
LIQUIDITY_OVERLAY_ENABLED = os.environ.get("LIQUIDITY_OVERLAY_ENABLED", "true").lower() == "true"
LIQUIDITY_OVERLAY_BASELINE_IORB = float(os.environ.get("LIQUIDITY_OVERLAY_BASELINE_IORB", "5.40"))
LIQUIDITY_OVERLAY_BASELINE_FED_LIABILITIES_BN = float(
    os.environ.get("LIQUIDITY_OVERLAY_BASELINE_FED_LIABILITIES_BN", "3500")
)
LIQUIDITY_OVERLAY_PRESSURE_FULL_SCALE_BP = float(
    os.environ.get("LIQUIDITY_OVERLAY_PRESSURE_FULL_SCALE_BP", "4.0")
)
LIQUIDITY_OVERLAY_MAX_ADJUSTMENT = float(
    os.environ.get("LIQUIDITY_OVERLAY_MAX_ADJUSTMENT", "8.0")
)
LIQUIDITY_OVERLAY_TIGHT_THRESHOLD_BP = float(
    os.environ.get("LIQUIDITY_OVERLAY_TIGHT_THRESHOLD_BP", "1.0")
)
LIQUIDITY_OVERLAY_EASING_THRESHOLD_BP = float(
    os.environ.get("LIQUIDITY_OVERLAY_EASING_THRESHOLD_BP", "-1.0")
)
LIQUIDITY_FRED_TIMEOUT_SEC = float(os.environ.get("LIQUIDITY_FRED_TIMEOUT_SEC", "15"))

# Liberty Street Economics (2026-04-06) の one-standard-deviation 推定値を日次overlayに転用
LIQUIDITY_RATE_BETA_LOW_BP_PER_BP = 2.1 / 226
LIQUIDITY_RATE_BETA_BASE_BP_PER_BP = 2.8 / 226
LIQUIDITY_RATE_BETA_HIGH_BP_PER_BP = 3.5 / 226
LIQUIDITY_LIABILITIES_BETA_LOW_BP_PER_BN = -1.6 / 750
LIQUIDITY_LIABILITIES_BETA_BASE_BP_PER_BN = -2.05 / 750
LIQUIDITY_LIABILITIES_BETA_HIGH_BP_PER_BN = -2.5 / 750
