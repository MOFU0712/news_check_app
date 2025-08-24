from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class URLParseRequest(BaseModel):
    """URL解析リクエスト"""
    urls_text: str = Field(..., description="URL一覧のテキスト（複数行対応）")

class URLParseResponse(BaseModel):
    """URL解析レスポンス"""
    valid_urls: List[str] = Field(..., description="有効なURL一覧")
    invalid_urls: List[Dict[str, str]] = Field(..., description="無効なURL一覧（理由付き）")
    duplicate_urls: List[str] = Field(..., description="重複URL一覧")
    summary: Dict[str, int] = Field(..., description="解析結果サマリー")
    estimated_time: str = Field(..., description="推定処理時間")

class ScrapingJobRequest(BaseModel):
    """スクレイピングジョブ作成リクエスト"""
    urls_text: str = Field(..., description="URL一覧のテキスト")
    auto_generate_tags: bool = Field(default=True, description="自動タグ生成")
    skip_duplicates: bool = Field(default=True, description="重複URLをスキップ")

class ScrapingJobResponse(BaseModel):
    """スクレイピングジョブ作成レスポンス"""
    job_id: str = Field(..., description="ジョブID")
    parsed_urls: List[str] = Field(..., description="解析済みURL一覧")
    duplicate_urls: List[str] = Field(..., description="重複URL一覧")
    invalid_urls: List[Dict[str, str]] = Field(..., description="無効URL一覧")
    estimated_time: str = Field(..., description="推定処理時間")

class ScrapingJobStatus(BaseModel):
    """スクレイピングジョブ状態"""
    id: str = Field(..., description="ジョブID")
    status: str = Field(..., description="ステータス（pending/running/completed/failed）")
    progress: int = Field(..., description="進捗（処理済み数）")
    total: int = Field(..., description="総URL数")
    completed_urls: List[str] = Field(default=[], description="処理完了URL一覧")
    failed_urls: List[Dict[str, str]] = Field(default=[], description="失敗URL一覧（理由付き）")
    created_articles: List[str] = Field(default=[], description="作成された記事ID一覧")
    created_at: Optional[datetime] = Field(None, description="作成日時")
    started_at: Optional[datetime] = Field(None, description="開始日時")
    completed_at: Optional[datetime] = Field(None, description="完了日時")

class ScrapingResult(BaseModel):
    """スクレイピング結果（個別URL）"""
    url: str = Field(..., description="対象URL")
    success: bool = Field(..., description="成功フラグ")
    article_id: Optional[str] = Field(None, description="作成された記事ID")
    error_message: Optional[str] = Field(None, description="エラーメッセージ")
    scraped_data: Optional[Dict[str, Any]] = Field(None, description="取得したデータ")

class URLPreviewRequest(BaseModel):
    """URLプレビューリクエスト"""
    url: str = Field(..., description="プレビュー対象URL")

class URLPreviewResponse(BaseModel):
    """URLプレビューレスポンス"""
    url: str = Field(..., description="対象URL")
    title: Optional[str] = Field(None, description="記事タイトル")
    description: Optional[str] = Field(None, description="記事説明")
    site_name: Optional[str] = Field(None, description="サイト名")
    is_duplicate: bool = Field(..., description="既存記事との重複フラグ")
    estimated_tags: List[str] = Field(default=[], description="推定されるタグ")
    error: Optional[str] = Field(None, description="エラーメッセージ")