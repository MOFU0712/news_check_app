from typing import List, Optional
from datetime import datetime, time
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field
import logging

from app.db.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.report_schedule import ReportScheduleConfig
from app.services.report_scheduler_service import report_scheduler_service

logger = logging.getLogger(__name__)
router = APIRouter()


# スキーマ定義
class ReportScheduleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="スケジュール名")
    description: Optional[str] = Field(None, max_length=500, description="説明")
    schedule_type: str = Field(..., description="スケジュールタイプ: daily, weekly, monthly")
    schedule_time: str = Field(..., description="実行時刻 (HH:MM形式)")
    weekday: Optional[str] = Field(None, description="週次用: 曜日 (0=月曜, 6=日曜)")
    day_of_month: Optional[str] = Field(None, description="月次用: 日付 (1-31)")
    
    # レポート設定
    report_type: str = Field(..., description="レポートタイプ: summary, tag_analysis, source_analysis, trend_analysis")
    report_title_template: str = Field(..., min_length=1, max_length=200, description="レポートタイトルテンプレート")
    
    # フィルター設定
    date_range_days: Optional[str] = Field(None, description="日付範囲の日数")
    tags_filter: Optional[List[str]] = Field(default=[], description="タグフィルター")
    sources_filter: Optional[List[str]] = Field(default=[], description="ソースフィルター")
    
    # プロンプトテンプレート
    prompt_template_id: Optional[str] = Field(None, description="カスタムプロンプトテンプレートID")
    
    # メール設定
    email_enabled: bool = Field(default=False, description="メール送信有効/無効")
    email_recipients: Optional[List[EmailStr]] = Field(default=[], description="送信先メールアドレス")
    email_subject_template: Optional[str] = Field(None, max_length=200, description="メール件名テンプレート")
    
    # 有効/無効
    enabled: bool = Field(default=True, description="スケジュール有効/無効")


class ReportScheduleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    schedule_time: Optional[str] = Field(None, description="実行時刻 (HH:MM形式)")
    weekday: Optional[str] = Field(None, description="週次用: 曜日")
    day_of_month: Optional[str] = Field(None, description="月次用: 日付")
    
    report_title_template: Optional[str] = Field(None, min_length=1, max_length=200)
    date_range_days: Optional[str] = Field(None)
    tags_filter: Optional[List[str]] = Field(None)
    sources_filter: Optional[List[str]] = Field(None)
    
    prompt_template_id: Optional[str] = Field(None)
    
    email_enabled: Optional[bool] = Field(None)
    email_recipients: Optional[List[EmailStr]] = Field(None)
    email_subject_template: Optional[str] = Field(None, max_length=200)
    
    enabled: Optional[bool] = Field(None)


class ReportScheduleResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    enabled: bool
    
    schedule_type: str
    schedule_time: str  # HH:MM形式
    schedule_display: str  # 表示用
    weekday: Optional[str]
    day_of_month: Optional[str]
    
    report_type: str
    report_title_template: str
    date_range_days: Optional[str]
    tags_filter: List[str]
    sources_filter: List[str]
    
    prompt_template_id: Optional[str]
    
    email_enabled: bool
    email_recipients: List[str]
    email_subject_template: Optional[str]
    
    last_executed_at: Optional[datetime]
    last_execution_status: Optional[str]
    last_execution_message: Optional[str]
    next_scheduled_at: Optional[datetime]
    
    created_at: datetime
    updated_at: datetime


class ScheduleExecutionResponse(BaseModel):
    schedule_id: str
    report_id: Optional[str]
    report_title: Optional[str]
    email_sent: bool
    email_recipients_count: int
    execution_time: datetime
    status: str
    message: str


@router.post("/", response_model=ReportScheduleResponse)
async def create_report_schedule(
    schedule_data: ReportScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """レポートスケジュールを作成"""
    try:
        # バリデーション
        if schedule_data.schedule_type not in ["daily", "weekly", "monthly"]:
            raise HTTPException(status_code=400, detail="無効なスケジュールタイプです")
        
        if schedule_data.report_type not in ["summary", "tag_analysis", "source_analysis", "trend_analysis"]:
            raise HTTPException(status_code=400, detail="無効なレポートタイプです")
        
        # 時刻解析
        try:
            hour, minute = map(int, schedule_data.schedule_time.split(":"))
            schedule_time = time(hour=hour, minute=minute)
        except ValueError:
            raise HTTPException(status_code=400, detail="無効な時刻形式です（HH:MM形式で入力してください）")
        
        # 週次・月次の場合の追加バリデーション
        if schedule_data.schedule_type == "weekly" and schedule_data.weekday is None:
            raise HTTPException(status_code=400, detail="週次スケジュールでは曜日の指定が必要です")
        
        if schedule_data.schedule_type == "monthly" and schedule_data.day_of_month is None:
            raise HTTPException(status_code=400, detail="月次スケジュールでは日付の指定が必要です")
        
        # データベースレコード作成
        schedule = ReportScheduleConfig(
            name=schedule_data.name,
            description=schedule_data.description,
            enabled=schedule_data.enabled,
            schedule_type=schedule_data.schedule_type,
            schedule_time=schedule_time,
            weekday=schedule_data.weekday,
            day_of_month=schedule_data.day_of_month,
            report_type=schedule_data.report_type,
            report_title_template=schedule_data.report_title_template,
            date_range_days=schedule_data.date_range_days,
            tags_filter=schedule_data.tags_filter,
            sources_filter=schedule_data.sources_filter,
            prompt_template_id=schedule_data.prompt_template_id,
            email_enabled=schedule_data.email_enabled,
            email_recipients=schedule_data.email_recipients,
            email_subject_template=schedule_data.email_subject_template,
            created_by=current_user.id
        )
        
        db.add(schedule)
        db.commit()
        db.refresh(schedule)
        
        logger.info(f"Created report schedule {schedule.id} for user {current_user.email}")
        
        return _schedule_to_response(schedule)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating report schedule: {e}")
        raise HTTPException(status_code=500, detail=f"スケジュール作成に失敗しました: {str(e)}")


@router.get("/", response_model=List[ReportScheduleResponse])
async def get_report_schedules(
    enabled_only: bool = Query(False, description="有効なスケジュールのみ取得"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """レポートスケジュール一覧を取得"""
    try:
        query = db.query(ReportScheduleConfig).filter(
            ReportScheduleConfig.created_by == current_user.id
        )
        
        if enabled_only:
            query = query.filter(ReportScheduleConfig.enabled == True)
        
        schedules = query.order_by(
            ReportScheduleConfig.created_at.desc()
        ).offset(offset).limit(limit).all()
        
        return [_schedule_to_response(schedule) for schedule in schedules]
        
    except Exception as e:
        logger.error(f"Error getting report schedules: {e}")
        raise HTTPException(status_code=500, detail=f"スケジュール一覧の取得に失敗しました: {str(e)}")


@router.get("/{schedule_id}", response_model=ReportScheduleResponse)
async def get_report_schedule(
    schedule_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """特定のレポートスケジュールを取得"""
    try:
        schedule = db.query(ReportScheduleConfig).filter(
            ReportScheduleConfig.id == schedule_id,
            ReportScheduleConfig.created_by == current_user.id
        ).first()
        
        if not schedule:
            raise HTTPException(status_code=404, detail="スケジュールが見つかりません")
        
        return _schedule_to_response(schedule)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting report schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail=f"スケジュールの取得に失敗しました: {str(e)}")


@router.put("/{schedule_id}", response_model=ReportScheduleResponse)
async def update_report_schedule(
    schedule_id: str,
    update_data: ReportScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """レポートスケジュールを更新"""
    try:
        schedule = db.query(ReportScheduleConfig).filter(
            ReportScheduleConfig.id == schedule_id,
            ReportScheduleConfig.created_by == current_user.id
        ).first()
        
        if not schedule:
            raise HTTPException(status_code=404, detail="スケジュールが見つかりません")
        
        # 更新データを適用
        update_dict = update_data.model_dump(exclude_unset=True)
        
        # 時刻の解析
        if 'schedule_time' in update_dict:
            try:
                hour, minute = map(int, update_dict['schedule_time'].split(":"))
                schedule.schedule_time = time(hour=hour, minute=minute)
                del update_dict['schedule_time']
            except ValueError:
                raise HTTPException(status_code=400, detail="無効な時刻形式です（HH:MM形式で入力してください）")
        
        # その他のフィールドを更新
        for field, value in update_dict.items():
            if hasattr(schedule, field):
                setattr(schedule, field, value)
        
        db.commit()
        db.refresh(schedule)
        
        logger.info(f"Updated report schedule {schedule_id} for user {current_user.email}")
        
        return _schedule_to_response(schedule)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating report schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail=f"スケジュールの更新に失敗しました: {str(e)}")


@router.delete("/{schedule_id}")
async def delete_report_schedule(
    schedule_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """レポートスケジュールを削除"""
    try:
        schedule = db.query(ReportScheduleConfig).filter(
            ReportScheduleConfig.id == schedule_id,
            ReportScheduleConfig.created_by == current_user.id
        ).first()
        
        if not schedule:
            raise HTTPException(status_code=404, detail="スケジュールが見つかりません")
        
        # 実行中タスクがあればキャンセル
        await report_scheduler_service.cancel_running_task(schedule_id)
        
        db.delete(schedule)
        db.commit()
        
        logger.info(f"Deleted report schedule {schedule_id} for user {current_user.email}")
        
        return {"message": "スケジュールを削除しました"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting report schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail=f"スケジュールの削除に失敗しました: {str(e)}")


@router.post("/{schedule_id}/execute", response_model=ScheduleExecutionResponse)
async def execute_report_schedule_manually(
    schedule_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """レポートスケジュールを手動実行"""
    try:
        schedule = db.query(ReportScheduleConfig).filter(
            ReportScheduleConfig.id == schedule_id,
            ReportScheduleConfig.created_by == current_user.id
        ).first()
        
        if not schedule:
            raise HTTPException(status_code=404, detail="スケジュールが見つかりません")
        
        # 現在実行中でないかチェック
        running_tasks = await report_scheduler_service.get_running_tasks()
        if schedule_id in running_tasks:
            raise HTTPException(status_code=409, detail="このスケジュールは既に実行中です")
        
        # 手動実行
        current_time = datetime.now()
        await report_scheduler_service._execute_scheduled_report(db, schedule, current_time)
        
        return ScheduleExecutionResponse(
            schedule_id=schedule_id,
            report_id=None,  # 非同期実行のため即座には分からない
            report_title=None,
            email_sent=False,
            email_recipients_count=0,
            execution_time=current_time,
            status="started",
            message="手動実行を開始しました。実行状況は実行履歴で確認できます。"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing report schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail=f"スケジュールの手動実行に失敗しました: {str(e)}")


@router.get("/{schedule_id}/status")
async def get_schedule_status(
    schedule_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """スケジュールの実行状況を取得"""
    try:
        schedule = db.query(ReportScheduleConfig).filter(
            ReportScheduleConfig.id == schedule_id,
            ReportScheduleConfig.created_by == current_user.id
        ).first()
        
        if not schedule:
            raise HTTPException(status_code=404, detail="スケジュールが見つかりません")
        
        # 実行中タスクの確認
        running_tasks = await report_scheduler_service.get_running_tasks()
        is_running = schedule_id in running_tasks
        task_id = running_tasks.get(schedule_id)
        
        return {
            "schedule_id": schedule_id,
            "schedule_name": schedule.name,
            "is_running": is_running,
            "task_id": task_id,
            "last_executed_at": schedule.last_executed_at,
            "last_execution_status": schedule.last_execution_status,
            "last_execution_message": schedule.last_execution_message,
            "next_scheduled_at": schedule.next_scheduled_at,
            "enabled": schedule.enabled
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting schedule status {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail=f"スケジュール状況の取得に失敗しました: {str(e)}")


@router.post("/{schedule_id}/cancel")
async def cancel_running_schedule(
    schedule_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """実行中スケジュールをキャンセル"""
    try:
        schedule = db.query(ReportScheduleConfig).filter(
            ReportScheduleConfig.id == schedule_id,
            ReportScheduleConfig.created_by == current_user.id
        ).first()
        
        if not schedule:
            raise HTTPException(status_code=404, detail="スケジュールが見つかりません")
        
        # キャンセル実行
        success = await report_scheduler_service.cancel_running_task(schedule_id)
        
        if success:
            return {"message": "実行中タスクをキャンセルしました"}
        else:
            raise HTTPException(status_code=404, detail="実行中のタスクが見つかりません")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail=f"タスクのキャンセルに失敗しました: {str(e)}")


@router.get("/running-tasks/list")
async def get_running_tasks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """実行中タスク一覧を取得"""
    try:
        running_tasks = await report_scheduler_service.get_running_tasks()
        
        # ユーザーのスケジュールのみフィルタリング
        user_schedules = db.query(ReportScheduleConfig).filter(
            ReportScheduleConfig.created_by == current_user.id,
            ReportScheduleConfig.id.in_(running_tasks.keys()) if running_tasks else False
        ).all()
        
        result = []
        for schedule in user_schedules:
            if schedule.id in running_tasks:
                result.append({
                    "schedule_id": schedule.id,
                    "schedule_name": schedule.name,
                    "task_id": running_tasks[schedule.id]
                })
        
        return {"running_tasks": result}
        
    except Exception as e:
        logger.error(f"Error getting running tasks: {e}")
        raise HTTPException(status_code=500, detail=f"実行中タスクの取得に失敗しました: {str(e)}")


def _schedule_to_response(schedule: ReportScheduleConfig) -> ReportScheduleResponse:
    """ReportScheduleConfigをレスポンス形式に変換"""
    return ReportScheduleResponse(
        id=str(schedule.id),
        name=schedule.name,
        description=schedule.description,
        enabled=schedule.enabled,
        schedule_type=schedule.schedule_type,
        schedule_time=schedule.schedule_time.strftime('%H:%M'),
        schedule_display=schedule.schedule_display,
        weekday=schedule.weekday,
        day_of_month=schedule.day_of_month,
        report_type=schedule.report_type,
        report_title_template=schedule.report_title_template,
        date_range_days=schedule.date_range_days,
        tags_filter=schedule.get_tags_filter(),
        sources_filter=schedule.get_sources_filter(),
        prompt_template_id=str(schedule.prompt_template_id) if schedule.prompt_template_id else None,
        email_enabled=schedule.email_enabled,
        email_recipients=schedule.get_email_recipients(),
        email_subject_template=schedule.email_subject_template,
        last_executed_at=schedule.last_executed_at,
        last_execution_status=schedule.last_execution_status,
        last_execution_message=schedule.last_execution_message,
        next_scheduled_at=schedule.next_scheduled_at,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at
    )