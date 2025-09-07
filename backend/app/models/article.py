import uuid
from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base

class Article(Base):
    __tablename__ = "articles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(500), nullable=False)
    content = Column(Text)
    url = Column(String(1000), unique=True, nullable=False, index=True)
    source = Column(String(200))
    published_date = Column(DateTime(timezone=True))
    scraped_date = Column(DateTime(timezone=True), server_default=func.now())
    tags = Column(JSON)
    summary = Column(Text)
    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    creator = relationship("User", back_populates="articles")
    favorites = relationship("UserFavorite", back_populates="article", cascade="all, delete-orphan")

class UserFavorite(Base):
    __tablename__ = "user_favorites"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    article_id = Column(String(36), ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="favorites")
    article = relationship("Article", back_populates="favorites")
    
    # Unique constraint
    __table_args__ = (
        {"schema": None},  # Add unique constraint in migration
    )