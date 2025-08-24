import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Integer, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base

class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(Text)
    
    # 拡張フィールド
    template_type = Column(String(50), nullable=False, default='blog_report')  # 'blog_report', 'summary', 'analysis'
    system_prompt = Column(Text, nullable=True)  # 一時的にnullableにして後で修正
    user_prompt_template = Column(Text, nullable=True)
    
    # AI設定
    model_name = Column(String(100), nullable=False, default='claude-3-7-sonnet-20250219')
    max_tokens = Column(Integer, nullable=False, default=2000)
    temperature = Column(Float, nullable=False, default=0.3)
    
    # 互換性のための既存フィールド（非推奨だが削除すると既存データが壊れる可能性）
    template = Column(Text, nullable=True)  # system_promptのエイリアス
    type = Column(String(50), nullable=True)  # template_typeのエイリアス
    
    is_active = Column(Boolean, default=True)
    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    creator = relationship("User", back_populates="prompt_templates")
    
    def __repr__(self):
        return f"<PromptTemplate(id={self.id}, name='{self.name}', type='{self.template_type}')>"