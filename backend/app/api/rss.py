from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import time, datetime
from pydantic import BaseModel, Field
import os
import tempfile
import logging

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.services.rss_service import RSSService
from app.services.arxiv_service import ArxivService
from app.services.scheduler_service import scheduler_service
from app.core.background_tasks import task_manager

logger = logging.getLogger(__name__)

router = APIRouter()


class RSSFeedURL(BaseModel):
    """RSSフィードURL"""
    url: str = Field(..., description="RSSフィードのURL")


class RSSFeedList(BaseModel):
    """RSSフィードURLリスト"""
    feeds: List[RSSFeedURL] = Field(..., description="RSSフィードURLのリスト")


class ScheduleRequest(BaseModel):
    """スケジュール設定リクエスト"""
    rss_file_path: str = Field(..., description="RSSフィードリストファイルのパス")
    hour: int = Field(..., ge=0, le=23, description="実行時刻（時）")
    minute: int = Field(..., ge=0, le=59, description="実行時刻（分）")
    auto_generate_tags: bool = Field(True, description="自動タグ生成を有効にするか")
    skip_duplicates: bool = Field(True, description="重複記事をスキップするか")
    include_arxiv: bool = Field(False, description="arXiv論文を含めるかどうか")
    arxiv_categories: Optional[List[str]] = Field(None, description="arXiv検索カテゴリ")
    arxiv_max_results: int = Field(20, ge=1, le=100, description="arXivから取得する最大論文数")


class ScheduleUpdateRequest(BaseModel):
    """スケジュール更新リクエスト"""
    hour: Optional[int] = Field(None, ge=0, le=23, description="実行時刻（時）")
    minute: Optional[int] = Field(None, ge=0, le=59, description="実行時刻（分）")
    enabled: Optional[bool] = Field(None, description="スケジュールを有効にするか")
    rss_file_path: Optional[str] = Field(None, description="RSSフィードリストファイルのパス")
    auto_generate_tags: Optional[bool] = Field(None, description="自動タグ生成を有効にするか")
    skip_duplicates: Optional[bool] = Field(None, description="重複記事をスキップするか")
    include_arxiv: Optional[bool] = Field(None, description="arXiv論文を含めるかどうか")
    arxiv_categories: Optional[List[str]] = Field(None, description="arXiv検索カテゴリ")
    arxiv_max_results: Optional[int] = Field(None, ge=1, le=100, description="arXivから取得する最大論文数")


class ManualRSSScrapingRequest(BaseModel):
    """手動RSSスクレイピングリクエスト"""
    rss_file_path: str = Field(..., description="RSSフィードリストファイルのパス")
    auto_generate_tags: bool = Field(True, description="自動タグ生成を有効にするか")
    skip_duplicates: bool = Field(True, description="重複記事をスキップするか")
    include_arxiv: bool = Field(False, description="arXiv論文を含めるかどうか")
    arxiv_categories: Optional[List[str]] = Field(None, description="arXiv検索カテゴリ")
    arxiv_max_results: int = Field(20, ge=0, le=100, description="arXivから取得する最大論文数")
    hours_back: int = Field(24, ge=1, le=168, description="遡る時間（時間、最大7日間）")


class ArxivSearchRequest(BaseModel):
    """arXiv論文検索リクエスト"""
    categories: Optional[List[str]] = Field(None, description="検索カテゴリ（例: ['cs.AI', 'cs.LG']）")
    max_results: int = Field(20, ge=1, le=100, description="最大取得件数")
    days_back: int = Field(3, ge=1, le=30, description="何日前の論文を対象とするか")


@router.post("/feeds/test")
async def test_rss_feeds(
    rss_feeds: RSSFeedList,
    current_user: User = Depends(get_current_user)
):
    """RSSフィードをテスト取得"""
    try:
        feed_urls = [feed.url for feed in rss_feeds.feeds]
        
        async with RSSService() as rss_service:
            results = await rss_service.fetch_multiple_feeds(feed_urls)
        
        # 結果をまとめる
        test_results = []
        total_articles = 0
        
        for result in results:
            article_count = len(result.articles)
            total_articles += article_count
            
            test_results.append({
                "feed_url": result.feed_url,
                "status": "success" if not result.error else "failed",
                "error": result.error,
                "articles_count": article_count,
                "last_updated": result.last_updated.isoformat() if result.last_updated else None,
                "sample_articles": [
                    {
                        "title": article.title,
                        "url": article.url,
                        "published_date": article.published_date.isoformat() if article.published_date else None
                    }
                    for article in result.articles[:3]  # 最初の3件のみ
                ]
            })
        
        return {
            "message": "RSS feeds tested successfully",
            "feeds_tested": len(feed_urls),
            "feeds_success": len([r for r in results if not r.error]),
            "feeds_failed": len([r for r in results if r.error]),
            "total_articles_found": total_articles,
            "results": test_results
        }
        
    except Exception as e:
        logger.exception(f"Failed to test RSS feeds for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test RSS feeds: {str(e)}"
        )


@router.post("/arxiv/search")
async def search_arxiv_papers(
    request: ArxivSearchRequest,
    current_user: User = Depends(get_current_user)
):
    """arXiv論文を検索"""
    try:
        async with ArxivService() as arxiv_service:
            result = await arxiv_service.search_papers(
                categories=request.categories or ['cs.AI', 'cs.LG', 'cs.CV', 'cs.CL'],
                max_results=request.max_results,
                target_date=datetime.now(),
                days_back=request.days_back
            )
            
            if result.error:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"arXiv search failed: {result.error}"
                )
            
            # 結果を辞書形式に変換
            papers_data = arxiv_service.papers_to_paper_info(result.papers)
            
            return {
                "message": "arXiv search completed successfully",
                "total_found": result.total_found,
                "papers_returned": len(result.papers),
                "search_query": result.search_query,
                "target_date": result.target_date.isoformat() if result.target_date else None,
                "papers": papers_data
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to search arXiv papers for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search arXiv papers: {str(e)}"
        )


class RSSTestRequest(BaseModel):
    """RSSテストリクエスト"""
    rss_file_path: str = Field(..., description="RSSフィードリストファイルのパス")
    include_arxiv: bool = Field(False, description="arXiv論文を含めるかどうか")
    arxiv_categories: Optional[List[str]] = Field(None, description="arXiv検索カテゴリ")
    arxiv_max_results: int = Field(20, ge=0, le=100, description="arXivから取得する最大論文数")
    hours_back: int = Field(24, ge=1, le=168, description="遡る時間（時間、最大7日間）")


@router.post("/feeds/from-file")
async def test_rss_feeds_from_file(
    request: RSSTestRequest,
    current_user: User = Depends(get_current_user)
):
    """ファイルからRSSフィードをテスト取得"""
    try:
        if not os.path.exists(request.rss_file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"RSS file not found: {request.rss_file_path}"
            )
        
        async with RSSService(hours_back=request.hours_back) as rss_service:
            if request.include_arxiv:
                article_urls, rss_results, arxiv_papers = await rss_service.get_latest_articles_with_arxiv(
                    request.rss_file_path,
                    include_arxiv=True,
                    arxiv_categories=request.arxiv_categories,
                    arxiv_max_results=request.arxiv_max_results,
                    target_date=datetime.now()
                )
            else:
                article_urls, rss_results = await rss_service.get_latest_articles_from_file(request.rss_file_path)
                arxiv_papers = []
        
        # RSS結果をまとめる
        feed_results = []
        for result in rss_results:
            feed_results.append({
                "feed_url": result.feed_url,
                "status": "success" if not result.error else "failed",
                "error": result.error,
                "articles_count": len(result.articles),
                "last_updated": result.last_updated.isoformat() if result.last_updated else None
            })
        
        response = {
            "message": "RSS feeds from file processed successfully",
            "file_path": request.rss_file_path,
            "feeds_processed": len(rss_results),
            "feeds_success": len([r for r in rss_results if not r.error]),
            "feeds_failed": len([r for r in rss_results if r.error]),
            "unique_article_urls": len(article_urls),
            "feed_results": feed_results,
            "sample_urls": article_urls  # 全件のURL
        }
        
        # arXiv結果を追加
        if request.include_arxiv:
            response["arxiv_enabled"] = True
            response["arxiv_papers_found"] = len(arxiv_papers)
            response["arxiv_papers"] = [
                {
                    "title": paper.title,
                    "url": paper.url,
                    "published_date": paper.published_date.isoformat(),
                    "categories": paper.categories,
                    "authors": paper.authors[:3]  # 最初の3人の著者のみ
                }
                for paper in arxiv_papers[:5]  # 最初の5件のみ
            ]
        else:
            response["arxiv_enabled"] = False
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to test RSS feeds from file for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process RSS feeds from file: {str(e)}"
        )


@router.post("/upload")
async def upload_rss_file(
    file: UploadFile = File(..., description="RSSフィードURLリストファイル"),
    current_user: User = Depends(get_current_user)
):
    """RSSフィードリストファイルをアップロード"""
    try:
        if not file.filename.endswith('.txt'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only .txt files are supported"
            )
        
        # ユーザー専用ディレクトリを作成
        user_dir = f"/tmp/rss_feeds/{current_user.id}"
        os.makedirs(user_dir, exist_ok=True)
        
        # ファイルを保存
        file_path = os.path.join(user_dir, file.filename)
        content = await file.read()
        
        with open(file_path, 'wb') as f:
            f.write(content)
        
        # ファイル内容を検証
        rss_service = RSSService()
        feed_urls = rss_service.read_rss_feeds_from_file(file_path)
        
        return {
            "message": "RSS file uploaded successfully",
            "file_path": file_path,
            "file_name": file.filename,
            "feeds_count": len(feed_urls),
            "feed_urls": feed_urls
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to upload RSS file for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload RSS file: {str(e)}"
        )


@router.post("/scrape/manual")
async def manual_rss_scraping(
    request: ManualRSSScrapingRequest,
    current_user: User = Depends(get_current_user)
):
    """手動でRSSスクレイピングを実行"""
    try:
        if not os.path.exists(request.rss_file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"RSS file not found: {request.rss_file_path}"
            )
        
        # バックグラウンドタスクとして実行
        task_id = await task_manager.create_task(
            _manual_rss_scraping_task,
            current_user.id,
            request.rss_file_path,
            request.auto_generate_tags,
            request.skip_duplicates,
            request.include_arxiv,
            request.arxiv_categories,
            request.arxiv_max_results,
            request.hours_back,
            task_id=f"manual_rss_{current_user.id}_{int(datetime.now().timestamp())}",
            total=100,
            message=f"手動RSSスクレイピング開始（{request.hours_back}時間遡り）: {request.rss_file_path}"
        )
        
        return {
            "message": "Manual RSS scraping started",
            "task_id": task_id,
            "rss_file_path": request.rss_file_path
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to start manual RSS scraping for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start manual RSS scraping: {str(e)}"
        )


async def _manual_rss_scraping_task(
    user_id: str, 
    rss_file_path: str, 
    auto_generate_tags: bool, 
    skip_duplicates: bool,
    include_arxiv: bool,
    arxiv_categories: Optional[List[str]],
    arxiv_max_results: int,
    hours_back: int,
    progress_callback=None
):
    """手動RSSスクレイピングタスク"""
    from app.services.scheduler_service import ScheduleConfig
    from datetime import time
    
    # 一時的なスケジュール設定を作成
    config = ScheduleConfig(
        user_id=user_id,
        rss_file_path=rss_file_path,
        schedule_time=time(0, 0),  # ダミー値
        auto_generate_tags=auto_generate_tags,
        skip_duplicates=skip_duplicates,
        include_arxiv=include_arxiv,
        arxiv_categories=arxiv_categories,
        arxiv_max_results=arxiv_max_results,
        hours_back=hours_back
    )
    
    # スケジューラーサービスのタスクを再利用
    return await scheduler_service._rss_scraping_task(user_id, config, progress_callback)


@router.post("/schedule")
async def create_schedule(
    request: ScheduleRequest,
    current_user: User = Depends(get_current_user)
):
    """定期実行スケジュールを作成"""
    try:
        if not os.path.exists(request.rss_file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"RSS file not found: {request.rss_file_path}"
            )
        
        schedule_time = time(hour=request.hour, minute=request.minute)
        
        success = await scheduler_service.add_schedule(
            user_id=current_user.id,
            rss_file_path=request.rss_file_path,
            schedule_time=schedule_time,
            auto_generate_tags=request.auto_generate_tags,
            skip_duplicates=request.skip_duplicates,
            include_arxiv=request.include_arxiv,
            arxiv_categories=request.arxiv_categories,
            arxiv_max_results=request.arxiv_max_results
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create schedule"
            )
        
        return {
            "message": "Schedule created successfully",
            "user_id": current_user.id,
            "rss_file_path": request.rss_file_path,
            "schedule_time": f"{request.hour:02d}:{request.minute:02d}",
            "auto_generate_tags": request.auto_generate_tags,
            "skip_duplicates": request.skip_duplicates
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to create schedule for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create schedule: {str(e)}"
        )


@router.get("/schedule")
async def get_schedule(
    current_user: User = Depends(get_current_user)
):
    """現在のスケジュール設定を取得"""
    try:
        schedule = await scheduler_service.get_schedule(current_user.id)
        
        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No schedule found for this user"
            )
        
        return {
            "user_id": schedule.user_id,
            "rss_file_path": schedule.rss_file_path,
            "schedule_time": f"{schedule.schedule_time.hour:02d}:{schedule.schedule_time.minute:02d}",
            "enabled": schedule.enabled,
            "auto_generate_tags": schedule.auto_generate_tags,
            "skip_duplicates": schedule.skip_duplicates,
            "include_arxiv": schedule.include_arxiv,
            "arxiv_categories": schedule.arxiv_categories,
            "arxiv_max_results": schedule.arxiv_max_results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get schedule for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get schedule: {str(e)}"
        )


@router.put("/schedule")
async def update_schedule(
    request: ScheduleUpdateRequest,
    current_user: User = Depends(get_current_user)
):
    """スケジュール設定を更新"""
    try:
        schedule_time = None
        if request.hour is not None and request.minute is not None:
            schedule_time = time(hour=request.hour, minute=request.minute)
        
        success = await scheduler_service.update_schedule(
            user_id=current_user.id,
            schedule_time=schedule_time,
            enabled=request.enabled,
            rss_file_path=request.rss_file_path,
            auto_generate_tags=request.auto_generate_tags,
            skip_duplicates=request.skip_duplicates,
            include_arxiv=request.include_arxiv,
            arxiv_categories=request.arxiv_categories,
            arxiv_max_results=request.arxiv_max_results
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No schedule found for this user"
            )
        
        return {"message": "Schedule updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to update schedule for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update schedule: {str(e)}"
        )


@router.delete("/schedule")
async def delete_schedule(
    current_user: User = Depends(get_current_user)
):
    """スケジュールを削除"""
    try:
        success = await scheduler_service.remove_schedule(current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No schedule found for this user"
            )
        
        return {"message": "Schedule deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to delete schedule for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete schedule: {str(e)}"
        )


@router.get("/running-task")
async def get_running_task(
    current_user: User = Depends(get_current_user)
):
    """実行中のRSSスクレイピングタスクを取得"""
    try:
        running_tasks = await scheduler_service.get_running_tasks()
        
        if current_user.id not in running_tasks:
            return {"running": False, "task_id": None}
        
        task_id = running_tasks[current_user.id]
        task_progress = await task_manager.get_task_progress(task_id)
        
        if not task_progress:
            return {"running": False, "task_id": task_id}
        
        return {
            "running": task_progress.is_active,
            "task_id": task_id,
            "progress": task_progress.to_dict()
        }
        
    except Exception as e:
        logger.exception(f"Failed to get running task for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get running task: {str(e)}"
        )


@router.post("/cancel-task")
async def cancel_running_task(
    current_user: User = Depends(get_current_user)
):
    """実行中のRSSスクレイピングタスクをキャンセル"""
    try:
        success = await scheduler_service.cancel_running_task(current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No running task found for this user"
            )
        
        return {"message": "Task cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to cancel task for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel task: {str(e)}"
        )


class AutoScheduleRequest(BaseModel):
    """自動スケジュール設定リクエスト"""
    hour: int = Field(2, ge=0, le=23, description="実行時刻（時）デフォルト深夜2時")
    minute: int = Field(0, ge=0, le=59, description="実行時刻（分）")
    auto_generate_tags: bool = Field(True, description="自動タグ生成を有効にするか")
    skip_duplicates: bool = Field(True, description="重複記事をスキップするか")
    include_arxiv: bool = Field(True, description="arXiv論文を含めるかどうか")
    arxiv_categories: Optional[List[str]] = Field(['cs.AI', 'cs.LG', 'cs.CV'], description="arXiv検索カテゴリ")
    arxiv_max_results: int = Field(50, ge=10, le=100, description="arXivから取得する最大論文数")


@router.post("/auto-schedule")
async def setup_auto_schedule(
    request: AutoScheduleRequest,
    current_user: User = Depends(get_current_user)
):
    """自動スケジュールを設定（深夜帯にRSS+arXiv→スクレイピング実行）"""
    try:
        schedule_time = time(hour=request.hour, minute=request.minute)
        
        success = await scheduler_service.create_auto_schedule_for_user(
            user_id=current_user.id,
            schedule_time=schedule_time,
            auto_generate_tags=request.auto_generate_tags,
            skip_duplicates=request.skip_duplicates,
            include_arxiv=request.include_arxiv,
            arxiv_categories=request.arxiv_categories,
            arxiv_max_results=request.arxiv_max_results
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create auto schedule"
            )
        
        return {
            "message": "Auto schedule created successfully",
            "schedule_time": f"{request.hour:02d}:{request.minute:02d}",
            "description": "RSS+arXiv取得→解析→スクレイピングを毎日自動実行します"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to setup auto schedule for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to setup auto schedule: {str(e)}"
        )


class RSSFeedFileContent(BaseModel):
    """RSSフィードファイルの内容"""
    content: str = Field(..., description="RSSフィードファイルの内容")
    file_path: str = Field(..., description="ファイルパス")


@router.get("/feeds/file")
async def get_rss_feeds_file(
    current_user: User = Depends(get_current_user)
):
    """RSSフィードファイルの内容を取得"""
    try:
        file_path = '/Users/tsutsuikana/Desktop/coding_workspace/news_check_app/backend/rss_feeds.txt'
        
        if not os.path.exists(file_path):
            # ファイルが存在しない場合はデフォルト内容で作成
            default_content = """# ITニュース RSS フィードリスト
# このファイルは、定期的にチェックするRSSフィードのURLを記載するサンプルです
# '#' で始まる行はコメントとして無視されます
# 空行も無視されます

https://gigazine.net/news/rss_2.0/
https://www.watch.impress.co.jp/data/rss/1.0/ipw/feed.rdf
https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml
https://b.hatena.ne.jp/hotentry/it.rss
https://news.mit.edu/topic/mitartificial-intelligence2-rss.xml
https://bair.berkeley.edu/blog/feed.xml
https://openai.com/blog/rss
https://blog.tensorflow.org/feeds/posts/default
https://deepmind.google/blog/rss.xml
https://huggingface.co/blog/feed.xml
https://blog.research.google/atom.xml
https://news.microsoft.com/ja-jp/category/blog/feed
"""
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(default_content)
        
        # ファイル内容を読み込み
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return {
            "content": content,
            "file_path": file_path,
            "message": "RSS feeds file loaded successfully"
        }
        
    except Exception as e:
        logger.exception(f"Failed to load RSS feeds file for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load RSS feeds file: {str(e)}"
        )


@router.put("/feeds/file")
async def update_rss_feeds_file(
    request: RSSFeedFileContent,
    current_user: User = Depends(get_current_user)
):
    """RSSフィードファイルの内容を更新"""
    try:
        file_path = request.file_path
        
        # ファイルパスの安全性チェック
        if not file_path.endswith('rss_feeds.txt'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file path"
            )
        
        # バックアップを作成
        backup_path = f"{file_path}.backup"
        if os.path.exists(file_path):
            import shutil
            shutil.copy2(file_path, backup_path)
        
        # ファイル内容を保存
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(request.content)
        
        # 内容を検証（有効なURLが含まれているかチェック）
        rss_service = RSSService()
        try:
            feed_urls = rss_service.read_rss_feeds_from_file(file_path)
            feeds_count = len(feed_urls)
        except Exception as e:
            # 検証に失敗した場合はバックアップから復元
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, file_path)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid RSS feeds file format: {str(e)}"
            )
        
        return {
            "message": "RSS feeds file updated successfully",
            "file_path": file_path,
            "feeds_count": feeds_count,
            "backup_created": backup_path
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to update RSS feeds file for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update RSS feeds file: {str(e)}"
        )