from typing import Set, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.article import Article
from app.utils.url_parser import URLParser
from app.utils.web_scraper import WebScraper
from app.services.scraping_service import ScrapingService
from app.core.background_tasks import task_manager, TaskStatus
from app.schemas.scraping import (
    URLParseRequest, URLParseResponse, 
    ScrapingJobRequest, ScrapingJobResponse,
    URLPreviewRequest, URLPreviewResponse,
    ScrapingJobStatus
)

router = APIRouter()

@router.post("/parse-urls", response_model=URLParseResponse)
async def parse_urls(
    request: URLParseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    URLテキストを解析・バリデーション
    スクレイピング実行前の事前チェック
    """
    if not request.urls_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URLテキストが空です"
        )
    
    # URLパース実行
    parse_result = URLParser.parse_urls_from_text(request.urls_text)
    
    if not parse_result.valid_urls:
        return URLParseResponse(
            valid_urls=[],
            invalid_urls=[{"url": item[0], "reason": item[1]} for item in parse_result.invalid_urls],
            duplicate_urls=[],
            summary=parse_result.summary,
            estimated_time="0秒"
        )
    
    # 既存記事との重複チェック
    existing_urls: Set[str] = set(
        row.url for row in db.query(Article.url).all()
    )
    
    new_urls, duplicate_urls = URLParser.check_duplicates_with_existing(
        parse_result.valid_urls, existing_urls
    )
    
    # レスポンス作成
    return URLParseResponse(
        valid_urls=new_urls,
        invalid_urls=[{"url": item[0], "reason": item[1]} for item in parse_result.invalid_urls],
        duplicate_urls=duplicate_urls,
        summary={
            "valid_count": len(new_urls),
            "invalid_count": len(parse_result.invalid_urls),
            "duplicate_count": len(duplicate_urls),
            "total_lines": parse_result.total_input_lines
        },
        estimated_time=URLParser.estimate_processing_time(len(new_urls))
    )

@router.post("/preview", response_model=URLPreviewResponse)
async def preview_url(
    request: URLPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    単一URLのプレビュー取得
    実際のスクレイピングでメタデータを確認
    """
    # URL正規化
    normalized_url = URLParser._normalize_url(request.url)
    if not normalized_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid URL format"
        )
    
    # 重複チェック
    existing_article = db.query(Article).filter(Article.url == normalized_url).first()
    is_duplicate = existing_article is not None
    
    try:
        # 実際のスクレイピングでプレビュー取得
        async with WebScraper(timeout=15) as scraper:  # プレビューは短いタイムアウト
            scraped_content = await scraper.scrape_url(normalized_url)
            
            if scraped_content.error:
                return URLPreviewResponse(
                    url=normalized_url,
                    title=None,
                    description=None,
                    site_name=None,
                    is_duplicate=is_duplicate,
                    estimated_tags=[],
                    error=scraped_content.error
                )
            
            return URLPreviewResponse(
                url=normalized_url,
                title=scraped_content.title,
                description=scraped_content.description,
                site_name=scraped_content.site_name,
                is_duplicate=is_duplicate,
                estimated_tags=scraped_content.auto_tags,
                error=None
            )
            
    except Exception as e:
        return URLPreviewResponse(
            url=normalized_url,
            title=None,
            description=None,
            site_name=None,
            is_duplicate=is_duplicate,
            estimated_tags=[],
            error=f"Preview failed: {str(e)}"
        )

@router.post("/start", response_model=ScrapingJobResponse)
async def start_scraping_job(
    request: ScrapingJobRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    スクレイピングジョブを開始
    非同期バックグラウンド処理で実行
    """
    try:
        scraping_service = ScrapingService(db)
        job = await scraping_service.create_and_start_scraping_job(
            user=current_user,
            urls_text=request.urls_text,
            auto_generate_tags=request.auto_generate_tags,
            skip_duplicates=request.skip_duplicates
        )
        
        # URLパース結果を取得（レスポンス用）
        parse_result = URLParser.parse_urls_from_text(request.urls_text)
        
        # 重複チェック
        if request.skip_duplicates:
            existing_urls: Set[str] = set(
                row.url for row in db.query(Article.url).all()
            )
            new_urls, duplicate_urls = URLParser.check_duplicates_with_existing(
                parse_result.valid_urls, existing_urls
            )
        else:
            new_urls = parse_result.valid_urls
            duplicate_urls = []
        
        return ScrapingJobResponse(
            job_id=str(job.id),
            parsed_urls=new_urls,
            duplicate_urls=duplicate_urls,
            invalid_urls=[{"url": item[0], "reason": item[1]} for item in parse_result.invalid_urls],
            estimated_time=URLParser.estimate_processing_time(len(new_urls))
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create scraping job: {str(e)}"
        )

@router.get("/jobs/{job_id}", response_model=ScrapingJobStatus)
async def get_scraping_job_status(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    スクレイピングジョブの状態確認（タスクマネージャー統合）
    """
    # タスクマネージャーから進捗を取得
    task_progress = await task_manager.get_task_progress(job_id)
    
    if task_progress:
        # タスクマネージャーから詳細情報を取得
        failed_urls = []
        completed_urls = task_progress.progress_details.get('completed_urls', [])
        
        # failed_urls の処理
        failed_url_strings = task_progress.progress_details.get('failed_urls', [])
        for failed_url in failed_url_strings:
            if isinstance(failed_url, str) and ":" in failed_url:
                url, error = failed_url.split(":", 1)
                failed_urls.append({"url": url.strip(), "error": error.strip()})
            else:
                failed_urls.append({"url": str(failed_url), "error": "Unknown error"})
        
        return ScrapingJobStatus(
            id=job_id,
            status=task_progress.status.value,
            progress=task_progress.current,
            total=task_progress.total,
            completed_urls=completed_urls,
            failed_urls=failed_urls,
            skipped_urls=task_progress.progress_details.get('skipped_urls', []),
            created_articles=task_progress.progress_details.get('created_articles', []),
            created_at=task_progress.created_at,
            started_at=task_progress.started_at,
            completed_at=task_progress.completed_at
        )
    else:
        # フォールバック: データベースから取得
        scraping_service = ScrapingService(db)
        job = scraping_service.get_scraping_job(job_id, str(current_user.id))
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scraping job not found"
            )
        
        # failed_urlsを文字列から辞書形式に変換
        failed_urls = []
        for failed_url in (job.failed_urls or []):
            if ":" in failed_url:
                url, error = failed_url.split(":", 1)
                failed_urls.append({"url": url.strip(), "error": error.strip()})
            else:
                failed_urls.append({"url": failed_url, "error": "Unknown error"})
        
        return ScrapingJobStatus(
            id=str(job.id),
            status=job.status,
            progress=job.progress,
            total=job.total,
            completed_urls=job.completed_urls or [],
            failed_urls=failed_urls,
            skipped_urls=job.skipped_urls or [],
            created_articles=job.created_article_ids or [],
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at
        )

@router.get("/jobs", response_model=List[ScrapingJobStatus])
async def list_user_scraping_jobs(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    ユーザーのスクレイピングジョブ一覧
    """
    scraping_service = ScrapingService(db)
    jobs = scraping_service.get_user_scraping_jobs(str(current_user.id), limit, offset)
    
    result = []
    for job in jobs:
        # failed_urlsを文字列から辞書形式に変換
        failed_urls = []
        for failed_url in (job.failed_urls or []):
            if ":" in failed_url:
                url, error = failed_url.split(":", 1)
                failed_urls.append({"url": url.strip(), "error": error.strip()})
            else:
                failed_urls.append({"url": failed_url, "error": "Unknown error"})
        
        result.append(ScrapingJobStatus(
            id=str(job.id),
            status=job.status,
            progress=job.progress,
            total=job.total,
            completed_urls=job.completed_urls or [],
            failed_urls=failed_urls,
            skipped_urls=job.skipped_urls or [],
            created_articles=job.created_article_ids or [],
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at
        ))
    
    return result

@router.delete("/jobs/{job_id}")
async def delete_scraping_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    スクレイピングジョブを削除
    """
    scraping_service = ScrapingService(db)
    success = scraping_service.delete_scraping_job(job_id, str(current_user.id))
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scraping job not found"
        )
    
    return {"message": "Scraping job deleted successfully"}

@router.post("/jobs/{job_id}/cancel")
async def cancel_scraping_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    スクレイピングジョブをキャンセル
    """
    try:
        # タスクマネージャーから直接キャンセル
        success = await task_manager.cancel_task(job_id)
        
        if success:
            # データベースの状態も更新
            scraping_service = ScrapingService(db)
            scraping_service.cancel_scraping_job(job_id, str(current_user.id))
            return {"message": "Scraping job cancelled successfully"}
        else:
            # タスクが見つからない場合、データベースで確認
            scraping_service = ScrapingService(db)
            job = scraping_service.get_scraping_job(job_id, str(current_user.id))
            
            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Scraping job not found"
                )
            
            # 既に完了/キャンセル済みの場合
            if job.status in ['completed', 'cancelled', 'failed']:
                return {"message": f"Job is already {job.status}"}
            
            # データベース上でキャンセル状態に更新
            scraping_service.cancel_scraping_job(job_id, str(current_user.id))
            return {"message": "Scraping job cancelled successfully"}
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel scraping job: {str(e)}"
        )