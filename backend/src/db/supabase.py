"""
Supabase storage and email integration helpers.

This module provides a small, environment-driven adapter for:
- uploading files to Supabase Storage
- generating signed URLs for Supabase objects
- sending notification emails via SMTP when configured

The implementation is intentionally minimal so the service can remain
functional even when Supabase env vars are not present.
"""
import asyncio
import logging
import ssl
import smtplib
from email.message import EmailMessage
from urllib.parse import quote

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


class SupabaseClient:
    """Simple Supabase client for storage and outbound email."""

    def __init__(self) -> None:
        self.url = settings.SUPABASE_URL.rstrip("/") if settings.SUPABASE_URL else ""
        self.service_role_key = settings.SUPABASE_SERVICE_ROLE_KEY
        self.storage_bucket = settings.SUPABASE_STORAGE_BUCKET
        self.email_from = settings.SUPABASE_EMAIL_FROM
        self.smtp_host = settings.EMAIL_SMTP_HOST
        self.smtp_port = settings.EMAIL_SMTP_PORT
        self.smtp_user = settings.EMAIL_SMTP_USER
        self.smtp_password = settings.EMAIL_SMTP_PASSWORD
        self.smtp_use_tls = settings.EMAIL_SMTP_USE_TLS

    @property
    def is_storage_configured(self) -> bool:
        return bool(self.url and self.service_role_key and self.storage_bucket)

    @property
    def is_email_configured(self) -> bool:
        return bool(
            self.smtp_host
            and self.smtp_user
            and self.smtp_password
            and self.email_from
        )

    async def upload_file(
        self,
        object_path: str,
        content: bytes,
        content_type: str = "application/pdf",
    ) -> str:
        """Upload a file content to Supabase Storage."""
        if not self.is_storage_configured:
            raise RuntimeError("Supabase storage is not configured")

        encoded_path = quote(object_path.strip("/"))
        url = f"{self.url}/storage/v1/object/{self.storage_bucket}/{encoded_path}"
        headers = {
            "Authorization": f"Bearer {self.service_role_key}",
            "apikey": self.service_role_key,
            "Content-Type": content_type,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                url,
                content=content,
                headers=headers,
                params={"cacheControl": "3600", "upsert": "false"},
            )

        if response.status_code not in (200, 201, 204):
            logger.error(
                "Supabase upload failed %s %s %s",
                response.status_code,
                response.text,
                url,
            )
            raise RuntimeError(
                f"Failed to upload file to Supabase Storage: {response.status_code}"
            )

        logger.info("Uploaded file to Supabase Storage: %s", object_path)
        return object_path

    async def get_signed_url(self, object_path: str, expires_in: int = 3600) -> str:
        """Generate a signed URL for a Supabase Storage object."""
        if not self.is_storage_configured:
            raise RuntimeError("Supabase storage is not configured")

        encoded_path = quote(object_path.strip("/"))
        url = f"{self.url}/storage/v1/object/sign/{self.storage_bucket}/{encoded_path}"
        headers = {
            "Authorization": f"Bearer {self.service_role_key}",
            "apikey": self.service_role_key,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers=headers, json={"expiresIn": expires_in})

        if response.status_code != 200:
            logger.error(
                "Supabase signed URL failed %s %s %s",
                response.status_code,
                response.text,
                url,
            )
            raise RuntimeError("Failed to generate Supabase signed URL")

        payload = response.json()
        signed_url = payload.get("signedURL") or payload.get("signed_url")
        if not signed_url:
            raise RuntimeError("Supabase signed URL response missing signedURL")

        return signed_url

    async def send_email(self, to: str, subject: str, body: str) -> bool:
        """Send an email using configured SMTP credentials."""
        if not self.is_email_configured:
            raise RuntimeError("SMTP email is not configured")

        return await asyncio.to_thread(self._send_email_sync, to, subject, body)

    def _send_email_sync(self, to: str, subject: str, body: str) -> bool:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.email_from
        message["To"] = to
        message.set_content(body)

        context = ssl.create_default_context()
        if self.smtp_port == 465:
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=context) as smtp:
                smtp.login(self.smtp_user, self.smtp_password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=60) as smtp:
                if self.smtp_use_tls:
                    smtp.starttls(context=context)
                smtp.login(self.smtp_user, self.smtp_password)
                smtp.send_message(message)

        logger.info("Email sent via SMTP to %s", to)
        return True


supabase_client = SupabaseClient()
