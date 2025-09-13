from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.api import auth, articles, scraping, llm, export, reports, prompt_templates, admin, rss, email, report_schedules, usage

@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションのライフサイクル管理"""
    # 起動時の処理
    print("=== APPLICATION STARTUP ===")
    
    from app.services.scheduler_service import scheduler_service
    from app.services.report_scheduler_service import report_scheduler_service
    from app.services.llm_service import llm_service
    import logging
    
    logger = logging.getLogger(__name__)
    
    print(f"=== LLM service initialized: {llm_service.is_available()} ===")
    logger.info(f"LLM service initialized: {llm_service.is_available()}")
    
    # RSSスケジューラーを開始
    try:
        print("=== Starting RSS scheduler ===")
        await scheduler_service.start_scheduler()
        print(f"=== RSS scheduler started: {scheduler_service.is_running} ===")
        print(f"=== Loaded schedules: {len(scheduler_service.schedules)} ===")
        logger.info("RSS scheduler started successfully")
    except Exception as e:
        print(f"=== Failed to start RSS scheduler: {e} ===")
        logger.error(f"Failed to start RSS scheduler: {e}")
    
    # レポートスケジューラーを開始
    try:
        print("=== Starting Report scheduler ===")
        await report_scheduler_service.start_scheduler()
        print(f"=== Report scheduler started: {report_scheduler_service.is_running} ===")
        logger.info("Report scheduler started successfully")
    except Exception as e:
        print(f"=== Failed to start Report scheduler: {e} ===")
        logger.error(f"Failed to start report scheduler: {e}")
    
    print("=== APPLICATION STARTUP COMPLETE ===")
    
    yield  # アプリケーション実行
    
    # 終了時の処理
    print("=== APPLICATION SHUTDOWN ===")
    try:
        await scheduler_service.stop_scheduler()
        await report_scheduler_service.stop_scheduler()
        logger.info("Schedulers stopped successfully")
    except Exception as e:
        logger.error(f"Failed to stop schedulers: {e}")
    print("=== APPLICATION SHUTDOWN COMPLETE ===")

app = FastAPI(
    lifespan=lifespan,
    title="ITニュース管理システム",
    description="ITニュースの効率的な収集・管理・活用システム",
    version="1.0.0",
    openapi_version="3.0.2",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS middleware - Production and Development configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000", 
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "https://news-check-app.mofu-mofu-application.com",
        "https://www.news-check-app.mofu-mofu-application.com"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["*"],
)

# Trusted host middleware - Commented out for development
# app.add_middleware(
#     TrustedHostMiddleware,
#     allowed_hosts=settings.ALLOWED_HOSTS
# )

# API routes
app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(articles.router, prefix="/api/articles", tags=["articles"])
app.include_router(scraping.router, prefix="/api/scrape", tags=["scraping"])
app.include_router(llm.router, prefix="/api/llm", tags=["llm"])
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(prompt_templates.router, prefix="/api/prompt-templates", tags=["prompt_templates"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(rss.router, prefix="/api/rss", tags=["rss"])
app.include_router(email.router, prefix="/api/email", tags=["email"])
app.include_router(report_schedules.router, prefix="/api/report-schedules", tags=["report_schedules"])
app.include_router(usage.router, prefix="/api/usage", tags=["usage"])


# API エンドポイント
@app.get("/")
async def root():
    return {"message": "ITニュース管理システム API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}