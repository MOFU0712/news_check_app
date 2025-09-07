from typing import Dict, Any
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.services.usage_service import UsageService

router = APIRouter()

@router.get("/status")
async def get_usage_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """現在のユーザーの使用状況を取得"""
    try:
        usage_summary = UsageService.get_user_usage_summary(db, current_user.id)
        return usage_summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"使用状況の取得に失敗しました: {str(e)}")

@router.get("/status/{action_type}")
async def get_action_usage_status(
    action_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """特定のアクションタイプの使用状況を取得"""
    try:
        usage_info = UsageService.check_usage_limit(db, current_user.id, action_type, current_user)
        return usage_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"使用状況の取得に失敗しました: {str(e)}")

@router.get("/history")
async def get_usage_history(
    days: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """使用履歴を取得"""
    try:
        from app.models.usage_log import UsageLog
        from datetime import datetime, timedelta
        
        start_date = date.today() - timedelta(days=days)
        
        logs = db.query(UsageLog).filter(
            UsageLog.user_id == str(current_user.id),
            UsageLog.usage_date >= start_date
        ).order_by(UsageLog.created_at.desc()).all()
        
        return {
            'user_id': str(current_user.id),
            'period_days': days,
            'total_logs': len(logs),
            'logs': [
                {
                    'id': log.id,
                    'action_type': log.action_type,
                    'usage_date': log.usage_date.isoformat(),
                    'resource_used': log.resource_used,
                    'created_at': log.created_at.isoformat()
                }
                for log in logs
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"使用履歴の取得に失敗しました: {str(e)}")