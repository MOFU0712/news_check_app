import logging
from typing import List, Dict, Optional, Set
from sqlalchemy.orm import Session
from datetime import datetime
import uuid

from app.models.article import Article
from app.models.scraping_job import ScrapingJob
from app.models.user import User
from app.utils.web_scraper import ScrapedContent
from app.services.article_service import ArticleService
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

class ArticleIntegrationService:
    """記事統合・保存サービス"""
    
    def __init__(self, db: Session):
        self.db = db
        # ArticleServiceはstaticメソッドクラスなので、インスタンス化は不要
    
    async def process_scraping_results(
        self,
        scraping_job: ScrapingJob,
        scraping_results: List[ScrapedContent]
    ) -> Dict[str, List[str]]:
        """
        スクレイピング結果を処理して記事として保存
        
        Args:
            scraping_job: スクレイピングジョブ
            scraping_results: スクレイピング結果一覧
            
        Returns:
            処理結果（成功・失敗・重複のID一覧）
        """
        results = {
            "created_articles": [],
            "failed_urls": [],
            "duplicate_urls": [],
            "updated_articles": []
        }
        
        for scraped_content in scraping_results:
            try:
                if scraped_content.error:
                    results["failed_urls"].append(scraped_content.url)
                    continue
                
                # 記事処理
                result = await self._process_single_article(scraping_job, scraped_content)
                
                if result["action"] == "created":
                    results["created_articles"].append(result["article_id"])
                elif result["action"] == "duplicate":
                    results["duplicate_urls"].append(scraped_content.url)
                elif result["action"] == "updated":
                    results["updated_articles"].append(result["article_id"])
                else:
                    results["failed_urls"].append(scraped_content.url)
                    
            except Exception as e:
                logger.exception(f"Failed to process article {scraped_content.url}")
                results["failed_urls"].append(scraped_content.url)
        
        # 統計情報を更新
        await self._update_job_statistics(scraping_job, results)
        
        return results
    
    async def _process_single_article(
        self,
        scraping_job: ScrapingJob,
        scraped_content: ScrapedContent
    ) -> Dict[str, any]:
        """単一記事の処理"""
        
        # 既存記事チェック
        existing_article = await self._find_existing_article(scraped_content.url)
        
        if existing_article:
            if scraping_job.skip_duplicates_bool:
                return {
                    "action": "duplicate",
                    "article_id": str(existing_article.id),
                    "message": "Article already exists"
                }
            else:
                # 既存記事を更新
                updated_article = await self._update_existing_article(
                    existing_article, scraped_content, scraping_job
                )
                return {
                    "action": "updated",
                    "article_id": str(updated_article.id),
                    "message": "Article updated"
                }
        else:
            # 新規記事作成
            new_article = await self._create_new_article(scraped_content, scraping_job)
            return {
                "action": "created",
                "article_id": str(new_article.id),
                "message": "New article created"
            }
    
    async def _find_existing_article(self, url: str) -> Optional[Article]:
        """既存記事を検索"""
        return self.db.query(Article).filter(Article.url == url).first()
    
    async def _create_new_article(
        self,
        scraped_content: ScrapedContent,
        scraping_job: ScrapingJob
    ) -> Article:
        """新規記事を作成（AI要約・タグ生成統合）"""
        
        # AI要約・タグ生成の実行（すべての記事に対して統一的に実行）
        ai_summary = ""
        ai_primary_tag = ""
        ai_technologies = []
        
        if llm_service.is_available():
            try:
                # すべての記事に対してLLMで統一的な要約・タグ・技術キーワードを生成
                ai_summary, ai_primary_tag, ai_technologies = await llm_service.generate_summary_and_tags(
                    title=scraped_content.title or "",
                    content=scraped_content.content or ""
                )
                
                logger.info(f"AI processing completed for article: {scraped_content.url}")
                logger.info(f"  - Generated LLM summary: YES")
                logger.info(f"  - Generated tag: {ai_primary_tag}")
                logger.info(f"  - Detected technologies: {len(ai_technologies)} items")
                
            except Exception as e:
                logger.error(f"AI processing failed for article {scraped_content.url}: {e}")
                # フォールバック：LLM要約を優先し、失敗した場合は簡易要約生成
                ai_summary = self._generate_simple_summary(scraped_content.title, scraped_content.content)
                ai_technologies = []
        else:
            # LLMサービスが利用不可の場合のフォールバック処理
            logger.warning(f"LLM service not available for {scraped_content.url}, using simple summary generation")
            ai_summary = self._generate_simple_summary(scraped_content.title, scraped_content.content)
        
        # タグの処理（AI生成タグまたは従来の処理）
        if ai_primary_tag:
            tags = [ai_primary_tag]
        else:
            tags = self._process_tags(scraped_content, scraping_job)
        
        # 技術キーワードをタグに追加（重複除去）
        if ai_technologies:
            # 技術タグを追加（最大5個まで）
            tech_tags = ai_technologies[:5]
            all_tags = tags + [f"技術:{tech}" for tech in tech_tags]
            tags = list(dict.fromkeys(all_tags))  # 重複除去
        
        # 記事データの準備
        current_time = datetime.utcnow()
        article_data = {
            "title": scraped_content.title or "無題",
            "content": scraped_content.content or "",
            "url": scraped_content.url,
            "source": scraped_content.site_name or self._extract_domain(scraped_content.url),
            "summary": ai_summary,  # LLMで生成された要約を使用
            "tags": tags,
            "published_date": scraped_content.published_date or current_time,  # published_dateがNoneの場合はスクレイピング時刻を使用
            "scraped_date": current_time,
            "created_by": scraping_job.user_id
        }
        
        # 記事作成
        article = Article(**article_data)
        self.db.add(article)
        self.db.commit()
        self.db.refresh(article)
        
        logger.info(f"Created new article {article.id} from {scraped_content.url}")
        logger.info(f"  - Title: {article.title[:50]}...")
        logger.info(f"  - Tags: {len(article.tags)} items")
        logger.info(f"  - Summary: {len(article.summary or '')} chars")
        
        return article
    
    async def _update_existing_article(
        self,
        existing_article: Article,
        scraped_content: ScrapedContent,
        scraping_job: ScrapingJob
    ) -> Article:
        """既存記事を更新"""
        
        # 更新対象フィールドの決定
        updates = {}
        
        # タイトル更新（空でない場合）
        if scraped_content.title and scraped_content.title.strip():
            updates["title"] = scraped_content.title
        
        # コンテンツ更新（新しい方が長い場合）
        if (scraped_content.content and 
            len(scraped_content.content) > len(existing_article.content or "")):
            updates["content"] = scraped_content.content
        
        # サマリー更新（空の場合のみ）
        if not existing_article.summary and scraped_content.description:
            updates["summary"] = scraped_content.description
        
        # タグのマージ
        existing_tags = set(existing_article.tags or [])
        new_tags = set(self._process_tags(scraped_content, scraping_job))
        merged_tags = list(existing_tags.union(new_tags))[:15]  # 最大15個
        
        if merged_tags != existing_article.tags:
            updates["tags"] = merged_tags
        
        # 公開日時（空の場合のみ）
        if not existing_article.published_date and scraped_content.published_date:
            updates["published_date"] = scraped_content.published_date
        
        # 更新実行
        if updates:
            for key, value in updates.items():
                setattr(existing_article, key, value)
            
            existing_article.updated_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"Updated article {existing_article.id} with {len(updates)} fields")
        
        return existing_article
    
    def _process_tags(
        self,
        scraped_content: ScrapedContent,
        scraping_job: ScrapingJob
    ) -> List[str]:
        """タグを処理"""
        tags = set()
        
        # 既存キーワード
        if scraped_content.keywords:
            tags.update(scraped_content.keywords)
        
        # 自動生成タグ
        if scraping_job.auto_generate_tags_bool and scraped_content.auto_tags:
            tags.update(scraped_content.auto_tags)
        
        # タグの清浄化
        cleaned_tags = []
        for tag in tags:
            tag = tag.strip()
            if tag and len(tag) > 1 and len(tag) <= 50:
                cleaned_tags.append(tag)
        
        return cleaned_tags[:10]  # 最大10個
    
    def _extract_domain(self, url: str) -> str:
        """URLからドメイン名を抽出"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.replace('www.', '')
            return domain
        except:
            return "Unknown"
    
    def _generate_summary(self, content: str, max_length: int = 300) -> str:
        """コンテンツから要約を生成"""
        if not content:
            return ""
        
        # 改行を除去して先頭部分を取得
        summary = content.replace('\n', ' ').replace('\r', ' ')
        summary = ' '.join(summary.split())  # 連続する空白を除去
        
        if len(summary) <= max_length:
            return summary
        
        # 文の区切りで切る
        sentences = summary.split('。')
        result = ""
        
        for sentence in sentences:
            if len(result + sentence + "。") <= max_length:
                result += sentence + "。"
            else:
                break
        
        if not result:
            result = summary[:max_length] + "..."
        
        return result
    
    async def _update_job_statistics(
        self,
        scraping_job: ScrapingJob,
        results: Dict[str, List[str]]
    ):
        """ジョブ統計情報を更新"""
        scraping_job.created_article_ids = results["created_articles"]
        scraping_job.completed_urls = [
            url for url in scraping_job.urls 
            if url not in results["failed_urls"]
        ]
        scraping_job.failed_urls = [
            f"{url}: Processing failed" for url in results["failed_urls"]
        ]
        
        self.db.commit()
        
        logger.info(
            f"Job {scraping_job.id} statistics: "
            f"created={len(results['created_articles'])}, "
            f"updated={len(results['updated_articles'])}, "
            f"duplicate={len(results['duplicate_urls'])}, "
            f"failed={len(results['failed_urls'])}"
        )
    
    async def bulk_tag_articles(
        self,
        article_ids: List[str],
        tags_to_add: List[str],
        tags_to_remove: List[str] = None
    ) -> Dict[str, int]:
        """記事の一括タグ操作"""
        
        updated_count = 0
        failed_count = 0
        
        for article_id in article_ids:
            try:
                article = self.db.query(Article).filter(Article.id == article_id).first()
                if not article:
                    failed_count += 1
                    continue
                
                current_tags = set(article.tags or [])
                
                # タグ追加
                if tags_to_add:
                    current_tags.update(tags_to_add)
                
                # タグ削除
                if tags_to_remove:
                    current_tags.difference_update(tags_to_remove)
                
                # 更新
                article.tags = list(current_tags)[:15]  # 最大15個
                article.updated_at = datetime.utcnow()
                updated_count += 1
                
            except Exception as e:
                logger.exception(f"Failed to update tags for article {article_id}")
                failed_count += 1
        
        if updated_count > 0:
            self.db.commit()
        
        return {
            "updated": updated_count,
            "failed": failed_count
        }
    
    async def merge_duplicate_articles(
        self,
        primary_article_id: str,
        duplicate_article_ids: List[str]
    ) -> Dict[str, any]:
        """重複記事をマージ"""
        
        primary_article = self.db.query(Article).filter(
            Article.id == primary_article_id
        ).first()
        
        if not primary_article:
            raise ValueError(f"Primary article {primary_article_id} not found")
        
        merged_data = {
            "merged_articles": [],
            "deleted_articles": [],
            "updated_fields": []
        }
        
        for duplicate_id in duplicate_article_ids:
            try:
                duplicate_article = self.db.query(Article).filter(
                    Article.id == duplicate_id
                ).first()
                
                if not duplicate_article:
                    continue
                
                # データマージ
                if self._merge_article_data(primary_article, duplicate_article):
                    merged_data["updated_fields"].extend([
                        "content", "tags", "summary"
                    ])
                
                # 重複記事削除
                self.db.delete(duplicate_article)
                merged_data["deleted_articles"].append(duplicate_id)
                merged_data["merged_articles"].append({
                    "id": duplicate_id,
                    "title": duplicate_article.title,
                    "url": duplicate_article.url
                })
                
            except Exception as e:
                logger.exception(f"Failed to merge article {duplicate_id}")
        
        if merged_data["deleted_articles"]:
            primary_article.updated_at = datetime.utcnow()
            self.db.commit()
        
        return merged_data
    
    def _merge_article_data(self, primary: Article, duplicate: Article) -> bool:
        """記事データをマージ"""
        updated = False
        
        # より長いコンテンツを採用
        if (duplicate.content and 
            len(duplicate.content) > len(primary.content or "")):
            primary.content = duplicate.content
            updated = True
        
        # タグをマージ
        primary_tags = set(primary.tags or [])
        duplicate_tags = set(duplicate.tags or [])
        merged_tags = list(primary_tags.union(duplicate_tags))[:15]
        
        if merged_tags != primary.tags:
            primary.tags = merged_tags
            updated = True
        
        # より良いサマリーを採用
        if (not primary.summary and duplicate.summary):
            primary.summary = duplicate.summary
            updated = True
        
        return updated
    
    async def process_scraping_results_batch(
        self,
        scraping_job: ScrapingJob,
        scraping_results: List[ScrapedContent]
    ) -> Dict[str, List[str]]:
        """
        スクレイピング結果をバッチ処理（メモリ効率化版）
        
        Args:
            scraping_job: スクレイピングジョブ
            scraping_results: スクレイピング結果一覧（バッチ）
            
        Returns:
            処理結果（成功・失敗・重複のID一覧）
        """
        results = {
            "created_articles": [],
            "failed_urls": [],
            "duplicate_urls": [],
            "updated_articles": []
        }
        
        logger.info(f"Processing batch of {len(scraping_results)} scraping results")
        
        # バッチ内でのURL重複チェックを事前に実行
        batch_urls = [result.url for result in scraping_results if not result.error]
        if batch_urls:
            existing_articles = self.db.query(Article.url, Article.id).filter(
                Article.url.in_(batch_urls)
            ).all()
            existing_url_map = {article.url: str(article.id) for article in existing_articles}
        else:
            existing_url_map = {}
        
        for scraped_content in scraping_results:
            try:
                if scraped_content.error:
                    results["failed_urls"].append(scraped_content.url)
                    continue
                
                # バッチ処理用の軽量な重複チェック
                if scraped_content.url in existing_url_map:
                    results["duplicate_urls"].append(existing_url_map[scraped_content.url])
                    logger.debug(f"Duplicate URL found in batch: {scraped_content.url}")
                    continue
                
                # 記事作成処理（LLM要約生成付き）
                article = await self._create_article_from_scraped_content_batch(
                    scraped_content, scraping_job
                )
                
                if article:
                    self.db.add(article)
                    results["created_articles"].append(str(article.id))
                    logger.debug(f"Created article in batch: {article.title[:50]}...")
                else:
                    results["failed_urls"].append(scraped_content.url)
                
            except Exception as e:
                logger.error(f"Error processing scraped content in batch: {scraped_content.url}: {e}")
                results["failed_urls"].append(scraped_content.url)
        
        # バッチ処理の最後にコミット
        try:
            self.db.commit()
            logger.info(f"Batch integration complete: {len(results['created_articles'])} created, {len(results['duplicate_urls'])} duplicates, {len(results['failed_urls'])} failed")
        except Exception as e:
            logger.error(f"Error committing batch: {e}")
            self.db.rollback()
            # 失敗した場合、全URLを失敗扱いに
            for article_id in results["created_articles"]:
                results["failed_urls"].append(f"rollback_{article_id}")
            results["created_articles"] = []
        
        return results
    
    def _generate_simple_summary(self, title: str, content: str, max_length: int = 200) -> str:
        """タイトルと内容から簡易要約を生成（LLM使用不可時のフォールバック）"""
        if not content and not title:
            return "要約が設定されていません"
        
        # タイトルがある場合は、タイトルをベースに内容の要約を作成
        if title and content:
            # タイトルで始めて、内容の重要部分を追加
            summary_base = title
            
            # 内容から最初の数文を取得
            content_clean = content.replace('\n', ' ').replace('\r', ' ')
            content_clean = ' '.join(content_clean.split())  # 連続する空白を除去
            
            # 文の区切りで分割
            sentences = content_clean.split('。')
            if len(sentences) > 1:
                # 最初の1-2文を追加
                first_sentences = '。'.join(sentences[:2])
                if first_sentences and not first_sentences.endswith('。'):
                    first_sentences += '。'
                
                # タイトルと内容を組み合わせ
                combined = f"{summary_base}。{first_sentences}"
                
                # 長すぎる場合は調整
                if len(combined) <= max_length:
                    return combined
                else:
                    # タイトルのみに戻す
                    return summary_base if len(summary_base) <= max_length else summary_base[:max_length-3] + "..."
            else:
                return summary_base
        
        # タイトルのみの場合
        elif title:
            return title if len(title) <= max_length else title[:max_length-3] + "..."
        
        # 内容のみの場合
        else:
            return self._generate_summary(content, max_length)
    
    async def _create_article_from_scraped_content_batch(
        self,
        scraped_content: ScrapedContent,
        scraping_job: ScrapingJob
    ) -> Optional[Article]:
        """バッチ処理用の記事作成（LLM要約生成付き）"""
        try:
            # LLM要約生成
            summary = ""
            if llm_service.is_available():
                try:
                    summary = await llm_service.generate_news_summary(
                        title=scraped_content.title or "",
                        content=scraped_content.content or ""
                    )
                    logger.info(f"Generated LLM summary for batch article: {scraped_content.url}")
                except Exception as e:
                    logger.error(f"LLM summary generation failed in batch: {e}")
                    summary = self._generate_simple_summary(scraped_content.title, scraped_content.content)
            else:
                summary = self._generate_simple_summary(scraped_content.title, scraped_content.content)
            
            # タグ処理
            tags = self._process_tags(scraped_content, scraping_job)
            
            # 記事データの準備
            article = Article(
                title=scraped_content.title or "無題",
                content=scraped_content.content or "",
                url=scraped_content.url,
                source=scraped_content.site_name or self._extract_domain(scraped_content.url),
                summary=summary,
                tags=tags,
                published_date=scraped_content.published_date,
                scraped_date=datetime.utcnow(),
                created_by=scraping_job.user_id
            )
            
            return article
            
        except Exception as e:
            logger.error(f"Error creating article from scraped content in batch: {e}")
            return None