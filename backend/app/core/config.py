from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, field_validator
import secrets

class Settings(BaseSettings):
    # API Settings
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # Database (PostgreSQL)
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_USER: str = "tsutsuikana"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = "news_system_migration"
    
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []
    
    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                # JSON-like format
                import json
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    # Fallback to simple parsing
                    v = v.strip("[]")
                    return [i.strip().strip('"').strip("'") for i in v.split(",")]
            else:
                # Comma-separated format
                return [i.strip() for i in v.split(",")]
        elif isinstance(v, list):
            return v
        return []
    
    @property
    def ALLOWED_HOSTS(self) -> List[str]:
        hosts = ["localhost", "127.0.0.1"]
        if self.BACKEND_CORS_ORIGINS:
            for origin in self.BACKEND_CORS_ORIGINS:
                if isinstance(origin, str):
                    # Extract hostname from URL
                    from urllib.parse import urlparse
                    parsed = urlparse(origin)
                    if parsed.hostname:
                        hosts.append(parsed.hostname)
        return hosts
    
    # Anthropic API
    ANTHROPIC_API_KEY: Optional[str] = None
    
    # Timezone settings
    TIMEZONE: str = "Asia/Tokyo"
    DEFAULT_TIMEZONE: str = "Asia/Tokyo"
    
    # Scraping settings
    SCRAPING_USER_AGENT: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    SCRAPING_TIMEOUT: int = 30
    SCRAPING_RATE_LIMIT: float = 1.0  # seconds between requests to same domain
    
    # Admin user
    FIRST_SUPERUSER_EMAIL: str = "kana.011235813213455@gmail.com"
    FIRST_SUPERUSER_PASSWORD: str = "kagishippo0712"
    
    # Email settings
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_USE_TLS: bool = True
    FROM_EMAIL: Optional[str] = None
    FROM_NAME: str = "News Check App"
    
    # Email templates
    ENABLE_EMAIL_REPORTS: bool = False
    
    # System settings (can be dynamically updated)
    DEFAULT_SCRAPING_DELAY: float = 2.0  # より長い間隔で負荷軽減
    MAX_CONCURRENT_REQUESTS: int = 3  # 同時リクエスト数を削減
    DEFAULT_REPORT_TEMPLATE: str = "summary"
    ENABLE_AUTO_TAGGING: bool = True
    MAX_SCRAPING_BATCH_SIZE: int = 10  # バッチサイズ制限を追加
    MAX_CONTENT_LENGTH: int = 50000
    SESSION_TIMEOUT_MINUTES: int = 1440
    ENABLE_USER_REGISTRATION: bool = False
    
    class Config:
        env_file = ".env"

settings = Settings()