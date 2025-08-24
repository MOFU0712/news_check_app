from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from app.core.config import settings
from app.api import auth, articles, scraping, llm, export, reports, prompt_templates, admin

app = FastAPI(
    title="ITニュース管理システム",
    description="ITニュースの効率的な収集・管理・活用システム",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS middleware - Development configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000", 
        "http://localhost:3001",
        "http://127.0.0.1:3001"
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

@app.get("/")
async def root():
    return {"message": "ITニュース管理システム API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}