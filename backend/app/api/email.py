from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from datetime import datetime
import logging

from app.db.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.services.email_service import EmailService, EmailMessage, EmailConfig
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


class EmailTestRequest(BaseModel):
    to_emails: List[EmailStr]
    subject: str = "News Check App テストメール"
    test_content: str = "これはNews Check Appからのテストメールです。"


class EmailConfigRequest(BaseModel):
    smtp_host: str
    smtp_port: int = 587
    smtp_user: str
    smtp_password: str
    smtp_use_tls: bool = True
    from_email: str = ""
    from_name: str = "News Check App"


class ReportEmailRequest(BaseModel):
    to_emails: List[EmailStr]
    report_title: str
    report_content: str
    report_type: str = "test"


@router.post("/test")
async def send_test_email(
    request: EmailTestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """テストメールを送信"""
    try:
        # 環境変数からメールサービス初期化
        email_service = EmailService.from_env()
        
        # メール設定の検証
        if not await email_service.test_connection():
            raise HTTPException(
                status_code=400, 
                detail="メール設定が正しくないか、SMTP接続に失敗しました"
            )
        
        # テストメール作成
        html_content = f"""
        <html>
            <body>
                <h2>🧪 News Check App テストメール</h2>
                <p>こんにちは、{current_user.email}さん！</p>
                <p>{request.test_content}</p>
                <hr>
                <p><small>送信日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}</small></p>
            </body>
        </html>
        """
        
        message = EmailMessage(
            to_emails=request.to_emails,
            subject=request.subject,
            html_content=html_content,
            text_content=f"News Check App テストメール\n\n{request.test_content}\n\n送信日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}"
        )
        
        # メール送信
        success = await email_service.send_email(message)
        
        if not success:
            raise HTTPException(status_code=500, detail="メール送信に失敗しました")
        
        return {
            "message": "テストメールを送信しました",
            "sent_to": request.to_emails,
            "sent_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"テストメール送信エラー: {e}")
        raise HTTPException(status_code=500, detail=f"メール送信に失敗しました: {str(e)}")


@router.post("/test-connection")
async def test_email_connection(
    config: EmailConfigRequest,
    current_user: User = Depends(get_current_user)
):
    """指定した設定でメール接続をテスト"""
    try:
        email_config = EmailConfig(
            smtp_host=config.smtp_host,
            smtp_port=config.smtp_port,
            smtp_user=config.smtp_user,
            smtp_password=config.smtp_password,
            smtp_use_tls=config.smtp_use_tls,
            from_email=config.from_email or config.smtp_user,
            from_name=config.from_name
        )
        
        email_service = EmailService(email_config)
        success = await email_service.test_connection()
        
        if success:
            return {"message": "メール接続テスト成功", "status": "success"}
        else:
            return {"message": "メール接続テスト失敗", "status": "failed"}
            
    except Exception as e:
        logger.error(f"メール接続テストエラー: {e}")
        raise HTTPException(status_code=400, detail=f"接続テストに失敗しました: {str(e)}")


@router.post("/send-report")
async def send_report_email(
    request: ReportEmailRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """レポートメールを送信"""
    try:
        email_service = EmailService.from_env()
        
        # メール設定チェック
        if not await email_service.test_connection():
            raise HTTPException(
                status_code=400,
                detail="メール設定が正しくありません"
            )
        
        # レポートメール送信
        success = await email_service.send_report_email(
            to_emails=request.to_emails,
            report_title=request.report_title,
            report_content=request.report_content,
            report_type=request.report_type,
            generated_at=datetime.now()
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="レポートメール送信に失敗しました")
        
        return {
            "message": "レポートメールを送信しました",
            "report_title": request.report_title,
            "sent_to": request.to_emails,
            "sent_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"レポートメール送信エラー: {e}")
        raise HTTPException(status_code=500, detail=f"レポートメール送信に失敗しました: {str(e)}")


@router.get("/config/status")
async def get_email_config_status(
    current_user: User = Depends(get_current_user)
):
    """メール設定の状態を確認"""
    try:
        # 設定の存在チェック
        config_status = {
            "smtp_host": bool(settings.SMTP_HOST),
            "smtp_user": bool(settings.SMTP_USER),
            "smtp_password": bool(settings.SMTP_PASSWORD),
            "enable_email_reports": settings.ENABLE_EMAIL_REPORTS
        }
        
        # 接続テスト（設定がある場合のみ）
        connection_ok = False
        if all([settings.SMTP_HOST, settings.SMTP_USER, settings.SMTP_PASSWORD]):
            try:
                email_service = EmailService.from_env()
                connection_ok = await email_service.test_connection()
            except Exception as e:
                logger.warning(f"メール接続テスト中にエラー: {e}")
        
        return {
            "config_complete": all(config_status.values()),
            "connection_ok": connection_ok,
            "details": config_status,
            "message": "メール設定は完了しています" if all(config_status.values()) else "メール設定が不完全です"
        }
        
    except Exception as e:
        logger.error(f"メール設定状態確認エラー: {e}")
        raise HTTPException(status_code=500, detail=f"設定状態の確認に失敗しました: {str(e)}")