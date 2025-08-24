#!/usr/bin/env python3
"""
新しい管理者ユーザーを作成するスクリプト
"""

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash
import uuid
from datetime import datetime, timezone

def create_new_admin_user():
    """新しい管理者ユーザーを作成"""
    db = SessionLocal()
    
    try:
        # 新しい管理者ユーザーをチェック
        existing_admin = db.query(User).filter(User.email == settings.FIRST_SUPERUSER_EMAIL).first()
        
        if existing_admin:
            print(f"管理者ユーザー '{settings.FIRST_SUPERUSER_EMAIL}' は既に存在します")
            # パスワードを更新
            existing_admin.hashed_password = get_password_hash(settings.FIRST_SUPERUSER_PASSWORD)
            existing_admin.is_admin = True
            existing_admin.is_active = True
            db.commit()
            print("既存ユーザーのパスワードと権限を更新しました")
            return
        
        # 新しい管理者ユーザーを作成
        admin_user = User(
            id=uuid.uuid4(),
            email=settings.FIRST_SUPERUSER_EMAIL,
            hashed_password=get_password_hash(settings.FIRST_SUPERUSER_PASSWORD),
            is_admin=True,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        print(f"新しい管理者ユーザーを作成しました:")
        print(f"  メール: {admin_user.email}")
        print(f"  管理者権限: {admin_user.is_admin}")
        print(f"  ID: {admin_user.id}")
        
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("=== 新しい管理者ユーザー作成スクリプト ===")
    create_new_admin_user()
    print("=== 完了 ===")