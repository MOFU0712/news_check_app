#!/usr/bin/env python3
"""
簡易バックエンド起動スクリプト（認証のみ）
"""
import uvicorn
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

# 簡易アプリケーション
app = FastAPI(
    title="ITニュース管理システム（簡易版）",
    description="認証機能のテスト用",
    version="1.0.0"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 簡易スキーマ
class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool = True

# 簡易認証（テスト用）
@app.post("/api/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """テスト用ログイン"""
    # 固定の管理者アカウント
    if request.email == "admin@example.com" and request.password == "admin123":
        return LoginResponse(
            access_token="test-jwt-token-admin",
            token_type="bearer"
        )
    # 固定の一般ユーザー
    elif request.email == "user@example.com" and request.password == "user123":
        return LoginResponse(
            access_token="test-jwt-token-user", 
            token_type="bearer"
        )
    else:
        raise HTTPException(status_code=401, detail="Incorrect email or password")

@app.get("/api/auth/me", response_model=UserResponse)
async def get_current_user():
    """テスト用ユーザー情報"""
    return UserResponse(
        id="test-user-id",
        email="admin@example.com",
        role="admin"
    )

@app.get("/api/auth/validate-token")
async def validate_token():
    """テスト用トークン検証"""
    return {"valid": True, "user_id": "test-user-id"}

# URLパーサーとWebスクレイパーを追加
from app.utils.url_parser import URLParser
from app.utils.web_scraper import WebScraper

# スクレイピング関連のエンドポイント
@app.post("/api/scrape/parse-urls")
async def parse_urls(request: dict):
    """URLパース・バリデーション API"""
    urls_text = request.get("urls_text", "")
    
    if not urls_text.strip():
        return {
            "valid_urls": [],
            "invalid_urls": [],
            "duplicate_urls": [],
            "summary": {"valid_count": 0, "invalid_count": 0, "duplicate_count": 0, "total_lines": 0},
            "estimated_time": "0秒"
        }
    
    # URLパース実行
    parse_result = URLParser.parse_urls_from_text(urls_text)
    
    # 既存記事との重複チェック（ダミーデータ）
    existing_urls = {
        "https://example.com/existing1",
        "https://blog.example.com/existing2"
    }
    
    new_urls, duplicate_urls = URLParser.check_duplicates_with_existing(
        parse_result.valid_urls, existing_urls
    )
    
    return {
        "valid_urls": new_urls,
        "invalid_urls": [{"url": item[0], "reason": item[1]} for item in parse_result.invalid_urls],
        "duplicate_urls": duplicate_urls,
        "summary": {
            "valid_count": len(new_urls),
            "invalid_count": len(parse_result.invalid_urls),
            "duplicate_count": len(duplicate_urls),
            "total_lines": parse_result.total_input_lines
        },
        "estimated_time": URLParser.estimate_processing_time(len(new_urls))
    }

@app.post("/api/scrape/preview")
async def preview_url(request: dict):
    """URLプレビュー API（実際のスクレイピング実行）"""
    url = request.get("url", "")
    
    # URL正規化
    normalized_url = URLParser._normalize_url(url)
    if not normalized_url:
        return {"error": "Invalid URL format"}
    
    # 重複チェック（ダミー）
    existing_urls = {"https://example.com/existing1", "https://blog.example.com/existing2"}
    is_duplicate = normalized_url in existing_urls
    
    try:
        # 実際のスクレイピング実行
        async with WebScraper(timeout=15) as scraper:
            scraped_content = await scraper.scrape_url(normalized_url)
            
            if scraped_content.error:
                return {
                    "url": normalized_url,
                    "title": None,
                    "description": None,
                    "site_name": None,
                    "is_duplicate": is_duplicate,
                    "estimated_tags": [],
                    "error": scraped_content.error
                }
            
            return {
                "url": normalized_url,
                "title": scraped_content.title,
                "description": scraped_content.description,
                "site_name": scraped_content.site_name,
                "is_duplicate": is_duplicate,
                "estimated_tags": scraped_content.auto_tags,
                "error": None
            }
            
    except Exception as e:
        return {
            "url": normalized_url,
            "title": None,
            "description": None,
            "site_name": None,
            "is_duplicate": is_duplicate,
            "estimated_tags": [],
            "error": f"Preview failed: {str(e)}"
        }

# 記事関連のダミーエンドポイント
@app.get("/api/articles")
async def list_articles():
    """ダミー記事一覧"""
    return {
        "articles": [
            {
                "id": "article-1",
                "title": "React 18の新機能：Concurrent Featuresの使い方",
                "url": "https://example.com/react18-concurrent",
                "content": "React 18では、Concurrent Featuresと呼ばれる新しい機能が追加されました...",
                "source": "React公式ブログ",
                "tags": ["React", "JavaScript", "フロントエンド"],
                "summary": "React 18で導入されたConcurrent Featuresの概要と使用方法について解説。",
                "scraped_date": "2024-01-15T10:30:00Z",
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:30:00Z",
                "is_favorite": False
            },
            {
                "id": "article-2", 
                "title": "FastAPIでモダンなWeb API開発",
                "url": "https://example.com/fastapi-modern-api",
                "content": "FastAPIは、PythonでモダンなWeb APIを構築するための高性能なフレームワークです...",
                "source": "Python Weekly",
                "tags": ["Python", "FastAPI", "バックエンド"],
                "summary": "FastAPIを使ったモダンなWeb API開発の手法を紹介。",
                "scraped_date": "2024-01-14T14:20:00Z",
                "created_at": "2024-01-14T14:20:00Z", 
                "updated_at": "2024-01-14T14:20:00Z",
                "is_favorite": True
            }
        ],
        "total": 2,
        "page": 1,
        "limit": 20,
        "has_next": False,
        "has_prev": False
    }

@app.get("/api/articles/stats/overview")
async def get_stats():
    """ダミー統計情報"""
    return {
        "total_articles": 2,
        "monthly_articles": 2,
        "popular_tags": [["React", 1], ["Python", 1], ["JavaScript", 1]],
        "source_stats": [["React公式ブログ", 1], ["Python Weekly", 1]]
    }

@app.get("/")
async def root():
    return {"message": "ITニュース管理システム（テスト版）が起動中"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    print("🚀 簡易バックエンドサーバーを起動します...")
    print("📍 URL: http://localhost:8000")
    print("📖 API仕様書: http://localhost:8000/docs")
    print("")
    print("🔐 テスト用ログイン情報:")
    print("  管理者: admin@example.com / admin123")
    print("  一般: user@example.com / user123")
    print("")
    
    uvicorn.run(
        "start_backend_simple:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )