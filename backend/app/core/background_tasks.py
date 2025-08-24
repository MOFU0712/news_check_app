import asyncio
import logging
import uuid
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
import traceback

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    """タスクステータス"""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class TaskProgress:
    """タスク進捗情報"""
    task_id: str
    status: TaskStatus
    current: int = 0
    total: int = 0
    message: str = ""
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress_details: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.progress_details is None:
            self.progress_details = {}
    
    @property
    def progress_percentage(self) -> float:
        """進捗率を計算"""
        if self.total <= 0:
            return 0.0
        return min(100.0, (self.current / self.total) * 100.0)
    
    @property
    def is_active(self) -> bool:
        """アクティブなタスクかどうか"""
        return self.status in [TaskStatus.PENDING, TaskStatus.RUNNING]
    
    @property
    def is_finished(self) -> bool:
        """完了したタスクかどうか"""
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式で返す"""
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "current": self.current,
            "total": self.total,
            "progress_percentage": self.progress_percentage,
            "message": self.message,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress_details": self.progress_details
        }

class BackgroundTaskManager:
    """バックグラウンドタスクマネージャー"""
    
    def __init__(self):
        self._tasks: Dict[str, TaskProgress] = {}
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._progress_callbacks: Dict[str, list] = {}
        self._lock = asyncio.Lock()
    
    async def create_task(
        self,
        task_func: Callable,
        *args,
        task_id: Optional[str] = None,
        total: int = 0,
        message: str = "",
        **kwargs
    ) -> str:
        """
        バックグラウンドタスクを作成・開始
        
        Args:
            task_func: 実行する非同期関数
            *args: 関数の引数
            task_id: タスクID（省略時は自動生成）
            total: 総処理数
            message: 初期メッセージ
            **kwargs: 関数のキーワード引数
            
        Returns:
            タスクID
        """
        if task_id is None:
            task_id = str(uuid.uuid4())
        
        async with self._lock:
            if task_id in self._tasks:
                raise ValueError(f"Task {task_id} already exists")
            
            # タスク進捗を初期化
            progress = TaskProgress(
                task_id=task_id,
                status=TaskStatus.PENDING,
                total=total,
                message=message
            )
            self._tasks[task_id] = progress
            self._progress_callbacks[task_id] = []
        
        # 非同期タスクを開始
        async_task = asyncio.create_task(
            self._execute_task(task_id, task_func, *args, **kwargs)
        )
        self._running_tasks[task_id] = async_task
        
        logger.info(f"Created background task {task_id}")
        return task_id
    
    async def _execute_task(
        self,
        task_id: str,
        task_func: Callable,
        *args,
        **kwargs
    ):
        """タスクを実行"""
        progress = self._tasks[task_id]
        
        try:
            # タスク開始
            progress.status = TaskStatus.RUNNING
            progress.started_at = datetime.now(timezone.utc)
            progress.message = "Task started"
            await self._notify_progress_update(task_id)
            
            # プログレス更新コールバックを作成
            progress_callback = self._create_progress_callback(task_id)
            
            # タスク実行（プログレスコールバックを渡す）
            if 'progress_callback' in kwargs:
                # 既存のコールバックがある場合はチェーン
                original_callback = kwargs['progress_callback']
                def chained_callback(*cb_args, **cb_kwargs):
                    progress_callback(*cb_args, **cb_kwargs)
                    if original_callback:
                        original_callback(*cb_args, **cb_kwargs)
                kwargs['progress_callback'] = chained_callback
            else:
                kwargs['progress_callback'] = progress_callback
            
            result = await task_func(*args, **kwargs)
            
            # タスク完了
            progress.status = TaskStatus.COMPLETED
            progress.completed_at = datetime.now(timezone.utc)
            progress.result = result
            progress.message = "Task completed successfully"
            await self._notify_progress_update(task_id)
            
            logger.info(f"Background task {task_id} completed successfully")
            
        except asyncio.CancelledError:
            # タスクキャンセル
            progress.status = TaskStatus.CANCELLED
            progress.completed_at = datetime.now(timezone.utc)
            progress.message = "Task was cancelled"
            await self._notify_progress_update(task_id)
            
            logger.info(f"Background task {task_id} was cancelled")
            
        except Exception as e:
            # タスク失敗
            progress.status = TaskStatus.FAILED
            progress.completed_at = datetime.now(timezone.utc)
            progress.error = str(e)
            progress.message = f"Task failed: {str(e)}"
            await self._notify_progress_update(task_id)
            
            logger.error(f"Background task {task_id} failed: {str(e)}")
            logger.error(traceback.format_exc())
            
        finally:
            # クリーンアップ
            if task_id in self._running_tasks:
                del self._running_tasks[task_id]
    
    def _create_progress_callback(self, task_id: str):
        """プログレス更新コールバックを作成"""
        def progress_callback(current: int = None, total: int = None, message: str = None, **details):
            """プログレス更新コールバック"""
            asyncio.create_task(self.update_progress(
                task_id, current=current, total=total, message=message, **details
            ))
        
        return progress_callback
    
    async def update_progress(
        self,
        task_id: str,
        current: Optional[int] = None,
        total: Optional[int] = None,
        message: Optional[str] = None,
        **details
    ):
        """タスクの進捗を更新"""
        async with self._lock:
            if task_id not in self._tasks:
                return
            
            progress = self._tasks[task_id]
            
            if current is not None:
                progress.current = current
            if total is not None:
                progress.total = total
            if message is not None:
                progress.message = message
            if details:
                progress.progress_details.update(details)
        
        await self._notify_progress_update(task_id)
    
    async def _notify_progress_update(self, task_id: str):
        """進捗更新を通知"""
        if task_id in self._progress_callbacks:
            progress = self._tasks[task_id]
            for callback in self._progress_callbacks[task_id]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(progress)
                    else:
                        callback(progress)
                except Exception as e:
                    logger.error(f"Progress callback error for task {task_id}: {e}")
    
    async def get_task_progress(self, task_id: str) -> Optional[TaskProgress]:
        """タスクの進捗を取得"""
        return self._tasks.get(task_id)
    
    async def list_tasks(
        self, 
        status_filter: Optional[TaskStatus] = None,
        limit: int = 100
    ) -> list[TaskProgress]:
        """タスク一覧を取得"""
        tasks = list(self._tasks.values())
        
        if status_filter:
            tasks = [t for t in tasks if t.status == status_filter]
        
        # 作成日時の降順でソート
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        
        return tasks[:limit]
    
    async def cancel_task(self, task_id: str) -> bool:
        """タスクをキャンセル"""
        if task_id in self._running_tasks:
            task = self._running_tasks[task_id]
            task.cancel()
            return True
        return False
    
    async def cleanup_finished_tasks(self, keep_hours: int = 24):
        """完了したタスクをクリーンアップ"""
        cutoff_time = datetime.now(timezone.utc).timestamp() - (keep_hours * 3600)
        
        async with self._lock:
            tasks_to_remove = []
            for task_id, progress in self._tasks.items():
                if (progress.is_finished and 
                    progress.completed_at and 
                    progress.completed_at.timestamp() < cutoff_time):
                    tasks_to_remove.append(task_id)
            
            for task_id in tasks_to_remove:
                del self._tasks[task_id]
                if task_id in self._progress_callbacks:
                    del self._progress_callbacks[task_id]
        
        if tasks_to_remove:
            logger.info(f"Cleaned up {len(tasks_to_remove)} finished tasks")
    
    def add_progress_callback(self, task_id: str, callback: Callable):
        """進捗更新コールバックを追加"""
        if task_id in self._progress_callbacks:
            self._progress_callbacks[task_id].append(callback)
    
    def remove_progress_callback(self, task_id: str, callback: Callable):
        """進捗更新コールバックを削除"""
        if task_id in self._progress_callbacks and callback in self._progress_callbacks[task_id]:
            self._progress_callbacks[task_id].remove(callback)

# グローバルタスクマネージャーインスタンス
task_manager = BackgroundTaskManager()