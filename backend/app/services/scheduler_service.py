import asyncio
import logging
import json
from typing import Dict, List, Optional, Callable
from datetime import datetime, timezone, time, timedelta
from dataclasses import dataclass
from sqlalchemy.orm import Session
import threading

from app.core.background_tasks import task_manager
from app.services.rss_service import RSSService
from app.services.scraping_service import ScrapingService
from app.models.user import User
from app.models.rss_schedule import RSSSchedule
from app.db.database import get_db

logger = logging.getLogger(__name__)


@dataclass
class ScheduleConfig:
    """スケジュール設定"""
    user_id: str
    rss_file_path: str
    schedule_time: time  # 実行時刻（例：time(9, 0) = 09:00）
    enabled: bool = True
    auto_generate_tags: bool = True
    skip_duplicates: bool = True
    include_arxiv: bool = False
    arxiv_categories: Optional[List[str]] = None
    arxiv_max_results: int = 20


class SchedulerService:
    """スケジューラーサービス - 日次実行を管理"""
    
    def __init__(self):
        self.schedules: Dict[str, ScheduleConfig] = {}
        self.running_tasks: Dict[str, str] = {}  # user_id -> task_id
        self.scheduler_task: Optional[asyncio.Task] = None
        self.is_running = False
        self._lock = asyncio.Lock()
        self._schedules_loaded = False
    
    async def start_scheduler(self):
        """スケジューラーを開始"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        # 初回起動時にデータベースからスケジュールを読み込み
        if not self._schedules_loaded:
            await self._load_schedules_from_db()
            self._schedules_loaded = True
        
        self.is_running = True
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("RSS Scheduler started")
    
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
        
        logger.info("RSS Scheduler stopped")
    
    async def _scheduler_loop(self):
        """スケジューラーメインループ"""
        logger.info("RSS Scheduler loop started")
        
        while self.is_running:
            try:
                current_time = datetime.now(timezone.utc).time()
                
                # 実行すべきスケジュールをチェック
                schedules_to_run = []
                async with self._lock:
                    for user_id, config in self.schedules.items():
                        if (config.enabled and 
                            self._should_run_now(current_time, config.schedule_time) and
                            user_id not in self.running_tasks):
                            schedules_to_run.append((user_id, config))
                
                # スケジュールされたタスクを実行
                for user_id, config in schedules_to_run:
                    try:
                        await self._execute_scheduled_rss_scraping(user_id, config)
                    except Exception as e:
                        logger.exception(f"Failed to execute scheduled RSS scraping for user {user_id}")
                
                # 1分間待機
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Error in scheduler loop: {e}")
                await asyncio.sleep(60)  # エラー時も1分待機
    
    def _should_run_now(self, current_time: time, schedule_time: time) -> bool:
        """現在時刻がスケジュール時刻かどうか判定"""
        # 分精度での比較（秒は無視）
        current_hour_min = (current_time.hour, current_time.minute)
        schedule_hour_min = (schedule_time.hour, schedule_time.minute)
        
        return current_hour_min == schedule_hour_min
    
    async def _execute_scheduled_rss_scraping(self, user_id: str, config: ScheduleConfig):
        """スケジュールされたRSSスクレイピングを実行"""
        try:
            logger.info(f"Starting scheduled RSS scraping for user {user_id}")
            
            # タスクIDを生成してバックグラウンドタスクとして実行
            task_id = await task_manager.create_task(
                self._rss_scraping_task,
                user_id,
                config,
                task_id=f"rss_scraping_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M')}",
                total=100,  # 仮の値、実際の処理で更新される
                message=f"RSS自動スクレイピング開始: {config.rss_file_path}"
            )
            
            # 実行中タスクとして記録
            async with self._lock:
                self.running_tasks[user_id] = task_id
            
            logger.info(f"Started RSS scraping task {task_id} for user {user_id}")
            
        except Exception as e:
            logger.exception(f"Failed to start scheduled RSS scraping for user {user_id}")
    
    async def _rss_scraping_task(self, user_id: str, config: ScheduleConfig, progress_callback=None):
        """RSSスクレイピングタスクの実行"""
        from app.db.database import SessionLocal
        
        db = SessionLocal()
        try:
            # ユーザー取得
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            # プログレス更新
            if progress_callback:
                progress_callback(0, 100, f"RSSフィードを読み込み中: {config.rss_file_path}")
            
            # RSSサービスでRSSフィード・arXiv論文から記事URLを取得
            async with RSSService() as rss_service:
                def rss_progress_callback(current, total, message):
                    if progress_callback:
                        # RSS処理は全体の30%とする
                        adjusted_current = min(30, int((current / max(total, 1)) * 30))
                        progress_callback(adjusted_current, 100, f"RSS処理: {message}")
                
                if config.include_arxiv:
                    article_urls, rss_results, arxiv_papers = await rss_service.get_latest_articles_with_arxiv(
                        config.rss_file_path,
                        include_arxiv=True,
                        arxiv_categories=config.arxiv_categories,
                        arxiv_max_results=config.arxiv_max_results,
                        target_date=datetime.now(timezone.utc),
                        progress_callback=rss_progress_callback
                    )
                    
                    logger.info(f"取得完了: RSS記事{len(rss_results)}件 + arXiv論文{len(arxiv_papers)}件")
                else:
                    article_urls, rss_results = await rss_service.get_latest_articles_from_file(
                        config.rss_file_path,
                        rss_progress_callback
                    )
                    arxiv_papers = []
            
            if not article_urls:
                if progress_callback:
                    progress_callback(100, 100, "新しい記事が見つかりませんでした")
                logger.info(f"No new articles found for user {user_id}")
                return {"message": "No new articles found", "articles_count": 0}
            
            # プログレス更新
            if progress_callback:
                progress_callback(30, 100, f"スクレイピング開始: {len(article_urls)}件のURL")
            
            # URLリストを文字列に変換（ScrapingServiceの要求形式）
            urls_text = "\n".join(article_urls)
            
            # ScrapingServiceでスクレイピング実行
            scraping_service = ScrapingService(db)
            
            def scraping_progress_callback(current, total, message, **details):
                if progress_callback:
                    # スクレイピング処理は全体の70%とする（30% + 70% = 100%）
                    adjusted_current = 30 + min(70, int((current / max(total, 1)) * 70))
                    progress_callback(adjusted_current, 100, f"スクレイピング: {message}")
            
            # スクレイピングジョブを作成・実行
            scraping_job = await scraping_service.create_and_start_scraping_job(
                user=user,
                urls_text=urls_text,
                auto_generate_tags=config.auto_generate_tags,
                skip_duplicates=config.skip_duplicates
            )
            
            # スクレイピング完了を待機
            max_wait_time = 3600  # 最大1時間待機
            wait_interval = 10    # 10秒間隔でチェック
            waited_time = 0
            
            while waited_time < max_wait_time:
                # ジョブ状態をチェック
                db.refresh(scraping_job)
                
                if scraping_job.status == "completed":
                    if progress_callback:
                        progress_callback(100, 100, f"完了: {len(scraping_job.created_article_ids or [])}件の記事を作成")
                    break
                elif scraping_job.status == "failed":
                    error_msg = scraping_job.error_message or "Unknown error"
                    if progress_callback:
                        progress_callback(100, 100, f"失敗: {error_msg}")
                    raise Exception(f"Scraping job failed: {error_msg}")
                elif scraping_job.status in ["pending", "running"]:
                    # 進捗更新
                    if progress_callback:
                        progress_pct = 30 + min(70, int((scraping_job.progress / max(scraping_job.total, 1)) * 70))
                        progress_callback(progress_pct, 100, f"スクレイピング中: {scraping_job.progress}/{scraping_job.total}")
                else:
                    # その他の状態（cancelled など）
                    if progress_callback:
                        progress_callback(100, 100, f"スクレイピングが中断されました: {scraping_job.status}")
                    break
                
                await asyncio.sleep(wait_interval)
                waited_time += wait_interval
            
            if waited_time >= max_wait_time:
                if progress_callback:
                    progress_callback(100, 100, "スクレイピングがタイムアウトしました")
                logger.warning(f"Scraping job {scraping_job.id} timed out after {max_wait_time} seconds")
            
            result = {
                "scraping_job_id": scraping_job.id,
                "articles_found": len(article_urls),
                "articles_created": len(scraping_job.created_article_ids or []),
                "rss_feeds_processed": len([r for r in rss_results if not r.error]),
                "rss_feeds_failed": len([r for r in rss_results if r.error]),
                "arxiv_enabled": config.include_arxiv,
                "arxiv_papers_found": len(arxiv_papers) if config.include_arxiv else 0
            }
            
            logger.info(f"Scheduled RSS scraping completed for user {user_id}: {result}")
            return result
            
        except Exception as e:
            logger.exception(f"RSS scraping task failed for user {user_id}")
            if progress_callback:
                progress_callback(100, 100, f"エラー: {str(e)}")
            raise
        finally:
            # 実行中タスクから削除
            async with self._lock:
                if user_id in self.running_tasks:
                    del self.running_tasks[user_id]
            
            db.close()
    
    async def add_schedule(
        self, 
        user_id: str, 
        rss_file_path: str, 
        schedule_time: time,
        auto_generate_tags: bool = True,
        skip_duplicates: bool = True,
        include_arxiv: bool = False,
        arxiv_categories: Optional[List[str]] = None,
        arxiv_max_results: int = 20
    ) -> bool:
        """スケジュールを追加"""
        try:
            config = ScheduleConfig(
                user_id=user_id,
                rss_file_path=rss_file_path,
                schedule_time=schedule_time,
                enabled=True,
                auto_generate_tags=auto_generate_tags,
                skip_duplicates=skip_duplicates,
                include_arxiv=include_arxiv,
                arxiv_categories=arxiv_categories,
                arxiv_max_results=arxiv_max_results
            )
            
            async with self._lock:
                self.schedules[user_id] = config
                
            # データベースに保存
            await self._save_schedule_to_db(config)
            
            logger.info(f"Added RSS schedule for user {user_id} at {schedule_time}")
            return True
            
        except Exception as e:
            logger.exception(f"Failed to add schedule for user {user_id}")
            return False
    
    async def remove_schedule(self, user_id: str) -> bool:
        """スケジュールを削除"""
        try:
            async with self._lock:
                if user_id in self.schedules:
                    del self.schedules[user_id]
                    
            # データベースからも削除
            await self._delete_schedule_from_db(user_id)
            
            logger.info(f"Removed RSS schedule for user {user_id}")
            return True
                
        except Exception as e:
            logger.exception(f"Failed to remove schedule for user {user_id}")
            return False
    
    async def update_schedule(
        self, 
        user_id: str, 
        schedule_time: Optional[time] = None,
        enabled: Optional[bool] = None,
        rss_file_path: Optional[str] = None,
        auto_generate_tags: Optional[bool] = None,
        skip_duplicates: Optional[bool] = None,
        include_arxiv: Optional[bool] = None,
        arxiv_categories: Optional[List[str]] = None,
        arxiv_max_results: Optional[int] = None
    ) -> bool:
        """スケジュールを更新"""
        try:
            async with self._lock:
                if user_id not in self.schedules:
                    return False
                
                config = self.schedules[user_id]
                
                if schedule_time is not None:
                    config.schedule_time = schedule_time
                if enabled is not None:
                    config.enabled = enabled
                if rss_file_path is not None:
                    config.rss_file_path = rss_file_path
                if auto_generate_tags is not None:
                    config.auto_generate_tags = auto_generate_tags
                if skip_duplicates is not None:
                    config.skip_duplicates = skip_duplicates
                if include_arxiv is not None:
                    config.include_arxiv = include_arxiv
                if arxiv_categories is not None:
                    config.arxiv_categories = arxiv_categories
                if arxiv_max_results is not None:
                    config.arxiv_max_results = arxiv_max_results
                    
            # データベースに保存
            await self._save_schedule_to_db(config)
                
            logger.info(f"Updated RSS schedule for user {user_id}")
            return True
                
        except Exception as e:
            logger.exception(f"Failed to update schedule for user {user_id}")
            return False
    
    async def get_schedule(self, user_id: str) -> Optional[ScheduleConfig]:
        """スケジュール設定を取得"""
        # 初回アクセス時にデータベースからスケジュールを読み込み
        if not self._schedules_loaded:
            await self._load_schedules_from_db()
            self._schedules_loaded = True
            
        return self.schedules.get(user_id)
    
    async def list_schedules(self) -> Dict[str, ScheduleConfig]:
        """全スケジュール設定を取得"""
        return self.schedules.copy()
    
    async def get_running_tasks(self) -> Dict[str, str]:
        """実行中タスク一覧を取得"""
        return self.running_tasks.copy()
    
    async def cancel_running_task(self, user_id: str) -> bool:
        """実行中タスクをキャンセル"""
        try:
            async with self._lock:
                if user_id in self.running_tasks:
                    task_id = self.running_tasks[user_id]
                    success = await task_manager.cancel_task(task_id)
                    if success:
                        del self.running_tasks[user_id]
                    return success
                return False
                
        except Exception as e:
            logger.exception(f"Failed to cancel running task for user {user_id}")
            return False
    
    async def create_auto_schedule_for_user(
        self,
        user_id: str,
        schedule_time: time = time(2, 0),  # デフォルト深夜2時
        auto_generate_tags: bool = True,
        skip_duplicates: bool = True,
        include_arxiv: bool = True,
        arxiv_categories: Optional[List[str]] = None,
        arxiv_max_results: int = 50,
        rss_file_path: Optional[str] = None
    ) -> bool:
        """
        ユーザーに自動スケジュールを設定
        RSS+arXiv取得→解析→スクレイピングを深夜に自動実行
        """
        try:
            # デフォルトのRSSファイルパス
            if not rss_file_path:
                rss_file_path = '/Users/tsutsuikana/Desktop/coding_workspace/news_check_app/backend/rss_feeds.txt'
            
            # デフォルトのarXivカテゴリ
            if not arxiv_categories:
                arxiv_categories = ['cs.AI', 'cs.LG', 'cs.CV']
            
            success = await self.add_schedule(
                user_id=user_id,
                rss_file_path=rss_file_path,
                schedule_time=schedule_time,
                auto_generate_tags=auto_generate_tags,
                skip_duplicates=skip_duplicates,
                include_arxiv=include_arxiv,
                arxiv_categories=arxiv_categories,
                arxiv_max_results=arxiv_max_results
            )
            
            if success:
                logger.info(f"Auto schedule created for user {user_id} at {schedule_time}")
            
            return success
            
        except Exception as e:
            logger.exception(f"Failed to create auto schedule for user {user_id}")
            return False

    async def _load_schedules_from_db(self):
        """データベースからスケジュールを読み込み"""
        try:
            async with self._lock:
                db_gen = get_db()
                db: Session = next(db_gen)
                try:
                    schedules = db.query(RSSSchedule).filter(RSSSchedule.enabled == True).all()
                    
                    for db_schedule in schedules:
                        # JSONからarxiv_categoriesを復元
                        arxiv_categories = None
                        if db_schedule.arxiv_categories:
                            try:
                                arxiv_categories = json.loads(db_schedule.arxiv_categories)
                            except json.JSONDecodeError:
                                arxiv_categories = ['cs.AI', 'cs.LG', 'cs.CV']  # デフォルト
                        
                        config = ScheduleConfig(
                            user_id=db_schedule.user_id,
                            rss_file_path=db_schedule.rss_file_path,
                            schedule_time=db_schedule.schedule_time,
                            enabled=db_schedule.enabled,
                            auto_generate_tags=db_schedule.auto_generate_tags,
                            skip_duplicates=db_schedule.skip_duplicates,
                            include_arxiv=db_schedule.include_arxiv,
                            arxiv_categories=arxiv_categories,
                            arxiv_max_results=db_schedule.arxiv_max_results
                        )
                        
                        self.schedules[db_schedule.user_id] = config
                    
                    logger.info(f"Loaded {len(schedules)} RSS schedules from database")
                    
                finally:
                    db.close()
                    
        except Exception as e:
            logger.exception("Failed to load schedules from database")
    
    async def _save_schedule_to_db(self, config: ScheduleConfig):
        """スケジュールをデータベースに保存/更新"""
        try:
            db_gen = get_db()
            db: Session = next(db_gen)
            try:
                # 既存のスケジュールを確認
                existing = db.query(RSSSchedule).filter(RSSSchedule.user_id == config.user_id).first()
                
                # arxiv_categoriesをJSON文字列に変換
                arxiv_categories_json = None
                if config.arxiv_categories:
                    arxiv_categories_json = json.dumps(config.arxiv_categories)
                
                if existing:
                    # 更新
                    existing.rss_file_path = config.rss_file_path
                    existing.schedule_time = config.schedule_time
                    existing.enabled = config.enabled
                    existing.auto_generate_tags = config.auto_generate_tags
                    existing.skip_duplicates = config.skip_duplicates
                    existing.include_arxiv = config.include_arxiv
                    existing.arxiv_categories = arxiv_categories_json
                    existing.arxiv_max_results = config.arxiv_max_results
                else:
                    # 新規作成
                    new_schedule = RSSSchedule(
                        user_id=config.user_id,
                        rss_file_path=config.rss_file_path,
                        schedule_time=config.schedule_time,
                        enabled=config.enabled,
                        auto_generate_tags=config.auto_generate_tags,
                        skip_duplicates=config.skip_duplicates,
                        include_arxiv=config.include_arxiv,
                        arxiv_categories=arxiv_categories_json,
                        arxiv_max_results=config.arxiv_max_results
                    )
                    db.add(new_schedule)
                
                db.commit()
                logger.info(f"Saved RSS schedule for user {config.user_id} to database")
                
            finally:
                db.close()
                
        except Exception as e:
            logger.exception(f"Failed to save schedule for user {config.user_id} to database")
            raise
    
    async def _delete_schedule_from_db(self, user_id: str):
        """データベースからスケジュールを削除"""
        try:
            db_gen = get_db()
            db: Session = next(db_gen)
            try:
                existing = db.query(RSSSchedule).filter(RSSSchedule.user_id == user_id).first()
                if existing:
                    db.delete(existing)
                    db.commit()
                    logger.info(f"Deleted RSS schedule for user {user_id} from database")
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.exception(f"Failed to delete schedule for user {user_id} from database")
            raise


# グローバルスケジューラーインスタンス
scheduler_service = SchedulerService()