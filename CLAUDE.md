# Alpha Seeker

## 概要

S&P500構成銘柄を対象に、過小評価された成長株を定量×定性のハイブリッドスコアリングで発掘するシステム。
「地政学的要因による恒久的な過小評価」ではなく「伸び代のある株」を見つけることが目的。

## アーキテクチャ

```
src/stock_ranking/
├── config.py      # スコアリングの重み・閾値設定 + ブローカー設定
├── data.py        # yfinanceからのデータ取得（財務・決算・アナリスト・ニュース）
├── scoring.py     # 4カテゴリのスコアリングロジック + バリュートラップフィルター
├── explain.py     # スコア根拠レポート生成 + ポートフォリオセクション
├── ranking.py     # CLI エントリポイント（データ取得→スコアリング→出力）
├── backtest.py    # IC分析バックテスト基盤
├── insider.py     # SEC EDGAR Form 4 インサイダー取引データ取得
└── broker/        # Moomoo証券API連携
    ├── client.py      # OpenDゲートウェイ接続管理（contextmanager）
    ├── portfolio.py   # ポジション取得・スコアリングデータとのマージ
    ├── signal.py      # スコアベース売買シグナル生成（買い/売り/リバランス）
    ├── order.py       # 注文確認フロー・発注実行
    └── safety.py      # 発注安全チェック（dry-run、ポジション制限、バリデーション）
```

## スコアリングモデル（4カテゴリ）

| カテゴリ | 重み | 指標 |
|---------|------|------|
| バリュエーション | 25% | PER(20%) PBR(15%) EV/EBITDA(20%) PSR(15%) **FCF利回り(30%)** |
| 成長力 | 30% | 売上成長(30%) 営業利益成長(25%) EPS成長(30%) **PEG(15%)** |
| 質 | 20% | ROE(30%) **粗利率(20%)** D/E(25%) FCFマージン(25%) |
| 決算モメンタム | 25% | サプライズ率(25%) EPS修正90d(25%) 売上加速度(20%) 来期EPS成長(30%) |

### 設計の学術的根拠

- マルチファクターモデルの有効性: MSCI(2018), S&P Global, Nature(2024)の研究で裏付け
- FCF利回りの優位性: Pacer ETFs 30年バックテストでPERより高リターン
- EPS修正の予測力: Zacks, Mill Street Research, Alpha Architectの実証
- セクター内パーセンタイルランク: Stockopedia, Seeking Alpha, Koyfin共通の手法
- 詳細は `docs/research/` を参照

### バリュートラップフィルター

売上3Q連続減少 or D/E>500% の銘柄は総合スコアから-20点のペナルティ。
Seeking Alphaの「失格ルール」、Lord Abbett(2025)のバリュートラップ研究に基づく。

### Piotroski F-Score

9つの財務指標で0-9のスコアを算出し、バリュートラップ検出を強化:
- 収益性(4): ROA>0, CFO>0, ROA改善, CFO>NI（アクルーアル品質）
- レバレッジ(3): 長期負債低下, 流動比率改善, 希薄化なし
- 効率(2): 粗利率改善, 資産回転率改善
- F-Score≤2の銘柄はバリュートラップとして-20点ペナルティ

## 開発規約

### 実行

```bash
# 特定銘柄のスコアリング
uv run python -m stock_ranking.ranking --tickers AAPL MSFT NVDA --top 30

# S&P500全銘柄（時間がかかる）
uv run python -m stock_ranking.ranking --top 50

# Moomoo保有ポジションをスコアと照合（OpenDが起動している必要あり）
uv run python -m stock_ranking.ranking --tickers AAPL MSFT NVDA --top 30 --portfolio

# スコアに基づく売買提案を生成（確認フロー付き、OpenD必須）
uv run python -m stock_ranking.ranking --top 50 --trade

# IC分析バックテスト
uv run python -m stock_ranking.backtest --csv output/ranking_YYYYMMDD.csv --days 21
```

### 出力

- CSV: `output/ranking_YYYYMMDD.csv`
- レポート: `output/report_YYYYMMDD.txt`

### データソース

yfinance経由で取得。主要データ:
- `info`: バリュエーション指標、アナリスト評価、企業情報
- `financials` / `cashflow`: 年次財務諸表
- `quarterly_financials`: 四半期業績
- `earnings_dates`: 決算サプライズ（EPS予想vs実績）
- `eps_trend`: EPS予想の修正トレンド（90日/30日前比較）
- `earnings_estimate` / `revenue_estimate`: 来期成長予想
- `upgrades_downgrades`: アナリストアクション
- `news`: 直近ニュース

### 依存関係

- Python 3.12+, uv
- yfinance, pandas, lxml, moomoo-api, pytest(dev)

### スコアリング手法

各指標をセクター内パーセンタイルランク(0-100)に変換し、重み付き平均で合成。
セクター内銘柄3未満はスキップ。外れ値は5-95パーセンタイルでクリッピング。

## Git ルール

- **こまめにコミットする**: 1つの機能追加・修正ごとにコミット。大きな変更を1コミットにまとめない
- コミットメッセージは日本語で、変更内容が明確にわかるように書く
- `output/` ディレクトリはCSVとレポートを含むが、大きくなりすぎる場合は `.gitignore` で制御

## Webダッシュボード

React + Tailwind + TanStack Table でインタラクティブなランキングビューアを提供。
- `web/` ディレクトリ: Vite + React + TypeScript
- GitHub Pagesで自動デプロイ: https://nicovalentine7.github.io/alpha-seeker/
- 機能: ソート、フィルター（セクター/銘柄名/Min Score/Value Trap/保有銘柄）、カラム表示切替、行クリック詳細展開
- セクター別平均スコアチャート（Recharts、折りたたみ式）
- 保有銘柄フィルター: CIのranking.json生成時に`is_portfolio`フラグを付与
  - 保有銘柄を変更する場合: `config/portfolio.json` の `tickers` を編集するだけ（CI側は自動反映）
- StockDetailはErrorBoundaryで保護（データ不正時もページ全体がクラッシュしない）

## CI/CD

GitHub Actionsで日次自動スコアリングを実行:
- `.github/workflows/daily-scoring.yml`
- 毎日 UTC 22:00（米国市場クローズ後、JST 07:00）に自動実行、手動トリガーも可
- S&P500全銘柄 + `--extra`銘柄（保有株）をスコアリング → CSV/レポート/JSON生成 → コミット＆push
- Reactダッシュボードをビルドして GitHub Pages にデプロイ
- 結果はアーティファクトとしても保存（90日間保持）
- yfinance rate limit対策: 優先銘柄の逐次先行取得 + バッチ分割(100銘柄) + クールダウン(5秒) + 失敗リトライ(3秒間隔)
- ranking.json生成時にCSVのリスト型カラム（news等）を`ast.literal_eval`でパース

## Moomoo証券API連携

moomoo OpenAPI経由でポートフォリオ取得・自動取引を実現する。OpenDゲートウェイデーモンがローカルで起動している必要がある。

### フェーズ

| Phase | 内容 | 状態 |
|-------|------|------|
| 1 | ポートフォリオ可視化（`--portfolio`フラグ） | 実装済み |
| 2 | 注文提案 + 手動確認フロー（`--trade`フラグ） | 実装済み |
| 3 | 半自動取引（指値のみ、ポジション制限付き） | 未着手 |

### 安全設計

- `BROKER_DRY_RUN = True` がデフォルト（実発注にはFalseに変更が必要）
- 1銘柄あたりポジション上限: 総資産の10%（`BROKER_MAX_POSITION_PCT`）
- 成行注文は原則禁止（指値のみ）
- OpenDはステートフルデーモンのためGitHub Actionsでは実行不可

### OpenDセットアップ

1. moomooアプリ → 設定 → OpenAPI → OpenDダウンロード
2. `FutuOpenD.xml` にmoomoo IDとパスワードを設定
3. OpenD起動後、`127.0.0.1:11111` でAPI接続可能

## 今後の改善候補

1. バックテスト基盤の構築（IC分析による重み最適化）
2. インサイダー取引データ（SEC EDGAR Form 4）
3. ニュースセンチメント分析（FinBERT）
4. Moomoo証券 Phase 3: 半自動取引（確認なし自動発注、スケジューラ連携）
5. テストカバレッジ拡充（order.py、portfolio.pyのテスト）

# currentDate
Today's date is 2026-03-24.
