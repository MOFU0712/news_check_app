#!/bin/bash

echo "=== ITニュース管理システム デモ起動 ==="
echo ""

# 現在の作業ディレクトリを確認
if [ ! -f "backend/app/main.py" ]; then
    echo "❌ backend/app/main.py が見つかりません"
    echo "プロジェクトルートディレクトリで実行してください"
    exit 1
fi

echo "📋 現在実装済みの機能:"
echo "✅ Phase 1: 基盤構築 (認証システム・基本UI)"
echo "✅ Phase 2: 記事管理機能 (CRUD・検索・お気に入り)"
echo "🔄 データベース: PostgreSQL"
echo ""

echo "🚀 デモ環境を起動しています..."
echo ""

# バックエンドディレクトリに移動
cd backend

# テーブル作成
echo "📊 データベーステーブルを作成中..."
python create_tables.py

# サンプルデータ作成
echo "📝 サンプルデータを作成中..."
python create_sample_data.py

echo ""
echo "🌐 アクセス情報:"
echo "- バックエンドAPI: http://localhost:8000"
echo "- API仕様書: http://localhost:8000/api/docs"
echo "- フロントエンド: http://localhost:3000 (別ターミナルで npm run dev)"
echo ""
echo "🔐 デフォルト管理者アカウント:"
echo "- Email: admin@example.com"
echo "- Password: admin123"
echo ""

echo "✨ バックエンドサーバーを起動します..."
echo "フロントエンドは別ターミナルで 'cd frontend && npm run dev' を実行してください"
echo ""

# バックエンドサーバー起動
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload