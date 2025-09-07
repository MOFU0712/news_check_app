import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, DateTime, Date, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base

class UsageLog(Base):
    __tablename__ = "usage_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    action_type = Column(String(50), nullable=False)  # 'report_generation', 'llm_query', etc.
    usage_date = Column(Date, nullable=False, default=date.today)
    resource_used = Column(String(100))  # 使用したリソース (template_id, model_name など)
    additional_data = Column(Text)  # 追加情報をJSON文字列として保存
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", backref="usage_logs")
    
    def __repr__(self):
        return f"<UsageLog(user_id={self.user_id}, action_type='{self.action_type}', usage_date={self.usage_date})>"