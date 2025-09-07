import asyncio
import aiohttp
import xml.etree.ElementTree as ET
import logging
from typing import List, Dict, Optional, Set
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ArxivPaper:
    """arXivから取得した論文情報"""
    title: str
    url: str
    abstract: str
    published_date: datetime
    authors: List[str]
    categories: List[str]
    pdf_url: str
    arxiv_id: str


@dataclass
class ArxivSearchResult:
    """arXiv検索結果"""
    papers: List[ArxivPaper]
    total_found: int
    search_query: str
    target_date: Optional[datetime] = None
    error: Optional[str] = None


class ArxivService:
    """arXiv論文検索・取得サービス"""
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = None
        self.base_url = 'http://export.arxiv.org/api/query'
        
        # User-Agent設定
        self.headers = {
            'User-Agent': 'ITNewsManager/1.0 (arXiv Paper Collector; Educational Purpose)',
            'Accept': 'application/atom+xml, application/xml, text/xml, */*',
            'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
            'Connection': 'keep-alive',
        }
    
    async def __aenter__(self):
        """非同期コンテキストマネージャー開始"""
        connector = aiohttp.TCPConnector(
            limit=5,
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
    
    async def search_papers(
        self,
        categories: List[str] = None,
        max_results: int = 30,
        target_date: Optional[datetime] = None,
        days_back: int = 3,
        progress_callback: Optional[callable] = None
    ) -> ArxivSearchResult:
        """
        arXivから論文を検索・取得
        
        Args:
            categories: 検索対象カテゴリ（例: ['cs.AI', 'cs.LG', 'cs.CV']）
            max_results: 最大取得件数
            target_date: 対象日時（Noneの場合は現在日時）
            days_back: 対象日の何日前の論文を取得するか（デフォルト: 3日前）
            progress_callback: プログレス更新コールバック
            
        Returns:
            ArxivSearchResult: 検索結果
        """
        try:
            if not categories:
                categories = ['cs.AI', 'cs.LG', 'cs.CV', 'cs.CL', 'stat.ML']
            
            # 対象日の設定（3日前から現在まで）
            if target_date is None:
                target_date = datetime.now(timezone.utc)
            
            start_date = target_date - timedelta(days=days_back)
            end_date = target_date
            
            logger.info(f"arXiv検索開始: 期間 {start_date.date()} から {end_date.date()} まで")
            
            if progress_callback:
                progress_callback(0, 100, f"arXiv検索開始: カテゴリ {', '.join(categories)}")
            
            all_papers = []
            
            # カテゴリごとに検索
            for i, category in enumerate(categories):
                try:
                    if progress_callback:
                        progress = int((i / len(categories)) * 80)  # 80%まではカテゴリ処理
                        progress_callback(progress, 100, f"カテゴリ {category} を検索中...")
                    
                    category_papers = await self._search_category(
                        category, 
                        max_results_per_category=max(10, max_results // len(categories)),
                        start_date=start_date,
                        end_date=end_date
                    )
                    
                    all_papers.extend(category_papers)
                    
                    # レート制限
                    await asyncio.sleep(1.0)
                    
                except Exception as e:
                    logger.warning(f"カテゴリ {category} の検索でエラー: {e}")
                    continue
            
            if progress_callback:
                progress_callback(80, 100, "論文を日付でフィルタリング中...")
            
            # 日付でフィルタリング（期間内の論文）
            filtered_papers = []
            target_date_papers = 0
            
            for paper in all_papers:
                if start_date.date() <= paper.published_date.date() <= end_date.date():
                    filtered_papers.append(paper)
                    target_date_papers += 1
            
            # 重複除去（arXiv IDベース）
            unique_papers = []
            seen_ids = set()
            
            for paper in filtered_papers:
                if paper.arxiv_id not in seen_ids:
                    unique_papers.append(paper)
                    seen_ids.add(paper.arxiv_id)
            
            # 品質による並び替え（著者数が多い、要約が詳細なもの優先）
            def quality_score(paper):
                score = 0
                score += len(paper.authors) * 2  # 著者数による加点
                if paper.description:
                    score += min(len(paper.description.split()), 50) // 10  # 要約の詳細度による加点
                if len(paper.categories) > 1:
                    score += 1  # 複数カテゴリにまたがる論文に加点
                return score
            
            # スコア順でソート
            unique_papers.sort(key=quality_score, reverse=True)
            
            if progress_callback:
                progress_callback(100, 100, f"完了: {len(unique_papers)}件の論文を取得")
            
            logger.info(f"arXiv検索完了: 対象日 {target_date.date()} で {len(unique_papers)} 件取得")
            
            return ArxivSearchResult(
                papers=unique_papers,
                total_found=len(all_papers),
                search_query=f"categories: {', '.join(categories)}",
                target_date=target_date
            )
            
        except Exception as e:
            error_msg = f"arXiv検索エラー: {str(e)}"
            logger.exception(error_msg)
            
            if progress_callback:
                progress_callback(100, 100, f"エラー: {str(e)}")
            
            return ArxivSearchResult(
                papers=[],
                total_found=0,
                search_query="",
                error=error_msg
            )
    
    async def _search_category(
        self, 
        category: str, 
        max_results_per_category: int, 
        start_date: datetime,
        end_date: datetime
    ) -> List[ArxivPaper]:
        """単一カテゴリでの論文検索"""
        try:
            # クエリ構築
            query = f'cat:{category}'
            
            params = {
                'search_query': query,
                'start': 0,
                'max_results': 300,  # より多めに取得してフィルタリング
                'sortBy': 'relevance',  # 関連性の高い（人気のある）論文を優先
                'sortOrder': 'descending'
            }
            
            # HTTP リクエスト実行
            logger.info(f"arXiv APIリクエスト: {self.base_url} with params: {params}")
            async with self.session.get(self.base_url, params=params) as response:
                logger.info(f"arXiv API response status: {response.status}")
                if response.status != 200:
                    logger.warning(f"arXiv API error for category {category}: {response.status}")
                    return []
                
                xml_content = await response.text()
                logger.info(f"arXiv XML content length: {len(xml_content)}")
            
            # XML解析
            root = ET.fromstring(xml_content)
            entries = root.findall('{http://www.w3.org/2005/Atom}entry')
            logger.info(f"arXiv entries found for {category}: {len(entries)}")
            
            papers = []
            for entry in entries:
                try:
                    paper = self._parse_entry(entry)
                    if paper:
                        # 期間フィルタリング（3日前から現在まで）
                        if start_date.date() <= paper.published_date.date() <= end_date.date():
                            # 品質フィルタリング（著者数2人以上、タイトル長5単語以上）
                            if len(paper.authors) >= 2 and len(paper.title.split()) >= 5:
                                papers.append(paper)
                        
                        # 指定件数に達したら終了
                        if len(papers) >= max_results_per_category:
                            break
                            
                except Exception as e:
                    logger.warning(f"論文エントリ解析エラー: {e}")
                    continue
            
            logger.debug(f"カテゴリ {category}: {len(papers)} 件取得")
            return papers
            
        except Exception as e:
            logger.exception(f"カテゴリ {category} の検索でエラー")
            return []
    
    def _parse_entry(self, entry) -> Optional[ArxivPaper]:
        """XML エントリを論文オブジェクトに変換"""
        try:
            # 基本情報
            title_elem = entry.find('{http://www.w3.org/2005/Atom}title')
            title = title_elem.text.strip() if title_elem is not None else ""
            
            if not title:
                return None
            
            # URL とarXiv ID
            id_elem = entry.find('{http://www.w3.org/2005/Atom}id')
            url = id_elem.text if id_elem is not None else ""
            arxiv_id = url.split('/')[-1] if url else ""
            
            # PDF URL
            pdf_url = url.replace('/abs/', '/pdf/') + '.pdf' if url else ""
            
            # 要約
            summary_elem = entry.find('{http://www.w3.org/2005/Atom}summary')
            abstract = summary_elem.text.strip() if summary_elem is not None else ""
            
            # 公開日
            published_elem = entry.find('{http://www.w3.org/2005/Atom}published')
            if published_elem is not None:
                published_str = published_elem.text[:10]  # YYYY-MM-DD部分のみ
                published_date = datetime.strptime(published_str, '%Y-%m-%d')
                published_date = published_date.replace(tzinfo=timezone.utc)
            else:
                return None
            
            # 著者
            authors = []
            author_elems = entry.findall('{http://www.w3.org/2005/Atom}author')
            for author_elem in author_elems:
                name_elem = author_elem.find('{http://www.w3.org/2005/Atom}name')
                if name_elem is not None:
                    authors.append(name_elem.text.strip())
            
            # カテゴリ
            categories = []
            category_elems = entry.findall('{http://www.w3.org/2005/Atom}category')
            for cat_elem in category_elems:
                term = cat_elem.get('term')
                if term:
                    categories.append(term)
            
            return ArxivPaper(
                title=title,
                url=url,
                abstract=abstract[:500] + '...' if len(abstract) > 500 else abstract,
                published_date=published_date,
                authors=authors[:5],  # 最大5人まで
                categories=categories,
                pdf_url=pdf_url,
                arxiv_id=arxiv_id
            )
            
        except Exception as e:
            logger.warning(f"論文エントリ解析エラー: {e}")
            return None
    
    def papers_to_urls(self, papers: List[ArxivPaper]) -> List[str]:
        """論文リストからURLリストを抽出"""
        urls = []
        for paper in papers:
            if paper.url:
                urls.append(paper.url)
        return urls
    
    def papers_to_paper_info(self, papers: List[ArxivPaper]) -> List[Dict]:
        """論文リストを辞書リストに変換（デバッグ・表示用）"""
        paper_info = []
        for paper in papers:
            paper_info.append({
                'title': paper.title,
                'url': paper.url,
                'pdf_url': paper.pdf_url,
                'abstract': paper.abstract,
                'authors': paper.authors,
                'categories': paper.categories,
                'published_date': paper.published_date.isoformat(),
                'arxiv_id': paper.arxiv_id
            })
        return paper_info
    
    async def get_paper_details(self, arxiv_id: str) -> Optional[ArxivPaper]:
        """特定のarXiv IDの論文詳細を取得"""
        try:
            params = {
                'id_list': arxiv_id,
                'max_results': 1
            }
            
            async with self.session.get(self.base_url, params=params) as response:
                if response.status != 200:
                    return None
                
                xml_content = await response.text()
            
            root = ET.fromstring(xml_content)
            entry = root.find('{http://www.w3.org/2005/Atom}entry')
            
            if entry is not None:
                return self._parse_entry(entry)
            
            return None
            
        except Exception as e:
            logger.exception(f"論文詳細取得エラー (ID: {arxiv_id})")
            return None