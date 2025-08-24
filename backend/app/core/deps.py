from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.auth_service import AuthService
from app.models.user import User

security = HTTPBearer()

def get_current_user(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    print(f"🔐 get_current_user called with token: {credentials.credentials[:50]}...")
    try:
        user = AuthService.get_current_user(db, credentials.credentials)
        print(f"✅ Authentication successful for user: {user.email}")
        return user
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        raise

def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="管理者権限が必要です"
        )
    return current_user

def get_optional_current_user(
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[User]:
    if credentials is None:
        return None
    try:
        return AuthService.get_current_user(db, credentials.credentials)
    except HTTPException:
        return None