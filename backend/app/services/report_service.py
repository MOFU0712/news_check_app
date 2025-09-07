import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, or_
import csv
import io
import uuid
import json
from collections import defaultdict, Counter
import pytz

from app.models.article import Article
from app.core.config import settings
from app.models.user import User
from app.models.saved_report import SavedReport
from app.models.prompt import PromptTemplate
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


def make_json_serializable(obj):
    """オブジェクトをJSON serializableに変換"""
    if isinstance(obj, uuid.UUID):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: make_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(item) for item in obj]
    else:
        return obj


class ReportService:
    """レポート生成・分析サービス"""
    
    def __init__(self, db: Session):
        self.db = db
        self.llm_service = llm_service
    
    async def generate_report(
        self,
        report_type: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        tags: Optional[List[str]] = None,
        sources: Optional[List[str]] = None,
        user: Optional[User] = None
    ) -> Dict[str, Any]:
        """指定された条件でレポートを生成"""
        
        # 日付範囲の処理
        date_filter = self._build_date_filter(start_date, end_date)
        
        if report_type == "summary":
            return await self._generate_summary_report(date_filter, tags, sources)
        elif report_type == "tag_analysis":
            return await self._generate_tag_analysis_report(date_filter, tags, sources)
        elif report_type == "source_analysis":
            return await self._generate_source_analysis_report(date_filter, sources)
        elif report_type == "trend_analysis":
            return await self._generate_trend_analysis_report(date_filter, tags, sources)
        else:
            raise ValueError(f"サポートされていないレポートタイプ: {report_type}")
    
    def _build_date_filter(self, start_date: Optional[str], end_date: Optional[str]) -> Tuple[Optional[datetime], Optional[datetime]]:
        """日付フィルターを構築"""
        start_dt = None
        end_dt = None
        
        logger.info(f"Building date filter: start_date={start_date}, end_date={end_date}")
        
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                logger.info(f"Parsed start_date: {start_dt}")
            except ValueError:
                logger.warning(f"Invalid start_date format: {start_date}")
        
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                
                # 終了日時を23:59:59.999999に設定（その日の最後の瞬間）
                if end_dt.hour == 0 and end_dt.minute == 0 and end_dt.second == 0 and end_dt.microsecond == 0:
                    end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
                    logger.info(f"Adjusted end_date to end of day: {end_dt}")
                else:
                    logger.info(f"Parsed end_date (no adjustment): {end_dt}")
                
            except ValueError:
                logger.warning(f"Invalid end_date format: {end_date}")
        
        logger.info(f"Final date filter: start_dt={start_dt}, end_dt={end_dt}")
        return start_dt, end_dt
    
    async def _generate_summary_report(
        self,
        date_filter: Tuple[Optional[datetime], Optional[datetime]],
        tags: Optional[List[str]] = None,
        sources: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """要約レポートを生成"""
        start_dt, end_dt = date_filter
        query = self.db.query(Article)
        
        # フィルター適用
        if start_dt:
            query = query.filter(Article.published_date >= start_dt)
        if end_dt:
            query = query.filter(Article.published_date <= end_dt)
        if tags:
            for tag in tags:
                query = query.filter(Article.tags.any(tag))
        if sources:
            query = query.filter(Article.source.in_(sources))
        
        articles = query.all()
        total_count = len(articles)
        
        # 基本統計
        tag_counter = Counter()
        source_counter = Counter()
        daily_counts = defaultdict(int)
        
        for article in articles:
            # タグ統計
            if article.tags:
                for tag in article.tags:
                    tag_counter[tag] += 1
            
            # ソース統計
            if article.source:
                source_counter[article.source] += 1
            
            # 日別統計
            date_str = article.published_date.strftime('%Y-%m-%d')
            daily_counts[date_str] += 1
        
        # 人気のタグ・ソース（上位10件）
        popular_tags = tag_counter.most_common(10)
        popular_sources = source_counter.most_common(10)
        
        # 記事要約リスト（全記事を含める）
        article_summaries = []
        for article in articles:
            if article.summary and len(article.summary.strip()) > 10:
                article_summaries.append({
                    "title": article.title,
                    "summary": article.summary,
                    "url": article.url,
                    "source": article.source,
                    "published_date": article.published_date.isoformat(),
                    "tags": article.tags or []
                })
        
        # 要約文を生成
        period_text = ""
        if start_dt and end_dt:
            period_text = f"{start_dt.strftime('%Y年%m月%d日')}から{end_dt.strftime('%Y年%m月%d日')}まで"
        elif start_dt:
            period_text = f"{start_dt.strftime('%Y年%m月%d日')}以降"
        elif end_dt:
            period_text = f"{end_dt.strftime('%Y年%m月%d日')}まで"
        else:
            period_text = "全期間"
        
        summary = f"{period_text}の記事レポート: 合計{total_count}件の記事を分析。"
        if popular_tags:
            summary += f" 人気のタグは「{popular_tags[0][0]}」({popular_tags[0][1]}件)。"
        if popular_sources:
            summary += f" 主要なソースは「{popular_sources[0][0]}」({popular_sources[0][1]}件)。"
        
        return {
            "data": {
                "total_articles": total_count,
                "popular_tags": popular_tags,
                "popular_sources": popular_sources,
                "daily_counts": dict(daily_counts),
                "article_summaries": article_summaries,
                "period": {"start": start_dt.isoformat() if start_dt else None, "end": end_dt.isoformat() if end_dt else None}
            },
            "summary": summary
        }
    
    async def _generate_tag_analysis_report(
        self,
        date_filter: Tuple[Optional[datetime], Optional[datetime]],
        tags: Optional[List[str]] = None,
        sources: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """タグ分析レポートを生成"""
        start_dt, end_dt = date_filter
        query = self.db.query(Article)
        
        # フィルター適用
        if start_dt:
            query = query.filter(Article.published_date >= start_dt)
        if end_dt:
            query = query.filter(Article.published_date <= end_dt)
        if sources:
            query = query.filter(Article.source.in_(sources))
        
        articles = query.all()
        
        # タグごとの詳細分析
        tag_analysis = defaultdict(lambda: {
            "count": 0,
            "sources": Counter(),
            "recent_articles": [],
            "trend": []
        })
        
        for article in articles:
            if article.tags:
                for tag in article.tags:
                    if not tags or tag in tags:  # 指定タグのみまたは全タグ
                        tag_analysis[tag]["count"] += 1
                        if article.source:
                            tag_analysis[tag]["sources"][article.source] += 1
                        
                        # 最近の記事（5件まで）
                        if len(tag_analysis[tag]["recent_articles"]) < 5:
                            tag_analysis[tag]["recent_articles"].append({
                                "title": article.title,
                                "url": article.url,
                                "published_date": article.published_date.isoformat(),
                                "source": article.source
                            })
        
        # 結果をソート（記事数順）
        sorted_tags = sorted(tag_analysis.items(), key=lambda x: x[1]["count"], reverse=True)
        
        # 記事要約リスト（全記事を含める）
        article_summaries = []
        for article in articles:
            if article.summary and len(article.summary.strip()) > 10:
                article_summaries.append({
                    "title": article.title,
                    "summary": article.summary,
                    "url": article.url,
                    "source": article.source,
                    "published_date": article.published_date.isoformat(),
                    "tags": article.tags or []
                })
        
        summary = f"タグ分析: {len(sorted_tags)}個のタグを分析。"
        if sorted_tags:
            top_tag = sorted_tags[0]
            summary += f" 最も多いタグは「{top_tag[0]}」({top_tag[1]['count']}件)。"
        
        return {
            "data": {
                "tag_analysis": dict(sorted_tags[:20]),  # 上位20件
                "total_unique_tags": len(sorted_tags),
                "article_summaries": article_summaries
            },
            "summary": summary
        }
    
    async def _generate_source_analysis_report(
        self,
        date_filter: Tuple[Optional[datetime], Optional[datetime]],
        sources: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """ソース分析レポートを生成"""
        start_dt, end_dt = date_filter
        query = self.db.query(Article)
        
        # フィルター適用
        if start_dt:
            query = query.filter(Article.published_date >= start_dt)
        if end_dt:
            query = query.filter(Article.published_date <= end_dt)
        if sources:
            query = query.filter(Article.source.in_(sources))
        
        articles = query.all()
        
        # ソースごとの詳細分析
        source_analysis = defaultdict(lambda: {
            "count": 0,
            "tags": Counter(),
            "recent_articles": [],
            "daily_counts": defaultdict(int)
        })
        
        for article in articles:
            if article.source:
                source = article.source
                source_analysis[source]["count"] += 1
                
                # タグ統計
                if article.tags:
                    for tag in article.tags:
                        source_analysis[source]["tags"][tag] += 1
                
                # 最近の記事（5件まで）
                if len(source_analysis[source]["recent_articles"]) < 5:
                    source_analysis[source]["recent_articles"].append({
                        "title": article.title,
                        "url": article.url,
                        "published_date": article.published_date.isoformat()
                    })
                
                # 日別統計
                date_str = article.published_date.strftime('%Y-%m-%d')
                source_analysis[source]["daily_counts"][date_str] += 1
        
        # 結果をソート
        sorted_sources = sorted(source_analysis.items(), key=lambda x: x[1]["count"], reverse=True)
        
        # 記事要約リスト（全記事を含める）
        article_summaries = []
        for article in articles:
            if article.summary and len(article.summary.strip()) > 10:
                article_summaries.append({
                    "title": article.title,
                    "summary": article.summary,
                    "url": article.url,
                    "source": article.source,
                    "published_date": article.published_date.isoformat(),
                    "tags": article.tags or []
                })
        
        summary = f"ソース分析: {len(sorted_sources)}個のソースを分析。"
        if sorted_sources:
            top_source = sorted_sources[0]
            summary += f" 最も多いソースは「{top_source[0]}」({top_source[1]['count']}件)。"
        
        return {
            "data": {
                "source_analysis": dict(sorted_sources[:20]),  # 上位20件
                "total_unique_sources": len(sorted_sources),
                "article_summaries": article_summaries
            },
            "summary": summary
        }
    
    async def _generate_trend_analysis_report(
        self,
        date_filter: Tuple[Optional[datetime], Optional[datetime]],
        tags: Optional[List[str]] = None,
        sources: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """トレンド分析レポートを生成"""
        start_dt, end_dt = date_filter
        
        logger.info(f"Generating trend analysis report with date_filter: start_dt={start_dt}, end_dt={end_dt}")
        
        # デフォルトで過去30日間
        if not start_dt:
            start_dt = datetime.now(pytz.timezone(settings.TIMEZONE)) - timedelta(days=30)
            logger.info(f"Using default start_dt: {start_dt}")
        if not end_dt:
            end_dt = datetime.now(pytz.timezone(settings.TIMEZONE))
            logger.info(f"Using default end_dt: {end_dt}")
        
        logger.info(f"Final date range for query: {start_dt} to {end_dt}")
        
        # 全記事数をまず確認
        total_articles = self.db.query(Article).count()
        logger.info(f"Total articles in database: {total_articles}")
        
        # 日付フィルタ前のクエリ
        base_query = self.db.query(Article)
        
        # 日付フィルタを適用
        query = base_query.filter(
            Article.published_date >= start_dt,
            Article.published_date <= end_dt
        )
        
        # 日付フィルタ後の件数をログ出力
        date_filtered_count = query.count()
        logger.info(f"Articles after date filtering ({start_dt} to {end_dt}): {date_filtered_count}")
        
        if tags:
            logger.info(f"Applying tag filter: {tags}")
            for tag in tags:
                query = query.filter(Article.tags.any(tag))
        if sources:
            logger.info(f"Applying source filter: {sources}")
            query = query.filter(Article.source.in_(sources))
        
        articles = query.all()
        logger.info(f"Final filtered articles count: {len(articles)}")
        
        # デバッグ: 最初の3記事の情報を表示
        if articles:
            logger.info("Sample articles found:")
            for i, article in enumerate(articles[:3]):
                logger.info(f"  Article {i+1}: title='{article.title[:50]}...', published_date={article.published_date}")
        else:
            logger.warning("No articles found matching the criteria!")
            
            # デバッグ: 記事の日付範囲を確認
            date_range_query = self.db.query(
                func.min(Article.published_date).label('min_date'),
                func.max(Article.published_date).label('max_date')
            ).first()
            if date_range_query:
                logger.info(f"Available article date range: {date_range_query.min_date} to {date_range_query.max_date}")
        
        # 日別トレンド
        daily_trends = defaultdict(lambda: {
            "count": 0,
            "tags": Counter(),
            "sources": Counter()
        })
        
        for article in articles:
            date_str = article.published_date.strftime('%Y-%m-%d')
            daily_trends[date_str]["count"] += 1
            
            if article.tags:
                for tag in article.tags:
                    daily_trends[date_str]["tags"][tag] += 1
            
            if article.source:
                daily_trends[date_str]["sources"][article.source] += 1
        
        # 週別集計
        weekly_trends = defaultdict(int)
        for article in articles:
            week_start = article.published_date - timedelta(days=article.published_date.weekday())
            week_key = week_start.strftime('%Y-%m-%d')
            weekly_trends[week_key] += 1
        
        # 記事要約リスト（全記事を含める）
        article_summaries = []
        for article in articles:
            if article.summary and len(article.summary.strip()) > 10:
                article_summaries.append({
                    "title": article.title,
                    "summary": article.summary,
                    "url": article.url,
                    "source": article.source,
                    "published_date": article.published_date.isoformat(),
                    "tags": article.tags or []
                })
        
        summary = f"トレンド分析: {start_dt.strftime('%Y年%m月%d日')}から{end_dt.strftime('%Y年%m月%d日')}までの{len(articles)}件の記事を分析。"
        
        return {
            "data": {
                "daily_trends": dict(daily_trends),
                "weekly_trends": dict(weekly_trends),
                "article_summaries": article_summaries,
                "period": {
                    "start": start_dt.isoformat(),
                    "end": end_dt.isoformat()
                },
                "total_articles": len(articles)
            },
            "summary": summary
        }
    
    async def export_articles_csv(
        self,
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        source: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        user: Optional[User] = None
    ) -> str:
        """記事データをCSV形式でエクスポート"""
        
        # クエリ構築
        db_query = self.db.query(Article)
        
        if query:
            db_query = db_query.filter(
                or_(
                    Article.title.ilike(f"%{query}%"),
                    Article.content.ilike(f"%{query}%"),
                    Article.summary.ilike(f"%{query}%")
                )
            )
        
        if tags:
            for tag in tags:
                db_query = db_query.filter(Article.tags.any(tag))
        
        if source:
            db_query = db_query.filter(Article.source.ilike(f"%{source}%"))
        
        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            db_query = db_query.filter(Article.published_date >= start_dt)
        
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            db_query = db_query.filter(Article.published_date <= end_dt)
        
        articles = db_query.order_by(desc(Article.published_date)).all()
        
        # CSV作成
        output = io.StringIO()
        writer = csv.writer(output)
        
        # ヘッダー
        writer.writerow([
            'ID',
            'タイトル',
            'URL',
            'ソース',
            '要約',
            'タグ',
            '公開日',
            '取得日',
            '作成者ID'
        ])
        
        # データ行
        for article in articles:
            writer.writerow([
                str(article.id),
                article.title or '',
                article.url or '',
                article.source or '',
                article.summary or '',
                ', '.join(article.tags) if article.tags else '',
                article.published_date.isoformat() if article.published_date else '',
                article.published_date.isoformat() if article.published_date else '',
                str(article.created_by) if article.created_by else ''
            ])
        
        return output.getvalue()
    
    async def get_analytics_overview(
        self,
        days: int = 30,
        user: Optional[User] = None
    ) -> Dict[str, Any]:
        """分析概要を取得（要約文含む）"""
        end_date = datetime.now(pytz.timezone(settings.TIMEZONE))
        start_date = end_date - timedelta(days=days)
        
        # 基本統計
        total_articles = self.db.query(Article).count()
        period_articles = self.db.query(Article).filter(
            Article.published_date >= start_date
        ).count()
        
        # 期間内の記事を取得（要約文含む）
        recent_articles = self.db.query(Article).filter(
            Article.published_date >= start_date
        ).order_by(Article.published_date.desc()).all()
        
        # 記事要約リスト（上位記事）
        article_summaries = []
        for article in recent_articles:
            if article.summary and len(article.summary.strip()) > 10:
                article_summaries.append({
                    "title": article.title,
                    "summary": article.summary,
                    "url": article.url,
                    "source": article.source,
                    "published_date": article.published_date.isoformat(),
                    "tags": article.tags or []
                })
        
        # 日別記事数
        daily_query = self.db.query(
            func.date(Article.published_date).label('date'),
            func.count().label('count')
        ).filter(
            Article.published_date >= start_date
        ).group_by(func.date(Article.published_date))
        
        daily_data = {str(row.date): row.count for row in daily_query.all()}
        
        # トップタグ
        articles_with_tags = self.db.query(Article).filter(
            Article.published_date >= start_date,
            Article.tags.isnot(None)
        ).all()
        
        tag_counter = Counter()
        for article in articles_with_tags:
            if article.tags:
                for tag in article.tags:
                    tag_counter[tag] += 1
        
        top_tags = tag_counter.most_common(10)
        
        # トップソース
        source_query = self.db.query(
            Article.source,
            func.count().label('count')
        ).filter(
            Article.published_date >= start_date,
            Article.source.isnot(None)
        ).group_by(Article.source).order_by(desc('count')).limit(10)
        
        top_sources = [(row.source, row.count) for row in source_query.all()]
        
        return {
            "period": {
                "days": days,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "statistics": {
                "total_articles": total_articles,
                "period_articles": period_articles,
                "daily_average": round(period_articles / days, 1)
            },
            "daily_data": daily_data,
            "top_tags": top_tags,
            "top_sources": top_sources,
            "article_summaries": article_summaries  # 全件を含める
        }
    
    async def get_tag_trends(
        self,
        days: int = 30,
        limit: int = 20,
        user: Optional[User] = None
    ) -> Dict[str, Any]:
        """タグトレンドを取得"""
        end_date = datetime.now(pytz.timezone(settings.TIMEZONE))
        start_date = end_date - timedelta(days=days)
        
        articles = self.db.query(Article).filter(
            Article.published_date >= start_date,
            Article.tags.isnot(None)
        ).all()
        
        # 日別タグ統計
        daily_tag_counts = defaultdict(lambda: Counter())
        
        for article in articles:
            date_str = article.published_date.strftime('%Y-%m-%d')
            if article.tags:
                for tag in article.tags:
                    daily_tag_counts[date_str][tag] += 1
        
        # トレンド計算（最近の増加率など）
        tag_trends = {}
        all_tags = Counter()
        
        for article in articles:
            if article.tags:
                for tag in article.tags:
                    all_tags[tag] += 1
        
        # 上位タグのみ処理
        top_tags = [tag for tag, _ in all_tags.most_common(limit)]
        
        for tag in top_tags:
            daily_counts = []
            for i in range(days):
                date = start_date + timedelta(days=i)
                date_str = date.strftime('%Y-%m-%d')
                count = daily_tag_counts[date_str][tag]
                daily_counts.append(count)
            
            tag_trends[tag] = {
                "total_count": all_tags[tag],
                "daily_counts": daily_counts,
                "average_daily": sum(daily_counts) / len(daily_counts)
            }
        
        return {
            "period": {
                "days": days,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "tag_trends": tag_trends
        }
    
    async def get_source_trends(
        self,
        days: int = 30,
        limit: int = 20,
        user: Optional[User] = None
    ) -> Dict[str, Any]:
        """ソーストレンドを取得"""
        end_date = datetime.now(pytz.timezone(settings.TIMEZONE))
        start_date = end_date - timedelta(days=days)
        
        # ソース別日別統計
        daily_query = self.db.query(
            func.date(Article.published_date).label('date'),
            Article.source,
            func.count().label('count')
        ).filter(
            Article.published_date >= start_date,
            Article.source.isnot(None)
        ).group_by(
            func.date(Article.published_date),
            Article.source
        )
        
        daily_source_counts = defaultdict(lambda: defaultdict(int))
        all_sources = Counter()
        
        for row in daily_query.all():
            date_str = str(row.date)
            source = row.source
            count = row.count
            
            daily_source_counts[date_str][source] = count
            all_sources[source] += count
        
        # 上位ソースのトレンド
        top_sources = [source for source, _ in all_sources.most_common(limit)]
        source_trends = {}
        
        for source in top_sources:
            daily_counts = []
            for i in range(days):
                date = start_date + timedelta(days=i)
                date_str = date.strftime('%Y-%m-%d')
                count = daily_source_counts[date_str][source]
                daily_counts.append(count)
            
            source_trends[source] = {
                "total_count": all_sources[source],
                "daily_counts": daily_counts,
                "average_daily": sum(daily_counts) / len(daily_counts)
            }
        
        return {
            "period": {
                "days": days,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "source_trends": source_trends
        }
    
    async def generate_blog_report(
        self,
        report_type: str,
        report_data: Dict[str, Any],
        summary: str,
        title: str,
        user: Optional[User] = None,
        prompt_template_id: Optional[str] = None
    ) -> str:
        """分析データからブログ記事形式のレポートを生成"""
        
        print(f"=== LLM service is_available: {llm_service.is_available()} ===")
        if not llm_service.is_available():
            logger.warning("LLM service not available. Generating basic report.")
            logger.info(f"LLM service client status: {llm_service.client}")
            return self._generate_basic_blog_report(report_type, report_data, summary, title)
        
        print("=== LLM service is available, proceeding with template check ===")
        
        # カスタムプロンプトテンプレートを使用するかチェック
        custom_template = None
        logger.info(f"Checking for custom template: template_id={prompt_template_id}, user_id={user.id if user else 'None'}")
        
        if prompt_template_id and user:
            # まずユーザー作成のテンプレートを確認
            custom_template = self.db.query(PromptTemplate).filter(
                PromptTemplate.id == prompt_template_id,
                PromptTemplate.created_by == str(user.id)  # 明示的に文字列に変換
                # template_type条件を削除してより柔軟に
            ).first()
            
            if custom_template:
                logger.info(f"Found user custom template: {custom_template.name}")
            else:
                logger.warning(f"User custom template not found: template_id={prompt_template_id}, user_id={user.id}, type={type(user.id)}")
                # デフォルトテンプレートもチェック
                default_template = self.db.query(PromptTemplate).filter(
                    PromptTemplate.id == prompt_template_id,
                    PromptTemplate.created_by == "system-default-user-id"
                ).first()
                if default_template:
                    logger.info(f"Using default template instead: {default_template.name}")
                    custom_template = default_template
                else:
                    # 最後にテンプレートIDだけで検索
                    any_template = self.db.query(PromptTemplate).filter(
                        PromptTemplate.id == prompt_template_id
                    ).first()
                    if any_template:
                        logger.info(f"Found template by ID only: {any_template.name}, created_by={any_template.created_by}")
                        custom_template = any_template
                    else:
                        logger.error(f"No template found with ID: {prompt_template_id}")
        
        if custom_template:
            logger.info(f"Using template: {custom_template.name}, system_prompt length: {len(custom_template.system_prompt or '')}")
        else:
            logger.info("No custom template will be used, using default behavior")
        
        # レポートタイプに応じたコンテキストを構築
        report_context = self._build_report_context(report_type, report_data, summary)
        
        # プロンプト選択（カスタムテンプレート or デフォルト）
        if custom_template:
            # カスタムテンプレートを使用
            system_prompt = custom_template.system_prompt or custom_template.template or ""
            if custom_template.user_prompt_template:
                # ユーザープロンプトテンプレートがある場合は安全に置換
                try:
                    # 記事のURL一覧とタイトル一覧を抽出
                    article_summaries = report_data.get("data", {}).get("article_summaries", [])
                    article_urls = [article.get('url', '') for article in article_summaries]
                    article_titles = [article.get('title', '') for article in article_summaries]
                    
                    # 生のニュース記事データを作成（構造化されていないシンプルな形式）
                    raw_articles = []
                    for i, article in enumerate(article_summaries, 1):
                        raw_article = f"ニュース{i}: {article.get('title', 'タイトルなし')}\n"
                        raw_article += f"要約: {article.get('summary', '要約なし')}\n"
                        raw_article += f"URL: {article.get('url', 'URLなし')}\n"
                        if article.get('tags'):
                            raw_article += f"タグ: {', '.join(article.get('tags', []))}\n"
                        raw_articles.append(raw_article)
                    
                    articles_text = '\n'.join(raw_articles)
                    
                    # 日付情報を取得
                    period_info = report_data.get("data", {}).get('period', {})
                    start_date = period_info.get('start', '')
                    end_date = period_info.get('end', '')
                    
                    # 使用可能な変数を定義
                    template_vars = {
                        'title': title,
                        'report_context': report_context,
                        'report_type': report_type,
                        'datetime': datetime.now(pytz.timezone(settings.TIMEZONE)).strftime('%Y年%m月%d日 %H:%M'),
                        'summary': summary,
                        'content': report_context,
                        'data': str(report_data),
                        'news_data': articles_text,  # 生のニュースデータ
                        'articles': articles_text,   # 生の記事データ
                        'news_information': articles_text,  # 生のニュース情報
                        'article_urls': '\n'.join(article_urls),  # URL一覧
                        'article_titles': '\n'.join(article_titles),  # タイトル一覧
                        'article_count': len(article_summaries),  # 記事数
                        'start_date': start_date,  # 開始日
                        'end_date': end_date  # 終了日
                    }
                    
                    # テンプレートの変数を安全に置換
                    import re
                    template_text = custom_template.user_prompt_template
                    
                    # 利用可能な変数のみを置換（存在しない変数はそのまま残す）
                    for var_name, var_value in template_vars.items():
                        template_text = template_text.replace(f'{{{var_name}}}', str(var_value))
                    
                    # 残った変数は空文字に置換（エラー回避）
                    template_text = re.sub(r'\{[^}]+\}', '', template_text)
                    
                    # カスタムテンプレートをそのまま使用（ニュースデータの挿入はテンプレート側で制御）
                    prompt = template_text
                    
                except Exception as e:
                    logger.warning(f"Template formatting failed: {e}, using fallback")
                    # フォールバック: ニュースデータ付きシンプルなプロンプト
                    prompt = f"""
## 具体的なニュース情報が提供されています

以下は指定された期間のIT・AIニュース記事です：

{report_context}

---

上記のニュース情報を使って、タイトル「{title}」でレポートタイプ「{report_type}」の記事を作成してください。
"""
            else:
                # ユーザープロンプトテンプレートがない場合のシンプルな構成
                prompt = f"タイトル「{title}」で{report_type}レポートを作成してください。"
            
            model_name = custom_template.model_name
            max_tokens = custom_template.max_tokens
            temperature = custom_template.temperature
            
            logger.info(f"Using custom prompt template: {custom_template.name}")
            
        else:
            # デフォルトのプロンプトを使用
            system_prompt = "あなたは経験豊富なデータサイエンティスト兼ライターです。"
            
            prompt = f"""
以下のデータを分析して、AIやIT業界に興味のあるライト層読者向けに、
「3分で読める」わかりやすいトレンド記事を作成してください。

## 分析データ
{report_context}

## ターゲット読者
- AIに興味があるが専門家ではない一般の方
- 最新技術の動向を手軽に知りたいビジネスパーソン
- スマホで読むことが多い忙しい人たち

## 記事構成要件

### 1. タイトル: {title}

### 2. データサイエンティスト目線の注目TOP3
各トピックについて：
- 🥇/🥈/🥉 [トピック名]
- **実務で使えそう度：** ★★★★★（5段階）
- **技術インパクト度：** ★★★★★（5段階）
- **話題度：** XX回
- **★ 専門家の一言コメント**

## 文体・表現のルール
- 親しみやすい丁寧語で
- 専門用語は必ず説明を添える
- 数字を使って具体性を出す
- 実用性を重視

## 出力形式
Markdown形式で出力してください。

親しみやすく、でも専門性のある分析を心がけてください。
"""
            
            model_name = 'claude-3-7-sonnet-20250219'
            max_tokens = 2000
            temperature = 0.3

        try:
            print("=== About to call LLM API ===")
            # Claude APIでブログ記事を生成
            messages = [{"role": "user", "content": prompt}]
            
            # systemプロンプトを分離して送信
            system_to_send = None
            if custom_template and system_prompt:
                system_to_send = system_prompt
                logger.info(f"Using custom system prompt: {system_prompt[:100]}...")
            
            print(f"=== Calling _api_call_with_retry with model: {model_name} ===")
            response = llm_service._api_call_with_retry(
                model=model_name,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_to_send
            )
            print("=== API call completed successfully ===")
            
            blog_content = llm_service.extract_text_from_response(response)
            
            # マークダウンの開始・終了タグを削除
            blog_content = blog_content.replace('```markdown', '').replace('```', '')
            blog_content = blog_content.strip()
            
            logger.info(f"Generated blog report for {report_type}")
            return blog_content
            
        except Exception as e:
            logger.error(f"Error generating blog report: {e}")
            # API overloadの場合でもカスタムテンプレートを適用した基本レポートを生成
            if custom_template:
                logger.info("Using custom template for fallback basic report")
                return self._generate_basic_blog_report_with_template(report_type, report_data, summary, title, custom_template)
            return self._generate_basic_blog_report(report_type, report_data, summary, title)
    
    def _build_report_context(self, report_type: str, report_data: Dict[str, Any], summary: str) -> str:
        """レポートタイプに応じた詳細なコンテキストを構築"""
        
        context = f"## レポートタイプ: {report_type}\n"
        context += f"## 分析概要: {summary}\n\n"
        
        data = report_data.get("data", {})
        
        # ニュース記事データ - 全記事を明確に提供
        if "article_summaries" in data:
            summaries = data["article_summaries"]
            if summaries:
                # 日付情報を取得
                period_info = data.get('period', {})
                start_date = period_info.get('start')
                end_date = period_info.get('end')
                
                context += f"## 具体的なIT・AIニュース情報（{len(summaries)}件）\n\n"
                
                if start_date and end_date:
                    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                    context += f"**対象期間**: {start_dt.strftime('%Y年%m月%d日')}から{end_dt.strftime('%Y年%m月%d日')}までのニュース\n\n"
                
                context += "### ニュース一覧：\n\n"
                
                for i, article in enumerate(summaries, 1):
                    # 日付を整形して表示
                    published_date = article.get('published_date', '')
                    if published_date:
                        try:
                            date_obj = datetime.fromisoformat(published_date.replace('Z', '+00:00'))
                            date_str = date_obj.strftime('%m月%d日')
                        except:
                            date_str = ''
                    else:
                        date_str = ''
                    
                    context += f"**ニュース{i}** ({date_str}): {article['title']}\n"
                    context += f"- **要約**: {article['summary']}\n"
                    
                    # 記事の詳細情報を取得（データベースから完全な記事情報を取得）
                    try:
                        from app.models.article import Article
                        full_article = self.db.query(Article).filter(Article.url == article['url']).first()
                        
                        # 記事の内容の一部も含める（最初の500文字）
                        if full_article and full_article.content and len(full_article.content.strip()) > 0:
                            content_text = full_article.content.strip()
                            # Markdown記法などを簡単にクリーンアップ
                            import re
                            content_text = re.sub(r'[#*`\[\]]+', '', content_text)
                            content_text = re.sub(r'\n+', ' ', content_text)
                            content_preview = content_text[:500] + "..." if len(content_text) > 500 else content_text
                            if len(content_preview.strip()) > 10:  # 意味のあるコンテンツがある場合のみ表示
                                context += f"- **記事内容の一部**: {content_preview}\n"
                        
                        # 公開日があれば追加
                        if full_article and full_article.published_date:
                            try:
                                pub_date = full_article.published_date.strftime('%Y年%m月%d日')
                                context += f"- **公開日**: {pub_date}\n"
                            except:
                                pass
                    except Exception as e:
                        logger.debug(f"Could not fetch full article content for {article['url']}: {e}")
                    
                    context += f"- **情報ソース**: {article['source']}\n"
                    if article.get('tags'):
                        context += f"- **関連技術・キーワード**: {', '.join(article['tags'][:5])}\n"
                    context += f"- **参照URL**: {article['url']}\n"
                    context += "\n"
                
                context += f"""
**重要な指示**: 
- 上記は具体的なIT・AIニュース情報（{len(summaries)}件）です
- 各ニュースには**要約**、**記事内容の一部**、**参照URL**が含まれています
- これらの詳細な情報を基にして、指定された形式で記事を作成してください
- 参照URLは必要に応じて記事内で言及してください
- 記事内容の一部を参考に、より具体的で詳細な分析を行ってください

"""
            else:
                context += "## 注意: 指定された期間にニュースが見つかりませんでした\n\n"
        
        # レポート固有データ
        if report_type == "summary":
            context += f"## 統計データ\n"
            context += f"- 総記事数: {data.get('total_articles', 0)}件\n"
            
            popular_tags = data.get('popular_tags', [])
            if popular_tags:
                context += "\n### 人気タグランキング\n"
                for i, (tag, count) in enumerate(popular_tags[:10], 1):
                    context += f"{i}. {tag}: {count}件\n"
            
            popular_sources = data.get('popular_sources', [])
            if popular_sources:
                context += "\n### 主要ソースランキング\n"
                for i, (source, count) in enumerate(popular_sources[:10], 1):
                    context += f"{i}. {source}: {count}件\n"
                    
            # 日別データ
            daily_data = data.get('daily_data', {})
            if daily_data:
                context += "\n### 日別記事数推移\n"
                sorted_days = sorted(daily_data.items())[-7:]  # 直近7日
                for date, count in sorted_days:
                    context += f"- {date}: {count}件\n"
                    
        elif report_type == "tag_analysis":
            tag_analysis = data.get('tag_analysis', {})
            context += f"## タグ分析データ\n"
            context += f"- 分析対象タグ数: {data.get('total_unique_tags', 0)}\n\n"
            context += "### 上位タグの詳細分析\n"
            for tag, info in list(tag_analysis.items())[:5]:
                context += f"#### 📊 {tag}\n"
                context += f"- 記事数: {info['count']}件\n"
                if 'sources' in info:
                    top_sources = info['sources'].most_common(3)
                    context += f"- 主要ソース: {', '.join([f'{s}({c}件)' for s, c in top_sources])}\n"
                context += "\n"
                
        elif report_type == "source_analysis":
            source_analysis = data.get('source_analysis', {})
            context += f"## ソース分析データ\n"
            context += f"- 分析対象ソース数: {data.get('total_unique_sources', 0)}\n\n"
            context += "### 上位ソースの詳細分析\n"
            for source, info in list(source_analysis.items())[:5]:
                context += f"#### 📰 {source}\n"
                context += f"- 記事数: {info['count']}件\n"
                if 'tags' in info:
                    top_tags = info['tags'].most_common(5)
                    context += f"- 主要タグ: {', '.join([f'{t}({c}件)' for t, c in top_tags])}\n"
                context += "\n"
                
        elif report_type == "trend_analysis":
            context += f"## トレンド分析データ\n"
            context += f"- 分析期間の記事数: {data.get('total_articles', 0)}\n\n"
            daily_trends = data.get('daily_trends', {})
            if daily_trends:
                context += "### 日別トレンド（直近7日）\n"
                sorted_trends = sorted(daily_trends.items())[-7:]
                for date, info in sorted_trends:
                    context += f"#### {date}\n"
                    context += f"- 記事数: {info['count']}件\n"
                    if 'tags' in info:
                        top_tags = info['tags'].most_common(3)
                        context += f"- 話題のタグ: {', '.join([f'{t}({c})' for t, c in top_tags])}\n"
                    context += "\n"
        
        return context
    
    def _generate_basic_blog_report_with_template(
        self,
        report_type: str, 
        report_data: Dict[str, Any], 
        summary: str, 
        title: str,
        custom_template: 'PromptTemplate'
    ) -> str:
        """カスタムテンプレートを適用した知的なブログレポート"""
        logger.info(f"Generating intelligent fallback report with custom template: {custom_template.name}")
        
        # データ分析
        data = report_data.get("data", {})
        
        # AIライト層向けのインテリジェントなレポート生成
        if "AIライト層向け" in custom_template.name:
            return self._generate_ai_light_user_report(title, data, summary, custom_template)
        
        # その他のテンプレート向け
        return self._generate_smart_fallback_report(title, report_type, data, summary, custom_template)
    
    def _generate_ai_light_user_report(self, title: str, data: Dict, summary: str, template: 'PromptTemplate') -> str:
        """AIライト層向けの知的なレポート生成"""
        
        # データから洞察を抽出
        # report_dataの構造に応じて記事数を取得
        report_data = data.get('data', {})
        article_count = report_data.get('total_articles', 0)
        
        # daily_trendsからも記事数を取得（フォールバック）
        if article_count == 0:
            daily_trends = report_data.get('daily_trends', {})
            article_count = sum(day_data.get('count', 0) for day_data in daily_trends.values())
        
        # top_tagsを抽出（daily_trendsから生成）
        top_tags = []
        daily_trends_data = report_data.get('daily_trends', {})
        if daily_trends_data:
            tag_counter = Counter()
            for day_data in daily_trends_data.values():
                if isinstance(day_data, dict) and 'tags' in day_data:
                    tag_counter.update(day_data['tags'])
            top_tags = tag_counter.most_common(5)
        else:
            # フォールバックで既存のtop_tagsを使用
            top_tags = data.get('top_tags', [])[:5]
        
        # AIライト層向けの親しみやすい記事を生成
        content = f"""# {title}

## 📱 3分で読めるAI・IT週刊トレンド

こんにちは！今週も面白いAI・ITトレンドをお届けします ✨

### 🔥 今週のハイライト

{self._create_friendly_summary(summary, article_count)}

### 📊 データで見る今週の動き

**分析した記事数**: {article_count}件
**注目キーワード**: {self._format_tags_for_light_users(top_tags)}

### 💡 今週の気になるポイント

{self._generate_light_user_insights(top_tags, data)}

### 🚀 来週への展望

{self._generate_outlook_for_light_users(top_tags)}

---

### 📚 用語解説コーナー
{self._generate_glossary_for_tags(top_tags)}

---

*このレポートは最新のAIトレンドを3分で理解できるよう、データサイエンティストの視点でわかりやすくまとめています*

**📱 スマホ最適化**: このレポートはスマホでの読みやすさを重視して作成されています
"""
        return content
    
    def _create_friendly_summary(self, summary: str, article_count: int) -> str:
        """親しみやすい要約を作成"""
        if article_count == 0:
            return "今週は記事データが少なめでしたが、AI・IT業界は相変わらず活発に動いています！"
        elif article_count < 5:
            return f"今週は{article_count}件の重要な記事をピックアップ。質の高い情報をお届けします 📰"
        else:
            return f"今週は{article_count}件の記事から、特に注目すべきトレンドを厳選してご紹介！"
    
    def _format_tags_for_light_users(self, top_tags) -> str:
        """ライト層向けのタグフォーマット"""
        if not top_tags:
            return "AI、機械学習、テクノロジー全般"
        
        friendly_tags = []
        for tag, count in top_tags:
            if 'Claude' in tag:
                friendly_tags.append(f"🤖 Claude AI ({count}件)")
            elif 'GitHub' in tag:
                friendly_tags.append(f"💻 GitHub ({count}件)")
            elif 'プロンプト' in tag:
                friendly_tags.append(f"💬 プロンプト技術 ({count}件)")
            else:
                friendly_tags.append(f"📌 {tag} ({count}件)")
        
        return "、".join(friendly_tags[:3])
    
    def _generate_light_user_insights(self, top_tags, data) -> str:
        """ライト層向けの洞察を生成"""
        insights = []
        
        for tag, count in top_tags[:3]:
            if 'Claude' in tag:
                insights.append("🤖 **Claude AI**: Anthropic社のAIアシスタントが話題に。ChatGPTのライバルとして注目度UP")
            elif 'GitHub' in tag:
                insights.append("💻 **GitHub**: 開発者のコラボレーションプラットフォームで新機能が登場")
            elif 'プロンプト' in tag:
                insights.append("💬 **プロンプトエンジニアリング**: AIとの対話スキルが重要に。誰でも学べる技術です")
        
        if not insights:
            insights.append("📈 **テクノロジー全般**: AI・IT分野で継続的な革新が進んでいます")
        
        return "\n\n".join(insights)
    
    def _generate_outlook_for_light_users(self, top_tags) -> str:
        """ライト層向けの展望を生成"""
        return """来週も引き続き、AI技術の進化と実用化が加速しそうです。
特に、日常生活により身近なAIサービスの登場に注目です！

**💡 おすすめアクション**: 今週のキーワードを覚えて、周りの人との会話で使ってみてください"""
    
    def _generate_glossary_for_tags(self, top_tags) -> str:
        """タグに基づく用語解説を生成"""
        glossary = []
        
        for tag, _ in top_tags[:2]:
            if 'Claude' in tag:
                glossary.append("**Claude**: Anthropic社が開発したAIアシスタント。自然な対話が得意")
            elif 'GitHub' in tag:
                glossary.append("**GitHub**: プログラマーがコードを共有・管理するプラットフォーム")
            elif 'プロンプト' in tag:
                glossary.append("**プロンプトエンジニアリング**: AIに指示を出すテクニック。上手な質問の仕方")
        
        return "\n".join(glossary) if glossary else "**AI**: 人工知能。コンピューターが人間のように考える技術"
    
    def _generate_smart_fallback_report(self, title: str, report_type: str, data: Dict, summary: str, template: 'PromptTemplate') -> str:
        """その他テンプレート向けのスマートフォールバック"""        
        return f"""# {title}

{summary}

{self._build_report_context(report_type, {"data": data}, summary)}
"""

    def _generate_basic_blog_report(
        self, 
        report_type: str, 
        report_data: Dict[str, Any], 
        summary: str, 
        title: str
    ) -> str:
        """基本的なブログレポート（LLMなしの場合）"""
        
        report_content = f"""# {title}

## はじめに

このレポートは{report_type}分析の結果をまとめたものです。

{summary}

## 分析結果

"""
        
        # レポートタイプに応じて内容を追加
        if report_type == "summary":
            data = report_data.get("data", {})
            report_content += f"**総記事数**: {data.get('total_articles', 0)}件\n\n"
            
            popular_tags = data.get('popular_tags', [])
            if popular_tags:
                report_content += "### 人気タグ\n\n"
                for i, (tag, count) in enumerate(popular_tags[:10], 1):
                    report_content += f"{i}. {tag} ({count}件)\n"
                report_content += "\n"
                
        report_content += f"""
## まとめ

{summary}

---
*生成日時: {datetime.now(pytz.timezone(settings.TIMEZONE)).strftime('%Y年%m月%d日 %H:%M')}*
"""
        
        return report_content
    
    async def save_report(
        self,
        title: str,
        report_type: str,
        content: str,
        parameters: Optional[Dict[str, Any]] = None,
        raw_data: Optional[Dict[str, Any]] = None,
        summary: Optional[str] = None,
        tags: Optional[List[str]] = None,
        user: Optional[User] = None
    ) -> SavedReport:
        """レポートをデータベースに保存"""
        
        now = datetime.now(pytz.timezone(settings.TIMEZONE))
        saved_report = SavedReport(
            title=title,
            report_type=report_type,
            content=content,
            parameters=make_json_serializable(parameters or {}),
            raw_data=make_json_serializable(raw_data or {}),
            summary=summary,
            tags=tags or [],
            created_by=str(user.id) if user else None,
            created_at=now,
            updated_at=now
        )
        
        self.db.add(saved_report)
        self.db.commit()
        self.db.refresh(saved_report)
        
        logger.info(f"Saved report: {title} (ID: {saved_report.id})")
        return saved_report
    
    def get_saved_reports(
        self,
        user: Optional[User] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[SavedReport]:
        """保存されたレポート一覧を取得"""
        query = self.db.query(SavedReport)
        
        if user:
            query = query.filter(SavedReport.created_by == user.id)
        
        query = query.order_by(SavedReport.created_at.desc()).offset(offset)
        
        if limit is not None:
            query = query.limit(limit)
            
        return query.all()
    
    def get_saved_report(self, report_id: str, user: Optional[User] = None) -> Optional[SavedReport]:
        """特定の保存されたレポートを取得"""
        query = self.db.query(SavedReport).filter(SavedReport.id == report_id)
        
        if user:
            query = query.filter(SavedReport.created_by == user.id)
        
        return query.first()
    
    def update_saved_report(
        self,
        report_id: str,
        updates: Dict[str, Any],
        user: Optional[User] = None
    ) -> Optional[SavedReport]:
        """保存されたレポートを更新"""
        report = self.get_saved_report(report_id, user)
        
        if not report:
            return None
        
        # 更新可能フィールドのみ適用
        allowed_fields = ['title', 'content', 'summary', 'tags']
        for field, value in updates.items():
            if field in allowed_fields and hasattr(report, field):
                setattr(report, field, value)
        
        report.updated_at = datetime.now(pytz.timezone(settings.TIMEZONE))
        self.db.commit()
        self.db.refresh(report)
        
        logger.info(f"Updated report: {report_id}")
        return report
    
    def delete_saved_report(self, report_id: str, user: Optional[User] = None) -> bool:
        """保存されたレポートを削除"""
        report = self.get_saved_report(report_id, user)
        
        if not report:
            return False
        
        self.db.delete(report)
        self.db.commit()
        
        logger.info(f"Deleted report: {report_id}")
        return True
    
    async def generate_technical_summary_report(
        self,
        keyword: str,
        date_range: Optional[Tuple[datetime, datetime]] = None,
        max_articles: int = 20,
        custom_template: Optional[PromptTemplate] = None
    ) -> str:
        """
        特定のキーワードの記事についての技術まとめレポートを生成
        
        Args:
            keyword: 検索キーワード
            date_range: 日付範囲のタプル (開始日, 終了日)
            max_articles: 対象記事の最大数
            custom_template: カスタムプロンプトテンプレート
        
        Returns:
            str: 生成された技術まとめレポート
        """
        try:
            # キーワードに関連する記事を検索
            query = self.db.query(Article).filter(
                or_(
                    Article.title.ilike(f"%{keyword}%"),
                    Article.content.ilike(f"%{keyword}%"),
                    Article.summary.ilike(f"%{keyword}%"),
                    Article.tags.op('LIKE')(f'%{keyword}%')
                )
            )
            
            # 日付範囲フィルタ
            if date_range:
                start_date, end_date = date_range
                query = query.filter(
                    and_(
                        Article.published_date >= start_date,
                        Article.published_date <= end_date
                    )
                )
            
            # 新しい順でソートし、制限を適用
            articles = query.order_by(desc(Article.published_date)).limit(max_articles).all()
            
            if not articles:
                logger.warning(f"No articles found for keyword: {keyword}")
                return f"「{keyword}」に関連する記事が見つかりませんでした。"
            
            logger.info(f"Found {len(articles)} articles for keyword: {keyword}")
            # デバッグ: 最初の記事の詳細を表示
            if articles:
                first_article = articles[0]
                logger.info(f"First article - Title: {first_article.title[:50]}..., Summary length: {len(first_article.summary) if first_article.summary else 0}")
                logger.info(f"First article - Tags: {first_article.tags}, Source: {first_article.source}")
            
            # 記事を整理・分析
            technical_content = self._analyze_technical_content(articles, keyword)
            
            # プロンプトテンプレートを使用してレポート生成
            if custom_template:
                return await self._generate_with_custom_template(
                    technical_content, custom_template, keyword
                )
            else:
                return await self._generate_default_technical_report(
                    technical_content, keyword
                )
                
        except Exception as e:
            logger.error(f"Error generating technical summary report: {e}")
            raise
    
    def _analyze_technical_content(self, articles: List[Article], keyword: str) -> Dict[str, Any]:
        """記事を分析して技術的な内容を整理"""
        
        # 技術要素の抽出
        technologies = set()
        concepts = set() 
        sources = defaultdict(int)
        timeline = []
        
        for article in articles:
            # ソース別の統計
            if article.source:
                sources[article.source] += 1
            
            # タイムラインデータ
            timeline.append({
                'date': article.published_date.strftime('%Y-%m-%d'),
                'title': article.title,
                'url': article.url,
                'source': article.source
            })
            
            # タグから技術要素を抽出
            if article.tags:
                for tag in article.tags:
                    if any(tech_keyword in tag.lower() for tech_keyword in 
                           ['api', 'ai', 'ml', 'python', 'javascript', 'react', 'node', 'docker', 'k8s', 'aws', 'gcp', 'azure']):
                        technologies.add(tag)
                    else:
                        concepts.add(tag)
        
        return {
            'keyword': keyword,
            'total_articles': len(articles),
            'date_range': {
                'start': min(a.published_date for a in articles).strftime('%Y-%m-%d'),
                'end': max(a.published_date for a in articles).strftime('%Y-%m-%d')
            },
            'technologies': sorted(list(technologies)),
            'concepts': sorted(list(concepts)),
            'sources': dict(sources),
            'timeline': sorted(timeline, key=lambda x: x['date'], reverse=True),
            'articles': [
                {
                    'title': a.title,
                    'url': a.url,
                    'summary': a.summary,
                    'source': a.source,
                    'date': a.published_date.strftime('%Y-%m-%d'),
                    'tags': a.tags or []
                }
                for a in articles
            ]
        }
    
    async def _generate_with_custom_template(
        self, 
        content: Dict[str, Any], 
        template: PromptTemplate, 
        keyword: str
    ) -> str:
        """カスタムテンプレートを使用してレポート生成"""
        try:
            # 記事の詳細情報を作成
            articles_detailed = self._format_articles_detailed(content['articles'])
            
            # テンプレート変数の準備
            template_vars = {
                'keyword': keyword,
                'articles_count': content['total_articles'],
                'date_range_start': content['date_range']['start'],
                'date_range_end': content['date_range']['end'],
                'technologies': ', '.join(content['technologies']) if content['technologies'] else '情報なし',
                'concepts': ', '.join(content['concepts']) if content['concepts'] else '情報なし',
                'articles_summary': self._format_articles_for_template(content['articles']),
                'articles_detailed': articles_detailed,
                'sources': ', '.join(content['sources'].keys()) if content['sources'] else '情報なし'
            }
            
            logger.info(f"Template variables prepared for keyword '{keyword}' with {content['total_articles']} articles")
            logger.info(f"Articles detailed length: {len(articles_detailed)}")
            
            # 記事データを必ず含めるためのベース情報
            article_data_section = f"""
## 分析対象の記事データ（{content['total_articles']}件）
{articles_detailed}

## 分析期間・概要
- 期間: {content['date_range']['start']} ～ {content['date_range']['end']}  
- 関連技術: {', '.join(content['technologies']) if content['technologies'] else '情報なし'}
- 主要概念: {', '.join(content['concepts']) if content['concepts'] else '情報なし'}
- 情報ソース: {', '.join(content['sources'].keys()) if content['sources'] else '情報なし'}
"""

            # ユーザープロンプトの生成
            if template.user_prompt_template:
                try:
                    # カスタムテンプレートを使用する場合でも記事データを必ず先頭に追加
                    formatted_template = template.user_prompt_template.format(**template_vars)
                    user_prompt = f"{article_data_section}\n\n## テンプレート指示\n{formatted_template}"
                    logger.info("Successfully formatted user prompt template with article data prepended")
                except Exception as format_error:
                    logger.warning(f"Template format error: {format_error}, using fallback with article data")
                    # フォールバック: 記事データ + 基本的なプロンプト
                    user_prompt = f"{article_data_section}\n\n上記の記事を分析して「{keyword}」について初心者向けの技術解説記事を作成してください。"
            else:
                # テンプレートがない場合も記事データを含む
                user_prompt = f"{article_data_section}\n\n上記の記事を分析して「{keyword}」について初心者向けの技術解説記事を作成してください。"
            
            logger.info(f"Final user prompt length: {len(user_prompt)}")
            
            # LLMサービスを使用してレポート生成
            response = self.llm_service._api_call_with_retry(
                model=template.model_name or 'claude-sonnet-4-20250514',
                system=template.system_prompt,
                messages=[
                    {
                        "role": "user", 
                        "content": user_prompt
                    }
                ],
                max_tokens=template.max_tokens or 4000,
                temperature=template.temperature or 0.3
            )
            
            return response.content[0].text
            
        except Exception as e:
            logger.error(f"Error with custom template: {e}")
            return await self._generate_default_technical_report(content, keyword)
    
    async def _generate_default_technical_report(
        self, 
        content: Dict[str, Any], 
        keyword: str
    ) -> str:
        """デフォルトの技術まとめレポートを生成"""
        
        system_prompt = """あなたは技術トレンド分析の専門家です。与えられた記事情報を基に、特定のキーワードに関する技術まとめレポートを作成してください。

以下の構成で分析してください：
1. 技術概要 - キーワードの現在の状況と重要性
2. 主要なトレンドと動向 - 記事から読み取れる技術の発展状況
3. 関連技術とツール - 関連する技術要素の整理
4. 実用事例と応用 - 具体的な活用事例
5. 今後の展望 - 技術の将来性と課題
6. 学習・導入のためのリソース - 参考記事の整理

技術的な正確性を重視し、具体的で実用的な情報を提供してください。"""

        articles_text = ""
        for i, article in enumerate(content['articles'][:15], 1):  # 最大15件
            summary_text = article.get('summary', '要約なし')
            # 記事の要約がない場合、タイトルから推測
            if not summary_text or len(summary_text.strip()) < 10:
                summary_text = f"記事タイトル: {article.get('title', 'タイトルなし')}"
            
            articles_text += f"""
{i}. 【{article.get('title', 'タイトルなし')}】({article.get('date', '日付不明')})
   ソース: {article.get('source', '不明')}
   要約: {summary_text[:300]}
   タグ: {', '.join(article.get('tags', []))}
   URL: {article.get('url', '')}
"""

        user_prompt = f"""
## 分析対象記事の詳細情報（{content['total_articles']}件）
{articles_text}

## 分析データ概要
- キーワード: {keyword}
- 対象記事数: {content['total_articles']}件
- 分析期間: {content['date_range']['start']} ～ {content['date_range']['end']}
- 関連技術: {', '.join(content['technologies']) if content['technologies'] else '情報なし'}
- 主要概念: {', '.join(content['concepts']) if content['concepts'] else '情報なし'}

## 指示
上記の具体的な記事情報を基に、「{keyword}」について技術者向けの包括的なまとめレポートを作成してください。
記事の内容、要約、タイトルを参考にして、実際のニュース記事に基づいた解説を行ってください。
"""

        try:
            response = self.llm_service._api_call_with_retry(
                model='claude-sonnet-4-20250514',
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                max_tokens=4000,
                temperature=0.3
            )
            
            return response.content[0].text
            
        except Exception as e:
            logger.error(f"Error generating technical report: {e}")
            raise
    
    def _format_articles_for_template(self, articles: List[Dict]) -> str:
        """テンプレート用に記事を整形"""
        formatted = []
        for article in articles[:10]:  # 最大10件
            formatted.append(
                f"- {article['title']} ({article['date']}) - {article['summary'][:100]}..."
            )
        return '\n'.join(formatted)
    
    def _format_articles_detailed(self, articles: List[Dict]) -> str:
        """詳細な記事情報を整形"""
        detailed = []
        for i, article in enumerate(articles[:15], 1):  # 最大15件
            content_preview = ""
            if article.get('summary'):
                content_preview = article['summary'][:500]  # より長い要約
            
            detailed_info = f"""
【記事 {i}】{article['title']}
日付: {article['date']}
ソース: {article.get('source', '不明')}
URL: {article.get('url', '')}
タグ: {', '.join(article.get('tags', []))}
内容: {content_preview}
"""
            detailed.append(detailed_info)
        return '\n'.join(detailed)
    
    def _create_fallback_prompt(self, keyword: str, content: Dict[str, Any], articles_detailed: str) -> str:
        """フォールバック用のプロンプトを作成"""
        return f"""
キーワード「{keyword}」に関する技術まとめレポートを作成してください。

## 分析データ概要
- 対象記事数: {content['total_articles']}件
- 分析期間: {content['date_range']['start']} ～ {content['date_range']['end']}
- 関連技術: {', '.join(content['technologies']) if content['technologies'] else '情報なし'}
- 主要概念: {', '.join(content['concepts']) if content['concepts'] else '情報なし'}
- 情報ソース: {', '.join(content['sources'].keys()) if content['sources'] else '情報なし'}

## 分析対象記事の詳細
{articles_detailed}

上記の記事を分析して、「{keyword}」について初心者にもわかりやすい技術まとめ記事を作成してください。
具体的な記事の内容と要約を参考にして、実際のニュース記事に基づいた解説を行ってください。
"""