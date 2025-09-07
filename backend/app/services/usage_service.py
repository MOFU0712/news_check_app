from datetime import date, datetime
from typing import Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.usage_log import UsageLog
from app.models.user import User
import json

class UsageService:
    """使用状況管理サービス"""
    
    # 使用制限設定
    DAILY_LIMITS = {
        'report_generation': 3,  # 一日3回のレポート生成制限
        'llm_query': 10,  # 一日10回のLLMクエリ制限
    }
    
    @staticmethod
    def log_usage(
        db: Session, 
        user_id: str, 
        action_type: str,
        resource_used: Optional[str] = None,
        additional_data: Optional[Dict] = None
    ) -> UsageLog:
        """使用ログを記録"""
        usage_log = UsageLog(
            user_id=str(user_id),
            action_type=action_type,
            usage_date=date.today(),
            resource_used=resource_used,
            additional_data=json.dumps(additional_data) if additional_data else None,
            created_at=datetime.utcnow()
        )
        
        db.add(usage_log)
        db.commit()
        db.refresh(usage_log)
        
        return usage_log
    
    @staticmethod
    def get_daily_usage_count(
        db: Session, 
        user_id: str, 
        action_type: str,
        usage_date: Optional[date] = None
    ) -> int:
        """指定した日の使用回数を取得"""
        if usage_date is None:
            usage_date = date.today()
        
        count = db.query(UsageLog).filter(
            UsageLog.user_id == str(user_id),
            UsageLog.action_type == action_type,
            UsageLog.usage_date == usage_date
        ).count()
        
        return count
    
    @staticmethod
    def check_usage_limit(
        db: Session, 
        user_id: str, 
        action_type: str,
        user: Optional[User] = None
    ) -> Dict[str, any]:
        """使用制限をチェック"""
        # ユーザー情報を取得（渡されていない場合）
        if user is None:
            user = db.query(User).filter(User.id == str(user_id)).first()
        
        # 管理者は制限なし
        if user and user.is_admin:
            return {
                'can_use': True,
                'remaining_count': -1,  # -1 = 無制限
                'daily_limit': -1,
                'used_count': 0,
                'reset_time': 'N/A (管理者)',
                'message': '管理者は使用制限がありません'
            }
        
        # アクションタイプの制限を取得
        daily_limit = UsageService.DAILY_LIMITS.get(action_type, 0)
        if daily_limit == 0:
            return {
                'can_use': True,
                'remaining_count': -1,
                'daily_limit': 0,
                'used_count': 0,
                'reset_time': 'N/A',
                'message': 'この操作には制限がありません'
            }
        
        # 今日の使用回数を取得
        used_count = UsageService.get_daily_usage_count(db, user_id, action_type)
        remaining_count = max(0, daily_limit - used_count)
        can_use = remaining_count > 0
        
        # リセット時刻（翌日の0時）
        tomorrow = date.today().replace(day=date.today().day + 1)
        reset_time = f"{tomorrow} 00:00"
        
        message = f"残り{remaining_count}回使用できます" if can_use else "本日の使用制限に達しました"
        
        return {
            'can_use': can_use,
            'remaining_count': remaining_count,
            'daily_limit': daily_limit,
            'used_count': used_count,
            'reset_time': reset_time,
            'message': message
        }
    
    @staticmethod
    def get_user_usage_summary(
        db: Session, 
        user_id: str,
        usage_date: Optional[date] = None
    ) -> Dict[str, any]:
        """ユーザーの使用状況サマリーを取得"""
        if usage_date is None:
            usage_date = date.today()
        
        user = db.query(User).filter(User.id == str(user_id)).first()
        if not user:
            return {'error': 'ユーザーが見つかりません'}
        
        summary = {
            'user_id': str(user_id),
            'is_admin': user.is_admin,
            'usage_date': usage_date.isoformat(),
            'actions': {}
        }
        
        # 各アクションタイプの使用状況をチェック
        for action_type, daily_limit in UsageService.DAILY_LIMITS.items():
            usage_info = UsageService.check_usage_limit(db, user_id, action_type, user)
            summary['actions'][action_type] = usage_info
        
        return summary