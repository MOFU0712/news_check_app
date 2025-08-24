#!/bin/bash

echo "=== ITニュース管理システム 開発環境起動 ==="

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Dockerが見つかりません。"
    echo ""
    echo "📋 手動セットアップが必要です："
    echo "1. PostgreSQL 15をインストール"
    echo "2. Redis 7をインストール"
    echo "3. データベース 'news_system' を作成"
    echo "4. .env ファイルの設定を確認"
    echo ""
    echo "🔧 開発環境起動コマンド："
    echo "バックエンド: cd backend && pip install -r requirements.txt && python create_tables.py && uvicorn app.main:app --reload"
    echo "フロントエンド: cd frontend && npm install && npm run dev"
    exit 1
fi

echo "🚀 Docker環境を起動します..."

# Start services
docker compose up -d

echo ""
echo "✅ サービスが起動しました！"
echo ""
echo "📖 アクセス情報:"
echo "- フロントエンド: http://localhost:3000"
echo "- バックエンドAPI: http://localhost:8000"
echo "- API仕様書: http://localhost:8000/api/docs"
echo ""
echo "🔐 デフォルト管理者アカウント:"
echo "- Email: admin@example.com"
echo "- Password: admin123"
echo ""
echo "📊 ログ確認: docker compose logs -f"
echo "🛑 停止: docker compose down"