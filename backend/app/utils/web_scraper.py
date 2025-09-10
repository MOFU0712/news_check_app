import asyncio
import aiohttp
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup, NavigableString
from datetime import datetime
import re
import time

logger = logging.getLogger(__name__)

@dataclass
class ScrapedContent:
    """スクレイピング結果"""
    url: str
    title: Optional[str] = None
    content: Optional[str] = None
    description: Optional[str] = None
    site_name: Optional[str] = None
    published_date: Optional[datetime] = None
    keywords: List[str] = None
    auto_tags: List[str] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []
        if self.auto_tags is None:
            self.auto_tags = []

class WebScraper:
    """Webスクレイピングエンジン"""
    
    def __init__(
        self, 
        timeout: int = 60,  # タイムアウトを60秒に延長
        rate_limit_delay: float = 15.0,  # レート制限を15秒に大幅延長
        max_content_length: int = 10_000_000  # 10MB
    ):
        self.timeout = timeout
        self.rate_limit_delay = rate_limit_delay
        self.max_content_length = max_content_length
        self.session = None
        self.domain_last_request = {}  # ドメイン毎の最後のリクエスト時刻
        
        # User-Agent設定
        self.headers = {
            'User-Agent': 'ITNewsManager/1.0 (Educational Purpose; +https://github.com/example/news-manager)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    async def __aenter__(self):
        """非同期コンテキストマネージャー開始"""
        connector = aiohttp.TCPConnector(
            limit=5,  # 総接続数を5に制限
            limit_per_host=1,  # ホスト毎の接続数を1に制限
            keepalive_timeout=30,  # キープアライブタイムアウト
            enable_cleanup_closed=True  # 閉じられた接続の自動クリーンアップ
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
    
    async def scrape_url(self, url: str) -> ScrapedContent:
        """単一URLのスクレイピング"""
        try:
            # レート制限の適用
            await self._apply_rate_limit(url)
            
            # HTTPリクエスト実行
            async with self.session.get(url, allow_redirects=True) as response:
                # レスポンスチェック
                if response.status != 200:
                    return ScrapedContent(
                        url=url,
                        error=f"HTTP {response.status}: {response.reason}"
                    )
                
                # Content-Lengthチェック
                content_length = response.headers.get('content-length')
                if content_length and int(content_length) > self.max_content_length:
                    return ScrapedContent(
                        url=url,
                        error=f"Content too large: {content_length} bytes"
                    )
                
                # HTML取得（エンコーディング自動検出）
                html_content = await self._get_html_content_with_encoding(response)
                
                # HTMLパース・データ抽出
                scraped_content = await self._extract_content(url, html_content)
                return scraped_content
                
        except asyncio.TimeoutError:
            return ScrapedContent(url=url, error="Request timeout")
        except aiohttp.ClientError as e:
            return ScrapedContent(url=url, error=f"Client error: {str(e)}")
        except UnicodeDecodeError as e:
            return ScrapedContent(url=url, error=f"Encoding error: {str(e)}")
        except Exception as e:
            logger.exception(f"Unexpected error scraping {url}")
            return ScrapedContent(url=url, error=f"Unexpected error: {str(e)}")
    
    async def scrape_multiple_urls(
        self, 
        urls: List[str],
        progress_callback: Optional[callable] = None
    ) -> List[ScrapedContent]:
        """複数URLの並列スクレイピング"""
        results = []
        
        for i, url in enumerate(urls):
            try:
                result = await self.scrape_url(url)
                results.append(result)
                
                # プログレスコールバック
                if progress_callback:
                    progress_callback(i + 1, len(urls), url, result)
                    
            except Exception as e:
                logger.exception(f"Failed to scrape {url}")
                results.append(ScrapedContent(url=url, error=str(e)))
        
        return results
    
    async def _apply_rate_limit(self, url: str):
        """ドメイン別レート制限"""
        domain = urlparse(url).netloc
        
        if domain in self.domain_last_request:
            elapsed = time.time() - self.domain_last_request[domain]
            if elapsed < self.rate_limit_delay:
                await asyncio.sleep(self.rate_limit_delay - elapsed)
        
        self.domain_last_request[domain] = time.time()
    
    async def _get_html_content_with_encoding(self, response) -> str:
        """エンコーディング自動検出でHTML内容を取得"""
        try:
            # まず標準の方法で試行
            return await response.text()
        except UnicodeDecodeError:
            # エンコーディングエラーの場合、バイト取得して自動検出
            try:
                raw_content = await response.read()
                
                # chardetを使った自動検出
                try:
                    import chardet
                    detected = chardet.detect(raw_content)
                    encoding = detected.get('encoding', 'utf-8')
                    
                    logger.info(f"Auto-detected encoding: {encoding} (confidence: {detected.get('confidence', 0)})")
                    return raw_content.decode(encoding, errors='replace')
                    
                except ImportError:
                    # chardetが利用不可の場合は一般的な日本語エンコーディングを順次試行
                    encodings = ['utf-8', 'shift_jis', 'euc-jp', 'iso-2022-jp', 'cp932']
                    
                    for encoding in encodings:
                        try:
                            decoded_content = raw_content.decode(encoding)
                            logger.info(f"Successfully decoded with {encoding}")
                            return decoded_content
                        except UnicodeDecodeError:
                            continue
                    
                    # すべてのエンコーディングで失敗した場合は強制的にutf-8でデコード
                    logger.warning("All encoding attempts failed, using utf-8 with error replacement")
                    return raw_content.decode('utf-8', errors='replace')
                    
            except Exception as e:
                logger.error(f"Failed to decode response content: {e}")
                raise UnicodeDecodeError("Failed to decode response content")
    
    async def _extract_content(self, url: str, html_content: str) -> ScrapedContent:
        """HTMLからコンテンツを抽出"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 基本情報の抽出
            title = self._extract_title(soup)
            description = self._extract_description(soup)
            site_name = self._extract_site_name(soup, url)
            published_date = self._extract_published_date(soup)
            keywords = self._extract_keywords(soup)
            
            # メインコンテンツの抽出
            content = self._extract_main_content(soup)
            
            # 自動タグ生成
            auto_tags = self._generate_auto_tags(title, content, keywords, url)
            
            return ScrapedContent(
                url=url,
                title=title,
                content=content,
                description=description,
                site_name=site_name,
                published_date=published_date,
                keywords=keywords,
                auto_tags=auto_tags
            )
            
        except Exception as e:
            logger.exception(f"Content extraction failed for {url}")
            return ScrapedContent(url=url, error=f"Content extraction error: {str(e)}")
    
    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """タイトル抽出"""
        # Open Graphタイトル
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            return og_title['content'].strip()
        
        # Twitterカードタイトル
        twitter_title = soup.find('meta', attrs={'name': 'twitter:title'})
        if twitter_title and twitter_title.get('content'):
            return twitter_title['content'].strip()
        
        # 標準のtitleタグ
        title_tag = soup.find('title')
        if title_tag and title_tag.string:
            return title_tag.string.strip()
        
        # h1タグをフォールバック
        h1_tag = soup.find('h1')
        if h1_tag:
            return h1_tag.get_text().strip()
        
        return None
    
    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """説明文抽出"""
        # Open Graph description
        og_desc = soup.find('meta', property='og:description')
        if og_desc and og_desc.get('content'):
            return og_desc['content'].strip()
        
        # 標準のmeta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            return meta_desc['content'].strip()
        
        return None
    
    def _extract_site_name(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        """サイト名抽出"""
        # Open Graph site name
        og_site = soup.find('meta', property='og:site_name')
        if og_site and og_site.get('content'):
            return og_site['content'].strip()
        
        # ドメイン名をフォールバック
        domain = urlparse(url).netloc
        return domain.replace('www.', '')
    
    def _extract_published_date(self, soup: BeautifulSoup) -> Optional[datetime]:
        """公開日時抽出（複数のパターンに対応）"""
        import json
        from dateutil import parser as date_parser
        
        # JSON-LD structured data
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        for json_ld in json_ld_scripts:
            try:
                data = json.loads(json_ld.string)
                # データが配列の場合は各要素をチェック
                data_list = data if isinstance(data, list) else [data]
                
                for item in data_list:
                    if isinstance(item, dict):
                        # 複数のプロパティをチェック
                        for date_prop in ['datePublished', 'dateCreated', 'dateModified', 'publishDate']:
                            if date_prop in item and item[date_prop]:
                                try:
                                    date_str = str(item[date_prop]).replace('Z', '+00:00')
                                    return datetime.fromisoformat(date_str)
                                except:
                                    # dateutilでのパースも試行
                                    try:
                                        return date_parser.parse(str(item[date_prop]))
                                    except:
                                        continue
            except:
                continue
        
        # meta タグからの日付抽出（より多くのパターンを追加）
        date_selectors = [
            ('meta', {'property': 'article:published_time'}),
            ('meta', {'property': 'article:modified_time'}),
            ('meta', {'name': 'date'}),
            ('meta', {'name': 'publish_date'}),
            ('meta', {'name': 'publication_date'}),
            ('meta', {'name': 'pubdate'}),
            ('meta', {'name': 'created'}),
            ('meta', {'name': 'DC.date'}),
            ('meta', {'name': 'DC.Date'}),
            ('meta', {'name': 'dc.date'}),
            ('meta', {'name': 'sailthru.date'}),
            ('meta', {'property': 'bt:pubDate'}),
            ('time', {'datetime': True}),
            ('time', {'pubdate': True})
        ]
        
        for tag_name, attrs in date_selectors:
            tags = soup.find_all(tag_name, attrs)
            for tag in tags:
                date_str = tag.get('content') or tag.get('datetime')
                if date_str:
                    try:
                        # ISO形式での解析を試行
                        date_str_clean = str(date_str).replace('Z', '+00:00')
                        return datetime.fromisoformat(date_str_clean)
                    except:
                        try:
                            # dateutilでの柔軟なパース
                            return date_parser.parse(str(date_str))
                        except:
                            continue
        
        # OpenGraphやTwitterカードの日付
        og_date = soup.find('meta', property='og:updated_time') or soup.find('meta', property='og:published_time')
        if og_date and og_date.get('content'):
            try:
                return date_parser.parse(og_date['content'])
            except:
                pass
        
        # HTML5のtimeタグ（より広範な検索）
        time_tags = soup.find_all('time')
        for time_tag in time_tags:
            datetime_attr = time_tag.get('datetime')
            if datetime_attr:
                try:
                    return date_parser.parse(datetime_attr)
                except:
                    continue
            
            # timeタグ内のテキストからも抽出を試行
            time_text = time_tag.get_text().strip()
            if time_text:
                try:
                    return date_parser.parse(time_text)
                except:
                    continue
        
        # classやidに日付が含まれる要素を検索
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{4}/\d{2}/\d{2}',  # YYYY/MM/DD
            r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
        ]
        
        date_classes = ['date', 'published', 'publish-date', 'post-date', 'article-date', 'timestamp']
        for class_name in date_classes:
            elements = soup.find_all(attrs={'class': lambda x: x and any(class_name in c.lower() for c in x)})
            for element in elements:
                text = element.get_text().strip()
                if text:
                    try:
                        return date_parser.parse(text)
                    except:
                        continue
        
        return None
    
    def _extract_keywords(self, soup: BeautifulSoup) -> List[str]:
        """キーワード抽出"""
        keywords = []
        
        # meta keywords
        meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
        if meta_keywords and meta_keywords.get('content'):
            keywords.extend([k.strip() for k in meta_keywords['content'].split(',')])
        
        return keywords
    
    def _extract_main_content(self, soup: BeautifulSoup) -> Optional[str]:
        """メインコンテンツ抽出（HTML構造を保持したMarkdown形式）"""
        # 不要な要素を削除
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'advertisement']):
            tag.decompose()
        
        # コンテンツ抽出の優先順位
        content_selectors = [
            'article',
            '[role="main"]',
            'main',
            '.content',
            '.post-content',
            '.entry-content',
            '.article-content',
            '#content',
            '.main-content'
        ]
        
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                return self._html_to_markdown(content_elem)
        
        # フォールバック: body全体から抽出
        body = soup.find('body')
        if body:
            return self._html_to_markdown(body)
        
        return None
    
    def _clean_text(self, text: str) -> str:
        """テキストの清浄化"""
        if not text:
            return ""
        
        # 改行・タブの正規化
        text = re.sub(r'\s+', ' ', text)
        
        # 前後の空白を削除
        text = text.strip()
        
        # 長すぎるコンテンツは切り詰める
        if len(text) > 50000:
            text = text[:50000] + "..."
        
        return text
    
    def _generate_auto_tags(self, title: str, content: str, keywords: List[str], url: str = "") -> List[str]:
        """自動タグ生成"""
        auto_tags = set()
        
        # 既存キーワードをタグに追加
        auto_tags.update(keywords)
        
        # arXiv論文の検出
        url_lower = url.lower()
        if 'arxiv.org' in url_lower or '/abs/' in url_lower:
            auto_tags.add('論文')
            auto_tags.add('arXiv')
            logger.debug(f"arXiv論文を検出: {url}")
        
        # 技術用語の検出
        tech_terms = {
            'react': 'React',
            'vue': 'Vue.js',
            'angular': 'Angular',
            'python': 'Python',
            'javascript': 'JavaScript',
            'typescript': 'TypeScript',
            'node.js': 'Node.js',
            'fastapi': 'FastAPI',
            'django': 'Django',
            'flask': 'Flask',
            'docker': 'Docker',
            'kubernetes': 'Kubernetes',
            'aws': 'AWS',
            'gcp': 'Google Cloud',
            'azure': 'Microsoft Azure',
            'api': 'API',
            'rest': 'REST API',
            'graphql': 'GraphQL',
            'database': 'データベース',
            'sql': 'SQL',
            'postgresql': 'PostgreSQL',
            'mysql': 'MySQL',
            'mongodb': 'MongoDB',
            'redis': 'Redis',
            'ai': '人工知能',
            'machine learning': '機械学習',
            'deep learning': '深層学習',
            'neural network': 'ニューラルネットワーク',
            'transformer': 'Transformer',
            'llm': 'LLM',
            'gpt': 'GPT',
            'bert': 'BERT'
        }
        
        text_to_analyze = f"{title or ''} {content or ''}".lower()
        
        for term, tag in tech_terms.items():
            if term in text_to_analyze:
                auto_tags.add(tag)
        
        # 論文関連キーワードの検出（URLベース検出を補完）
        paper_terms = ['paper', 'research', 'study', 'algorithm', 'method', 'approach', 
                      '論文', '研究', 'アルゴリズム', 'モデル', '手法']
        if any(word in text_to_analyze for word in paper_terms) and 'arxiv' in text_to_analyze:
            auto_tags.add('論文')
        
        # カテゴリ推定
        if any(word in text_to_analyze for word in ['frontend', 'フロントエンド', 'ui', 'ux']):
            auto_tags.add('フロントエンド')
        
        if any(word in text_to_analyze for word in ['backend', 'バックエンド', 'server', 'サーバー']):
            auto_tags.add('バックエンド')
        
        if any(word in text_to_analyze for word in ['mobile', 'モバイル', 'ios', 'android']):
            auto_tags.add('モバイル')
        
        return list(auto_tags)[:10]  # 最大10個まで
    
    def _html_to_markdown(self, element) -> str:
        """HTML要素をMarkdown形式に変換（構造を保持）"""
        if not element:
            return ""
        
        markdown_content = []
        
        def process_element(elem, depth=0):
            """要素を再帰的に処理"""
            if isinstance(elem, NavigableString):
                # テキストノードの処理
                text = str(elem).strip()
                if text:
                    return text
                return ""
            
            if not elem.name:
                return ""
            
            tag_name = elem.name.lower()
            result = ""
            
            # 見出しタグの処理
            if tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                level = int(tag_name[1])
                text = elem.get_text().strip()
                if text:
                    result = f"\n{'#' * level} {text}\n\n"
            
            # 段落タグの処理
            elif tag_name == 'p':
                text = ""
                for child in elem.children:
                    text += process_element(child, depth + 1)
                text = text.strip()
                if text:
                    result = f"{text}\n\n"
            
            # リストの処理
            elif tag_name in ['ul', 'ol']:
                items = []
                for li in elem.find_all('li', recursive=False):
                    item_text = ""
                    for child in li.children:
                        item_text += process_element(child, depth + 1)
                    item_text = item_text.strip()
                    if item_text:
                        prefix = "-" if tag_name == 'ul' else f"{len(items) + 1}."
                        items.append(f"{prefix} {item_text}")
                
                if items:
                    result = "\n" + "\n".join(items) + "\n\n"
            
            # リンクの処理
            elif tag_name == 'a':
                text = ""
                for child in elem.children:
                    text += process_element(child, depth + 1)
                text = text.strip()
                href = elem.get('href', '')
                if text and href:
                    result = f"[{text}]({href})"
                elif text:
                    result = text
            
            # 強調の処理
            elif tag_name in ['strong', 'b']:
                text = ""
                for child in elem.children:
                    text += process_element(child, depth + 1)
                text = text.strip()
                if text:
                    result = f"**{text}**"
            
            # 斜体の処理
            elif tag_name in ['em', 'i']:
                text = ""
                for child in elem.children:
                    text += process_element(child, depth + 1)
                text = text.strip()
                if text:
                    result = f"*{text}*"
            
            # コードの処理
            elif tag_name == 'code':
                text = elem.get_text()
                if text:
                    result = f"`{text}`"
            
            # pre（コードブロック）の処理
            elif tag_name == 'pre':
                text = elem.get_text()
                if text:
                    result = f"\n```\n{text}\n```\n\n"
            
            # 引用の処理
            elif tag_name == 'blockquote':
                text = ""
                for child in elem.children:
                    text += process_element(child, depth + 1)
                text = text.strip()
                if text:
                    # 各行に > を追加
                    quoted_lines = [f"> {line}" for line in text.split('\n') if line.strip()]
                    result = "\n" + "\n".join(quoted_lines) + "\n\n"
            
            # 改行の処理
            elif tag_name == 'br':
                result = "\n"
            
            # 区切り線の処理
            elif tag_name == 'hr':
                result = "\n---\n\n"
            
            # divやspanなどのコンテナ要素
            elif tag_name in ['div', 'span', 'section', 'article']:
                text = ""
                for child in elem.children:
                    text += process_element(child, depth + 1)
                result = text
                
                # divの場合は段落区切りを追加
                if tag_name == 'div' and text.strip():
                    result += "\n"
            
            # その他の要素（インライン要素として処理）
            else:
                text = ""
                for child in elem.children:
                    text += process_element(child, depth + 1)
                result = text
            
            return result
        
        # 要素を処理
        content = process_element(element)
        
        # 後処理：連続する改行を整理
        content = re.sub(r'\n{3,}', '\n\n', content)
        content = content.strip()
        
        # 長すぎるコンテンツは切り詰める
        if len(content) > 50000:
            content = content[:50000] + "\n\n*（コンテンツが長すぎるため切り詰められました）*"
        
        return content