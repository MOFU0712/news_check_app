import asyncio
import logging
from typing import List, Dict, Optional, Set
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.models.scraping_job import ScrapingJob
from app.models.article import Article
from app.models.user import User
from app.utils.web_scraper import WebScraper, ScrapedContent
from app.utils.url_parser import URLParser
from app.core.background_tasks import task_manager, TaskStatus
from app.services.article_integration_service import ArticleIntegrationService

logger = logging.getLogger(__name__)

class ScrapingService:
    """スクレイピングサービス"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def create_and_start_scraping_job(
        self,
        user: User,
        urls_text: str,
        auto_generate_tags: bool = True,
        skip_duplicates: bool = True
    ) -> ScrapingJob:
        """スクレイピングジョブを作成・開始"""
        
        # URL解析
        parse_result = URLParser.parse_urls_from_text(urls_text)
        
        if not parse_result.valid_urls:
            raise ValueError("有効なURLが見つかりません")
        
        target_urls = parse_result.valid_urls
        
        # 重複チェック
        duplicate_urls = []
        if skip_duplicates:
            existing_urls: Set[str] = set(
                row.url for row in self.db.query(Article.url).all()
            )
            target_urls, duplicate_urls = URLParser.check_duplicates_with_existing(
                parse_result.valid_urls, existing_urls
            )
            
            if not target_urls:
                raise ValueError("スクレイピング対象の新規URLがありません")
        
        # スクレイピングジョブを作成
        job = ScrapingJob(
            user_id=user.id,
            urls=target_urls,
            auto_generate_tags_bool=auto_generate_tags,
            skip_duplicates_bool=skip_duplicates,
            total=len(target_urls),
            status="pending",
            skipped_urls=duplicate_urls  # スキップされたURLを保存
        )
        
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        
        # バックグラウンドタスクとして実行
        task_id = await task_manager.create_task(
            self._execute_scraping_job_task,
            str(job.id),
            task_id=str(job.id),
            total=len(target_urls),
            message=f"スクレイピング開始: {len(target_urls)}件のURL"
        )
        
        logger.info(f"Created scraping job {job.id} as background task {task_id}")
        return job
    
    async def _execute_scraping_job_task(self, job_id: str, progress_callback=None):
        """バックグラウンドタスクとしてスクレイピングジョブを実行"""
        from app.db.database import SessionLocal
        
        # 新しいDBセッションを作成（バックグラウンドタスク用）
        db = SessionLocal()
        
        try:
            job = db.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
            if not job:
                raise ValueError(f"Scraping job {job_id} not found")
            
            # ジョブ開始
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            job.progress = 0
            db.commit()
            
            if progress_callback:
                progress_callback(0, len(job.urls), "スクレイピング開始")
            
            # スクレイピング実行（バッチ処理と遅延制御付き）
            async with WebScraper() as scraper:
                scraping_results = []
                batch_size = 1  # 1件ずつ処理（最小に変更）
                delay_between_requests = 15.0  # リクエスト間隔（15秒に大幅延長）
                delay_between_batches = 60.0  # バッチ間の遅延（60秒に大幅延長）
                
                total_urls = len(job.urls)
                logger.info(f"Starting batch scraping for {total_urls} URLs with batch_size={batch_size}")
                
                for batch_start in range(0, total_urls, batch_size):
                    batch_end = min(batch_start + batch_size, total_urls)
                    batch_urls = job.urls[batch_start:batch_end]
                    
                    logger.info(f"Processing batch {batch_start//batch_size + 1}: URLs {batch_start+1}-{batch_end}")
                    
                    # バッチ内のURL処理
                    for i, url in enumerate(batch_urls):
                        current_index = batch_start + i
                        
                        try:
                            if progress_callback:
                                progress_callback(
                                    current_index, total_urls, 
                                    f"スクレイピング中 (バッチ {batch_start//batch_size + 1}): {url}",
                                    current_url=url,
                                    phase="scraping"
                                )
                            
                            # URLスクレイピング
                            result = await scraper.scrape_url(url)
                            scraping_results.append(result)
                            
                            # 進捗更新
                            job.progress = current_index + 1
                            db.commit()
                            
                            # リクエスト間の遅延
                            if i < len(batch_urls) - 1:  # バッチ内の最後のURL以外
                                logger.debug(f"Waiting {delay_between_requests}s before next request")
                                await asyncio.sleep(delay_between_requests)
                            
                            # メモリリーク防止：定期的なガベージコレクション
                            if (current_index + 1) % 5 == 0:
                                import gc
                                gc.collect()
                                logger.debug(f"Garbage collection performed at URL {current_index + 1}")
                            
                        except Exception as e:
                            error_result = ScrapedContent(url=url, error=str(e))
                            scraping_results.append(error_result)
                            logger.exception(f"Error scraping {url}")
                    
                    # バッチ間の遅延（最後のバッチ以外）
                    if batch_end < total_urls:
                        logger.info(f"Completed batch {batch_start//batch_size + 1}, waiting {delay_between_batches}s before next batch")
                        await asyncio.sleep(delay_between_batches)
                        
                        # メモリ使用量をログ出力
                        try:
                            import psutil
                            process = psutil.Process()
                            memory_mb = process.memory_info().rss / 1024 / 1024
                            logger.info(f"Memory usage after batch: {memory_mb:.1f} MB")
                        except ImportError:
                            pass
            
            # 記事統合処理（バッチ化）
            if progress_callback:
                progress_callback(
                    len(job.urls), len(job.urls),
                    "記事を保存・統合中...",
                    phase="integration"
                )
            
            # 統合処理もバッチ化してメモリ使用量を抑制
            integration_service = ArticleIntegrationService(db)
            
            # スクレイピング結果をバッチに分けて統合処理
            integration_batch_size = 1  # 統合処理のバッチサイズ（1件ずつ処理）
            all_integration_results = {
                'created_articles': [],
                'updated_articles': [],
                'duplicate_urls': [],
                'failed_urls': []
            }
            
            logger.info(f"Starting batch integration for {len(scraping_results)} results")
            
            for batch_start in range(0, len(scraping_results), integration_batch_size):
                batch_end = min(batch_start + integration_batch_size, len(scraping_results))
                batch_results = scraping_results[batch_start:batch_end]
                
                logger.info(f"Processing integration batch: results {batch_start+1}-{batch_end}")
                
                try:
                    batch_integration = await integration_service.process_scraping_results_batch(
                        job, batch_results
                    )
                    
                    # 結果をマージ
                    for key in all_integration_results.keys():
                        all_integration_results[key].extend(batch_integration.get(key, []))
                    
                    # バッチ間でDBセッションをリフレッシュ
                    db.commit()
                    
                    # 遅延を入れてリソース負荷を軽減（超大幅延長）
                    await asyncio.sleep(30.0)
                    
                except Exception as batch_error:
                    logger.error(f"Error in integration batch {batch_start+1}-{batch_end}: {batch_error}")
                    # 失敗したバッチのURLをfailed_urlsに追加
                    for result in batch_results:
                        all_integration_results['failed_urls'].append(result.url)
            
            integration_results = all_integration_results
            
            # ジョブ完了
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            
            if progress_callback:
                progress_callback(
                    len(job.urls), len(job.urls),
                    f"完了: 作成{len(integration_results['created_articles'])}件, "
                    f"更新{len(integration_results['updated_articles'])}件, "
                    f"重複{len(integration_results['duplicate_urls'])}件, "
                    f"失敗{len(integration_results['failed_urls'])}件",
                    phase="completed",
                    integration_results=integration_results
                )
            
            logger.info(f"Scraping job {job_id} completed with integration: {integration_results}")
            return integration_results
            
        except Exception as e:
            # ジョブ失敗
            if 'job' in locals():
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.now(timezone.utc)
                try:
                    db.commit()
                except Exception as commit_error:
                    logger.error(f"Failed to commit job failure status: {commit_error}")
            
            logger.exception(f"Scraping job {job_id} failed")
            
            # プログレスコールバックで失敗を通知
            if progress_callback:
                try:
                    progress_callback(
                        0, 0, 
                        f"エラーが発生しました: {str(e)}",
                        phase="failed"
                    )
                except Exception as callback_error:
                    logger.error(f"Progress callback failed: {callback_error}")
            
            raise
            
        finally:
            # リソースクリーンアップ
            try:
                if 'scraping_results' in locals():
                    del scraping_results  # メモリリークを防ぐ
                if 'integration_results' in locals():
                    del integration_results
                db.close()
            except Exception as cleanup_error:
                logger.error(f"Cleanup failed: {cleanup_error}")
    
    def _save_scraped_article_sync(self, db: Session, job: ScrapingJob, content: ScrapedContent) -> Optional[str]:
        """スクレイピング結果を記事として保存（同期版）"""
        try:
            # 重複チェック（念のため）
            existing = db.query(Article).filter(Article.url == content.url).first()
            if existing:
                logger.warning(f"Article with URL {content.url} already exists, skipping")
                return None
            
            # タグの準備
            tags = []
            if job.auto_generate_tags_bool and content.auto_tags:
                tags.extend(content.auto_tags)
            if content.keywords:
                tags.extend(content.keywords)
            
            # 重複除去
            tags = list(set(tags))[:10]  # 最大10個まで
            
            # 記事作成
            article = Article(
                title=content.title or "無題",
                content=content.content or "",
                url=content.url,
                source=content.site_name or "",
                summary="",  # スクレイピング時は要約を空にして、LLMで後から生成
                tags=tags,
                published_date=content.published_date,
                scraped_date=datetime.now(timezone.utc),
                created_by=job.user_id
            )
            
            db.add(article)
            db.commit()
            db.refresh(article)
            
            logger.info(f"Created article {article.id} from {content.url}")
            return article.id
            
        except Exception as e:
            logger.exception(f"Failed to save article for {content.url}")
            raise
    
    async def _execute_scraping_job(self, job_id: str):
        """スクレイピングジョブを実行"""
        job = self.db.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
        if not job:
            logger.error(f"Scraping job {job_id} not found")
            return
        
        try:
            # ジョブ開始
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            job.progress = 0
            self.db.commit()
            
            # スクレイピング実行
            async with WebScraper() as scraper:
                def progress_callback(current: int, total: int, url: str, result: ScrapedContent):
                    """プログレス更新コールバック"""
                    job.progress = current
                    if result.error:
                        job.failed_urls.append(f"{url}: {result.error}")
                    else:
                        job.completed_urls.append(url)
                    self.db.commit()
                
                # 複数URL並列スクレイピング
                results = await scraper.scrape_multiple_urls(
                    job.urls, 
                    progress_callback=progress_callback
                )
            
            # 結果を記事として保存
            created_article_ids = []
            for result in results:
                if not result.error and result.title:
                    try:
                        article_id = await self._save_scraped_article(job, result)
                        if article_id:
                            created_article_ids.append(str(article_id))
                    except Exception as e:
                        logger.exception(f"Failed to save article for {result.url}")
                        job.failed_urls.append(f"{result.url}: Failed to save - {str(e)}")
            
            # ジョブ完了
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            job.created_article_ids = created_article_ids
            self.db.commit()
            
            logger.info(f"Scraping job {job_id} completed. Created {len(created_article_ids)} articles.")
            
        except Exception as e:
            # ジョブ失敗
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)
            self.db.commit()
            
            logger.exception(f"Scraping job {job_id} failed")
    
    async def _save_scraped_article(self, job: ScrapingJob, content: ScrapedContent) -> Optional[str]:
        """スクレイピング結果を記事として保存"""
        try:
            # 重複チェック（念のため）
            existing = self.db.query(Article).filter(Article.url == content.url).first()
            if existing:
                logger.warning(f"Article with URL {content.url} already exists, skipping")
                return None
            
            # タグの準備
            tags = []
            if job.auto_generate_tags_bool and content.auto_tags:
                tags.extend(content.auto_tags)
            if content.keywords:
                tags.extend(content.keywords)
            
            # 重複除去
            tags = list(set(tags))[:10]  # 最大10個まで
            
            # 記事作成
            article = Article(
                title=content.title or "無題",
                content=content.content or "",
                url=content.url,
                source=content.site_name or "",
                summary="",  # スクレイピング時は要約を空にして、LLMで後から生成
                tags=tags,
                published_date=content.published_date,
                scraped_date=datetime.now(timezone.utc),
                created_by=job.user_id
            )
            
            self.db.add(article)
            self.db.commit()
            self.db.refresh(article)
            
            logger.info(f"Created article {article.id} from {content.url}")
            return article.id
            
        except Exception as e:
            logger.exception(f"Failed to save article for {content.url}")
            raise
    
    def get_scraping_job(self, job_id: str, user_id: str) -> Optional[ScrapingJob]:
        """スクレイピングジョブを取得"""
        return self.db.query(ScrapingJob).filter(
            ScrapingJob.id == job_id,
            ScrapingJob.user_id == user_id
        ).first()
    
    def get_user_scraping_jobs(
        self, 
        user_id: str, 
        limit: int = 20,
        offset: int = 0
    ) -> List[ScrapingJob]:
        """ユーザーのスクレイピングジョブ一覧を取得"""
        return self.db.query(ScrapingJob).filter(
            ScrapingJob.user_id == user_id
        ).order_by(
            ScrapingJob.created_at.desc()
        ).offset(offset).limit(limit).all()
    
    def cancel_scraping_job(self, job_id: str, user_id: str) -> bool:
        """スクレイピングジョブをキャンセル"""
        job = self.get_scraping_job(job_id, user_id)
        if not job:
            return False
        
        if job.status in ["pending", "running"]:
            job.status = "cancelled"
            job.completed_at = datetime.now(timezone.utc)
            job.error_message = "User cancelled"
            self.db.commit()
            return True
        
        return False
    
    def delete_scraping_job(self, job_id: str, user_id: str) -> bool:
        """スクレイピングジョブを削除"""
        job = self.get_scraping_job(job_id, user_id)
        if not job:
            return False
        
        # 実行中の場合はキャンセルしてから削除
        if job.status in ["pending", "running"]:
            self.cancel_scraping_job(job_id, user_id)
        
        self.db.delete(job)
        self.db.commit()
        return True