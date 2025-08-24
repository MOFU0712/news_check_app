from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from typing import Dict, List
import json
import logging
import asyncio
from app.core.background_tasks import task_manager, TaskProgress
from app.core.deps import get_current_user_from_token
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()

class ConnectionManager:
    """WebSocket接続管理"""
    
    def __init__(self):
        # ユーザーID -> WebSocket接続のマッピング
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # タスクID -> 購読ユーザーIDのマッピング
        self.task_subscriptions: Dict[str, List[str]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        """WebSocket接続を受け入れ"""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        
        logger.info(f"WebSocket connected for user {user_id}")
    
    def disconnect(self, websocket: WebSocket, user_id: str):
        """WebSocket接続を切断"""
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            
            # 接続がなくなったらユーザーを削除
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                
                # タスク購読も削除
                tasks_to_remove = []
                for task_id, subscribers in self.task_subscriptions.items():
                    if user_id in subscribers:
                        subscribers.remove(user_id)
                        if not subscribers:
                            tasks_to_remove.append(task_id)
                
                for task_id in tasks_to_remove:
                    del self.task_subscriptions[task_id]
        
        logger.info(f"WebSocket disconnected for user {user_id}")
    
    async def send_personal_message(self, message: dict, user_id: str):
        """特定ユーザーにメッセージを送信"""
        if user_id in self.active_connections:
            disconnected_connections = []
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_text(json.dumps(message))
                except Exception as e:
                    logger.error(f"Failed to send message to user {user_id}: {e}")
                    disconnected_connections.append(connection)
            
            # 切断された接続を削除
            for connection in disconnected_connections:
                self.disconnect(connection, user_id)
    
    async def broadcast_task_progress(self, task_id: str, progress: TaskProgress):
        """タスク進捗を購読者に配信"""
        if task_id in self.task_subscriptions:
            message = {
                "type": "task_progress",
                "task_id": task_id,
                "progress": progress.to_dict()
            }
            
            for user_id in self.task_subscriptions[task_id]:
                await self.send_personal_message(message, user_id)
    
    def subscribe_to_task(self, task_id: str, user_id: str):
        """タスクの進捗購読を開始"""
        if task_id not in self.task_subscriptions:
            self.task_subscriptions[task_id] = []
        
        if user_id not in self.task_subscriptions[task_id]:
            self.task_subscriptions[task_id].append(user_id)
            
            # タスクマネージャーにコールバックを登録
            task_manager.add_progress_callback(
                task_id, 
                lambda progress: asyncio.create_task(
                    self.broadcast_task_progress(task_id, progress)
                )
            )
            
            logger.info(f"User {user_id} subscribed to task {task_id}")
    
    def unsubscribe_from_task(self, task_id: str, user_id: str):
        """タスクの進捗購読を停止"""
        if (task_id in self.task_subscriptions and 
            user_id in self.task_subscriptions[task_id]):
            
            self.task_subscriptions[task_id].remove(user_id)
            
            if not self.task_subscriptions[task_id]:
                del self.task_subscriptions[task_id]
            
            logger.info(f"User {user_id} unsubscribed from task {task_id}")

# グローバル接続マネージャー
connection_manager = ConnectionManager()

@router.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    """WebSocketエンドポイント"""
    try:
        # トークンからユーザー情報を取得
        # 簡易実装（実際の認証実装に合わせて調整）
        user_id = await get_user_id_from_token(token)
        if not user_id:
            await websocket.close(code=4001, reason="Invalid token")
            return
        
        # 接続を受け入れ
        await connection_manager.connect(websocket, user_id)
        
        try:
            while True:
                # クライアントからのメッセージを受信
                data = await websocket.receive_text()
                message = json.loads(data)
                
                await handle_websocket_message(message, user_id)
                
        except WebSocketDisconnect:
            pass
        
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    
    finally:
        connection_manager.disconnect(websocket, user_id)

async def handle_websocket_message(message: dict, user_id: str):
    """WebSocketメッセージを処理"""
    message_type = message.get("type")
    
    if message_type == "subscribe_task":
        # タスク進捗の購読開始
        task_id = message.get("task_id")
        if task_id:
            connection_manager.subscribe_to_task(task_id, user_id)
            
            # 現在の進捗を即座に送信
            progress = await task_manager.get_task_progress(task_id)
            if progress:
                await connection_manager.send_personal_message({
                    "type": "task_progress",
                    "task_id": task_id,
                    "progress": progress.to_dict()
                }, user_id)
    
    elif message_type == "unsubscribe_task":
        # タスク進捗の購読停止
        task_id = message.get("task_id")
        if task_id:
            connection_manager.unsubscribe_from_task(task_id, user_id)
    
    elif message_type == "ping":
        # Pingレスポンス
        await connection_manager.send_personal_message({
            "type": "pong",
            "timestamp": message.get("timestamp")
        }, user_id)

async def get_user_id_from_token(token: str) -> str:
    """トークンからユーザーIDを取得（簡易実装）"""
    # 実際の実装では、JWTデコードや認証処理を行う
    # 現在は簡易的に固定値を返す
    if token == "test-token":
        return "test-user-id"
    return None

# タスク進捗通知APIエンドポイント
@router.get("/tasks/{task_id}/progress")
async def get_task_progress_api(task_id: str):
    """タスク進捗を取得（REST API）"""
    progress = await task_manager.get_task_progress(task_id)
    if not progress:
        return {"error": "Task not found"}
    
    return progress.to_dict()

@router.get("/tasks")
async def list_tasks_api(status: str = None, limit: int = 20):
    """タスク一覧を取得（REST API）"""
    from app.core.background_tasks import TaskStatus
    
    status_filter = None
    if status:
        try:
            status_filter = TaskStatus(status)
        except ValueError:
            return {"error": f"Invalid status: {status}"}
    
    tasks = await task_manager.list_tasks(status_filter, limit)
    
    return {
        "tasks": [task.to_dict() for task in tasks],
        "total": len(tasks)
    }

@router.post("/tasks/{task_id}/cancel")
async def cancel_task_api(task_id: str):
    """タスクをキャンセル（REST API）"""
    success = await task_manager.cancel_task(task_id)
    if success:
        return {"message": "Task cancelled successfully"}
    else:
        return {"error": "Task not found or already finished"}

@router.delete("/tasks/{task_id}")
async def delete_task_api(task_id: str):
    """タスクを削除（REST API）"""
    # タスクをキャンセルしてから削除
    await task_manager.cancel_task(task_id)
    
    # タスクマネージャーから削除（実装簡略化）
    if task_id in task_manager._tasks:
        del task_manager._tasks[task_id]
        if task_id in task_manager._running_tasks:
            del task_manager._running_tasks[task_id]
        return {"message": "Task deleted successfully"}
    else:
        return {"error": "Task not found"}