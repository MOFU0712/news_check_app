import asyncio
import aiohttp
import feedparser
import logging
from typing import List, Dict, Optional, Set, Union
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
import os
from pathlib import Path

from app.services.arxiv_service import ArxivService, ArxivPaper

logger = logging.getLogger(__name__)


@dataclass
class RSSArticle:
    """RSSから取得した記事情報"""
    title: str
    url: str
    published_date: Optional[datetime] = None
    description: Optional[str] = None
    source: Optional[str] = None


@dataclass
class RSSFeedResult:
    """RSSフィード処理結果"""
    feed_url: str
    articles: List[RSSArticle]
    error: Optional[str] = None
    last_updated: Optional[datetime] = None


class RSSService:
    """RSSフィード処理サービス"""
    
    def __init__(self, timeout: int = 30, hours_back: int = 24):
        self.timeout = timeout
        self.hours_back = hours_back
        self.session = None
        
        # User-Agent設定
        self.headers = {
            'User-Agent': 'ITNewsManager/1.0 (RSS Reader; Educational Purpose)',
            'Accept': 'application/rss+xml, application/xml, text/xml, */*',
            'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
            'Connection': 'keep-alive',
        }
    
    async def __aenter__(self):
        """非同期コンテキストマネージャー開始"""
        connector = aiohttp.TCPConnector(
            limit=10,
            limit_per_host=2,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=self.headers
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """非同期コンテキストマネージャー終了"""
        if self.session:
            await self.session.close()
    
    async def fetch_rss_feed(self, feed_url: str) -> RSSFeedResult:
        """単一のRSSフィードを取得・解析"""
        try:
            logger.info(f"Fetching RSS feed: {feed_url}")
            
            # RSSフィード取得
            async with self.session.get(feed_url, allow_redirects=True) as response:
                if response.status != 200:
                    return RSSFeedResult(
                        feed_url=feed_url,
                        articles=[],
                        error=f"HTTP {response.status}: {response.reason}"
                    )
                
                # XML内容を取得
                xml_content = await response.text()
                
            # feedparserでRSSを解析
            feed = feedparser.parse(xml_content)
            
            if feed.bozo and feed.bozo_exception:
                logger.warning(f"RSS feed parsing warning for {feed_url}: {feed.bozo_exception}")
            
            # 記事リストを構築（指定時間以内のもののみ）
            articles = []
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.hours_back)
            
            for entry in feed.entries:  # 全件をチェック
                try:
                    article = self._parse_rss_entry(entry, feed)
                    if article and article.url:  # URLが存在する記事のみ
                        # 指定時間以内の記事のみフィルタリング
                        if article.published_date and article.published_date >= cutoff_time:
                            articles.append(article)
                        elif not article.published_date:
                            # 公開日時が不明な場合は含める（最新フィードと仮定）
                            articles.append(article)
                except Exception as e:
                    logger.warning(f"Failed to parse RSS entry: {e}")
                    continue
            
            # フィードの最終更新日時
            last_updated = None
            if hasattr(feed.feed, 'updated_parsed') and feed.feed.updated_parsed:
                try:
                    import time
                    last_updated = datetime.fromtimestamp(
                        time.mktime(feed.feed.updated_parsed), 
                        timezone.utc
                    )
                except:
                    pass
            
            return RSSFeedResult(
                feed_url=feed_url,
                articles=articles,
                last_updated=last_updated
            )
            
        except asyncio.TimeoutError:
            return RSSFeedResult(
                feed_url=feed_url,
                articles=[],
                error="Request timeout"
            )
        except aiohttp.ClientError as e:
            return RSSFeedResult(
                feed_url=feed_url,
                articles=[],
                error=f"Client error: {str(e)}"
            )
        except Exception as e:
            logger.exception(f"Unexpected error fetching RSS feed {feed_url}")
            return RSSFeedResult(
                feed_url=feed_url,
                articles=[],
                error=f"Unexpected error: {str(e)}"
            )
    
    def _parse_rss_entry(self, entry, feed) -> Optional[RSSArticle]:
        """RSSエントリーを記事情報に変換"""
        try:
            # タイトル
            title = getattr(entry, 'title', '').strip()
            if not title:
                return None
            
            # URL
            url = getattr(entry, 'link', '').strip()
            if not url:
                return None
            
            # 説明文
            description = None
            if hasattr(entry, 'description'):
                description = entry.description.strip()
            elif hasattr(entry, 'summary'):
                description = entry.summary.strip()
            
            # 公開日時
            published_date = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                try:
                    import time
                    published_date = datetime.fromtimestamp(
                        time.mktime(entry.published_parsed), 
                        timezone.utc
                    )
                except:
                    pass
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                try:
                    import time
                    published_date = datetime.fromtimestamp(
                        time.mktime(entry.updated_parsed), 
                        timezone.utc
                    )
                except:
                    pass
            
            # ソース（フィード名）
            source = None
            if hasattr(feed.feed, 'title'):
                source = feed.feed.title.strip()
            
            return RSSArticle(
                title=title,
                url=url,
                published_date=published_date,
                description=description,
                source=source
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse RSS entry: {e}")
            return None
    
    async def fetch_multiple_feeds(
        self, 
        feed_urls: List[str],
        progress_callback: Optional[callable] = None
    ) -> List[RSSFeedResult]:
        """複数のRSSフィードを並列取得"""
        results = []
        
        for i, feed_url in enumerate(feed_urls):
            try:
                if progress_callback:
                    progress_callback(i, len(feed_urls), f"取得中: {feed_url}")
                
                result = await self.fetch_rss_feed(feed_url)
                results.append(result)
                
                # レート制限（短い間隔）
                await asyncio.sleep(1.0)
                
            except Exception as e:
                logger.exception(f"Failed to fetch RSS feed {feed_url}")
                results.append(RSSFeedResult(
                    feed_url=feed_url,
                    articles=[],
                    error=str(e)
                ))
        
        return results
    
    def read_rss_feeds_from_file(self, file_path: str) -> List[str]:
        """テキストファイルからRSSフィードURLリストを読み込み"""
        try:
            path = Path(file_path)
            if not path.exists():
                logger.error(f"RSS feeds file not found: {file_path}")
                return []
            
            feeds = []
            with open(path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    # 空行やコメント行をスキップ
                    if not line or line.startswith('#'):
                        continue
                    
                    # URLの基本的な検証
                    if line.startswith(('http://', 'https://')):
                        feeds.append(line)
                    else:
                        logger.warning(f"Invalid RSS URL in {file_path} line {line_num}: {line}")
            
            logger.info(f"Loaded {len(feeds)} RSS feed URLs from {file_path}")
            return feeds
            
        except Exception as e:
            logger.exception(f"Failed to read RSS feeds from file {file_path}")
            return []
    
    def extract_article_urls(self, results: List[RSSFeedResult]) -> List[str]:
        """RSSフィード結果から記事URLリストを抽出"""
        urls = []
        url_set: Set[str] = set()  # 重複除去用
        
        for result in results:
            if result.error:
                logger.warning(f"Skipping failed RSS feed {result.feed_url}: {result.error}")
                continue
            
            for article in result.articles:
                if article.url and article.url not in url_set:
                    urls.append(article.url)
                    url_set.add(article.url)
        
        logger.info(f"Extracted {len(urls)} unique article URLs from RSS feeds")
        return urls
    
    async def get_latest_articles_from_file(
        self, 
        file_path: str,
        progress_callback: Optional[callable] = None
    ) -> tuple[List[str], List[RSSFeedResult]]:
        """
        テキストファイルからRSSフィードを読み込み、最新記事URLを取得
        
        Returns:
            tuple: (記事URLリスト, RSSフィード結果リスト)
        """
        try:
            # RSSフィードURLを読み込み
            feed_urls = self.read_rss_feeds_from_file(file_path)
            if not feed_urls:
                logger.warning(f"No RSS feeds found in {file_path}")
                return [], []
            
            if progress_callback:
                progress_callback(0, len(feed_urls), f"開始: {len(feed_urls)}個のRSSフィードを処理")
            
            # RSSフィードを並列取得
            results = await self.fetch_multiple_feeds(feed_urls, progress_callback)
            
            # 記事URLを抽出
            article_urls = self.extract_article_urls(results)
            
            if progress_callback:
                progress_callback(
                    len(feed_urls), len(feed_urls), 
                    f"完了: {len(article_urls)}件の記事URLを取得"
                )
            
            return article_urls, results
            
        except Exception as e:
            logger.exception(f"Failed to get latest articles from file {file_path}")
            if progress_callback:
                progress_callback(0, 0, f"エラー: {str(e)}")
            return [], []
    
    async def get_latest_articles_with_arxiv(
        self, 
        file_path: str,
        include_arxiv: bool = True,
        arxiv_categories: List[str] = None,
        arxiv_max_results: int = 20,
        target_date: Optional[datetime] = None,
        progress_callback: Optional[callable] = None
    ) -> tuple[List[str], List[RSSFeedResult], List[ArxivPaper]]:
        """
        RSSフィードとarXiv論文の両方から最新記事・論文URLを取得
        
        Args:
            file_path: RSSフィードリストファイルのパス
            include_arxiv: arXiv論文を含めるかどうか
            arxiv_categories: arXiv検索カテゴリ
            arxiv_max_results: arXivから取得する最大論文数
            target_date: 対象日時（Noneの場合は現在日時）
            progress_callback: プログレス更新コールバック
        
        Returns:
            tuple: (全URLリスト, RSSフィード結果リスト, arXiv論文リスト)
        """
        try:
            if target_date is None:
                target_date = datetime.now(timezone.utc)
            
            total_steps = 100
            rss_progress_weight = 60 if include_arxiv else 100
            arxiv_progress_weight = 40 if include_arxiv else 0
            
            # RSS フィード取得
            if progress_callback:
                progress_callback(0, total_steps, "RSSフィードから記事を取得中...")
            
            def rss_progress(current, total, message):
                if progress_callback:
                    progress = int((current / max(total, 1)) * rss_progress_weight)
                    progress_callback(progress, total_steps, f"RSS: {message}")
            
            article_urls, rss_results = await self.get_latest_articles_from_file(
                file_path, rss_progress
            )
            
            arxiv_papers = []
            
            # arXiv論文取得
            if include_arxiv:
                if progress_callback:
                    progress_callback(rss_progress_weight, total_steps, "arXiv論文を検索中...")
                
                try:
                    async with ArxivService() as arxiv_service:
                        def arxiv_progress(current, total, message):
                            if progress_callback:
                                base_progress = rss_progress_weight
                                arxiv_progress = int((current / max(total, 1)) * arxiv_progress_weight)
                                progress_callback(base_progress + arxiv_progress, total_steps, f"arXiv: {message}")
                        
                        arxiv_result = await arxiv_service.search_papers(
                            categories=arxiv_categories or ['cs.AI', 'cs.LG', 'cs.CV', 'cs.CL'],
                            max_results=arxiv_max_results,
                            target_date=target_date,
                            days_back=3,  # 3日前の論文を対象
                            progress_callback=arxiv_progress
                        )
                        
                        if not arxiv_result.error:
                            arxiv_papers = arxiv_result.papers
                            arxiv_urls = arxiv_service.papers_to_urls(arxiv_papers)
                            article_urls.extend(arxiv_urls)
                            
                            logger.info(f"arXiv論文 {len(arxiv_papers)} 件を追加（対象日: {arxiv_result.target_date.date() if arxiv_result.target_date else 'N/A'}）")
                        else:
                            logger.warning(f"arXiv取得エラー: {arxiv_result.error}")
                
                except Exception as e:
                    logger.exception("arXiv論文取得でエラーが発生")
                    if progress_callback:
                        progress_callback(rss_progress_weight + arxiv_progress_weight, total_steps, f"arXivエラー: {str(e)}")
            
            if progress_callback:
                total_items = len(article_urls)
                arxiv_count = len(arxiv_papers)
                rss_count = total_items - arxiv_count
                progress_callback(
                    total_steps, total_steps, 
                    f"完了: RSS記事{rss_count}件 + arXiv論文{arxiv_count}件 = 合計{total_items}件"
                )
            
            return article_urls, rss_results, arxiv_papers
            
        except Exception as e:
            logger.exception(f"Failed to get articles with arXiv from file {file_path}")
            if progress_callback:
                progress_callback(0, 0, f"エラー: {str(e)}")
            return [], [], []