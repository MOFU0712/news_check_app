from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import tempfile
import zipfile
import os
import re
import urllib.parse
from datetime import datetime
from app.db.database import get_db
from app.core.deps import get_current_user, get_current_admin_user
from app.models.user import User
from app.services.article_service import ArticleService
from app.schemas.article import (
    ArticleCreate, ArticleUpdate, ArticleResponse, ArticleListResponse,
    ArticleSearchRequest, FavoriteToggleRequest, FavoriteResponse
)

router = APIRouter()

@router.get("/", response_model=ArticleListResponse)
async def list_articles(
    query: str = Query(None, description="検索クエリ"),
    search_mode: str = Query("and", description="検索モード: 'and' または 'or'"),
    tags: List[str] = Query(default=[], description="タグフィルター"),
    source: str = Query(None, description="ソースフィルター"),
    start_date: Optional[datetime] = Query(None, description="開始日時"),
    end_date: Optional[datetime] = Query(None, description="終了日時"),
    favorites_only: bool = Query(False, description="お気に入りのみ"),
    page: int = Query(1, ge=1, description="ページ番号"),
    limit: int = Query(20, ge=1, le=100, description="1ページあたりの件数"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """記事一覧取得（検索・フィルタリング・ページネーション対応）"""
    print(f"Articles API called by user: {current_user.email} (ID: {current_user.id})")
    print(f"User is_admin: {current_user.is_admin}, is_active: {current_user.is_active}")
    search_params = ArticleSearchRequest(
        query=query,
        search_mode=search_mode,
        tags=tags,
        source=source,
        start_date=start_date,
        end_date=end_date,
        favorites_only=favorites_only,
        page=page,
        limit=limit
    )
    
    articles, total = ArticleService.get_articles(db, search_params, current_user)
    
    # お気に入り状態を追加
    article_responses = []
    for article in articles:
        is_fav = ArticleService.is_favorite(db, article.id, current_user.id)
        article_dict = {
            "id": str(article.id),
            "title": article.title,
            "url": article.url,
            "content": article.content,
            "source": article.source,
            "published_date": article.published_date,
            "scraped_date": article.scraped_date,
            "tags": article.tags or [],
            "summary": article.summary,
            "created_by": str(article.created_by) if article.created_by else None,
            "created_at": article.created_at,
            "updated_at": article.updated_at,
            "is_favorite": is_fav
        }
        article_responses.append(ArticleResponse(**article_dict))
    
    return ArticleListResponse(
        articles=article_responses,
        total=total,
        page=page,
        limit=limit,
        has_next=(page * limit) < total,
        has_prev=page > 1
    )

@router.get("/tags")
async def get_available_tags(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """利用可能なタグ一覧を取得"""
    tags = ArticleService.get_all_tags(db)
    return {"tags": tags}

@router.get("/stats/overview")
async def get_article_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """記事統計情報取得"""
    stats = ArticleService.get_article_stats(db)
    return stats

@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(
    article_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """記事詳細取得"""
    article = ArticleService.get_article(db, article_id, current_user)
    is_fav = ArticleService.is_favorite(db, article.id, current_user.id)
    
    article_dict = {
        "id": str(article.id),
        "title": article.title,
        "url": article.url,
        "content": article.content,
        "source": article.source,
        "published_date": article.published_date,
        "scraped_date": article.scraped_date,
        "tags": article.tags or [],
        "summary": article.summary,
        "created_by": str(article.created_by) if article.created_by else None,
        "created_at": article.created_at,
        "updated_at": article.updated_at,
        "is_favorite": is_fav
    }
    
    return ArticleResponse(**article_dict)

@router.post("/", response_model=ArticleResponse, status_code=status.HTTP_201_CREATED)
async def create_article(
    article_data: ArticleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """記事作成（手動登録用）"""
    article = ArticleService.create_article(db, article_data, current_user)
    
    article_dict = {
        "id": str(article.id),
        "title": article.title,
        "url": article.url,
        "content": article.content,
        "source": article.source,
        "published_date": article.published_date,
        "scraped_date": article.scraped_date,
        "tags": article.tags or [],
        "summary": article.summary,
        "created_by": str(article.created_by) if article.created_by else None,
        "created_at": article.created_at,
        "updated_at": article.updated_at,
        "is_favorite": False
    }
    
    return ArticleResponse(**article_dict)

@router.put("/{article_id}", response_model=ArticleResponse)
async def update_article(
    article_id: str,
    article_data: ArticleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """記事更新（作成者または管理者のみ）"""
    print(f"記事更新開始 - ID: {article_id}")
    print(f"更新データ: {article_data.model_dump(exclude_unset=True)}")
    print(f"ユーザー: {current_user.email} (admin: {current_user.is_admin})")
    
    try:
        article = ArticleService.update_article(db, article_id, article_data, current_user)
        is_fav = ArticleService.is_favorite(db, article.id, current_user.id)
        print(f"記事更新成功 - ID: {article_id}")
    except Exception as e:
        print(f"記事更新エラー詳細: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise
    
    article_dict = {
        "id": str(article.id),
        "title": article.title,
        "url": article.url,
        "content": article.content,
        "source": article.source,
        "published_date": article.published_date,
        "scraped_date": article.scraped_date,
        "tags": article.tags or [],
        "summary": article.summary,
        "created_by": str(article.created_by) if article.created_by else None,
        "created_at": article.created_at,
        "updated_at": article.updated_at,
        "is_favorite": is_fav
    }
    
    return ArticleResponse(**article_dict)

@router.delete("/{article_id}")
async def delete_article(
    article_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """記事削除（作成者または管理者のみ）"""
    ArticleService.delete_article(db, article_id, current_user)
    return {"message": "記事を削除しました"}

@router.post("/{article_id}/regenerate-summary")
async def regenerate_article_summary(
    article_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """記事の要約をLLMで再生成（管理者のみ）"""
    from app.services.llm_service import llm_service
    
    print(f"要約再生成開始 - 記事ID: {article_id}, ユーザー: {current_user.email}")
    
    try:
        # 記事を取得
        article = ArticleService.get_article(db, article_id, current_user)
        
        # LLMサービスが利用可能かチェック
        if not llm_service.is_available():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LLMサービスが利用できません。APIキーを確認してください。"
            )
        
        # タイトルと内容が両方空の場合はエラー
        if not article.title and not article.content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="記事にタイトルと内容がないため、要約を生成できません。"
            )
        
        # LLMで要約生成
        new_summary = await llm_service.generate_news_summary(
            title=article.title or "",
            content=article.content or ""
        )
        
        if not new_summary or not new_summary.strip():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="要約の生成に失敗しました。"
            )
        
        # 要約を更新
        article.summary = new_summary.strip()
        db.commit()
        db.refresh(article)
        
        print(f"要約再生成成功 - 記事ID: {article_id}, 新要約長: {len(new_summary)}文字")
        
        return {
            "message": "要約を再生成しました",
            "summary": new_summary.strip()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"要約再生成エラー - 記事ID: {article_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"要約の再生成に失敗しました: {str(e)}"
        )

@router.post("/favorites", response_model=FavoriteResponse)
async def toggle_favorite(
    request: FavoriteToggleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """お気に入りの切り替え"""
    is_favorite, message = ArticleService.toggle_favorite(db, request.article_id, current_user)
    
    return FavoriteResponse(
        article_id=request.article_id,
        is_favorite=is_favorite,
        message=message
    )

# エクスポート用のスキーマ
class ArticleExportRequest(BaseModel):
    article_ids: List[str]

@router.get("/{article_id}/export/markdown")
async def export_article_as_markdown(
    article_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """単一記事をMarkdown形式でエクスポート"""
    try:
        article = ArticleService.get_article(db, article_id, current_user)
        
        # ファイル名を生成（日本語文字を安全な形式に変換）
        safe_title = re.sub(r'[^\w\-_\.]', '_', article.title or "article")
        filename = f"{safe_title}_{article.published_date.strftime('%Y%m%d_%H%M%S')}.md"
        encoded_filename = urllib.parse.quote(filename)
        
        # Markdownコンテンツを準備
        markdown_content = f"""# {article.title}

**URL**: {article.url}  
**ソース**: {article.source or "不明"}  
**公開日**: {article.published_date.strftime('%Y年%m月%d日') if article.published_date else "不明"}  
**取得日**: {article.published_date.strftime('%Y年%m月%d日 %H:%M:%S')}

"""
        
        # タグがある場合は追加
        if article.tags:
            markdown_content += f"**タグ**: {', '.join(article.tags)}\n\n"
        
        markdown_content += "---\n\n"
        
        # 要約がある場合は追加
        if article.summary:
            markdown_content += f"## 要約\n\n{article.summary}\n\n---\n\n"
        
        # 記事内容
        markdown_content += f"## 記事内容\n\n{article.content or 'コンテンツが取得できませんでした'}\n\n"
        
        markdown_content += "---\n\n*この記事はNews Check Appで取得されました*\n"
        
        return Response(
            content=markdown_content.encode('utf-8'),
            media_type="text/markdown",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
                "Content-Type": "text/markdown; charset=utf-8"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"エクスポートに失敗しました: {str(e)}")

@router.post("/export/markdown/bulk")
async def export_multiple_articles_as_markdown(
    request: ArticleExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """複数記事をZIP形式でエクスポート"""
    try:
        # 一時ファイルを作成
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, "articles.zip")
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for article_id in request.article_ids:
                try:
                    article = ArticleService.get_article(db, article_id, current_user)
                    
                    # ファイル名を生成
                    safe_title = re.sub(r'[^\w\-_\.]', '_', article.title or "article")
                    filename = f"{safe_title}_{article.published_date.strftime('%Y%m%d_%H%M%S')}.md"
                    
                    # Markdownコンテンツを準備
                    markdown_content = f"""# {article.title}

**URL**: {article.url}  
**ソース**: {article.source or "不明"}  
**公開日**: {article.published_date.strftime('%Y年%m月%d日') if article.published_date else "不明"}  
**取得日**: {article.published_date.strftime('%Y年%m月%d日 %H:%M:%S')}

"""
                    
                    # タグがある場合は追加
                    if article.tags:
                        markdown_content += f"**タグ**: {', '.join(article.tags)}\n\n"
                    
                    markdown_content += "---\n\n"
                    
                    # 要約がある場合は追加
                    if article.summary:
                        markdown_content += f"## 要約\n\n{article.summary}\n\n---\n\n"
                    
                    # 記事内容
                    markdown_content += f"## 記事内容\n\n{article.content or 'コンテンツが取得できませんでした'}\n\n"
                    
                    markdown_content += "---\n\n*この記事はNews Check Appで取得されました*\n"
                    
                    # ZIPファイルに追加
                    zip_file.writestr(filename, markdown_content.encode('utf-8'))
                    
                except Exception as e:
                    # 個別の記事でエラーが発生した場合はスキップ
                    print(f"Failed to export article {article_id}: {e}")
                    continue
        
        # ZIPファイルを読み込み
        with open(zip_path, 'rb') as zip_file:
            zip_content = zip_file.read()
        
        # 一時ファイルをクリーンアップ
        os.unlink(zip_path)
        os.rmdir(temp_dir)
        
        return Response(
            content=zip_content,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=articles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"一括エクスポートに失敗しました: {str(e)}")

