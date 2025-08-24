from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.article import Article
from app.services.llm_service import llm_service

router = APIRouter()

# スキーマ定義
class SummarizeRequest(BaseModel):
    title: str
    content: str
    
class SummarizeResponse(BaseModel):
    summary: str
    primary_tag: str
    technologies: List[str]

class QuestionGenerationRequest(BaseModel):
    article_id: str

class QuestionGenerationResponse(BaseModel):
    questions: List[str]

class QARequest(BaseModel):
    article_id: str
    question: str

class QAResponse(BaseModel):
    answer: str

class GenerateSummaryRequest(BaseModel):
    article_id: str

class GenerateSummaryResponse(BaseModel):
    summary: str
    success: bool

@router.post("/summarize", response_model=SummarizeResponse)
async def generate_summary_and_tags(
    request: SummarizeRequest,
    current_user: User = Depends(get_current_user)
):
    """記事の要約とタグを生成"""
    if not llm_service.is_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM service is not available. Please check ANTHROPIC_API_KEY configuration."
        )
    
    try:
        summary, primary_tag, technologies = await llm_service.generate_summary_and_tags(
            title=request.title,
            content=request.content
        )
        
        return SummarizeResponse(
            summary=summary,
            primary_tag=primary_tag,
            technologies=technologies
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate summary and tags: {str(e)}"
        )

@router.post("/articles/{article_id}/questions", response_model=QuestionGenerationResponse)
async def generate_article_questions(
    article_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """記事に関連する質問を生成"""
    if not llm_service.is_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM service is not available."
        )
    
    # 記事を取得
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found"
        )
    
    try:
        questions = await llm_service.generate_article_questions(
            title=article.title or "",
            content=article.content or "",
            summary=article.summary or ""
        )
        
        return QuestionGenerationResponse(questions=questions)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate questions: {str(e)}"
        )

@router.post("/articles/{article_id}/qa", response_model=QAResponse)
async def answer_article_question(
    article_id: str,
    request: QARequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """記事内容に基づいて質問に回答"""
    if not llm_service.is_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM service is not available."
        )
    
    # 記事を取得
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found"
        )
    
    try:
        answer = await llm_service.answer_question_about_article(
            question=request.question,
            title=article.title or "",
            content=article.content or "",
            summary=article.summary or ""
        )
        
        return QAResponse(answer=answer)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to answer question: {str(e)}"
        )

@router.post("/articles/{article_id}/generate-summary", response_model=GenerateSummaryResponse)
async def generate_and_save_summary(
    article_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """記事のLLM要約を生成して保存"""
    if not llm_service.is_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM service is not available."
        )
    
    # 記事を取得
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found"
        )
    
    try:
        # LLMで要約を生成
        summary = await llm_service.generate_news_summary(
            title=article.title or "",
            content=article.content or ""
        )
        
        # 記事の要約フィールドを更新
        article.summary = summary
        db.commit()
        db.refresh(article)
        
        return GenerateSummaryResponse(summary=summary, success=True)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate and save summary: {str(e)}"
        )

@router.get("/status")
async def llm_service_status():
    """LLMサービスの状態を確認"""
    return {
        "available": llm_service.is_available(),
        "service": "Anthropic Claude" if llm_service.is_available() else "Not configured"
    }