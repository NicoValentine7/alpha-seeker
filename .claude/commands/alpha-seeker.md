# Alpha Seeker 運用コマンド

stock-rankingプロジェクトの日常運用を一括実行するコマンド。
引数に応じてサブコマンドを実行する。引数なしの場合は status+verify を並列実行。

## 使い方

- `/alpha-seeker` — status + verify を**並列エージェント**で同時実行（デフォルト）
- `/alpha-seeker status` — デプロイ済みダッシュボードの状態確認
- `/alpha-seeker deploy` — CI手動トリガー→完了監視→デプロイ確認
- `/alpha-seeker verify` — ranking.jsonのデータ整合性チェック
- `/alpha-seeker portfolio` — 保有銘柄リスト確認・更新
- `/alpha-seeker all` — verify + portfolio確認 → deploy の順で全実行

引数: $ARGUMENTS

---

## 並列実行ルール

以下のサブコマンドは**独立しているためAgentツールで並列実行**する:
- `status` と `verify` → 同時にAgentを起動して並列で結果を取得

以下は**依存があるため順次実行**:
- `portfolio` → 変更があった場合に `deploy` をチェーン実行
- `deploy` → CI完了後に自動で status 相当の検証を実行

引数なし（デフォルト）の場合: `status` と `verify` を2つのAgentで並列起動し、両方の結果をまとめて報告する。

---

## 実行手順

### `status`

Agentツールで以下を実行（subagent_type: general-purpose, model: haiku）:

1. `curl -s 'https://nicovalentine7.github.io/alpha-seeker/ranking.json'` でデプロイ済みJSONを取得
2. 以下を報告:
   - 最終更新日（`date`）
   - 総銘柄数（`count`）
   - ポートフォリオ銘柄の一覧とスコア
   - `earnings_surprises` データ有無の統計
   - スコア上位5銘柄
3. `gh run list --limit 3` で直近のCI実行結果を表示
4. CI結果が最新のranking.jsonの日付より新しい場合、「デプロイ未反映の可能性」を警告

### `verify`

Agentツールで以下を実行（subagent_type: general-purpose, model: haiku）:

1. `curl -s 'https://nicovalentine7.github.io/alpha-seeker/ranking.json'` でデプロイ済みJSONを取得
2. 以下のチェックを実行:
   - `portfolio_tickers` に含まれる全銘柄が `stocks` 配列に存在するか
   - `is_portfolio=True` の銘柄数が `portfolio_tickers` の件数と一致するか
   - `earnings_surprises` がnullでない銘柄の割合（50%以上を期待）
   - `total_score` がnullの銘柄がないか
   - `sparkline` データがある銘柄の割合
   - `news` データがある銘柄の割合
3. 問題があれば詳細を報告し、修正方針を提案
4. 問題がなければ「検証OK」と報告

### `deploy`

1. `gh workflow run daily-scoring.yml` でCI手動トリガー
2. 2分間隔のcronで `gh run view <run_id> --json status,conclusion` を監視（CronCreate使用）
3. CI完了後:
   - success → デプロイ済みranking.jsonを `curl` で取得して `status` と同じ検証を実行
   - failure → `gh run view <run_id> --log` でエラーログを取得して報告
4. cron監視ジョブを削除（CronDelete）

### `portfolio`

1. `config/portfolio.json` の現在の内容を表示
2. ユーザーに変更があるか `AskUserQuestion` で確認
3. 変更がある場合:
   - `config/portfolio.json` を更新
   - git add → commit → push
   - `deploy` サブコマンドと同じCI監視フローを実行
4. 変更がない場合は現在の状態を報告して終了

### `all`

1. `status` と `verify` を**並列Agentで同時実行**
2. 両方の結果をまとめて報告
3. `portfolio` を実行（対話式、ユーザー入力を待つ）
4. 必要に応じて `deploy` を実行
