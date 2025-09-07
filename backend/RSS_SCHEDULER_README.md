# RSS自動スクレイピング機能

このドキュメントでは、news_check_appに追加された「毎日決まった時間にRSSフィードから記事を自動取得・スクレイピングする機能」の使用方法を説明します。

## 概要

この機能により以下が可能になります：
- テキストファイルに記載されたRSSフィードURLリストの読み込み
- 毎日決まった時間での自動実行
- RSSフィードから最新記事URLを取得し、既存のスクレイピング機能を実行
- 重複記事のスキップと自動タグ生成

## セットアップ

### 1. 依存関係のインストール

```bash
cd backend
pip install -r requirements.txt
```

新しく追加された依存関係：
- `feedparser==6.0.10` - RSSフィード解析
- `aiohttp==3.9.1` - 非同期HTTP クライアント（更新版）

### 2. RSSフィードリストファイルの準備

RSSフィードのURLを記載したテキストファイルを作成します：

```txt
# sample_rss_feeds.txt
https://feeds.feedburner.com/itmedia-news
https://rss.itmedia.co.jp/rss/2.0/topstory.xml
https://feeds.feedburner.jp/ascii/
https://qiita.com/popular-items/feed
# コメント行は無視されます
```

**ファイル形式**：
- 1行1つのRSSフィードURL
- `#` で始まる行はコメント（無視される）
- 空行は無視される
- HTTP/HTTPSプロトコルのURLのみ有効

## API エンドポイント

### RSS関連

#### 1. RSSフィードのテスト
```http
POST /api/rss/feeds/test
Content-Type: application/json

{
  "feeds": [
    {"url": "https://example.com/rss.xml"},
    {"url": "https://example2.com/feed.xml"}
  ]
}
```

#### 2. ファイルからRSSフィードをテスト
```http
POST /api/rss/feeds/from-file?rss_file_path=/path/to/rss_feeds.txt
```

#### 3. RSSファイルのアップロード
```http
POST /api/rss/upload
Content-Type: multipart/form-data

file: <rss_feeds.txt ファイル>
```

#### 4. 手動RSSスクレイピング実行
```http
POST /api/rss/scrape/manual
Content-Type: application/json

{
  "rss_file_path": "/path/to/rss_feeds.txt",
  "auto_generate_tags": true,
  "skip_duplicates": true
}
```

### スケジュール関連

#### 1. スケジュール作成
```http
POST /api/rss/schedule
Content-Type: application/json

{
  "rss_file_path": "/path/to/rss_feeds.txt",
  "hour": 9,
  "minute": 0,
  "auto_generate_tags": true,
  "skip_duplicates": true
}
```

#### 2. スケジュール取得
```http
GET /api/rss/schedule
```

#### 3. スケジュール更新
```http
PUT /api/rss/schedule
Content-Type: application/json

{
  "hour": 10,
  "minute": 30,
  "enabled": true
}
```

#### 4. スケジュール削除
```http
DELETE /api/rss/schedule
```

#### 5. 実行中タスクの確認
```http
GET /api/rss/running-task
```

#### 6. 実行中タスクのキャンセル
```http
POST /api/rss/cancel-task
```

## 使用方法

### 1. RSSフィードリストファイルの作成

```bash
# サンプルファイルをコピーして編集
cp backend/sample_rss_feeds.txt /your/path/my_rss_feeds.txt
```

### 2. RSSフィードのテスト

ファイルが正しく読み込めるかテスト：

```bash
curl -X POST "http://localhost:8000/api/rss/feeds/from-file?rss_file_path=/your/path/my_rss_feeds.txt" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 3. スケジュールの設定

毎朝9時に実行するスケジュールを作成：

```bash
curl -X POST "http://localhost:8000/api/rss/schedule" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
    "rss_file_path": "/your/path/my_rss_feeds.txt",
    "hour": 9,
    "minute": 0,
    "auto_generate_tags": true,
    "skip_duplicates": true
  }'
```

### 4. 手動実行（テスト）

スケジュール待ちせずに手動実行：

```bash
curl -X POST "http://localhost:8000/api/rss/scrape/manual" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
    "rss_file_path": "/your/path/my_rss_feeds.txt",
    "auto_generate_tags": true,
    "skip_duplicates": true
  }'
```

## 動作フロー

1. **スケジューラー起動**: アプリケーション起動時に自動でスケジューラーが開始
2. **時刻チェック**: 1分間隔で現在時刻をチェック
3. **RSSフィード読み込み**: 指定されたファイルからRSSフィードURLを読み込み
4. **RSS取得**: 各RSSフィードから最新記事URLを並列取得
5. **URL統合**: 重複を排除して記事URLリストを作成
6. **スクレイピング実行**: 既存のスクレイピング機能を使用して記事を取得・保存
7. **完了通知**: バックグラウンドタスクとして進捗を追跡

## 技術仕様

### アーキテクチャ

- **RSSService**: RSSフィード解析とURL抽出
- **SchedulerService**: 定期実行スケジュール管理  
- **BackgroundTaskManager**: 既存のバックグラウンドタスク機能を活用
- **ScrapingService**: 既存のスクレイピング機能と統合

### 特徴

- **非同期処理**: aiohttp使用による高速並列RSS取得
- **レート制限**: サーバー負荷軽減のため適切な間隔制御
- **エラーハンドリング**: 個別RSSフィードのエラーは他に影響せず
- **プログレス追跡**: リアルタイムで進捗状況を確認可能
- **既存機能統合**: 既存のスクレイピング・記事管理機能をそのまま活用

### パフォーマンス

- RSSフィード取得: 1件ずつ順次処理（1秒間隔）
- スクレイピング: 既存設定（15秒間隔、バッチ処理）に従う
- メモリ効率: バッチ処理とガベージコレクションでメモリ使用量を最適化

## トラブルシューティング

### よくある問題

1. **RSSフィードが取得できない**
   - URLが正しいか確認
   - RSSフィードが有効か確認
   - ネットワーク接続を確認

2. **スケジュールが実行されない**
   - スケジューラーが起動しているか確認
   - スケジュール設定が有効になっているか確認
   - ログファイルでエラーメッセージを確認

3. **ファイルが見つからない**
   - ファイルパスが正しいか確認
   - ファイルの読み取り権限があるか確認
   - 絶対パスを使用することを推奨

### ログ確認

```bash
# アプリケーションログを確認
tail -f logs/app.log

# 特定の機能のログを絞り込み
grep "RSS" logs/app.log
grep "scheduler" logs/app.log
```

## セキュリティ考慮事項

- RSSフィードのURLは信頼できるソースのみを使用
- ファイルパスの検証でディレクトリトラバーサル攻撃を防止
- レート制限により過度なリクエストを防止
- ユーザー認証が必要な全API エンドポイント

## 制限事項

- RSSフィード数: 推奨上限50個（パフォーマンス考慮）
- ファイルサイズ: アップロードファイルは1MB以下
- 実行頻度: 最短1分間隔（現在は日次のみサポート）
- 同時実行: ユーザーあたり1つのRSSスクレイピングタスクのみ

## 今後の拡張可能性

- 週次・月次スケジュール対応
- RSSフィード個別設定（取得件数制限など）
- Webインターフェースでのスケジュール管理
- 通知機能（メール・Slack等）
- RSS フィードの健全性監視

## サポート

問題が発生した場合は、以下の情報を含めて報告してください：
- 使用していたRSSフィードURL
- エラーメッセージ
- 実行時刻・環境
- ログファイルの該当箇所