import logging
from typing import List, Optional, Tuple, Any
from anthropic import Anthropic, RateLimitError, APIError
from app.core.config import settings

logger = logging.getLogger(__name__)

class LLMService:
    """LLM統合サービス（Anthropic Claude）"""
    
    def __init__(self):
        """LLMサービスの初期化"""
        self.anthropic_api_key = settings.ANTHROPIC_API_KEY
        if not self.anthropic_api_key:
            logger.warning("ANTHROPIC_API_KEY not set. LLM features will be disabled.")
            self.client = None
        else:
            self.client = Anthropic(api_key=self.anthropic_api_key)
        
        # デフォルトタグリスト
        self.default_tags = [
            'ニュース', '新サービス', 'AIの活用', '技術解説', 'AIエージェント',
            'コーディング・開発支援AI', 'つくってみた・やってみた', 'AIと人間の未来',
            'プロンプトエンジニアリング', 'OpenAI', '新しいLLM', 'LLM新技術',
            'LLMの評価', 'LLMの性質', 'セキュリティ', 'ロボット・ドローン',
            '自動運転', 'DL新技術', '動画生成AI', '新技術', '科学技術',
            'RAG', '量子コンピュータ', 'AIと法律・規制', 'データセット',
            '通信技術', '音楽生成AI', '画像生成AI', 'マネジメント',
            'スキルアップ', '3D生成AI', '音声AI', '小規模言語モデル',
            'VR・AR', 'ハードウェア', 'web開発技術', 'ゲーム生成AI'
        ]
        
        # 技術キーワードリスト
        self.tech_keywords = [
            'Python', 'JavaScript', 'TypeScript', 'React', 'Vue.js', 'Angular',
            'Node.js', 'Django', 'Flask', 'FastAPI', 'PostgreSQL', 'MySQL',
            'MongoDB', 'Redis', 'Docker', 'Kubernetes', 'AWS', 'Azure',
            'GCP', 'TensorFlow', 'PyTorch', 'OpenAI', 'Claude', 'GPT',
            'ChatGPT', 'Gemini', 'LangChain', 'LlamaIndex', 'Hugging Face',
            'Transformers', 'BERT', 'GPT-4', 'Claude-3', 'Mistral',
            'Anthropic', 'OpenAI', 'Google', 'Meta', 'Microsoft',
            'GitHub', 'GitLab', 'Linux', 'Ubuntu', 'CentOS', 'Debian',
            'API', 'REST', 'GraphQL', 'WebSocket', 'gRPC', 'Microservices',
            'Machine Learning', 'Deep Learning', 'Neural Network',
            'Computer Vision', 'Natural Language Processing', 'NLP',
            'Reinforcement Learning', 'Generative AI', 'Diffusion Model',
            'Stable Diffusion', 'DALL-E', 'Midjourney', 'Runway',
            'RAG', 'Vector Database', 'Embeddings', 'Semantic Search',
            'Fine-tuning', 'LoRA', 'PEFT', 'Quantization', 'RLHF'
        ]
    
    def is_available(self) -> bool:
        """LLMサービスが利用可能かチェック"""
        return self.client is not None
    
    def extract_text_from_response(self, response: Any) -> str:
        """APIレスポンスからテキストを抽出"""
        if hasattr(response, 'content'):
            # Anthropic APIのレスポンス形式
            if isinstance(response.content, list) and len(response.content) > 0:
                first_block = response.content[0]
                if hasattr(first_block, 'text'):
                    return first_block.text
        return str(response)
    
    def _api_call_with_retry(self, model: str, messages: list, max_tokens: int = 1000, temperature: float = 0.3, max_retries: int = 3, system: str = None):
        """リトライ機能付きのAPI呼び出し"""
        import time
        
        # 最初のリクエスト前に少し待機してAPI制限を回避
        if hasattr(self, '_last_request_time'):
            elapsed = time.time() - self._last_request_time
            min_interval = 30.0  # 最小30秒間隔（超大幅延長）
            if elapsed < min_interval:
                wait_time = min_interval - elapsed
                logger.info(f"Rate limiting: waiting {wait_time:.1f}s before API call")
                time.sleep(wait_time)
        
        for attempt in range(max_retries):
            try:
                # APIリクエストパラメータを構築
                request_params = {
                    "model": model,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "messages": messages
                }
                
                # systemプロンプトがある場合は追加
                if system:
                    request_params["system"] = system
                
                response = self.client.messages.create(**request_params)
                
                # リクエスト時刻を記録
                self._last_request_time = time.time()
                
                return response
            except RateLimitError as e:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 45  # 指数バックオフ: 45秒, 90秒, 180秒
                    logger.warning(f"Rate limit hit, retrying in {wait_time} seconds... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    logger.error("Max retries reached for rate limit")
                    raise e
            except APIError as e:
                if "overloaded" in str(e).lower() and attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 60  # API overload の場合はより長く待機
                    logger.warning(f"API overloaded, retrying in {wait_time} seconds... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    logger.error(f"API error: {e}")
                    raise e
            except Exception as e:
                logger.error(f"Unexpected error in API call: {e}")
                raise e
    
    async def generate_news_summary(
        self,
        title: str,
        content: str
    ) -> str:
        """
        ニュース記事専用の要約を生成
        
        Args:
            title: 記事タイトル
            content: 記事本文
        
        Returns:
            生成された要約
        """
        if not self.is_available():
            logger.warning("LLM service not available. Returning empty summary.")
            return ""
        
        prompt = f"""
以下のニュース記事について、詳細な要約を生成してください。

タイトル: {title}
本文: {content}

要求仕様:
- ニュースまとめ記事用の簡潔な要約を日本語で1-2文程度、ですます調で記述してください
- 要約は箇条書きではなく文章で記述してください
- 記事の最も重要なポイントのみを簡潔にまとめてください
- 100文字以内で要点を伝えてください

要約:
"""
        
        try:
            response = self._api_call_with_retry(
                model='claude-sonnet-4-20250514',  # 最新のモデルを使用
                messages=[{
                    "role": "user",
                    "content": prompt
                }],
                max_tokens=200,
                temperature=0.3
            )
            
            response_text = self.extract_text_from_response(response)
            summary = response_text.strip()
            
            logger.info(f"Generated news summary for article: {title[:50]}...")
            return summary
            
        except Exception as e:
            logger.error(f"Error generating news summary: {e}")
            return ""

    async def generate_summary_and_tags(
        self,
        title: str,
        content: str,
        custom_tags: Optional[List[str]] = None
    ) -> Tuple[str, str, List[str]]:
        """
        記事の要約とタグを生成
        
        Args:
            title: 記事タイトル
            content: 記事本文
            custom_tags: カスタムタグリスト（省略時はデフォルトを使用）
        
        Returns:
            (summary, primary_tag, detected_technologies)
        """
        if not self.is_available():
            logger.warning("LLM service not available. Returning empty results.")
            return "", self.default_tags[0] if self.default_tags else "その他", []
        
        tag_list = custom_tags if custom_tags else self.default_tags
        available_tags = ", ".join(tag_list)
        
        # 技術キーワードの検出
        detected_techs = self.detect_technologies(title, content)
        
        # 新しいニュース要約生成メソッドを使用
        summary = await self.generate_news_summary(title, content)
        
        # タグ生成部分
        tag_prompt = f"""
以下のニュース記事について、最適なタグを選択してください。

タイトル: {title}
本文: {content[:1000]}  # 長すぎる場合は切り詰め

利用可能なタグ: {available_tags}

利用可能なタグの中から最も適切な1つだけを選択して、そのタグ名だけを回答してください。
"""
        
        try:
            tag_response = self._api_call_with_retry(
                model='claude-sonnet-4-20250514',  # タグ選択は高速なモデルで十分
                messages=[{
                    "role": "user",
                    "content": tag_prompt
                }],
                max_tokens=50,
                temperature=0
            )
            
            predicted_tag = self.extract_text_from_response(tag_response).strip()
            
            # タグがリストに含まれているかチェック
            if predicted_tag not in tag_list:
                predicted_tag = tag_list[0] if tag_list else "その他"
            
            logger.info(f"Generated summary and tag for article: {title[:50]}...")
            return summary, predicted_tag, detected_techs
            
        except Exception as e:
            logger.error(f"Error generating summary and tag: {e}")
            return summary, tag_list[0] if tag_list else "その他", detected_techs
    
    def detect_technologies(self, title: str, content: str) -> List[str]:
        """
        タイトルと本文から技術キーワードを検出
        
        Args:
            title: 記事タイトル
            content: 記事本文
        
        Returns:
            検出された技術キーワードのリスト
        """
        detected_techs = []
        text_to_search = f"{title} {content}".lower()
        
        # 正規化用の辞書を作成（小文字キー → 正規化名）
        normalized_dict = {}
        for keyword in self.tech_keywords:
            normalized_dict[keyword.lower()] = keyword
        
        for keyword_lower, normalized_name in normalized_dict.items():
            # 大文字小文字を区別しない検索
            if keyword_lower in text_to_search:
                detected_techs.append(normalized_name)
        
        # 重複を除去（順序を保持）
        unique_techs = list(dict.fromkeys(detected_techs))
        
        # 技術が検出されない場合は空リストを返す
        return unique_techs[:10]  # 最大10個まで
    
    async def generate_article_questions(
        self,
        title: str,
        content: str,
        summary: str = ""
    ) -> List[str]:
        """
        記事内容に基づいて関連する質問を生成
        
        Args:
            title: 記事タイトル
            content: 記事本文
            summary: 記事要約（あれば）
        
        Returns:
            生成された質問のリスト
        """
        if not self.is_available():
            logger.warning("LLM service not available. Returning empty questions.")
            return []
        
        article_text = f"タイトル: {title}\n要約: {summary}\n本文: {content[:1000]}"  # 長すぎる場合は切り詰め
        
        prompt = f"""
以下の記事について、読者が興味を持ちそうな質問を3つ生成してください。

{article_text}

以下の形式で回答してください：
[質問1]
(記事の内容に基づく具体的な質問)
[質問2]
(記事の内容に基づく具体的な質問)  
[質問3]
(記事の内容に基づく具体的な質問)

注意点:
- 質問は記事の内容で答えられるものにしてください
- 技術的な内容がある場合は技術に関する質問も含めてください
- それぞれの質問は1行で簡潔に
"""
        
        try:
            response = self._api_call_with_retry(
                model='claude-sonnet-4-20250514',
                messages=[{
                    "role": "user",
                    "content": prompt
                }],
                max_tokens=300,
                temperature=0.3
            )
            
            response_text = self.extract_text_from_response(response)
            
            # 質問を抽出
            questions = []
            for i in range(1, 4):
                question_start = response_text.find(f"[質問{i}]")
                if i < 3:
                    question_end = response_text.find(f"[質問{i+1}]")
                else:
                    question_end = len(response_text)
                
                if question_start != -1:
                    if question_end == -1:
                        question_end = len(response_text)
                    question = response_text[question_start + 5:question_end].strip()
                    if question:
                        questions.append(question)
            
            logger.info(f"Generated {len(questions)} questions for article: {title[:50]}...")
            return questions
            
        except Exception as e:
            logger.error(f"Error generating questions: {e}")
            return []
    
    async def answer_question_about_article(
        self,
        question: str,
        title: str,
        content: str,
        summary: str = ""
    ) -> str:
        """
        記事内容に基づいて質問に回答
        
        Args:
            question: 質問
            title: 記事タイトル
            content: 記事本文
            summary: 記事要約（あれば）
        
        Returns:
            質問への回答
        """
        if not self.is_available():
            logger.warning("LLM service not available. Cannot answer question.")
            return "LLMサービスが利用できないため、質問に回答できません。"
        
        article_text = f"タイトル: {title}\n要約: {summary}\n本文: {content}"
        
        prompt = f"""
以下の記事について、質問に答えてください。

記事:
{article_text}

質問: {question}

記事の内容に基づいて、日本語で簡潔に回答してください。記事に明確な情報がない場合は「記事にはその情報が含まれていません」と回答してください。
"""
        
        try:
            response = self._api_call_with_retry(
                model='claude-sonnet-4-20250514',
                messages=[{
                    "role": "user",
                    "content": prompt
                }],
                max_tokens=300,
                temperature=0
            )
            
            response_text = self.extract_text_from_response(response)
            
            logger.info(f"Answered question about article: {title[:50]}...")
            return response_text.strip()
            
        except Exception as e:
            logger.error(f"Error answering question: {e}")
            return "質問への回答中にエラーが発生しました。"

# グローバルインスタンス
llm_service = LLMService()