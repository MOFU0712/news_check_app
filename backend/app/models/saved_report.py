import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, JSON, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.database import Base

class SavedReport(Base):
    """保存されたレポートモデル"""
    __tablename__ = "saved_reports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    
    # レポート基本情報
    title = Column(String, nullable=False, index=True)
    report_type = Column(String, nullable=False)  # "summary", "tag_analysis", etc.
    content = Column(Text, nullable=False)  # ブログ記事形式のコンテンツ
    
    # 生成パラメータ
    parameters = Column(JSON, nullable=True)  # 生成時のパラメータ（日付範囲、タグ、ソースなど）
    raw_data = Column(JSON, nullable=True)  # 生成元の分析データ
    
    # メタデータ
    summary = Column(Text, nullable=True)  # レポートの要約
    tags = Column(JSON, nullable=True)  # レポートのタグ
    
    # 作成者・日時
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # リレーション
    creator = relationship("User", back_populates="saved_reports")
    
    def __repr__(self):
        return f"<SavedReport(id={self.id}, title='{self.title}', type='{self.report_type}')>"