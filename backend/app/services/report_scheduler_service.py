import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone, time, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.core.background_tasks import task_manager
from app.services.report_service import ReportService
from app.services.email_service import get_email_service
from app.models.user import User
from app.models.report_schedule import ReportScheduleConfig

logger = logging.getLogger(__name__)


class ReportSchedulerService:
    """レポート自動生成・送信スケジューラー"""
    
    def __init__(self):
        self.running_tasks: Dict[str, str] = {}  # schedule_id -> task_id
        self.scheduler_task: Optional[asyncio.Task] = None
        self.is_running = False
        self._lock = asyncio.Lock()
    
    async def start_scheduler(self):
        """スケジューラーを開始"""
        if self.is_running:
            logger.warning("Report scheduler is already running")
            return
        
        self.is_running = True
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Report Scheduler started")
    
    async def stop_scheduler(self):
        """スケジューラーを停止"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Report Scheduler stopped")
    
    async def _scheduler_loop(self):
        """スケジューラーメインループ"""
        logger.info("Report Scheduler loop started")
        
        while self.is_running:
            try:
                current_time = datetime.now(timezone.utc)
                
                # データベースから実行すべきスケジュールを取得
                from app.db.database import SessionLocal
                db = SessionLocal()
                
                try:
                    schedules_to_run = await self._get_schedules_to_run(db, current_time)
                    
                    # スケジュールされたタスクを実行
                    for schedule in schedules_to_run:
                        try:
                            if schedule.id not in self.running_tasks:
                                await self._execute_scheduled_report(db, schedule, current_time)
                            else:
                                logger.info(f"Schedule {schedule.id} is already running, skipping")
                                
                        except Exception as e:
                            logger.exception(f"Failed to execute scheduled report for schedule {schedule.id}")
                            
                            # 実行状態を更新
                            schedule.last_executed_at = current_time
                            schedule.last_execution_status = "error"
                            schedule.last_execution_message = str(e)
                            db.commit()
                finally:
                    db.close()
                
                # 1分間待機
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Error in report scheduler loop: {e}")
                await asyncio.sleep(60)  # エラー時も1分待機
    
    async def _get_schedules_to_run(
        self, 
        db: Session, 
        current_time: datetime
    ) -> List[ReportScheduleConfig]:
        """実行すべきスケジュールを取得"""
        
        # 現在時刻（分精度）
        current_time_minute = current_time.replace(second=0, microsecond=0)
        current_hour_minute = current_time_minute.time()
        
        schedules = db.query(ReportScheduleConfig).filter(
            ReportScheduleConfig.enabled == True
        ).all()
        
        schedules_to_run = []
        
        for schedule in schedules:
            should_run = False
            
            # 時刻チェック（分精度）
            schedule_time = schedule.schedule_time
            if (schedule_time.hour == current_hour_minute.hour and 
                schedule_time.minute == current_hour_minute.minute):
                
                # 日次スケジュール
                if schedule.schedule_type == "daily":
                    # 今日まだ実行されていないかチェック
                    if not schedule.last_executed_at or schedule.last_executed_at.date() < current_time.date():
                        should_run = True
                
                # 週次スケジュール
                elif schedule.schedule_type == "weekly":
                    weekday = int(schedule.weekday) if schedule.weekday else 0  # デフォルト月曜日
                    if current_time.weekday() == weekday:
                        # 今週まだ実行されていないかチェック
                        week_start = current_time - timedelta(days=current_time.weekday())
                        if not schedule.last_executed_at or schedule.last_executed_at < week_start:
                            should_run = True
                
                # 月次スケジュール  
                elif schedule.schedule_type == "monthly":
                    day_of_month = int(schedule.day_of_month) if schedule.day_of_month else 1
                    if current_time.day == day_of_month:
                        # 今月まだ実行されていないかチェック
                        month_start = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                        if not schedule.last_executed_at or schedule.last_executed_at < month_start:
                            should_run = True
                
                if should_run:
                    logger.info(f"Schedule {schedule.id} ({schedule.name}) should run now")
                    schedules_to_run.append(schedule)
        
        return schedules_to_run
    
    async def _execute_scheduled_report(
        self, 
        db: Session, 
        schedule: ReportScheduleConfig,
        current_time: datetime
    ):
        """スケジュールされたレポート生成・送信を実行"""
        try:
            logger.info(f"Starting scheduled report generation for schedule {schedule.id} ({schedule.name})")
            
            # タスクIDを生成してバックグラウンドタスクとして実行
            task_id = await task_manager.create_task(
                self._report_generation_task,
                schedule.id,
                current_time,
                task_id=f"report_schedule_{schedule.id}_{current_time.strftime('%Y%m%d_%H%M')}",
                total=100,
                message=f"レポート自動生成開始: {schedule.name}"
            )
            
            # 実行中タスクとして記録
            async with self._lock:
                self.running_tasks[schedule.id] = task_id
            
            logger.info(f"Started report generation task {task_id} for schedule {schedule.id}")
            
        except Exception as e:
            logger.exception(f"Failed to start scheduled report generation for schedule {schedule.id}")
            raise
    
    async def _report_generation_task(
        self, 
        schedule_id: str, 
        execution_time: datetime,
        progress_callback=None
    ):
        """レポート生成タスクの実行"""
        from app.db.database import SessionLocal
        
        db = SessionLocal()
        try:
            # スケジュール設定取得
            schedule = db.query(ReportScheduleConfig).filter(
                ReportScheduleConfig.id == schedule_id
            ).first()
            
            if not schedule:
                raise ValueError(f"Schedule {schedule_id} not found")
            
            # ユーザー取得
            user = db.query(User).filter(User.id == schedule.created_by).first()
            if not user:
                raise ValueError(f"User {schedule.created_by} not found")
            
            # 実行開始をデータベースに記録
            schedule.last_executed_at = execution_time
            schedule.last_execution_status = "running"
            schedule.last_execution_message = "レポート生成中..."
            db.commit()
            
            if progress_callback:
                progress_callback(10, 100, f"レポート生成開始: {schedule.name}")
            
            # レポート生成用の日付範囲を計算
            start_date, end_date = self._calculate_date_range(schedule, execution_time)
            
            if progress_callback:
                progress_callback(20, 100, f"対象期間: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
            
            # レポートサービスでレポート生成
            report_service = ReportService(db)
            
            report_data = await report_service.generate_report(
                report_type=schedule.report_type,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                tags=schedule.get_tags_filter(),
                sources=schedule.get_sources_filter(),
                user=user
            )
            
            if progress_callback:
                progress_callback(50, 100, "レポートデータ生成完了")
            
            # レポートタイトル生成
            report_title = schedule.generate_report_title(execution_time)
            
            # ブログレポート生成
            blog_content = await report_service.generate_blog_report(
                report_type=schedule.report_type,
                report_data=report_data,
                summary=report_data["summary"],
                title=report_title,
                user=user,
                prompt_template_id=schedule.prompt_template_id
            )
            
            if progress_callback:
                progress_callback(70, 100, "レポート記事生成完了")
            
            # レポートを保存
            saved_report = await report_service.save_report(
                title=report_title,
                report_type=schedule.report_type,
                content=blog_content,
                parameters={
                    "schedule_id": schedule_id,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "tags": schedule.get_tags_filter(),
                    "sources": schedule.get_sources_filter(),
                    "auto_generated": True
                },
                raw_data=report_data,
                summary=report_data["summary"],
                tags=schedule.get_tags_filter() + [f"auto-{schedule.schedule_type}"],
                user=user
            )
            
            if progress_callback:
                progress_callback(80, 100, "レポート保存完了")
            
            # メール送信（有効な場合）
            email_sent = False
            email_error = None
            
            if schedule.email_enabled and schedule.get_email_recipients():
                try:
                    email_service = get_email_service()
                    if email_service:
                        email_subject = schedule.generate_email_subject(execution_time)
                        
                        email_sent = await email_service.send_report_email(
                            to_emails=schedule.get_email_recipients(),
                            report_title=report_title,
                            report_content=blog_content,
                            report_type=schedule.report_type,
                            generated_at=execution_time
                        )
                        
                        if email_sent:
                            if progress_callback:
                                progress_callback(90, 100, f"メール送信完了: {len(schedule.get_email_recipients())}件")
                        else:
                            email_error = "メール送信に失敗しました"
                            if progress_callback:
                                progress_callback(90, 100, "メール送信失敗")
                    else:
                        email_error = "メールサービスが設定されていません"
                        if progress_callback:
                            progress_callback(90, 100, "メール設定なし")
                            
                except Exception as e:
                    email_error = f"メール送信エラー: {str(e)}"
                    logger.exception(f"Email sending failed for schedule {schedule_id}")
                    if progress_callback:
                        progress_callback(90, 100, f"メール送信エラー: {str(e)}")
            else:
                if progress_callback:
                    progress_callback(90, 100, "メール送信はスキップされました")
            
            # 実行完了をデータベースに記録
            success_message = f"レポート生成完了: {saved_report.id}"
            if schedule.email_enabled:
                if email_sent:
                    success_message += f", メール送信成功({len(schedule.get_email_recipients())}件)"
                elif email_error:
                    success_message += f", メール送信失敗({email_error})"
                else:
                    success_message += ", メール送信スキップ"
            
            schedule.last_execution_status = "success"
            schedule.last_execution_message = success_message
            
            # 次回実行予定時刻を計算・設定
            next_scheduled = self._calculate_next_execution(schedule, execution_time)
            schedule.next_scheduled_at = next_scheduled
            
            db.commit()
            
            if progress_callback:
                progress_callback(100, 100, f"完了: {success_message}")
            
            result = {
                "schedule_id": schedule_id,
                "report_id": saved_report.id,
                "report_title": report_title,
                "email_sent": email_sent,
                "email_recipients_count": len(schedule.get_email_recipients()) if schedule.email_enabled else 0,
                "next_scheduled_at": next_scheduled.isoformat() if next_scheduled else None,
                "execution_time": execution_time.isoformat()
            }
            
            logger.info(f"Scheduled report generation completed for schedule {schedule_id}: {result}")
            return result
            
        except Exception as e:
            logger.exception(f"Report generation task failed for schedule {schedule_id}")
            
            # エラー状態をデータベースに記録
            try:
                schedule = db.query(ReportScheduleConfig).filter(
                    ReportScheduleConfig.id == schedule_id
                ).first()
                if schedule:
                    schedule.last_execution_status = "failed"
                    schedule.last_execution_message = f"エラー: {str(e)}"
                    db.commit()
            except:
                pass
            
            if progress_callback:
                progress_callback(100, 100, f"エラー: {str(e)}")
            raise
            
        finally:
            # 実行中タスクから削除
            async with self._lock:
                if schedule_id in self.running_tasks:
                    del self.running_tasks[schedule_id]
            
            db.close()
    
    def _calculate_date_range(
        self, 
        schedule: ReportScheduleConfig, 
        execution_time: datetime
    ) -> Tuple[datetime, datetime]:
        """スケジュールタイプに応じた日付範囲を計算"""
        
        if schedule.schedule_type == "daily":
            # 前日の丸1日分
            yesterday = execution_time.date() - timedelta(days=1)
            start_date = datetime.combine(yesterday, time.min).replace(tzinfo=timezone.utc)
            end_date = datetime.combine(yesterday, time.max).replace(tzinfo=timezone.utc)
            
        elif schedule.schedule_type == "weekly":
            # 先週月曜日〜日曜日
            days_since_monday = execution_time.weekday()  # 0=月曜, 6=日曜
            last_monday = execution_time.date() - timedelta(days=days_since_monday + 7)
            last_sunday = last_monday + timedelta(days=6)
            
            start_date = datetime.combine(last_monday, time.min).replace(tzinfo=timezone.utc)
            end_date = datetime.combine(last_sunday, time.max).replace(tzinfo=timezone.utc)
            
        elif schedule.schedule_type == "monthly":
            # 先月全体
            first_this_month = execution_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if first_this_month.month == 1:
                first_last_month = first_this_month.replace(year=first_this_month.year - 1, month=12)
            else:
                first_last_month = first_this_month.replace(month=first_this_month.month - 1)
            
            # 先月の最終日を計算
            last_day_last_month = first_this_month - timedelta(days=1)
            
            start_date = first_last_month
            end_date = datetime.combine(
                last_day_last_month.date(), 
                time.max
            ).replace(tzinfo=timezone.utc)
        
        else:
            # カスタム範囲（日数指定）
            days = schedule.get_date_range_days()
            end_date = execution_time
            start_date = end_date - timedelta(days=days)
        
        return start_date, end_date
    
    def _calculate_next_execution(
        self, 
        schedule: ReportScheduleConfig, 
        current_execution: datetime
    ) -> Optional[datetime]:
        """次回実行予定時刻を計算"""
        
        try:
            if schedule.schedule_type == "daily":
                # 次の日の同じ時刻
                next_date = current_execution.date() + timedelta(days=1)
                next_execution = datetime.combine(
                    next_date, 
                    schedule.schedule_time
                ).replace(tzinfo=timezone.utc)
                
            elif schedule.schedule_type == "weekly":
                # 来週の同じ曜日・時刻
                next_execution = current_execution + timedelta(days=7)
                next_execution = next_execution.replace(
                    hour=schedule.schedule_time.hour,
                    minute=schedule.schedule_time.minute,
                    second=0,
                    microsecond=0
                )
                
            elif schedule.schedule_type == "monthly":
                # 来月の同じ日・時刻
                current_month = current_execution.month
                current_year = current_execution.year
                
                if current_month == 12:
                    next_month = 1
                    next_year = current_year + 1
                else:
                    next_month = current_month + 1
                    next_year = current_year
                
                day_of_month = int(schedule.day_of_month) if schedule.day_of_month else 1
                
                # 月末日チェック
                import calendar
                max_day = calendar.monthrange(next_year, next_month)[1]
                if day_of_month > max_day:
                    day_of_month = max_day
                
                next_execution = datetime(
                    year=next_year,
                    month=next_month,
                    day=day_of_month,
                    hour=schedule.schedule_time.hour,
                    minute=schedule.schedule_time.minute,
                    tzinfo=timezone.utc
                )
            else:
                # その他の場合は計算しない
                return None
            
            return next_execution
            
        except Exception as e:
            logger.warning(f"Failed to calculate next execution for schedule {schedule.id}: {e}")
            return None
    
    async def get_running_tasks(self) -> Dict[str, str]:
        """実行中タスク一覧を取得"""
        return self.running_tasks.copy()
    
    async def cancel_running_task(self, schedule_id: str) -> bool:
        """実行中タスクをキャンセル"""
        try:
            async with self._lock:
                if schedule_id in self.running_tasks:
                    task_id = self.running_tasks[schedule_id]
                    success = await task_manager.cancel_task(task_id)
                    if success:
                        del self.running_tasks[schedule_id]
                    return success
                return False
                
        except Exception as e:
            logger.exception(f"Failed to cancel running task for schedule {schedule_id}")
            return False


# グローバルスケジューラーインスタンス
report_scheduler_service = ReportSchedulerService()