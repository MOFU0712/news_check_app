import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    password_change_required = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships (using string references to avoid circular imports)
    articles = relationship("Article", back_populates="creator", lazy="dynamic")
    favorites = relationship("UserFavorite", back_populates="user", cascade="all, delete-orphan", lazy="dynamic")
    scraping_jobs = relationship("ScrapingJob", back_populates="user", lazy="dynamic")
    prompt_templates = relationship("PromptTemplate", back_populates="creator", lazy="dynamic")
    saved_reports = relationship("SavedReport", back_populates="creator", lazy="dynamic")
    report_schedules = relationship("ReportScheduleConfig", back_populates="creator", lazy="dynamic")