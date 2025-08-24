# ITニュース管理システム 設計書・要件定義書

## 1. プロジェクト概要

### 目的
- NotionからAPIコストと安定性の問題を解決
- ITニュースの効率的な収集・管理・活用システムの構築
- 複数ユーザーでの共有とコラボレーション機能

### システム構成
```
フロントエンド: React + TypeScript + Tailwind CSS
バックエンド: Python FastAPI
データベース: PostgreSQL + pgvector
AI処理: Anthropic Claude API
認証: JWT
デプロイ: レンタルサーバー (メモリ1GB, CPU2コア)
```

## 2. 機能要件

### 2.1 ユーザー管理機能

#### 2.1.1 認証・認可
- **ログイン機能**: JWT認証
- **招待制システム**: 管理者が招待URLを生成
- **ユーザー役割**:
  - `admin`: 全機能利用可能
  - `user`: 閲覧、検索、エクスポート機能のみ

#### 2.1.2 ユーザー管理
- ユーザー一覧表示
- ユーザー削除機能
- 招待リンク生成・管理

### 2.2 記事管理機能

#### 2.2.1 記事データ構造
```sql
articles (
  id: UUID PRIMARY KEY,
  title: VARCHAR(500) NOT NULL,
  content: TEXT,
  url: VARCHAR(1000) UNIQUE NOT NULL,
  source: VARCHAR(200),
  published_date: TIMESTAMP,
  scraped_date: TIMESTAMP DEFAULT NOW(),
  tags: VARCHAR(100)[],
  summary: TEXT,
  is_favorite: BOOLEAN DEFAULT FALSE,
  created_by: UUID REFERENCES users(id),
  search_vector: tsvector, -- PostgreSQL全文検索用
  created_at: TIMESTAMP DEFAULT NOW(),
  updated_at: TIMESTAMP DEFAULT NOW()
)
```

#### 2.2.2 記事操作
- **記事一覧表示**: ページネーション対応
- **記事詳細表示**: Markdown対応
- **お気に入り機能**: ユーザー毎の管理
- **タグ管理**: 自動抽出 + 手動編集
- **記事削除**: 管理者のみ

### 2.3 URLスクレイピング機能

#### 2.3.1 URL入力方式
- **テキストエリア入力**: 複数URL一括入力
  - **対応形式**:
    - 1行1URL形式: `https://example.com/article1`
    - Markdown箇条書き: `- https://example.com/article1`
    - 混在形式も対応（自動パース）
  - **前処理機能**:
    - 空行自動除去
    - 重複URL検出・除去
    - URL形式バリデーション
    - 既存記事との重複チェック
- **iPhoneショートカット連携想定**: 
  - ショートカットでメモアプリにURL蓄積
  - メモからコピペしてテキストエリアに貼り付け
- **Obsidian連携想定**:
  - デイリーページのMarkdown箇条書きをコピペ
  - `## ITニュース` セクション等からの抽出

#### 2.3.2 URL入力インターフェース
- **大きなテキストエリア**: 100URL程度を想定
- **URLプレビュー**: 入力URLの一覧表示・個別削除可能
- **重複チェック結果**: 既存記事との照合結果表示
- **推定処理時間**: URL数から処理時間を概算表示
- **一括処理開始**: 確認後にスクレイピング開始

#### 2.3.3 スクレイピング処理
- **非同期処理**: Celery + Redis
- **進捗表示**: WebSocket or ポーリング
  - 処理済みURL数 / 総URL数
  - 現在処理中のURL表示
  - 成功・失敗カウント
- **エラーハンドリング**: 
  - タイムアウト: 30秒
  - 404エラー: 失敗URL一覧に記録
  - SSL証明書エラー: 警告付きで継続
  - 文字化け: エンコーディング自動検出
- **対応サイト**: 一般的なニュースサイト、技術ブログ
  - User-Agent設定でブロック回避
  - robots.txt準拠
  - レート制限（同一ドメイン1秒間隔）

#### 2.3.4 取得データ
- **基本情報**:
  - タイトル（`<title>`タグ、`og:title`）
  - 本文内容（メインコンテンツ抽出）
  - URL（正規化後）
- **メタデータ**:
  - 公開日時（`<meta>`タグ、構造化データ）
  - サイト名（ドメイン名、`og:site_name`）
  - description（`<meta name="description">`）
  - keywords（`<meta name="keywords"`）
- **自動タグ生成**:
  - タイトル・本文からキーワード抽出
  - 技術名の自動認識（React, Python等）

#### 2.3.5 Mac mini移行後の拡張機能
- **iCloudフォルダ監視**: 
  - 指定フォルダのテキストファイル自動取り込み
  - ファイル更新検知で自動スクレイピング
- **API直接登録**: 
  - Raycast/Alfred拡張からの直接登録
  - ショートカットからAPI直接呼び出し

### 2.4 検索機能

#### 2.4.1 検索方式
- **全文検索**: PostgreSQL tsvector
- **フィルター検索**:
  - 日付範囲
  - タグ
  - サイト（source）
  - お気に入りのみ
- **並び替え**: 関連度、日付、タイトル

#### 2.4.2 検索インターフェース
- **検索ボックス**: Google風シンプル検索
- **サジェスト機能**: よく検索されるキーワード
- **詳細検索**: サイドバーでフィルター
- **保存検索**: ユーザー毎の検索条件保存

#### 2.4.3 検索結果表示
- **ハイライト表示**: マッチ部分の強調
- **スニペット**: 関連部分の抜粋
- **関連記事**: 類似記事の提案

### 2.5 LLM連携機能

#### 2.5.1 要約生成
- **個別要約**: 記事1件の要約生成
- **一括要約**: 選択記事の要約
- **要約保存**: データベースに保存

#### 2.5.2 レポート生成
- **カスタムレポート**: 選択記事からのレポート作成
- **期間別レポート**: 指定期間のトレンド分析
- **テーマ別レポート**: 技術分野別の動向分析

#### 2.5.3 プロンプト管理
- **プロンプトテンプレート**: 用途別プロンプト
- **プロンプト編集**: 管理者による編集機能
- **バージョン管理**: プロンプトの履歴管理

### 2.6 エクスポート機能

#### 2.6.1 Markdownエクスポート
- **単一記事**: 個別記事のMarkdown出力（`.md`ファイル）
- **複数記事選択**: チェックボックスで選択
- **出力形式**:
  - 個別ファイル: 記事ごとに分割してZIP出力
  - 記事一覧形式: タイトル・URL・要約のリスト（`.md`ファイル）
- **ダウンロード**: 
  - 単一記事: `.md`ファイル直接ダウンロード
  - 複数記事: ZIPファイル
  - 記事一覧: `.md`ファイル直接ダウンロード

#### 2.6.2 その他エクスポート
- **JSON形式**: API連携用
- **CSV形式**: データ分析用（記事メタデータ）

## 3. 非機能要件

### 3.1 性能要件
- **レスポンス時間**: 通常画面2秒以内
- **検索性能**: 1万件データで1秒以内
- **同時接続**: 10ユーザー程度

### 3.2 可用性
- **稼働時間**: 99%以上
- **バックアップ**: 日次自動バックアップ
- **復旧時間**: 1時間以内

### 3.3 セキュリティ
- **認証**: JWT（有効期限24時間）
- **権限管理**: RBAC
- **データ保護**: HTTPS通信
- **入力検証**: XSS、SQLインジェクション対策

### 3.4 運用性
- **ログ**: アクセスログ、エラーログ
- **監視**: ヘルスチェック機能
- **メンテナンス**: ローリングアップデート対応

## 4. データベース設計

### 4.1 テーブル定義

#### users
```sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role VARCHAR(20) NOT NULL DEFAULT 'user', -- 'admin' or 'user'
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
```

#### articles
```sql
CREATE TABLE articles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title VARCHAR(500) NOT NULL,
  content TEXT,
  url VARCHAR(1000) UNIQUE NOT NULL,
  source VARCHAR(200),
  published_date TIMESTAMP,
  scraped_date TIMESTAMP DEFAULT NOW(),
  tags TEXT[],
  summary TEXT,
  created_by UUID REFERENCES users(id),
  search_vector tsvector,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- 全文検索インデックス
CREATE INDEX idx_articles_search ON articles USING GIN(search_vector);
CREATE INDEX idx_articles_url ON articles(url);
CREATE INDEX idx_articles_scraped_date ON articles(scraped_date DESC);
```

#### user_favorites
```sql
CREATE TABLE user_favorites (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  article_id UUID REFERENCES articles(id) ON DELETE CASCADE,
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(user_id, article_id)
);
```

#### scraping_jobs
```sql
CREATE TABLE scraping_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  urls TEXT[],
  status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed'
  progress INTEGER DEFAULT 0,
  total INTEGER DEFAULT 0,
  error_urls TEXT[],
  created_at TIMESTAMP DEFAULT NOW(),
  completed_at TIMESTAMP
);
```

#### prompt_templates
```sql
CREATE TABLE prompt_templates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(100) NOT NULL,
  description TEXT,
  template TEXT NOT NULL,
  type VARCHAR(50) NOT NULL, -- 'summary', 'report', 'analysis'
  is_active BOOLEAN DEFAULT TRUE,
  created_by UUID REFERENCES users(id),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
```

### 4.2 初期データ

#### 管理者ユーザー
```sql
INSERT INTO users (email, password_hash, role) VALUES 
('admin@example.com', '$hashed_password', 'admin');
```

#### プロンプトテンプレート
```sql
INSERT INTO prompt_templates (name, description, template, type) VALUES 
(
  '記事要約',
  '技術記事の要約生成用',
  'この技術記事を簡潔に要約してください。主要なポイントを箇条書きで整理してください。\n\n記事内容:\n{content}',
  'summary'
),
(
  'トレンドレポート',
  '複数記事からのトレンド分析',
  '以下の技術記事から、{period}期間のトレンドを分析してレポートを作成してください。\n\n記事一覧:\n{articles}',
  'report'
);
```

## 5. API設計

### 5.1 認証API

#### POST /api/auth/login
```json
{
  "email": "user@example.com",
  "password": "password"
}
```

#### POST /api/auth/register (招待URL経由)
```json
{
  "token": "invitation_token",
  "email": "user@example.com",
  "password": "password"
}
```

#### POST /api/auth/invite (管理者のみ)
```json
{
  "email": "user@example.com"
}
```

### 5.2 記事API

#### GET /api/articles
```
Query Parameters:
- page: int (default: 1)
- limit: int (default: 20)
- search: string
- tags: string[]
- source: string
- start_date: string (YYYY-MM-DD)
- end_date: string (YYYY-MM-DD)
- favorites_only: boolean
```

#### POST /api/articles/scrape
```json
{
  "urls_text": "https://example.com/article1\n- https://example.com/article2\nhttps://example.com/article3",
  "auto_generate_tags": true,
  "skip_duplicates": true
}
```

Response:
```json
{
  "job_id": "uuid",
  "parsed_urls": ["https://example.com/article1", "https://example.com/article2"],
  "duplicate_urls": ["https://example.com/article3"],
  "invalid_urls": [],
  "estimated_time": "約5分"
}
```

#### GET /api/articles/scrape/{job_id}
```json
{
  "id": "job_id",
  "status": "running",
  "progress": 5,
  "total": 10,
  "completed_urls": ["url1", "url2"],
  "error_urls": [{"url": "url3", "error": "404 Not Found"}]
}
```

### 5.3 LLM API

#### POST /api/llm/summarize
```json
{
  "article_ids": ["uuid1", "uuid2"],
  "prompt_template_id": "uuid"
}
```

#### POST /api/llm/report
```json
{
  "article_ids": ["uuid1", "uuid2"],
  "prompt_template_id": "uuid",
  "period": "2024年1月"
}
```

### 5.4 エクスポートAPI

#### POST /api/export/markdown
```json
{
  "article_ids": ["uuid1", "uuid2"],
  "format": "individual", // "individual" or "list"
  "include_content": true,
  "include_summary": true,
  "include_tags": true
}
```

Response:
- 単一記事: Markdownファイル直接返却
- individual形式: ZIPファイル返却（各記事が個別の.mdファイル）
- list形式: 記事一覧のMarkdown返却

## 6. フロントエンド設計

### 6.1 ページ構成

#### 6.1.1 認証ページ
- `/login` - ログイン
- `/register/{token}` - 招待URL経由登録

#### 6.1.2 メインページ
- `/` - 記事一覧・検索
- `/article/{id}` - 記事詳細
- `/scrape` - URL入力・スクレイピング
- `/export` - エクスポート機能

#### 6.1.3 管理ページ (管理者のみ)
- `/admin/users` - ユーザー管理
- `/admin/prompts` - プロンプト管理
- `/admin/invite` - 招待管理

### 6.2 コンポーネント設計

#### 6.2.1 共通コンポーネント
- `Header` - ナビゲーション、ユーザーメニュー
- `SearchBox` - 検索入力
- `FilterSidebar` - 検索フィルター
- `Pagination` - ページネーション
- `LoadingSpinner` - ローディング表示

#### 6.2.2 記事関連コンポーネント
- `ArticleCard` - 記事カード表示
- `ArticleList` - 記事一覧
- `ArticleDetail` - 記事詳細
- `TagList` - タグ表示・編集

#### 6.2.3 機能コンポーネント
- `URLInput` - URL入力フォーム
  - 大きなテキストエリア（10行以上）
  - URLパース・プレビュー機能
  - 重複チェック結果表示
  - 処理時間推定表示
- `ScrapingProgress` - スクレイピング進捗
  - プログレスバー
  - 現在処理中URL表示
  - 成功・失敗カウント
  - リアルタイム更新
- `ExportModal` - エクスポート設定
- `LLMResultModal` - LLM処理結果表示

### 6.3 状態管理
- React Context API を使用
- `AuthContext` - 認証状態
- `ArticleContext` - 記事データ
- `UIContext` - UI状態（ローディング等）

## 7. 実装フェーズ

### Phase 1: 基盤構築 (1-2週間)
1. **プロジェクト構成**
   - FastAPI + React プロジェクト作成
   - Docker環境構築
   - PostgreSQL設定

2. **認証機能**
   - JWT認証実装
   - ユーザー登録・ログイン
   - 招待機能

3. **基本UI**
   - レイアウト構築
   - ルーティング
   - 認証画面

### Phase 2: コア機能 (2-3週間)
1. **記事管理**
   - 記事一覧・詳細表示
   - データベース操作
   - お気に入り機能

2. **検索機能**
   - 全文検索実装
   - フィルター機能
   - 検索結果表示

3. **スクレイピング**
   - URL入力機能
   - BeautifulSoup実装
   - 非同期処理

### Phase 3: 高度機能 (2-3週間)
1. **LLM連携**
   - Anthropic API統合
   - プロンプト管理
   - 要約・レポート生成

2. **エクスポート**
   - Markdown出力
   - ファイルダウンロード

3. **管理機能**
   - ユーザー管理
   - システム設定

### Phase 4: 最適化・運用準備 (1週間)
1. **パフォーマンス調整**
2. **エラーハンドリング強化**
3. **デプロイ設定**
4. **テスト実装**

## 8. 技術スタック詳細

### バックエンド
- **FastAPI** - 高速なAPI開発
- **SQLAlchemy** - ORM
- **Alembic** - マイグレーション
- **Celery** - 非同期タスク
- **Redis** - キャッシュ・タスクキュー
- **BeautifulSoup4** - Webスクレイピング
- **python-jose** - JWT処理
- **anthropic** - Claude API

### フロントエンド
- **React 18** - UI構築
- **TypeScript** - 型安全性
- **Tailwind CSS** - スタイリング
- **React Router** - ルーティング
- **Axios** - API通信
- **React Hook Form** - フォーム処理

### データベース
- **PostgreSQL 14+** - メインDB
- **pgvector** - 将来のセマンティック検索用

### デプロイ・運用
- **Docker** - コンテナ化
- **nginx** - リバースプロキシ
- **SSL/TLS** - HTTPS通信
- **Backup** - 自動バックアップ

## 9. セキュリティ対策

### 9.1 認証・認可
- パスワードハッシュ化 (bcrypt)
- JWT有効期限管理
- リフレッシュトークン実装
- 権限チェック機能

### 9.2 入力検証
- バリデーション機能
- XSS対策（エスケープ処理）
- SQLインジェクション対策
- CSRF対策

### 9.3 通信セキュリティ
- HTTPS強制
- CORS設定
- レート制限

## 10. 運用・保守

### 10.1 ログ管理
- アクセスログ
- エラーログ
- パフォーマンスログ

### 10.2 監視
- ヘルスチェック機能
- リソース監視
- エラー監視

### 10.3 バックアップ
- 日次データベースバックアップ
- 設定ファイルバックアップ
- 復旧手順書

---

この設計書をベースに、Claude Codeでの実装を進めてください。各フェーズごとに詳細な実装を行い、段階的にシステムを構築していきます。