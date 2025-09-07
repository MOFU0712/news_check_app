#!/usr/bin/env python3
"""
データベーステーブル作成スクリプト
"""
import asyncio
from sqlalchemy import text
from app.db.database import engine, Base
from app.models import *
from app.core.config import settings

def create_database():
    """データベースとテーブルを作成"""
    print("Creating database tables...")
    
    # テーブル作成
    Base.metadata.create_all(bind=engine)
    
    # インデックス設定
    try:
        with engine.connect() as conn:
            # 基本的なインデックス
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_articles_scraped_date 
                ON articles(scraped_date DESC);
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_articles_title 
                ON articles(title);
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_articles_url 
                ON articles(url);
            """))
            
            conn.commit()
    except Exception as e:
        print(f"インデックス作成でエラー（継続します）: {e}")
    
    print("Database tables created successfully!")

if __name__ == "__main__":
    create_database()