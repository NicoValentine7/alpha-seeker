"""スコアリングの重み付け・設定値"""

import os

# --- カテゴリ別の総合スコアへの重み ---
CATEGORY_WEIGHTS = {
    "valuation": 0.25,
    "growth": 0.30,
    "quality": 0.20,
    "earnings_momentum": 0.25,
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
GROWTH_WEIGHTS = {
    "revenue_growth": 0.30,
    "operating_income_growth": 0.25,
    "eps_growth": 0.30,
    "peg_ratio": 0.15,  # GARP: 成長と価格のバランス
}

# --- 質・健全性の指標別重み ---
QUALITY_WEIGHTS = {
    "roe": 0.30,
    "gross_margin": 0.20,  # 粗利率（モート/コスト優位性のプロキシ）
    "debt_to_equity": 0.25,
    "fcf_margin": 0.25,
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

# --- 外れ値クリッピング ---
CLIP_LOWER_PERCENTILE = 5
CLIP_UPPER_PERCENTILE = 95

# --- データ取得設定 ---
FETCH_DELAY_SEC = 0.15  # yfinance APIへのリクエスト間隔（逐次取得時）
FETCH_MAX_WORKERS = 8   # 並列取得のワーカー数
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
