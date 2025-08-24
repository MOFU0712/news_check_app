from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from datetime import datetime

from app.db.database import get_db
from app.core.deps import get_current_admin_user
from app.models.user import User
from app.services.user_service import UserService
from app.core.config import settings
from app.services.llm_service import llm_service

router = APIRouter()

# スキーマ定義
class UserResponse(BaseModel):
    id: str
    email: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    is_admin: bool = False

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None

class SystemSettings(BaseModel):
    anthropic_api_key: str = ""
    default_scraping_delay: float = 1.0
    max_concurrent_requests: int = 5
    default_report_template: str = "summary"
    enable_auto_tagging: bool = True
    max_content_length: int = 50000
    session_timeout_minutes: int = 1440
    enable_user_registration: bool = False

class ApiConnectionTest(BaseModel):
    status: str
    model: Optional[str] = None
    message: str

# ユーザー管理エンドポイント
@router.get("/users", response_model=List[UserResponse])
async def get_all_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """全ユーザー一覧を取得"""
    users = db.query(User).all()
    return [
        UserResponse(
            id=str(user.id),
            email=user.email,
            is_active=user.is_active,
            is_admin=user.is_admin,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
        for user in users
    ]

@router.post("/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """新しいユーザーを作成"""
    # メールアドレスの重複チェック
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="このメールアドレスは既に使用されています"
        )
    
    # ユーザー作成
    new_user = UserService.create_user(
        db=db,
        email=user_data.email,
        password=user_data.password,
        is_admin=user_data.is_admin
    )
    
    return UserResponse(
        id=str(new_user.id),
        email=new_user.email,
        is_active=new_user.is_active,
        is_admin=new_user.is_admin,
        created_at=new_user.created_at,
        updated_at=new_user.updated_at
    )

@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """ユーザー情報を更新"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ユーザーが見つかりません"
        )
    
    # 自分自身の権限変更を防止
    if user.id == current_user.id and user_data.is_admin is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="自分自身の管理者権限は変更できません"
        )
    
    # 自分自身の無効化を防止
    if user.id == current_user.id and user_data.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="自分自身のアカウントを無効化することはできません"
        )
    
    # 更新
    if user_data.email is not None:
        # メールアドレスの重複チェック
        existing_user = db.query(User).filter(
            User.email == user_data.email, 
            User.id != user_id
        ).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="このメールアドレスは既に使用されています"
            )
        user.email = user_data.email
    
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    
    if user_data.is_admin is not None:
        user.is_admin = user_data.is_admin
    
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    
    return UserResponse(
        id=str(user.id),
        email=user.email,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at,
        updated_at=user.updated_at
    )

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """ユーザーを削除"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ユーザーが見つかりません"
        )
    
    # 自分自身の削除を防止
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="自分自身を削除することはできません"
        )
    
    db.delete(user)
    db.commit()
    
    return {"message": "ユーザーを削除しました"}

# システム設定エンドポイント
@router.get("/settings", response_model=SystemSettings)
async def get_system_settings(
    current_user: User = Depends(get_current_admin_user)
):
    """システム設定を取得"""
    return SystemSettings(
        anthropic_api_key=getattr(settings, 'ANTHROPIC_API_KEY', '') or '',
        default_scraping_delay=getattr(settings, 'DEFAULT_SCRAPING_DELAY', 1.0),
        max_concurrent_requests=getattr(settings, 'MAX_CONCURRENT_REQUESTS', 5),
        default_report_template=getattr(settings, 'DEFAULT_REPORT_TEMPLATE', 'summary'),
        enable_auto_tagging=getattr(settings, 'ENABLE_AUTO_TAGGING', True),
        max_content_length=getattr(settings, 'MAX_CONTENT_LENGTH', 50000),
        session_timeout_minutes=getattr(settings, 'SESSION_TIMEOUT_MINUTES', 1440),
        enable_user_registration=getattr(settings, 'ENABLE_USER_REGISTRATION', False)
    )

@router.put("/settings", response_model=SystemSettings)
async def update_system_settings(
    settings_data: SystemSettings,
    current_user: User = Depends(get_current_admin_user)
):
    """システム設定を更新"""
    # 設定値の更新（実際の実装では環境変数やデータベースに保存）
    # ここでは一時的にsettingsオブジェクトを更新
    settings.ANTHROPIC_API_KEY = settings_data.anthropic_api_key
    settings.DEFAULT_SCRAPING_DELAY = settings_data.default_scraping_delay
    settings.MAX_CONCURRENT_REQUESTS = settings_data.max_concurrent_requests
    settings.DEFAULT_REPORT_TEMPLATE = settings_data.default_report_template
    settings.ENABLE_AUTO_TAGGING = settings_data.enable_auto_tagging
    settings.MAX_CONTENT_LENGTH = settings_data.max_content_length
    settings.SESSION_TIMEOUT_MINUTES = settings_data.session_timeout_minutes
    settings.ENABLE_USER_REGISTRATION = settings_data.enable_user_registration
    
    # LLMサービスのAPIキーを更新
    if settings_data.anthropic_api_key:
        llm_service.anthropic_api_key = settings_data.anthropic_api_key
        try:
            from anthropic import Anthropic
            llm_service.client = Anthropic(api_key=settings_data.anthropic_api_key)
        except Exception:
            pass
    
    return settings_data

@router.post("/test-api-connection", response_model=ApiConnectionTest)
async def test_api_connection(
    current_user: User = Depends(get_current_admin_user)
):
    """API接続テスト"""
    if not llm_service.is_available():
        return ApiConnectionTest(
            status="failed",
            message="APIキーが設定されていません"
        )
    
    try:
        # 簡単なテストリクエスト
        response = llm_service.client.messages.create(
            model='claude-sonnet-4-20250514',
            max_tokens=10,
            messages=[{
                "role": "user",
                "content": "Hello"
            }]
        )
        
        return ApiConnectionTest(
            status="success",
            model="Claude 3 Haiku",
            message="API接続が正常です"
        )
    except Exception as e:
        return ApiConnectionTest(
            status="failed",
            message=f"API接続エラー: {str(e)}"
        )