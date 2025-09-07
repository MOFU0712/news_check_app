from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.user import User
from app.core.security import verify_password, get_password_hash, create_access_token, verify_token
from app.schemas.auth import UserLogin, UserRegister, UserInvite, Token, PasswordChange
import secrets
import redis
from app.core.config import settings

# Redis client for storing invitation tokens
redis_client = redis.Redis.from_url(settings.REDIS_URL)

class AuthService:
    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    @staticmethod
    def create_user(db: Session, user_data: UserRegister) -> User:
        # Verify invitation token
        stored_email = redis_client.get(f"invite:{user_data.token}")
        if not stored_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired invitation token"
            )
        
        stored_email = stored_email.decode('utf-8')
        if stored_email != user_data.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email does not match invitation"
            )
        
        # Check if user already exists
        if db.query(User).filter(User.email == user_data.email).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Create user
        db_user = User(
            email=user_data.email,
            hashed_password=get_password_hash(user_data.password),
            is_admin=False
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        # Remove invitation token
        redis_client.delete(f"invite:{user_data.token}")
        
        return db_user

    @staticmethod
    def login_user(db: Session, user_data: UserLogin) -> Token:
        user = AuthService.authenticate_user(db, user_data.email, user_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )
        
        access_token = create_access_token(subject=user.email)
        return Token(access_token=access_token, token_type="bearer")

    @staticmethod
    def create_invitation(db: Session, user_email: str, current_user: User) -> str:
        # Check if current user is admin
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        
        # Check if user already exists
        if db.query(User).filter(User.email == user_email).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already exists"
            )
        
        # Generate invitation token
        token = secrets.token_urlsafe(32)
        
        # Store invitation token in Redis (expires in 24 hours)
        redis_client.setex(f"invite:{token}", 24 * 60 * 60, user_email)
        
        return token

    @staticmethod
    def get_current_user(db: Session, token: str) -> User:
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        email = verify_token(token)
        if email is None:
            raise credentials_exception
        
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            raise credentials_exception
        return user

    @staticmethod
    def change_password(db: Session, user: User, password_data: PasswordChange):
        """パスワード変更"""
        # 現在のパスワードを確認
        if not verify_password(password_data.current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="現在のパスワードが正しくありません"
            )
        
        # 新しいパスワードが現在のパスワードと同じでないことを確認
        if verify_password(password_data.new_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="新しいパスワードは現在のパスワードと異なるものにしてください"
            )
        
        # パスワードを更新
        user.hashed_password = get_password_hash(password_data.new_password)
        user.password_change_required = False
        db.commit()
        db.refresh(user)
        
        return {"message": "パスワードが正常に変更されました"}