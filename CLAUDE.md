# Alpha Seeker

## 概要

S&P500構成銘柄を対象に、過小評価された成長株を定量×定性のハイブリッドスコアリングで発掘するシステム。
「地政学的要因による恒久的な過小評価」ではなく「伸び代のある株」を見つけることが目的。

## アーキテクチャ

```
src/stock_ranking/
├── config.py      # スコアリングの重み・閾値設定
├── data.py        # yfinanceからのデータ取得（財務・決算・アナリスト・ニュース）
├── scoring.py     # 4カテゴリのスコアリングロジック + バリュートラップフィルター
├── explain.py     # スコア根拠レポート生成
└── ranking.py     # CLI エントリポイント（データ取得→スコアリング→出力）
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

## 開発規約

### 実行

```bash
# 特定銘柄のスコアリング
uv run python -m stock_ranking.ranking --tickers AAPL MSFT NVDA --top 30

# S&P500全銘柄（時間がかかる）
uv run python -m stock_ranking.ranking --top 50
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
- yfinance, pandas, lxml

### スコアリング手法

各指標をセクター内パーセンタイルランク(0-100)に変換し、重み付き平均で合成。
セクター内銘柄3未満はスキップ。外れ値は5-95パーセンタイルでクリッピング。

## Git ルール

- **こまめにコミットする**: 1つの機能追加・修正ごとにコミット。大きな変更を1コミットにまとめない
- コミットメッセージは日本語で、変更内容が明確にわかるように書く
- `output/` ディレクトリはCSVとレポートを含むが、大きくなりすぎる場合は `.gitignore` で制御

## CI/CD

GitHub Actionsで日次自動スコアリングを実行:
- `.github/workflows/daily-scoring.yml`
- 毎日 UTC 14:00（JST 23:00）に自動実行、手動トリガーも可
- S&P500全銘柄をスコアリング → CSV/レポート生成 → コミット＆push
- 結果はアーティファクトとしても保存（90日間保持）

## 今後の改善候補

1. バックテスト基盤の構築（IC分析による重み最適化）
2. インサイダー取引データ（SEC EDGAR Form 4）
3. ニュースセンチメント分析（FinBERT）
4. Moomoo証券API連携（ポートフォリオ取得・自動取引）
