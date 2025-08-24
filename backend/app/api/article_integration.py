from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.services.article_integration_service import ArticleIntegrationService

router = APIRouter()

class BulkTagRequest(BaseModel):
    """一括タグ操作リクエスト"""
    article_ids: List[str]
    tags_to_add: List[str] = []
    tags_to_remove: List[str] = []

class BulkTagResponse(BaseModel):
    """一括タグ操作レスポンス"""
    updated: int
    failed: int
    message: str

class MergeArticlesRequest(BaseModel):
    """記事マージリクエスト"""
    primary_article_id: str
    duplicate_article_ids: List[str]

class MergeArticlesResponse(BaseModel):
    """記事マージレスポンス"""
    merged_articles: List[Dict]
    deleted_articles: List[str]
    updated_fields: List[str]
    message: str

@router.post("/bulk-tag", response_model=BulkTagResponse)
async def bulk_tag_articles(
    request: BulkTagRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    記事の一括タグ操作
    """
    if not request.article_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No article IDs provided"
        )
    
    if not request.tags_to_add and not request.tags_to_remove:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No tag operations specified"
        )
    
    try:
        integration_service = ArticleIntegrationService(db)
        result = await integration_service.bulk_tag_articles(
            request.article_ids,
            request.tags_to_add,
            request.tags_to_remove
        )
        
        message = f"タグ操作完了: {result['updated']}件更新"
        if result['failed'] > 0:
            message += f", {result['failed']}件失敗"
        
        return BulkTagResponse(
            updated=result["updated"],
            failed=result["failed"],
            message=message
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk tag operation failed: {str(e)}"
        )

@router.post("/merge-articles", response_model=MergeArticlesResponse)
async def merge_duplicate_articles(
    request: MergeArticlesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    重複記事のマージ
    """
    if not request.duplicate_article_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No duplicate article IDs provided"
        )
    
    try:
        integration_service = ArticleIntegrationService(db)
        result = await integration_service.merge_duplicate_articles(
            request.primary_article_id,
            request.duplicate_article_ids
        )
        
        message = f"記事マージ完了: {len(result['merged_articles'])}件マージ、{len(result['deleted_articles'])}件削除"
        
        return MergeArticlesResponse(
            merged_articles=result["merged_articles"],
            deleted_articles=result["deleted_articles"],
            updated_fields=result["updated_fields"],
            message=message
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Article merge failed: {str(e)}"
        )

@router.get("/duplicates")
async def find_duplicate_articles(
    similarity_threshold: float = 0.8,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    重複記事の検出
    """
    try:
        # 簡易的な重複検出（URL、タイトルベース）
        from app.models.article import Article
        from sqlalchemy import func
        
        # URL重複
        url_duplicates = db.query(
            Article.url,
            func.count(Article.id).label('count'),
            func.array_agg(Article.id).label('article_ids')
        ).group_by(Article.url).having(func.count(Article.id) > 1).limit(limit).all()
        
        # タイトル重複（完全一致）
        title_duplicates = db.query(
            Article.title,
            func.count(Article.id).label('count'),
            func.array_agg(Article.id).label('article_ids')
        ).filter(
            Article.title.isnot(None)
        ).group_by(Article.title).having(func.count(Article.id) > 1).limit(limit).all()
        
        return {
            "url_duplicates": [
                {
                    "url": dup.url,
                    "count": dup.count,
                    "article_ids": [str(id) for id in dup.article_ids]
                }
                for dup in url_duplicates
            ],
            "title_duplicates": [
                {
                    "title": dup.title,
                    "count": dup.count,
                    "article_ids": [str(id) for id in dup.article_ids]
                }
                for dup in title_duplicates
            ],
            "total_url_duplicates": len(url_duplicates),
            "total_title_duplicates": len(title_duplicates)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Duplicate detection failed: {str(e)}"
        )

@router.get("/statistics")
async def get_integration_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    記事統合統計情報
    """
    try:
        from app.models.article import Article
        from app.models.scraping_job import ScrapingJob
        from sqlalchemy import func
        
        # 基本統計
        total_articles = db.query(func.count(Article.id)).scalar()
        
        # タグ統計
        tag_stats = db.query(
            func.unnest(Article.tags).label('tag'),
            func.count().label('count')
        ).filter(
            Article.tags.isnot(None)
        ).group_by(
            func.unnest(Article.tags)
        ).order_by(
            func.count().desc()
        ).limit(20).all()
        
        # ソース統計
        source_stats = db.query(
            Article.source,
            func.count(Article.id).label('count')
        ).filter(
            Article.source.isnot(None)
        ).group_by(Article.source).order_by(
            func.count(Article.id).desc()
        ).limit(10).all()
        
        # スクレイピングジョブ統計
        job_stats = db.query(
            ScrapingJob.status,
            func.count(ScrapingJob.id).label('count')
        ).group_by(ScrapingJob.status).all()
        
        return {
            "total_articles": total_articles,
            "top_tags": [
                {"tag": stat.tag, "count": stat.count}
                for stat in tag_stats
            ],
            "top_sources": [
                {"source": stat.source, "count": stat.count}
                for stat in source_stats
            ],
            "scraping_jobs": [
                {"status": stat.status, "count": stat.count}
                for stat in job_stats
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Statistics generation failed: {str(e)}"
        )