from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import logging

from app.db.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.prompt import PromptTemplate

logger = logging.getLogger(__name__)

router = APIRouter()

# スキーマ定義
class PromptTemplateResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    template_type: str
    system_prompt: str
    user_prompt_template: Optional[str]
    model_name: str
    max_tokens: int
    temperature: float
    created_at: str
    updated_at: str
    
class PromptTemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    template_type: str
    system_prompt: str
    user_prompt_template: Optional[str] = None
    model_name: str = 'claude-sonnet-4-20250514'
    max_tokens: int = 2000
    temperature: float = 0.3

class PromptTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    template_type: Optional[str] = None
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    model_name: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None

@router.get("/", response_model=List[PromptTemplateResponse])
def get_prompt_templates(
    template_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """プロンプトテンプレート一覧を取得"""
    logger.info(f"Getting templates for user {current_user.id}, type: {current_user.id.__class__.__name__}")
    
    # デフォルトテンプレート + ユーザーテンプレートを取得
    query = db.query(PromptTemplate).filter(
        (PromptTemplate.created_by == current_user.id) | 
        (PromptTemplate.created_by == "system-default-user-id")
    )
    
    if template_type:
        query = query.filter(PromptTemplate.template_type == template_type)
    
    templates = query.order_by(PromptTemplate.created_at.desc()).all()
    
    logger.info(f"Found {len(templates)} templates")
    
    return [
        PromptTemplateResponse(
            id=str(template.id),
            name=template.name,
            description=template.description,
            template_type=template.template_type or template.type or 'blog_report',
            system_prompt=template.system_prompt or template.template or '',
            user_prompt_template=template.user_prompt_template,
            model_name=template.model_name or 'claude-sonnet-4-20250514',
            max_tokens=template.max_tokens or 2000,
            temperature=template.temperature if template.temperature is not None else 0.3,
            created_at=template.created_at.isoformat(),
            updated_at=template.updated_at.isoformat()
        )
        for template in templates
    ]

@router.post("/", response_model=PromptTemplateResponse)
def create_prompt_template(
    template_data: PromptTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """プロンプトテンプレートを作成"""
    logger.info(f"Creating template for user {current_user.id}")
    logger.info(f"Template data: {template_data}")
    
    try:
        template = PromptTemplate(
            name=template_data.name,
            description=template_data.description,
            template_type=template_data.template_type,
            system_prompt=template_data.system_prompt,
            user_prompt_template=template_data.user_prompt_template,
            model_name=template_data.model_name,
            max_tokens=template_data.max_tokens,
            temperature=template_data.temperature,
            created_by=str(current_user.id),  # 明示的に文字列に変換
            # 互換性のため
            template=template_data.system_prompt,
            type=template_data.template_type
        )
        
        db.add(template)
        db.commit()
        db.refresh(template)
        
        logger.info(f"Template created successfully: {template.id}")
        
        return PromptTemplateResponse(
            id=str(template.id),
            name=template.name,
            description=template.description,
            template_type=template.template_type,
            system_prompt=template.system_prompt,
            user_prompt_template=template.user_prompt_template,
            model_name=template.model_name,
            max_tokens=template.max_tokens,
            temperature=template.temperature,
            created_at=template.created_at.isoformat(),
            updated_at=template.updated_at.isoformat()
        )
    except Exception as e:
        logger.error(f"Error creating template: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"テンプレート作成に失敗しました: {str(e)}")

@router.get("/{template_id}", response_model=PromptTemplateResponse)
def get_prompt_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """特定のプロンプトテンプレートを取得"""
    template = db.query(PromptTemplate).filter(
        PromptTemplate.id == template_id,
        PromptTemplate.created_by == current_user.id
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="プロンプトテンプレートが見つかりません")
    
    return PromptTemplateResponse(
        id=str(template.id),
        name=template.name,
        description=template.description,
        template_type=template.template_type,
        system_prompt=template.system_prompt,
        user_prompt_template=template.user_prompt_template,
        model_name=template.model_name,
        max_tokens=template.max_tokens,
        temperature=template.temperature,
        created_at=template.created_at.isoformat(),
        updated_at=template.updated_at.isoformat()
    )

@router.put("/{template_id}", response_model=PromptTemplateResponse)
def update_prompt_template(
    template_id: str,
    update_data: PromptTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """プロンプトテンプレートを更新"""
    logger.info(f"Updating template {template_id} for user {current_user.id}")
    
    template = db.query(PromptTemplate).filter(
        PromptTemplate.id == template_id,
        PromptTemplate.created_by == str(current_user.id)  # 明示的に文字列に変換
    ).first()
    
    if not template:
        logger.warning(f"Template not found or access denied: {template_id}")
        # デバッグ用に全テンプレートの所有者を確認
        all_templates = db.query(PromptTemplate).filter(PromptTemplate.id == template_id).all()
        for t in all_templates:
            logger.info(f"Template {t.id} created_by: {t.created_by} (type: {type(t.created_by)})")
            logger.info(f"Current user id: {current_user.id} (type: {type(current_user.id)})")
        raise HTTPException(status_code=404, detail="プロンプトテンプレートが見つかりません")
    
    try:
        # 更新データを適用
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(template, field, value)
            # 互換性のため、template_typeが更新された場合は古いtypeフィールドも更新
            if field == 'template_type':
                setattr(template, 'type', value)
            # 逆に、system_promptが更新された場合は古いtemplateフィールドも更新
            if field == 'system_prompt':
                setattr(template, 'template', value)
        
        db.commit()
        db.refresh(template)
        
        logger.info(f"Template updated successfully: {template.id}")
        
        return PromptTemplateResponse(
            id=str(template.id),
            name=template.name,
            description=template.description,
            template_type=template.template_type,
            system_prompt=template.system_prompt,
            user_prompt_template=template.user_prompt_template,
            model_name=template.model_name,
            max_tokens=template.max_tokens,
            temperature=template.temperature,
            created_at=template.created_at.isoformat(),
            updated_at=template.updated_at.isoformat()
        )
    except Exception as e:
        logger.error(f"Error updating template: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"テンプレート更新に失敗しました: {str(e)}")

@router.delete("/{template_id}")
def delete_prompt_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """プロンプトテンプレートを削除"""
    logger.info(f"Deleting template {template_id} for user {current_user.id}")
    
    template = db.query(PromptTemplate).filter(
        PromptTemplate.id == template_id,
        PromptTemplate.created_by == str(current_user.id)  # 明示的に文字列に変換
    ).first()
    
    if not template:
        logger.warning(f"Template not found or access denied: {template_id}")
        raise HTTPException(status_code=404, detail="プロンプトテンプレートが見つかりません")
    
    try:
        db.delete(template)
        db.commit()
        
        logger.info(f"Template deleted successfully: {template_id}")
        
        return {"message": "プロンプトテンプレートを削除しました"}
    except Exception as e:
        logger.error(f"Error deleting template: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"テンプレート削除に失敗しました: {str(e)}")