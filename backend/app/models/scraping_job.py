from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.database import Base
from datetime import datetime
import uuid

class ScrapingJob(Base):
    """スクレイピングジョブ"""
    __tablename__ = "scraping_jobs"
    __table_args__ = {'extend_existing': True}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    # ジョブ設定
    urls = Column(JSON, nullable=False)  # スクレイピング対象URL一覧（JSON array）
    auto_generate_tags = Column(String(5), default="true")  # 自動タグ生成フラグ（文字列で保存）
    skip_duplicates = Column(String(5), default="true")  # 重複スキップフラグ（文字列で保存）
    
    # ジョブ状態
    status = Column(String(20), default="pending")  # pending, running, completed, failed
    progress = Column(Integer, default=0)  # 処理済みURL数
    total = Column(Integer, default=0)  # 総URL数
    
    # 処理結果
    completed_urls = Column(JSON, default=list)  # 処理完了URL一覧（JSON array）
    failed_urls = Column(JSON, default=list)  # 処理失敗URL一覧（JSON array）
    skipped_urls = Column(JSON, default=list)  # 重複でスキップされたURL一覧（JSON array）
    error_message = Column(Text)  # エラーメッセージ
    created_article_ids = Column(JSON, default=list)  # 作成された記事ID一覧（JSON array）
    
    # 日時情報
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    # リレーション
    user = relationship("User", back_populates="scraping_jobs")
    
    @property
    def auto_generate_tags_bool(self) -> bool:
        """自動タグ生成フラグをbooleanで取得"""
        return self.auto_generate_tags == "true"
    
    @auto_generate_tags_bool.setter
    def auto_generate_tags_bool(self, value: bool):
        """自動タグ生成フラグをbooleanで設定"""
        self.auto_generate_tags = "true" if value else "false"
    
    @property
    def skip_duplicates_bool(self) -> bool:
        """重複スキップフラグをbooleanで取得"""
        return self.skip_duplicates == "true"
    
    @skip_duplicates_bool.setter
    def skip_duplicates_bool(self, value: bool):
        """重複スキップフラグをbooleanで設定"""
        self.skip_duplicates = "true" if value else "false"
    
    def to_dict(self):
        """辞書形式での出力"""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "urls": self.urls or [],
            "auto_generate_tags": self.auto_generate_tags_bool,
            "skip_duplicates": self.skip_duplicates_bool,
            "status": self.status,
            "progress": self.progress,
            "total": self.total,
            "completed_urls": self.completed_urls or [],
            "failed_urls": self.failed_urls or [],
            "error_message": self.error_message,
            "created_article_ids": self.created_article_ids or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }