import uuid
from datetime import datetime, time, timedelta
from sqlalchemy import Column, String, DateTime, Boolean, JSON, ForeignKey, Time, func
from sqlalchemy.orm import relationship
from app.db.database import Base


class ReportScheduleConfig(Base):
    """レポート自動生成スケジュール設定モデル"""
    __tablename__ = "report_schedule_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    
    # 基本設定
    name = Column(String, nullable=False, index=True)  # スケジュール名
    description = Column(String, nullable=True)  # 説明
    enabled = Column(Boolean, default=True, nullable=False, index=True)  # 有効/無効
    
    # スケジュール設定
    schedule_type = Column(String, nullable=False, index=True)  # "daily", "weekly", "monthly"
    schedule_time = Column(Time, nullable=False)  # 実行時刻
    # weekly用: 曜日 (0=月曜, 6=日曜)
    weekday = Column(String, nullable=True)  # "0" for Monday (週次レポート用)
    # monthly用: 日付 (1-31)  
    day_of_month = Column(String, nullable=True)  # "1" for 1st day (月次レポート用)
    
    # レポート設定
    report_type = Column(String, nullable=False)  # "summary", "tag_analysis", "source_analysis", "trend_analysis"
    report_title_template = Column(String, nullable=False)  # レポートタイトルのテンプレート
    
    # フィルター設定
    date_range_days = Column(String, nullable=True)  # 日付範囲 ("1" for daily, "7" for weekly, "30" for monthly)
    tags_filter = Column(JSON, nullable=True)  # タグフィルター
    sources_filter = Column(JSON, nullable=True)  # ソースフィルター
    
    # プロンプトテンプレート設定
    prompt_template_id = Column(String(36), nullable=True)  # カスタムプロンプトテンプレートID
    
    # メール送信設定
    email_enabled = Column(Boolean, default=False, nullable=False)  # メール送信有効/無効
    email_recipients = Column(JSON, nullable=True)  # 送信先メールアドレス一覧
    email_subject_template = Column(String, nullable=True)  # メール件名テンプレート
    
    # 実行履歴
    last_executed_at = Column(DateTime(timezone=True), nullable=True, index=True)  # 最後の実行日時
    last_execution_status = Column(String, nullable=True)  # 最後の実行状態 ("success", "failed", "error")
    last_execution_message = Column(String, nullable=True)  # 最後の実行メッセージ
    next_scheduled_at = Column(DateTime(timezone=True), nullable=True, index=True)  # 次回実行予定日時
    
    # 作成・更新情報
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # リレーション
    creator = relationship("User", back_populates="report_schedules")
    
    def __repr__(self):
        return f"<ReportScheduleConfig(id={self.id}, name='{self.name}', type='{self.schedule_type}', enabled={self.enabled})>"
    
    @property 
    def schedule_display(self) -> str:
        """スケジュール表示用文字列"""
        time_str = self.schedule_time.strftime('%H:%M')
        
        if self.schedule_type == "daily":
            return f"毎日 {time_str}"
        elif self.schedule_type == "weekly":
            weekdays = ["月", "火", "水", "木", "金", "土", "日"]
            weekday_name = weekdays[int(self.weekday)] if self.weekday else "月"
            return f"毎週{weekday_name}曜日 {time_str}"
        elif self.schedule_type == "monthly":
            day = self.day_of_month or "1"
            return f"毎月{day}日 {time_str}"
        else:
            return f"{self.schedule_type} {time_str}"
    
    def get_date_range_days(self) -> int:
        """日付範囲の日数を取得"""
        if self.date_range_days:
            try:
                return int(self.date_range_days)
            except (ValueError, TypeError):
                pass
        
        # デフォルト値
        if self.schedule_type == "daily":
            return 1
        elif self.schedule_type == "weekly":
            return 7
        elif self.schedule_type == "monthly":
            return 30
        else:
            return 1
    
    def get_email_recipients(self) -> list:
        """メール送信先一覧を取得"""
        if self.email_recipients and isinstance(self.email_recipients, list):
            return self.email_recipients
        return []
    
    def get_tags_filter(self) -> list:
        """タグフィルターを取得"""
        if self.tags_filter and isinstance(self.tags_filter, list):
            return self.tags_filter
        return []
    
    def get_sources_filter(self) -> list:
        """ソースフィルターを取得"""
        if self.sources_filter and isinstance(self.sources_filter, list):
            return self.sources_filter
        return []
    
    def generate_report_title(self, generated_at: datetime) -> str:
        """レポートタイトルを生成"""
        template = self.report_title_template or f"{self.schedule_type}レポート"
        
        # テンプレート変数の置換
        replacements = {
            '{date}': generated_at.strftime('%Y年%m月%d日'),
            '{year}': generated_at.strftime('%Y'),
            '{month}': generated_at.strftime('%m'),
            '{day}': generated_at.strftime('%d'),
            '{schedule_type}': self.schedule_type,
            '{report_type}': self.report_type,
            '{name}': self.name
        }
        
        # 週次・月次用の特別な処理
        if self.schedule_type == "weekly":
            # 週の開始日（月曜日）を計算
            days_to_subtract = generated_at.weekday()  # 0=月曜, 6=日曜
            week_start = generated_at - timedelta(days=days_to_subtract)
            week_end = week_start + timedelta(days=6)
            
            replacements.update({
                '{week_start}': week_start.strftime('%Y年%m月%d日'),
                '{week_end}': week_end.strftime('%Y年%m月%d日'),
                '{week_range}': f"{week_start.strftime('%m/%d')}-{week_end.strftime('%m/%d')}"
            })
        
        elif self.schedule_type == "monthly":
            # 前月の情報
            if generated_at.month == 1:
                prev_month_year = generated_at.year - 1
                prev_month = 12
            else:
                prev_month_year = generated_at.year
                prev_month = generated_at.month - 1
            
            replacements.update({
                '{prev_month_year}': str(prev_month_year),
                '{prev_month}': str(prev_month),
                '{prev_month_name}': f"{prev_month_year}年{prev_month}月"
            })
        
        # 文字列置換
        result = template
        for key, value in replacements.items():
            result = result.replace(key, str(value))
        
        return result
    
    def generate_email_subject(self, generated_at: datetime) -> str:
        """メール件名を生成"""
        if self.email_subject_template:
            # カスタムテンプレートを使用
            template = self.email_subject_template
            report_title = self.generate_report_title(generated_at)
            
            replacements = {
                '{report_title}': report_title,
                '{date}': generated_at.strftime('%Y年%m月%d日'),
                '{schedule_type}': self.schedule_type,
                '{name}': self.name
            }
            
            result = template
            for key, value in replacements.items():
                result = result.replace(key, str(value))
            return result
        else:
            # デフォルトの件名
            report_title = self.generate_report_title(generated_at)
            return f"📊 {report_title} - News Check App"