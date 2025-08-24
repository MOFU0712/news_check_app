#!/usr/bin/env python3
"""
サンプルデータ作成スクリプト
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.models.article import Article
from app.models.user import User
from app.core.security import get_password_hash

def create_sample_data():
    """サンプルデータを作成"""
    db = SessionLocal()
    
    try:
        # 管理者ユーザーを取得または作成
        admin_user = db.query(User).filter(User.email == "admin@example.com").first()
        if not admin_user:
            admin_user = User(
                email="admin@example.com",
                password_hash=get_password_hash("admin123"),
                role="admin",
                is_active=True
            )
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
            print("✅ 管理者ユーザーを作成しました")
        else:
            print("✅ 管理者ユーザーが既に存在します")
        
        # サンプル記事データ
        sample_articles = [
            {
                "title": "React 18の新機能：Concurrent Featuresの使い方",
                "url": "https://example.com/react18-concurrent",
                "content": "React 18では、Concurrent Featuresと呼ばれる新しい機能が追加されました。これにより、アプリケーションのパフォーマンスが大幅に向上し、ユーザーエクスペリエンスが改善されます。\n\n主な機能には以下があります：\n- Automatic Batching\n- startTransition\n- Suspense の改善\n\nこれらの機能を適切に使用することで、より反応性の高いアプリケーションを構築できます。",
                "source": "React公式ブログ",
                "tags": ["React", "JavaScript", "フロントエンド", "パフォーマンス"],
                "summary": "React 18で導入されたConcurrent Featuresの概要と使用方法について解説。Automatic BatchingやstartTransitionなどの新機能でアプリのパフォーマンスが向上。",
                "published_date": datetime.now() - timedelta(days=2)
            },
            {
                "title": "FastAPIでモダンなWeb API開発",
                "url": "https://example.com/fastapi-modern-api",
                "content": "FastAPIは、PythonでモダンなWeb APIを構築するための高性能なフレームワークです。型ヒントを活用した自動ドキュメント生成や、非同期処理のサポートなど、開発者にとって魅力的な機能が多数搭載されています。\n\n特徴：\n- 高速な実行速度\n- 自動API仕様書生成\n- 型安全性\n- 非同期処理対応\n\n実際のプロジェクトでの使用例も紹介します。",
                "source": "Python Weekly",
                "tags": ["Python", "FastAPI", "バックエンド", "API"],
                "summary": "FastAPIを使ったモダンなWeb API開発の手法を紹介。型ヒントによる自動ドキュメント生成や非同期処理などの特徴を解説。",
                "published_date": datetime.now() - timedelta(days=1)
            },
            {
                "title": "PostgreSQLの全文検索機能を活用した高速検索システム",
                "url": "https://example.com/postgresql-fulltext-search",
                "content": "PostgreSQLには強力な全文検索機能が組み込まれています。tsvectorとtsqueryを使用することで、Elasticsearchなどの外部ツールを使わずに高速な検索システムを構築できます。\n\n実装のポイント：\n- tsvectorインデックスの作成\n- 検索クエリの最適化\n- 言語固有の設定\n- パフォーマンスチューニング\n\nJapanese tokenizerの設定方法も含めて詳しく解説します。",
                "source": "データベース技術ブログ",
                "tags": ["PostgreSQL", "データベース", "検索", "全文検索"],
                "summary": "PostgreSQLの全文検索機能を使った高速検索システムの構築方法。tsvectorとtsqueryの活用法やパフォーマンス最適化について。",
                "published_date": datetime.now() - timedelta(hours=12)
            },
            {
                "title": "TypeScriptでの型安全なAPI開発パターン",
                "url": "https://example.com/typescript-api-patterns",
                "content": "TypeScriptを使用してフロントエンドとバックエンドで型を共有し、型安全なAPI開発を行う方法について説明します。\n\nこのアプローチにより、ランタイムエラーを大幅に減らし、開発効率を向上させることができます。\n\n主要なパターン：\n- 共有型定義\n- API クライアントの自動生成\n- バリデーションの統一\n- テスト戦略",
                "source": "TypeScript Japan",
                "tags": ["TypeScript", "API", "型安全", "開発効率"],
                "summary": "TypeScriptを活用した型安全なAPI開発の手法。フロントエンドとバックエンドでの型共有によるランタイムエラー削減と開発効率向上。",
                "published_date": datetime.now() - timedelta(hours=6)
            },
            {
                "title": "TailwindCSSで効率的なUIデザインシステム構築",
                "url": "https://example.com/tailwind-design-system",
                "content": "TailwindCSSを使用して一貫性のあるデザインシステムを構築する方法を紹介します。カスタムコンポーネントの作成からダークモードの実装まで、実践的なテクニックを解説。\n\n構築のステップ：\n1. 色とタイポグラフィの定義\n2. コンポーネントの標準化\n3. レスポンシブデザインの考慮\n4. アクセシビリティの確保\n\n大規模プロジェクトでの運用事例も含めて詳しく説明します。",
                "source": "フロントエンド技術ブログ",
                "tags": ["TailwindCSS", "CSS", "デザインシステム", "UI"],
                "summary": "TailwindCSSを使った効率的なデザインシステムの構築方法。色やタイポグラフィの統一からレスポンシブデザインまでの実践的手法。",
                "published_date": datetime.now() - timedelta(hours=3)
            }
        ]
        
        # 既存の記事数を確認
        existing_count = db.query(Article).count()
        
        if existing_count > 0:
            print(f"✅ 既に {existing_count} 件の記事が存在します")
            return
        
        # サンプル記事を作成
        for article_data in sample_articles:
            article = Article(
                title=article_data["title"],
                url=article_data["url"],
                content=article_data["content"],
                source=article_data["source"],
                tags=article_data["tags"],
                summary=article_data["summary"],
                published_date=article_data["published_date"],
                created_by=admin_user.id
            )
            db.add(article)
        
        db.commit()
        print(f"✅ {len(sample_articles)} 件のサンプル記事を作成しました")
        
        # 統計情報を表示
        total_articles = db.query(Article).count()
        print(f"📊 総記事数: {total_articles}")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("=== サンプルデータ作成 ===")
    create_sample_data()