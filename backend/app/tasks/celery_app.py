import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional
from celery import Celery
from app.core.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "pilgrim_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True
)

@celery_app.task(name="app.tasks.send_verification_email", bind=True)
def send_verification_email(self, email: str, token: str, user_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Background task to send an email verification link via Celery & RabbitMQ.
    If SMTP credentials are provided, attempts real SMTP dispatch.
    If not provided, logs and returns task metadata (does not falsely claim SMTP delivery).
    """
    logger.info(f"[CELERY TASK] Received send_verification_email for email: {email}")
    
    recipient_name = user_name or "Pilgrim"
    verification_link = f"/api/auth/verify-email?token={token}"
    
    # Check if SMTP is configured
    if not settings.SMTP_HOST or not settings.SMTP_USERNAME:
        logger.info(
            f"[CELERY EMAIL TASK] SMTP not configured. Generated verification token for {email}: {token}"
        )
        return {
            "status": "skipped",
            "reason": "SMTP_HOST or SMTP_USERNAME not configured",
            "email": email,
            "verification_token": token,
            "verification_link": verification_link
        }
    
    # Attempt real SMTP transmission
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Verify Your PilgrimAI Account"
        msg["From"] = settings.SMTP_FROM_EMAIL
        msg["To"] = email
        
        text_content = (
            f"Hello {recipient_name},\n\n"
            f"Thank you for registering with PilgrimAI.\n"
            f"Please verify your email using the following link or token:\n"
            f"{verification_link}\n\n"
            f"Token: {token}\n"
        )
        msg.attach(MIMEText(text_content, "plain"))
        
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            if settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM_EMAIL, email, msg.as_string())
            
        logger.info(f"[CELERY EMAIL TASK] Verification email dispatched successfully to {email}")
        return {
            "status": "delivered",
            "email": email,
            "verification_token": token
        }
    except Exception as e:
        logger.error(f"[CELERY EMAIL TASK] Failed to send email to {email}: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "email": email
        }

@celery_app.task(name="app.tasks.send_password_reset_email", bind=True)
def send_password_reset_email(self, email: str, token: str, user_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Background task to send a password reset link via Celery & RabbitMQ.
    If SMTP credentials are provided, attempts real SMTP dispatch to Gmail.
    If not provided, logs safely without exposing the raw token.
    """
    logger.info(f"[CELERY TASK] Received send_password_reset_email for email: {email}")
    
    recipient_name = user_name or "Pilgrim"
    reset_url = f"http://localhost:8000/?reset_token={token}"
    
    # Check if SMTP is configured
    if not settings.SMTP_HOST or not settings.SMTP_USERNAME:
        logger.info(f"[CELERY RESET TASK] SMTP not configured. Skipped dispatch for {email}")
        return {
            "status": "skipped",
            "reason": "SMTP_HOST or SMTP_USERNAME not configured",
            "email": email
        }
    
    # Attempt real SMTP transmission
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Reset Your PilgrimAI Password"
        msg["From"] = settings.SMTP_FROM_EMAIL
        msg["To"] = email
        
        text_content = (
            f"Hello {recipient_name},\n\n"
            f"We received a request to reset your PilgrimAI account password.\n"
            f"Click the link below to set a new password (valid for 30 minutes):\n\n"
            f"{reset_url}\n\n"
            f"If you did not request a password reset, you can safely ignore this email.\n\n"
            f"— The PilgrimAI Team\n"
        )
        msg.attach(MIMEText(text_content, "plain"))
        
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            if settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM_EMAIL, email, msg.as_string())
            
        logger.info(f"[CELERY RESET TASK] Password reset email dispatched successfully to {email}")
        return {
            "status": "delivered",
            "email": email
        }
    except Exception as e:
        logger.error(f"[CELERY RESET TASK] Failed to send password reset email to {email}: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "email": email
        }

