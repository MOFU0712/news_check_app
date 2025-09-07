import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import os
from jinja2 import Template

logger = logging.getLogger(__name__)


@dataclass
class EmailConfig:
    """メール設定"""
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_use_tls: bool = True
    from_email: str = ""
    from_name: str = "News Check App"


@dataclass 
class EmailMessage:
    """メールメッセージ"""
    to_emails: List[str]
    subject: str
    html_content: Optional[str] = None
    text_content: Optional[str] = None
    cc_emails: Optional[List[str]] = None
    bcc_emails: Optional[List[str]] = None
    attachments: Optional[List[Dict[str, Any]]] = None


class EmailService:
    """メール送信サービス"""
    
    def __init__(self, config: EmailConfig):
        self.config = config
        
    @classmethod
    def from_env(cls) -> 'EmailService':
        """設定からメール設定を読み込んで初期化"""
        from app.core.config import settings
        config = EmailConfig(
            smtp_host=settings.SMTP_HOST or 'smtp.gmail.com',
            smtp_port=settings.SMTP_PORT,
            smtp_user=settings.SMTP_USER or '',
            smtp_password=settings.SMTP_PASSWORD or '',
            smtp_use_tls=settings.SMTP_USE_TLS,
            from_email=settings.FROM_EMAIL or settings.SMTP_USER or '',
            from_name=settings.FROM_NAME
        )
        return cls(config)
    
    async def send_email(self, message: EmailMessage) -> bool:
        """メールを送信"""
        try:
            # メール設定の検証
            if not self._validate_config():
                logger.error("メール設定が不完全です")
                return False
            
            # MIMEメッセージを作成
            msg = self._create_mime_message(message)
            
            # SMTP接続とメール送信
            success = self._send_via_smtp(msg, message.to_emails, message.cc_emails, message.bcc_emails)
            
            if success:
                logger.info(f"メール送信成功: {message.subject} -> {', '.join(message.to_emails)}")
            else:
                logger.error(f"メール送信失敗: {message.subject}")
            
            return success
            
        except Exception as e:
            logger.exception(f"メール送信中にエラー: {e}")
            return False
    
    def _validate_config(self) -> bool:
        """メール設定を検証"""
        required_fields = ['smtp_host', 'smtp_port', 'smtp_user', 'smtp_password']
        for field in required_fields:
            if not getattr(self.config, field):
                logger.error(f"メール設定が不足: {field}")
                return False
        return True
    
    def _create_mime_message(self, message: EmailMessage) -> MIMEMultipart:
        """MIMEメッセージを作成"""
        msg = MIMEMultipart('alternative')
        
        # ヘッダー設定
        msg['From'] = f"{self.config.from_name} <{self.config.from_email or self.config.smtp_user}>"
        msg['To'] = ', '.join(message.to_emails)
        msg['Subject'] = message.subject
        
        if message.cc_emails:
            msg['Cc'] = ', '.join(message.cc_emails)
        
        # 日付設定
        msg['Date'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')
        
        # メッセージID設定（重複防止）
        import uuid
        msg['Message-ID'] = f"<{uuid.uuid4()}@{self.config.smtp_host}>"
        
        # テキストコンテンツ
        if message.text_content:
            text_part = MIMEText(message.text_content, 'plain', 'utf-8')
            msg.attach(text_part)
        
        # HTMLコンテンツ
        if message.html_content:
            html_part = MIMEText(message.html_content, 'html', 'utf-8')
            msg.attach(html_part)
        
        # HTMLのみの場合、テキスト版を自動生成
        if message.html_content and not message.text_content:
            text_content = self._html_to_text(message.html_content)
            text_part = MIMEText(text_content, 'plain', 'utf-8')
            msg.attach(text_part)
        
        # 添付ファイル
        if message.attachments:
            for attachment in message.attachments:
                self._add_attachment(msg, attachment)
        
        return msg
    
    def _html_to_text(self, html_content: str) -> str:
        """HTMLからテキストを抽出（簡易版）"""
        import re
        # HTMLタグを除去
        text = re.sub(r'<[^>]+>', '', html_content)
        # 複数の空白を単一に
        text = re.sub(r'\s+', ' ', text)
        # 改行を整理
        text = text.replace('\n\n\n', '\n\n')
        return text.strip()
    
    def _add_attachment(self, msg: MIMEMultipart, attachment: Dict[str, Any]):
        """添付ファイルを追加"""
        try:
            filename = attachment.get('filename', 'attachment')
            content = attachment.get('content', b'')
            content_type = attachment.get('content_type', 'application/octet-stream')
            
            part = MIMEBase(*content_type.split('/'))
            part.set_payload(content)
            encoders.encode_base64(part)
            
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {filename}'
            )
            msg.attach(part)
            
        except Exception as e:
            logger.warning(f"添付ファイル追加に失敗: {e}")
    
    def _send_via_smtp(
        self, 
        msg: MIMEMultipart, 
        to_emails: List[str],
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None
    ) -> bool:
        """SMTPでメールを送信"""
        try:
            # 全受信者のリストを作成
            all_recipients = to_emails.copy()
            if cc_emails:
                all_recipients.extend(cc_emails)
            if bcc_emails:
                all_recipients.extend(bcc_emails)
            
            # SMTP接続
            server = smtplib.SMTP(self.config.smtp_host, self.config.smtp_port)
            
            if self.config.smtp_use_tls:
                # TLS暗号化を開始
                context = ssl.create_default_context()
                server.starttls(context=context)
            
            # ログイン
            server.login(self.config.smtp_user, self.config.smtp_password)
            
            # メール送信
            server.send_message(msg, to_addrs=all_recipients)
            
            # 接続終了
            server.quit()
            
            return True
            
        except smtplib.SMTPException as e:
            logger.error(f"SMTP送信エラー: {e}")
            return False
        except Exception as e:
            logger.exception(f"メール送信エラー: {e}")
            return False
    
    async def send_report_email(
        self,
        to_emails: List[str],
        report_title: str,
        report_content: str,
        report_type: str,
        generated_at: datetime
    ) -> bool:
        """レポートメールを送信"""
        
        # HTMLテンプレート
        html_template = Template("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ report_title }}</title>
    <style>
        body { 
            font-family: 'Hiragino Kaku Gothic ProN', 'Hiragino Sans', Meiryo, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            text-align: center;
            margin-bottom: 30px;
        }
        .header h1 {
            margin: 0;
            font-size: 24px;
        }
        .report-info {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
            margin-bottom: 30px;
        }
        .report-content {
            background: white;
            padding: 30px;
            border-radius: 8px;
            border: 1px solid #e9ecef;
            margin-bottom: 30px;
        }
        .footer {
            text-align: center;
            color: #6c757d;
            font-size: 14px;
            border-top: 1px solid #e9ecef;
            padding-top: 20px;
        }
        .badge {
            display: inline-block;
            padding: 4px 8px;
            background: #667eea;
            color: white;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }
        a {
            color: #667eea;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        .highlight {
            background: #fff3cd;
            padding: 15px;
            border-radius: 5px;
            border-left: 4px solid #ffc107;
            margin: 15px 0;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 {{ report_title }}</h1>
        <p>News Check App 自動レポート</p>
    </div>
    
    <div class="report-info">
        <h3>📋 レポート情報</h3>
        <p><strong>レポートタイプ:</strong> <span class="badge">{{ report_type }}</span></p>
        <p><strong>生成日時:</strong> {{ generated_at.strftime('%Y年%m月%d日 %H:%M') }}</p>
        <p><strong>生成元:</strong> News Check App 自動スケジューリング機能</p>
    </div>
    
    <div class="report-content">
        {{ report_content_html }}
    </div>
    
    <div class="footer">
        <p>📱 このメールは <strong>News Check App</strong> により自動生成されました</p>
        <p>配信を停止したい場合は、アプリの設定画面からスケジュールを無効にしてください。</p>
        <p><small>Generated at {{ generated_at.strftime('%Y-%m-%d %H:%M:%S') }}</small></p>
    </div>
</body>
</html>
        """)
        
        # テキストテンプレート
        text_template = Template("""
===============================================
{{ report_title }}
===============================================

📊 News Check App 自動レポート

📋 レポート情報:
• レポートタイプ: {{ report_type }}
• 生成日時: {{ generated_at.strftime('%Y年%m月%d日 %H:%M') }}
• 生成元: News Check App 自動スケジューリング機能

===============================================
レポート内容:
===============================================

{{ report_content }}

===============================================

📱 このメールは News Check App により自動生成されました。
配信を停止したい場合は、アプリの設定画面からスケジュールを無効にしてください。

Generated at {{ generated_at.strftime('%Y-%m-%d %H:%M:%S') }}
        """)
        
        try:
            # Markdownを簡易HTMLに変換
            report_content_html = self._markdown_to_html(report_content)
            
            # HTMLコンテンツ生成
            html_content = html_template.render(
                report_title=report_title,
                report_type=report_type,
                generated_at=generated_at,
                report_content_html=report_content_html
            )
            
            # テキストコンテンツ生成
            text_content = text_template.render(
                report_title=report_title,
                report_type=report_type,
                generated_at=generated_at,
                report_content=report_content
            )
            
            # メールメッセージ作成
            message = EmailMessage(
                to_emails=to_emails,
                subject=f"📊 {report_title} - News Check App レポート",
                html_content=html_content,
                text_content=text_content
            )
            
            # メール送信
            return await self.send_email(message)
            
        except Exception as e:
            logger.exception(f"レポートメール送信でエラー: {e}")
            return False
    
    def _markdown_to_html(self, markdown_content: str) -> str:
        """Markdownを簡易HTMLに変換"""
        import re
        
        html = markdown_content
        
        # ヘッダー変換
        html = re.sub(r'^# (.*$)', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.*$)', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^### (.*$)', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^#### (.*$)', r'<h4>\1</h4>', html, flags=re.MULTILINE)
        
        # 太字変換
        html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'__(.*?)__', r'<strong>\1</strong>', html)
        
        # 斜体変換
        html = re.sub(r'\*(.*?)\*', r'<em>\1</em>', html)
        html = re.sub(r'_(.*?)_', r'<em>\1</em>', html)
        
        # コード変換
        html = re.sub(r'`(.*?)`', r'<code>\1</code>', html)
        
        # リンク変換
        html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', html)
        
        # リスト変換
        lines = html.split('\n')
        in_list = False
        result_lines = []
        
        for line in lines:
            if re.match(r'^[\*\-\+] ', line):
                if not in_list:
                    result_lines.append('<ul>')
                    in_list = True
                content = re.sub(r'^[\*\-\+] ', '', line)
                result_lines.append(f'<li>{content}</li>')
            elif re.match(r'^\d+\. ', line):
                if not in_list:
                    result_lines.append('<ol>')
                    in_list = True
                content = re.sub(r'^\d+\. ', '', line)
                result_lines.append(f'<li>{content}</li>')
            else:
                if in_list:
                    # 前がリストだった場合、リストを閉じる
                    prev_line = result_lines[-1] if result_lines else ''
                    if '<li>' in prev_line:
                        result_lines.append('</ul>' if '•' in prev_line else '</ol>')
                    in_list = False
                
                # 段落タグ
                if line.strip():
                    result_lines.append(f'<p>{line}</p>')
                else:
                    result_lines.append('<br>')
        
        # リストが最後まで続いている場合
        if in_list:
            result_lines.append('</ul>')
        
        return '\n'.join(result_lines)
    
    async def test_connection(self) -> bool:
        """メール接続をテスト"""
        try:
            server = smtplib.SMTP(self.config.smtp_host, self.config.smtp_port)
            
            if self.config.smtp_use_tls:
                context = ssl.create_default_context()
                server.starttls(context=context)
            
            server.login(self.config.smtp_user, self.config.smtp_password)
            server.quit()
            
            logger.info("メール接続テスト成功")
            return True
            
        except Exception as e:
            logger.error(f"メール接続テスト失敗: {e}")
            return False


# グローバルインスタンス（必要に応じて）
_email_service: Optional[EmailService] = None

def get_email_service() -> Optional[EmailService]:
    """メールサービスのグローバルインスタンスを取得"""
    global _email_service
    
    if _email_service is None:
        try:
            _email_service = EmailService.from_env()
        except Exception as e:
            logger.warning(f"メールサービス初期化に失敗: {e}")
            return None
    
    return _email_service