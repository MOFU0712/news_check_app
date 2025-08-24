from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
import csv
import io
from fastapi.responses import StreamingResponse, Response

from app.db.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.saved_report import SavedReport
from app.models.article import Article
from app.models.prompt import PromptTemplate
from app.services.report_service import ReportService
from sqlalchemy import or_, and_
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# スキーマ定義
class ReportRequest(BaseModel):
    report_type: str  # "summary", "tag_analysis", "source_analysis", "trend_analysis"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    tags: Optional[List[str]] = None
    sources: Optional[List[str]] = None

class ReportResponse(BaseModel):
    report_type: str
    generated_at: datetime
    data: Dict[str, Any]
    summary: str

class SavedReportResponse(BaseModel):
    id: str
    title: str
    report_type: str
    content: str
    summary: Optional[str]
    tags: Optional[List[str]]
    created_at: datetime
    updated_at: datetime
    
class SavedReportCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    report_type: str = Field(..., min_length=1, max_length=50)
    summary: Optional[str] = Field(None, max_length=500)
    tags: Optional[List[str]] = Field(default=[])
    save_as_blog: bool = True

class SavedReportUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    tags: Optional[List[str]] = None

@router.post("/generate", response_model=ReportResponse)
async def generate_report(
    request: ReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """レポートを生成"""
    try:
        report_service = ReportService(db)
        report_data = await report_service.generate_report(
            report_type=request.report_type,
            start_date=request.start_date,
            end_date=request.end_date,
            tags=request.tags,
            sources=request.sources,
            user=current_user
        )
        
        return ReportResponse(
            report_type=request.report_type,
            generated_at=datetime.utcnow(),
            data=report_data["data"],
            summary=report_data["summary"]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"レポート生成に失敗しました: {str(e)}")

@router.get("/export/csv")
async def export_articles_csv(
    query: Optional[str] = Query(None),
    tags: Optional[List[str]] = Query(default=[]),
    source: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """記事データをCSVでエクスポート"""
    try:
        report_service = ReportService(db)
        csv_data = await report_service.export_articles_csv(
            query=query,
            tags=tags,
            source=source,
            start_date=start_date,
            end_date=end_date,
            user=current_user
        )
        
        output = io.StringIO()
        output.write(csv_data)
        output.seek(0)
        
        response = StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),  # BOM付きUTF-8
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=articles_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CSVエクスポートに失敗しました: {str(e)}")

@router.get("/analytics/overview")
async def get_analytics_overview(
    days: int = Query(30, ge=7, le=365, description="分析期間（日数）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """記事分析の概要を取得"""
    try:
        report_service = ReportService(db)
        analytics = await report_service.get_analytics_overview(days=days, user=current_user)
        return analytics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析データの取得に失敗しました: {str(e)}")

@router.get("/trends/tags")
async def get_tag_trends(
    days: int = Query(30, ge=7, le=365),
    limit: int = Query(20, ge=5, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """タグのトレンド分析"""
    try:
        report_service = ReportService(db)
        trends = await report_service.get_tag_trends(days=days, limit=limit, user=current_user)
        return trends
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"タグトレンド分析に失敗しました: {str(e)}")

@router.get("/trends/sources")
async def get_source_trends(
    days: int = Query(30, ge=7, le=365),
    limit: int = Query(20, ge=5, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """ソースのトレンド分析"""
    try:
        report_service = ReportService(db)
        trends = await report_service.get_source_trends(days=days, limit=limit, user=current_user)
        return trends
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ソーストレンド分析に失敗しました: {str(e)}")

class GenerateAndSaveRequest(BaseModel):
    report_type: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    tags: Optional[List[str]] = None
    sources: Optional[List[str]] = None
    title: str
    save_as_blog: bool = True
    prompt_template_id: Optional[str] = None

@router.post("/generate-and-save", response_model=SavedReportResponse)
async def generate_and_save_report(
    request: GenerateAndSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """レポートを生成してブログ記事として保存"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Starting generate-and-save for user {current_user.email} (ID: {current_user.id})")
    logger.info(f"Request data: report_type={request.report_type}, title={request.title}, template_id={request.prompt_template_id}")
    logger.info(f"Current user ID type: {type(current_user.id)}")
    
    try:
        report_service = ReportService(db)
        
        # レポート生成
        report_data = await report_service.generate_report(
            report_type=request.report_type,
            start_date=request.start_date,
            end_date=request.end_date,
            tags=request.tags,
            sources=request.sources,
            user=current_user
        )
        
        logger.info("Report data generated successfully")
        
        # ブログ記事生成
        logger.info(f"Generating blog content with template_id: {request.prompt_template_id}")
        blog_content = await report_service.generate_blog_report(
            report_type=request.report_type,
            report_data=report_data,
            summary=report_data["summary"],
            title=request.title,
            user=current_user,
            prompt_template_id=request.prompt_template_id
        )
        
        logger.info("Blog content generated successfully")
        
        # レポート保存
        saved_report = await report_service.save_report(
            title=request.title,
            report_type=request.report_type,
            content=blog_content,
            parameters={
                "start_date": request.start_date,
                "end_date": request.end_date,
                "tags": request.tags,
                "sources": request.sources
            },
            raw_data=report_data,
            summary=report_data["summary"],
            tags=request.tags,
            user=current_user
        )
        
        return SavedReportResponse(
            id=str(saved_report.id),
            title=saved_report.title,
            report_type=saved_report.report_type,
            content=saved_report.content,
            summary=saved_report.summary,
            tags=saved_report.tags,
            created_at=saved_report.created_at,
            updated_at=saved_report.updated_at
        )
        
    except Exception as e:
        logger.error(f"Error in generate-and-save: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"レポート生成・保存に失敗しました: {str(e)}")

@router.post("/saved", response_model=SavedReportResponse)
async def save_report(
    request: SavedReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """レポートを保存"""
    try:
        report_service = ReportService(db)
        
        saved_report = await report_service.save_report(
            title=request.title,
            content=request.content,
            report_type=request.report_type,
            summary=request.summary,
            tags=request.tags or [],
            user=current_user
        )
        
        return SavedReportResponse(
            id=str(saved_report.id),
            title=saved_report.title,
            report_type=saved_report.report_type,
            content=saved_report.content,
            summary=saved_report.summary,
            tags=saved_report.tags,
            created_at=saved_report.created_at,
            updated_at=saved_report.updated_at
        )
        
    except Exception as e:
        logger.error(f"Error saving report: {e}")
        raise HTTPException(status_code=500, detail=f"レポートの保存に失敗しました: {str(e)}")

@router.get("/saved", response_model=List[SavedReportResponse])
async def get_saved_reports(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """保存されたレポート一覧を取得"""
    try:
        report_service = ReportService(db)
        reports = report_service.get_saved_reports(user=current_user, limit=limit, offset=offset)
        
        return [
            SavedReportResponse(
                id=str(report.id),
                title=report.title,
                report_type=report.report_type,
                content=report.content,
                summary=report.summary,
                tags=report.tags,
                created_at=report.created_at,
                updated_at=report.updated_at
            )
            for report in reports
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存されたレポートの取得に失敗しました: {str(e)}")

@router.get("/saved/{report_id}", response_model=SavedReportResponse)
async def get_saved_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """特定の保存されたレポートを取得"""
    try:
        report_service = ReportService(db)
        report = report_service.get_saved_report(report_id, user=current_user)
        
        if not report:
            raise HTTPException(status_code=404, detail="レポートが見つかりません")
        
        return SavedReportResponse(
            id=str(report.id),
            title=report.title,
            report_type=report.report_type,
            content=report.content,
            summary=report.summary,
            tags=report.tags,
            created_at=report.created_at,
            updated_at=report.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"レポートの取得に失敗しました: {str(e)}")

@router.put("/saved/{report_id}", response_model=SavedReportResponse)
async def update_saved_report(
    report_id: str,
    update_data: SavedReportUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """保存されたレポートを更新"""
    try:
        report_service = ReportService(db)
        updates = update_data.model_dump(exclude_unset=True)
        
        report = report_service.update_saved_report(report_id, updates, user=current_user)
        
        if not report:
            raise HTTPException(status_code=404, detail="レポートが見つかりません")
        
        return SavedReportResponse(
            id=str(report.id),
            title=report.title,
            report_type=report.report_type,
            content=report.content,
            summary=report.summary,
            tags=report.tags,
            created_at=report.created_at,
            updated_at=report.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"レポートの更新に失敗しました: {str(e)}")

@router.delete("/saved/{report_id}")
async def delete_saved_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """保存されたレポートを削除"""
    try:
        report_service = ReportService(db)
        success = report_service.delete_saved_report(report_id, user=current_user)
        
        if not success:
            raise HTTPException(status_code=404, detail="レポートが見つかりません")
        
        return {"message": "レポートを削除しました"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"レポートの削除に失敗しました: {str(e)}")

@router.get("/saved/{report_id}/export/markdown")
async def export_report_as_markdown(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """保存されたレポートをMarkdown形式でエクスポート"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Starting export for report_id: {report_id}, user: {current_user.email}")
        
        report_service = ReportService(db)
        report = report_service.get_saved_report(report_id, user=current_user)
        
        if not report:
            logger.warning(f"Report not found: {report_id}")
            raise HTTPException(status_code=404, detail="レポートが見つかりません")
        
        logger.info(f"Found report: {report.title}")
        
        # ファイル名を生成（日本語文字を安全な形式に変換）
        import re
        import urllib.parse
        safe_title = re.sub(r'[^\w\-_\.]', '_', report.title or "report")
        filename = f"{safe_title}_{report.created_at.strftime('%Y%m%d_%H%M%S')}.md"
        encoded_filename = urllib.parse.quote(filename)
        
        logger.info(f"Generated filename: {filename}")
        
        # Markdownコンテンツを準備
        markdown_content = f"""# {report.title}

**生成日時**: {report.created_at.strftime('%Y年%m月%d日 %H:%M:%S')}  
**レポートタイプ**: {report.report_type}  
**最終更新**: {report.updated_at.strftime('%Y年%m月%d日 %H:%M:%S')}

---

{report.content or "コンテンツがありません"}

---

*このレポートはNews Check Appで生成されました*
"""
        
        logger.info(f"Markdown content length: {len(markdown_content)}")
        
        return Response(
            content=markdown_content.encode('utf-8'),
            media_type="text/markdown",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
                "Content-Type": "text/markdown; charset=utf-8"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Export error for report {report_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"エクスポートに失敗しました: {str(e)}")

@router.post("/export/markdown/bulk")
async def export_multiple_reports_as_markdown(
    report_ids: List[str],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """複数の保存されたレポートをZIP形式でエクスポート"""
    try:
        import zipfile
        import tempfile
        import os
        
        report_service = ReportService(db)
        
        # 一時ファイルを作成
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, "reports.zip")
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for report_id in report_ids:
                report = report_service.get_saved_report(report_id, user=current_user)
                
                if report:
                    # ファイル名を生成
                    import re
                    safe_title = re.sub(r'[^\w\-_\.]', '_', report.title or "report")
                    filename = f"{safe_title}_{report.created_at.strftime('%Y%m%d_%H%M%S')}.md"
                    
                    # Markdownコンテンツを準備
                    markdown_content = f"""# {report.title}

**生成日時**: {report.created_at.strftime('%Y年%m月%d日 %H:%M:%S')}  
**レポートタイプ**: {report.report_type}  
**最終更新**: {report.updated_at.strftime('%Y年%m月%d日 %H:%M:%S')}

---

{report.content or "コンテンツがありません"}

---

*このレポートはNews Check Appで生成されました*
"""
                    
                    # ZIPファイルに追加
                    zip_file.writestr(filename, markdown_content.encode('utf-8'))
        
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
                "Content-Disposition": f"attachment; filename=reports_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"一括エクスポートに失敗しました: {str(e)}")

# 技術まとめレポート用のスキーマ
class TechnicalReportRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=100, description="検索キーワード")
    start_date: Optional[datetime] = Field(None, description="開始日")
    end_date: Optional[datetime] = Field(None, description="終了日")
    max_articles: int = Field(20, ge=1, le=100, description="最大記事数")
    template_id: Optional[str] = Field(None, description="カスタムプロンプトテンプレートID")

class TechnicalReportResponse(BaseModel):
    keyword: str
    content: str
    articles_count: int
    generated_at: datetime

@router.post("/technical-summary", response_model=TechnicalReportResponse)
async def generate_technical_summary(
    request: TechnicalReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """特定のキーワードの技術まとめレポートを生成"""
    try:
        report_service = ReportService(db)
        
        # 日付範囲の処理
        date_range = None
        if request.start_date and request.end_date:
            # 終了日は23:59:59に設定
            end_date_with_time = request.end_date.replace(hour=23, minute=59, second=59)
            date_range = (request.start_date, end_date_with_time)
        
        # カスタムテンプレートの取得
        custom_template = None
        if request.template_id:
            custom_template = db.query(PromptTemplate).filter(
                PromptTemplate.id == request.template_id
            ).first()
        
        # レポート生成
        content = await report_service.generate_technical_summary_report(
            keyword=request.keyword,
            date_range=date_range,
            max_articles=request.max_articles,
            custom_template=custom_template
        )
        
        # 記事数を取得（レポート生成と同じ条件で、max_articles制限も適用）
        query = db.query(Article).filter(
            or_(
                Article.title.ilike(f"%{request.keyword}%"),
                Article.content.ilike(f"%{request.keyword}%"),
                Article.summary.ilike(f"%{request.keyword}%"),
                Article.tags.op('LIKE')(f'%{request.keyword}%')  # SQLite用のJSON検索
            )
        )
        
        if date_range:
            start_date, end_date = date_range
            query = query.filter(
                and_(
                    Article.scraped_date >= start_date,
                    Article.scraped_date <= end_date
                )
            )
        
        # 新しい順でソートし、max_articles制限を適用して実際に使用された記事数を取得
        articles_count = min(query.count(), request.max_articles)
        
        return TechnicalReportResponse(
            keyword=request.keyword,
            content=content,
            articles_count=articles_count,
            generated_at=datetime.now(timezone.utc)
        )
        
    except Exception as e:
        logger.error(f"Error generating technical summary: {e}")
        raise HTTPException(status_code=500, detail=f"技術まとめレポートの生成に失敗しました: {str(e)}")

@router.post("/technical-summary/save")
async def generate_and_save_technical_summary(
    request: TechnicalReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """技術まとめレポートを生成して保存"""
    try:
        report_service = ReportService(db)
        
        # レポート生成
        report_response = await generate_technical_summary(request, db, current_user)
        
        # レポートを保存
        saved_report = await report_service.save_report(
            title=f"技術まとめ: {request.keyword}",
            content=report_response.content,
            report_type="technical_summary",
            summary=f"「{request.keyword}」に関する技術まとめレポート（{report_response.articles_count}件の記事を分析）",
            tags=[request.keyword, "技術まとめ", "technical_summary"],
            user=current_user
        )
        
        return {
            "message": "技術まとめレポートを生成・保存しました",
            "report": {
                "id": str(saved_report.id),
                "title": saved_report.title,
                "summary": saved_report.summary,
                "created_at": saved_report.created_at
            },
            "content": report_response.content,
            "articles_count": report_response.articles_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating and saving technical summary: {e}")
        raise HTTPException(status_code=500, detail=f"技術まとめレポートの生成・保存に失敗しました: {str(e)}")