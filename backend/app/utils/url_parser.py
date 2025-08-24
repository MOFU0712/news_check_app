import re
import urllib.parse
from typing import List, Set, Tuple, Dict
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse
import logging

logger = logging.getLogger(__name__)

@dataclass
class URLParseResult:
    """URLパース結果"""
    valid_urls: List[str]
    invalid_urls: List[Tuple[str, str]]  # (url, reason)
    duplicate_urls: List[str]
    total_input_lines: int
    
    @property
    def summary(self) -> Dict[str, int]:
        return {
            "valid_count": len(self.valid_urls),
            "invalid_count": len(self.invalid_urls),
            "duplicate_count": len(self.duplicate_urls),
            "total_lines": self.total_input_lines
        }

class URLParser:
    """URLパース・バリデーション機能"""
    
    # サポートするプロトコル
    SUPPORTED_PROTOCOLS = {'http', 'https'}
    
    # URL抽出用の正規表現パターン
    URL_PATTERNS = [
        # 標準的なHTTP/HTTPS URL
        re.compile(r'https?://[^\s\]]+', re.IGNORECASE),
        # Markdown リンク形式 [text](url)
        re.compile(r'\[.*?\]\((https?://[^\)]+)\)', re.IGNORECASE),
        # HTML リンク形式
        re.compile(r'href=["\']?(https?://[^"\'>\s]+)', re.IGNORECASE),
    ]
    
    @staticmethod
    def parse_urls_from_text(text: str) -> URLParseResult:
        """
        テキストからURLを抽出・バリデーション
        
        Args:
            text: 入力テキスト（複数行対応）
            
        Returns:
            URLParseResult: パース結果
        """
        if not text or not text.strip():
            return URLParseResult([], [], [], 0)
        
        lines = text.strip().split('\n')
        total_lines = len(lines)
        
        raw_urls = set()
        invalid_urls = []
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            
            # 空行をスキップ
            if not line:
                continue
                
            # URLを抽出
            extracted_urls = URLParser._extract_urls_from_line(line)
            
            if not extracted_urls:
                # URLが見つからない場合
                if line:  # 空行でない場合のみ無効として記録
                    invalid_urls.append((line, f"Line {line_num}: Valid URL not found"))
                continue
            
            for url in extracted_urls:
                # URL正規化
                normalized_url = URLParser._normalize_url(url)
                if normalized_url:
                    raw_urls.add(normalized_url)
                else:
                    invalid_urls.append((url, f"Line {line_num}: Invalid URL format"))
        
        # 重複除去と既存記事チェック用のデータ準備
        valid_urls = list(raw_urls)
        
        return URLParseResult(
            valid_urls=valid_urls,
            invalid_urls=invalid_urls,
            duplicate_urls=[],  # 後でデータベースチェック時に設定
            total_input_lines=total_lines
        )
    
    @staticmethod
    def _extract_urls_from_line(line: str) -> List[str]:
        """1行からURLを抽出"""
        urls = []
        
        # パターンごとにURLを検索
        for pattern in URLParser.URL_PATTERNS:
            matches = pattern.findall(line)
            if matches:
                # パターンによって抽出方法が異なる
                if isinstance(matches[0], tuple):
                    # グループマッチの場合（Markdownリンクなど）
                    urls.extend([match[0] if isinstance(match, tuple) else match for match in matches])
                else:
                    urls.extend(matches)
        
        # パターンマッチしない場合、行全体がURLかチェック
        if not urls:
            # Markdown箇条書きの場合（- や * で始まる）
            cleaned_line = re.sub(r'^[-*+]\s*', '', line.strip())
            if URLParser._is_valid_url_format(cleaned_line):
                urls.append(cleaned_line)
            # 行全体がURLの場合
            elif URLParser._is_valid_url_format(line.strip()):
                urls.append(line.strip())
        
        return urls
    
    @staticmethod
    def _is_valid_url_format(url: str) -> bool:
        """URL形式の基本チェック"""
        if not url or len(url) < 10:
            return False
            
        try:
            parsed = urlparse(url)
            return (
                parsed.scheme.lower() in URLParser.SUPPORTED_PROTOCOLS and
                parsed.netloc and
                len(parsed.netloc) > 3
            )
        except Exception:
            return False
    
    @staticmethod
    def _normalize_url(url: str) -> str:
        """URLの正規化"""
        try:
            # 前後の空白を削除
            url = url.strip()
            
            # プロトコルが省略されている場合はhttpsを追加
            if not url.startswith(('http://', 'https://')):
                if url.startswith('//'):
                    url = 'https:' + url
                elif url.startswith('www.') or ('.' in url):
                    url = 'https://' + url
                else:
                    return None
            
            # 大文字のHTTPSを修正
            if url.startswith(('HTTPS://', 'HTTP://')):
                if url.startswith('HTTPS://'):
                    url = 'https://' + url[8:]
                elif url.startswith('HTTP://'):
                    url = 'http://' + url[7:]
            
            # URL解析
            parsed = urlparse(url)
            
            # 基本バリデーション
            if not parsed.scheme or not parsed.netloc:
                return None
            
            # スキームを小文字に
            scheme = parsed.scheme.lower()
            if scheme not in URLParser.SUPPORTED_PROTOCOLS:
                return None
            
            # ドメインを小文字に
            netloc = parsed.netloc.lower()
            
            # パスの正規化（末尾スラッシュの統一など）
            path = parsed.path
            if path and path != '/' and path.endswith('/'):
                path = path.rstrip('/')
            
            # 正規化されたURLを再構築
            normalized = urlunparse((
                scheme,
                netloc,
                path,
                parsed.params,
                parsed.query,
                parsed.fragment
            ))
            
            return normalized
            
        except Exception as e:
            logger.debug(f"URL normalization failed for {url}: {e}")
            return None
    
    @staticmethod
    def check_duplicates_with_existing(urls: List[str], existing_urls: Set[str]) -> Tuple[List[str], List[str]]:
        """
        既存URLとの重複チェック
        
        Args:
            urls: チェック対象のURL一覧
            existing_urls: 既存のURL一覧
            
        Returns:
            Tuple[新規URL一覧, 重複URL一覧]
        """
        new_urls = []
        duplicate_urls = []
        
        for url in urls:
            if url in existing_urls:
                duplicate_urls.append(url)
            else:
                new_urls.append(url)
        
        return new_urls, duplicate_urls
    
    @staticmethod
    def estimate_processing_time(url_count: int) -> str:
        """
        処理時間の推定
        
        Args:
            url_count: URL数
            
        Returns:
            推定処理時間の文字列
        """
        if url_count == 0:
            return "0秒"
        elif url_count <= 5:
            return f"約{url_count * 2}秒"
        elif url_count <= 20:
            return f"約{url_count // 2}分"
        elif url_count <= 50:
            return f"約{url_count // 3}分"
        else:
            return f"約{url_count // 4}分"