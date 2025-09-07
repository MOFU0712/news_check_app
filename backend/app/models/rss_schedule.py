from sqlalchemy import Column, Integer, String, Boolean, Time, Text, DateTime
from sqlalchemy.sql import func
from app.db.database import Base


class RSSSchedule(Base):
    """RSSスクレイピングスケジュール設定"""
    __tablename__ = "rss_schedules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(50), nullable=False, unique=True, index=True)  # ユーザーごとに1つのスケジュール
    rss_file_path = Column(String(500), nullable=False)
    schedule_time = Column(Time, nullable=False)  # 実行時刻
    enabled = Column(Boolean, default=True, nullable=False)
    auto_generate_tags = Column(Boolean, default=True, nullable=False)
    skip_duplicates = Column(Boolean, default=True, nullable=False)
    include_arxiv = Column(Boolean, default=False, nullable=False)
    arxiv_categories = Column(Text)  # JSON文字列として保存
    arxiv_max_results = Column(Integer, default=20, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())