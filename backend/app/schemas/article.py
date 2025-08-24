from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, HttpUrl, Field

class ArticleBase(BaseModel):
    title: str = Field(..., max_length=500, description="記事タイトル")
    url: HttpUrl = Field(..., description="記事URL")
    content: Optional[str] = Field(None, description="記事本文")
    source: Optional[str] = Field(None, max_length=200, description="記事ソース（サイト名）")
    published_date: Optional[datetime] = Field(None, description="記事公開日時")
    tags: Optional[List[str]] = Field(default=[], description="タグリスト")
    summary: Optional[str] = Field(None, description="記事要約")

class ArticleCreate(ArticleBase):
    """記事作成用スキーマ"""
    pass

class ArticleUpdate(BaseModel):
    """記事更新用スキーマ"""
    title: Optional[str] = Field(None, max_length=500)
    url: Optional[HttpUrl] = None
    content: Optional[str] = None
    source: Optional[str] = Field(None, max_length=200)
    published_date: Optional[datetime] = None
    tags: Optional[List[str]] = None
    summary: Optional[str] = None

class ArticleResponse(ArticleBase):
    """記事レスポンス用スキーマ"""
    id: str
    scraped_date: datetime
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime
    is_favorite: bool = Field(default=False, description="現在のユーザーのお気に入り状態")
    
    class Config:
        from_attributes = True

class ArticleListResponse(BaseModel):
    """記事一覧レスポンス用スキーマ"""
    articles: List[ArticleResponse]
    total: int
    page: int
    limit: int
    has_next: bool
    has_prev: bool

class ArticleSearchRequest(BaseModel):
    """記事検索リクエスト用スキーマ"""
    query: Optional[str] = Field(None, description="検索クエリ")
    search_mode: str = Field(default="and", description="検索モード: 'and' または 'or'")
    tags: Optional[List[str]] = Field(default=[], description="タグフィルター")
    source: Optional[str] = Field(None, description="ソースフィルター")
    start_date: Optional[datetime] = Field(None, description="開始日時")
    end_date: Optional[datetime] = Field(None, description="終了日時")
    favorites_only: bool = Field(default=False, description="お気に入りのみ")
    page: int = Field(default=1, ge=1, description="ページ番号")
    limit: int = Field(default=20, ge=1, le=100, description="1ページあたりの件数")

class FavoriteToggleRequest(BaseModel):
    """お気に入り切り替えリクエスト用スキーマ"""
    article_id: str

class FavoriteResponse(BaseModel):
    """お気に入りレスポンス用スキーマ"""
    article_id: str
    is_favorite: bool
    message: str