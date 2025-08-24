# ITニュース管理システム

NotionからAPIコストと安定性の問題を解決するために開発された、ITニュースの効率的な収集・管理・活用システムです。

## 技術スタック

- **フロントエンド**: React 18 + TypeScript + Tailwind CSS + Vite
- **バックエンド**: FastAPI + Python 3.11
- **データベース**: PostgreSQL 15
- **キャッシュ**: Redis 7
- **AI**: Anthropic Claude API
- **コンテナ**: Docker + Docker Compose

## 機能

### ✅ Phase 1: 基盤構築 **【完了】**
- [x] プロジェクト構成作成
- [x] JWT認証システム
- [x] 基本UI・レイアウト
- [x] Docker環境構築
- [x] PostgreSQL設定
- [x] 認証フロー（ログイン・招待制登録）
- [x] レスポンシブデザイン
- [x] エラーハンドリング

### 🚧 Phase 2: コア機能（予定）
- [ ] 記事管理機能
- [ ] 検索機能（PostgreSQL全文検索）
- [ ] URLスクレイピング機能

### 🔄 Phase 3: 高度機能（予定）
- [ ] LLM連携（要約・レポート生成）
- [ ] Markdownエクスポート機能
- [ ] 管理者機能

### 📈 Phase 4: 最適化・運用準備（予定）
- [ ] パフォーマンス最適化
- [ ] エラーハンドリング強化
- [ ] デプロイ設定

## セットアップ

### 前提条件
- Docker & Docker Compose
- Node.js 18+ (開発時のみ)
- Python 3.11+ (開発時のみ)

### 開発環境セットアップ

1. リポジトリをクローン
```bash
git clone <repository-url>
cd news_check_app
```

2. 環境変数を設定
```bash
cp backend/.env.example backend/.env
# .envファイルを編集して必要な設定を行う
```

3. 開発環境を起動
```bash
# Docker環境がある場合
./start_dev.sh

# Docker環境がない場合（手動セットアップ）
# PostgreSQL・Redisをローカルにインストール後
cd backend
pip install -r requirements.txt
python create_tables.py
python create_admin.py
uvicorn app.main:app --reload

# 別ターミナルで
cd frontend  
npm install
npm run dev
```

4. アプリケーションにアクセス
- フロントエンド: http://localhost:3000
- バックエンドAPI: http://localhost:8000
- API仕様書: http://localhost:8000/api/docs

### 開発時のコマンド

```bash
# 全サービス起動
docker-compose up -d

# ログ確認
docker-compose logs -f

# データベースリセット
docker-compose down -v
docker-compose up -d db

# コンテナ再構築
docker-compose build --no-cache
```

## プロジェクト構成

```
news_check_app/
├── backend/                 # FastAPI アプリケーション
│   ├── app/
│   │   ├── api/            # APIルート
│   │   ├── core/           # 設定・セキュリティ
│   │   ├── db/             # データベース接続
│   │   ├── models/         # SQLAlchemyモデル
│   │   ├── schemas/        # Pydanticスキーマ
│   │   ├── services/       # ビジネスロジック
│   │   └── utils/          # ユーティリティ
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/               # React アプリケーション
│   ├── src/
│   │   ├── components/     # UIコンポーネント
│   │   ├── pages/          # ページコンポーネント
│   │   ├── services/       # API呼び出し
│   │   ├── hooks/          # カスタムフック
│   │   ├── contexts/       # React Context
│   │   └── types/          # TypeScript型定義
│   ├── package.json
│   └── Dockerfile
└── docker-compose.yml      # 開発環境設定
```

## 開発者向け情報

このプロジェクトはPhase 1の基盤構築が完了した段階です。以下の機能から段階的に実装を進める予定です：

1. JWT認証システム
2. データベースモデル作成
3. 基本的なCRUD操作
4. フロントエンドの認証画面

## ライセンス

Private project - All rights reserved