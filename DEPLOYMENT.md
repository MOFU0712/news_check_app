# デプロイメントガイド

ITニュース管理システムのデプロイ手順です。

## 前提条件

### 必要なソフトウェア
- Docker & Docker Compose (推奨)
- Node.js 18+ (手動デプロイ時)
- Python 3.11+ (手動デプロイ時)
- PostgreSQL 15+ (本番環境)
- Redis 7+ (推奨)

### 必要なサービス・API
- **Anthropic Claude API**: LLM要約機能に必要
- **PostgreSQL**: 本番データベース
- **Redis**: キャッシュ・セッション管理（推奨）

## 環境変数の設定

### 1. バックエンド環境変数 (.env)

```bash
cd backend
cp .env.example .env
```

`.env`ファイルを編集：

```bash
# データベース設定（本番環境用PostgreSQL）
POSTGRES_SERVER=your_postgres_host
POSTGRES_PORT=5432
POSTGRES_USER=your_postgres_user
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=news_system

# Redis設定
REDIS_URL=redis://your_redis_host:6379

# セキュリティ設定（必ず変更）
SECRET_KEY=your_very_secure_secret_key_change_this
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# CORS設定（本番ドメインに変更）
BACKEND_CORS_ORIGINS=["https://your-domain.com","https://www.your-domain.com"]

# 管理者アカウント設定
FIRST_SUPERUSER_EMAIL=admin@your-domain.com
FIRST_SUPERUSER_PASSWORD=your_secure_admin_password

# Anthropic API設定（必須）
ANTHROPIC_API_KEY=sk-ant-api03-your-actual-api-key-here

# 環境設定
ENVIRONMENT=production
DEBUG=false
```

### 2. フロントエンド環境変数 (.env)

```bash
cd frontend
cp .env.example .env
```

`.env`ファイルを編集：

```bash
# APIのベースURL（本番環境のドメインに変更）
VITE_API_BASE_URL=https://api.your-domain.com/api
```

## デプロイ方法

### 方法1: Docker Compose（推奨）

```bash
# リポジトリをクローン
git clone https://github.com/your-username/news_check_app.git
cd news_check_app

# 環境変数を設定（上記参照）
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
# 各ファイルを編集

# Docker Composeでデプロイ
docker-compose -f docker-compose.prod.yml up -d

# データベースの初期化
docker-compose exec backend python create_tables.py
docker-compose exec backend python create_new_admin.py
```

### 方法2: 個別デプロイ

#### バックエンドデプロイ

```bash
cd backend

# 依存関係のインストール
pip install -r requirements.txt

# データベースの初期化
python create_tables.py
python create_new_admin.py

# サーバー起動
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

#### フロントエンドデプロイ

```bash
cd frontend

# 依存関係のインストール
npm install

# ビルド
npm run build

# 静的ファイルの配信（Nginx等）
# distフォルダの内容をWebサーバーにデプロイ
```

## 本番環境での注意事項

### セキュリティ設定

1. **SECRET_KEY**: 強力な秘密鍵を設定
   ```bash
   # 秘密鍵生成例
   openssl rand -hex 32
   ```

2. **HTTPS**: 必ずHTTPS通信を使用
3. **CORS**: 本番ドメインのみに制限
4. **データベース**: 強力なパスワードを設定

### パフォーマンス設定

1. **スクレイピング設定**: 大量URLの場合は設定調整が必要
2. **LLM API制限**: Anthropic APIの使用量制限に注意
3. **データベースインデックス**: 大量データ時は適切なインデックス設定

### 監視・ログ

1. **ログファイル**: `backend/server.log`で動作状況を確認
2. **メトリクス**: API使用量、エラー率の監視
3. **バックアップ**: データベースの定期バックアップ

## トラブルシューティング

### よくある問題

1. **API Key Error**: Anthropic APIキーの確認
2. **Database Connection**: PostgreSQL接続設定の確認  
3. **CORS Error**: フロントエンドのドメイン設定確認
4. **Memory Issues**: 大量スクレイピング時のメモリ設定

### ログの確認

```bash
# バックエンドログ
docker-compose logs -f backend

# データベースログ
docker-compose logs -f db

# 全サービスのログ
docker-compose logs -f
```

## スケーリング

### 水平スケーリング

1. **ロードバランサー**: 複数のバックエンドインスタンス
2. **データベース**: 読み書き分離、レプリケーション
3. **Redis**: クラスタ構成

### 垂直スケーリング

1. **CPU・メモリ**: スクレイピング処理に応じて調整
2. **ストレージ**: 記事データ増加に応じて拡張

## サポート

- GitHub Issues: バグ報告・機能要望
- Documentation: `README.md`で基本的な使用方法を確認

---

*このデプロイメントガイドは定期的に更新されます。最新版をご確認ください。*