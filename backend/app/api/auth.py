from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.auth import UserLogin, UserRegister, UserInvite, Token, UserResponse
from app.services.auth_service import AuthService
from app.core.deps import get_current_admin_user, get_current_user
from app.models.user import User

router = APIRouter()

@router.post("/login", response_model=Token)
async def login(
    user_data: UserLogin,
    db: Session = Depends(get_db)
):
    """ユーザーログイン"""
    return AuthService.login_user(db, user_data)

@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    """招待URL経由でのユーザー登録"""
    user = AuthService.create_user(db, user_data)
    return UserResponse(
        id=str(user.id),
        email=user.email,
        is_admin=user.is_admin,
        is_active=user.is_active
    )

@router.post("/invite")
async def create_invite(
    invite_data: UserInvite,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """招待URLを生成（管理者のみ）"""
    token = AuthService.create_invitation(db, invite_data.email, current_user)
    return {
        "message": "Invitation created successfully",
        "invitation_token": token,
        "registration_url": f"/register/{token}"
    }

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """現在のユーザー情報を取得"""
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        is_admin=current_user.is_admin,
        is_active=current_user.is_active
    )

@router.get("/validate-token")
async def validate_token(
    current_user: User = Depends(get_current_user)
):
    """トークンの有効性を確認"""
    return {"valid": True, "user_id": str(current_user.id)}