import uuid
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.user import User
from app.core.security import get_password_hash, verify_password


class UserService:
    """ユーザー管理サービス"""

    @staticmethod
    def create_user(
        db: Session, 
        email: str, 
        password: str, 
        is_admin: bool = False
    ) -> User:
        """新しいユーザーを作成"""
        hashed_password = get_password_hash(password)
        
        user = User(
            id=uuid.uuid4(),
            email=email,
            hashed_password=hashed_password,
            is_admin=is_admin,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        return user

    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        """メールアドレスでユーザーを取得"""
        return db.query(User).filter(User.email == email).first()

    @staticmethod
    def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
        """IDでユーザーを取得"""
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
        """ユーザー認証"""
        user = UserService.get_user_by_email(db, email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    @staticmethod
    def update_user(
        db: Session,
        user_id: str,
        email: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_admin: Optional[bool] = None
    ) -> Optional[User]:
        """ユーザー情報を更新"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        
        if email is not None:
            user.email = email
        if is_active is not None:
            user.is_active = is_active
        if is_admin is not None:
            user.is_admin = is_admin
        
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        
        return user

    @staticmethod
    def change_password(
        db: Session, 
        user_id: str, 
        new_password: str
    ) -> Optional[User]:
        """パスワードを変更"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        
        user.hashed_password = get_password_hash(new_password)
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        
        return user

    @staticmethod
    def delete_user(db: Session, user_id: str) -> bool:
        """ユーザーを削除"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        
        db.delete(user)
        db.commit()
        return True

    @staticmethod
    def get_all_users(db: Session) -> list[User]:
        """全ユーザーを取得"""
        return db.query(User).all()

    @staticmethod
    def count_active_users(db: Session) -> int:
        """アクティブユーザー数を取得"""
        return db.query(User).filter(User.is_active == True).count()

    @staticmethod
    def count_admin_users(db: Session) -> int:
        """管理者ユーザー数を取得"""
        return db.query(User).filter(
            User.is_admin == True, 
            User.is_active == True
        ).count()