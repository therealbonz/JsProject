import re
import uuid
import logging
from typing import Optional, Dict, Any
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.tenant import Organization
from app.models.crm import CustomerNotification

logger = logging.getLogger(__name__)

class TwilioSMSGateway:
    @staticmethod
    def clean_phone_number(phone: str) -> str:
        """Sanitizes phone number into E.164 compatible format."""
        cleaned = re.sub(r"[^\d+]", "", phone)
        if not cleaned.startswith("+"):
            if len(cleaned) == 10:
                cleaned = "+1" + cleaned
            elif len(cleaned) == 11 and cleaned.startswith("1"):
                cleaned = "+" + cleaned
            else:
                cleaned = "+" + cleaned
        return cleaned

    @classmethod
    async def send_sms(
        cls,
        to_phone: str,
        message: str,
        org: Optional[Organization] = None
    ) -> Dict[str, Any]:
        """
        Sends SMS via Twilio REST API.
        Gracefully falls back to local simulation if credentials are not configured.
        """
        account_sid = (org.twilio_account_sid if org else None) or getattr(settings, "TWILIO_ACCOUNT_SID", None)
        auth_token = (org.twilio_auth_token if org else None) or getattr(settings, "TWILIO_AUTH_TOKEN", None)
        from_number = (org.twilio_from_number if org else None) or getattr(settings, "TWILIO_FROM_NUMBER", None)

        is_live = bool(
            account_sid and auth_token and from_number
            and str(account_sid).startswith("AC")
            and not str(account_sid).startswith("AC_test")
            and not str(account_sid).startswith("AC_mock")
        )
        recipient = cls.clean_phone_number(to_phone)

        if not is_live:
            sim_sid = f"SM_sim_{uuid.uuid4().hex[:20]}"
            logger.info(f"[SMS SIMULATION] To: {recipient} | From: {from_number or 'Auto-Dispatcher'} | Body: {message[:120]}...")
            return {
                "success": True,
                "mode": "simulated",
                "sid": sim_sid,
                "status": "simulated",
                "recipient": recipient,
                "message": message
            }

        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    url,
                    auth=(account_sid, auth_token),
                    data={"From": from_number, "To": recipient, "Body": message}
                )
                if res.status_code in (200, 201):
                    data = res.json()
                    logger.info(f"[TWILIO LIVE SMS SUCCESS] To: {recipient} | SID: {data.get('sid')}")
                    return {
                        "success": True,
                        "mode": "live_twilio",
                        "sid": data.get("sid"),
                        "status": data.get("status", "sent"),
                        "recipient": recipient
                    }
                else:
                    logger.warning(f"[TWILIO SMS ERROR] Status {res.status_code}: {res.text}")
                    return {
                        "success": False,
                        "mode": "live_twilio",
                        "status": "failed",
                        "error": res.text,
                        "recipient": recipient
                    }
        except Exception as e:
            logger.error(f"[TWILIO SMS EXCEPTION] {e}")
            return {
                "success": False,
                "mode": "live_twilio",
                "status": "failed",
                "error": str(e),
                "recipient": recipient
            }


class EmailNotificationGateway:
    @classmethod
    def render_branded_email_html(
        cls,
        title: str,
        message_body: str,
        org: Optional[Organization] = None,
        cta_url: Optional[str] = None,
        cta_text: Optional[str] = "View Live Tracking Portal",
        order_number: Optional[str] = None
    ) -> str:
        """
        Renders a responsive HTML transactional email customized with the tenant's brand styling.
        """
        brand_name = (org.brand_name or org.name) if org else "Order Bot Distribution"
        brand_color = (org.brand_accent_color or "#4f46e5") if org else "#4f46e5"
        logo_url = org.brand_logo_url if org else None
        support_email = (org.support_email or "support@therealbonz.com") if org else "support@therealbonz.com"
        support_phone = org.support_phone if org else None
        custom_footer = org.custom_footer_text if org else "Autonomous Wholesale & Distribution Solutions"

        logo_html = f'<img src="{logo_url}" alt="{brand_name}" style="max-height: 42px; margin-bottom: 12px; display: block;" />' if logo_url else f'<h2 style="margin: 0; color: #ffffff; font-size: 20px; font-weight: 800; letter-spacing: -0.5px;">{brand_name}</h2>'
        cta_button = f'<div style="margin: 28px 0;"><a href="{cta_url}" style="background-color: {brand_color}; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: 700; font-size: 14px; display: inline-block; box-shadow: 0 4px 14px rgba(0,0,0,0.25);">{cta_text} &rarr;</a></div>' if cta_url else ''
        phone_html = f' &bull; Phone: <span style="color: #cbd5e1;">{support_phone}</span>' if support_phone else ''

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
        </head>
        <body style="margin: 0; padding: 0; background-color: #0b0f19; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #f8fafc;">
            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="table-layout: fixed; background-color: #0b0f19; padding: 32px 16px;">
                <tr>
                    <td align="center">
                        <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 580px; background-color: #111827; border: 1px solid #1f2937; border-radius: 16px; overflow: hidden; box-shadow: 0 20px 40px rgba(0,0,0,0.5);">
                            <!-- Brand Header -->
                            <tr>
                                <td style="padding: 28px 32px; background-color: #0f172a; border-bottom: 1px solid #1e293b;">
                                    {logo_html}
                                    <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; tracking: 1px; font-weight: 600;">{brand_name} Logistics & Commerce</div>
                                </td>
                            </tr>
                            <!-- Content Body -->
                            <tr>
                                <td style="padding: 36px 32px;">
                                    <h1 style="margin: 0 0 16px 0; font-size: 20px; font-weight: 700; color: #ffffff; line-height: 1.3;">{title}</h1>
                                    <p style="margin: 0 0 20px 0; font-size: 14px; line-height: 1.6; color: #cbd5e1;">{message_body}</p>
                                    {cta_button}
                                    <div style="margin-top: 24px; padding: 16px; background-color: #0f172a; border: 1px solid #1e293b; border-radius: 10px; font-size: 12px; color: #94a3b8;">
                                        Order Reference: <strong style="color: #f1f5f9; font-family: monospace;">#{order_number or 'N/A'}</strong> &bull; Secured with 256-bit SSL Telemetry
                                    </div>
                                </td>
                            </tr>
                            <!-- Support Footer -->
                            <tr>
                                <td style="padding: 24px 32px; background-color: #090d16; border-top: 1px solid #1e293b; text-align: center; font-size: 11px; color: #64748b; line-height: 1.5;">
                                    <p style="margin: 0 0 6px 0;">{custom_footer}</p>
                                    <p style="margin: 0;">Need assistance? Contact <a href="mailto:{support_email}" style="color: {brand_color}; text-decoration: underline;">{support_email}</a>{phone_html}</p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

    @classmethod
    async def send_email(
        cls,
        to_email: str,
        subject: str,
        html_content: str,
        org: Optional[Organization] = None
    ) -> Dict[str, Any]:
        """
        Sends transactional email via SendGrid REST API.
        Gracefully falls back to simulation mode if API key is not configured.
        """
        sendgrid_key = (org.sendgrid_api_key if org else None) or getattr(settings, "SENDGRID_API_KEY", None)
        from_address = (org.email_from_address if org else None) or getattr(settings, "SENDGRID_FROM_EMAIL", "orders@therealbonz.com")
        from_name = (org.email_from_name or org.brand_name or org.name if org else "Order Bot Distribution")

        is_live = bool(
            sendgrid_key
            and str(sendgrid_key).startswith("SG.")
            and not str(sendgrid_key).startswith("SG.test")
            and not str(sendgrid_key).startswith("SG.mock")
        )

        if not is_live:
            sim_id = f"msg_sim_{uuid.uuid4().hex[:20]}"
            logger.info(f"[EMAIL SIMULATION] To: {to_email} | From: {from_name} <{from_address}> | Subject: {subject}")
            return {
                "success": True,
                "mode": "simulated",
                "message_id": sim_id,
                "status": "simulated",
                "recipient": to_email,
                "subject": subject
            }

        try:
            url = "https://api.sendgrid.com/v3/mail/send"
            payload = {
                "personalizations": [{"to": [{"email": to_email}]}],
                "from": {"email": from_address, "name": from_name},
                "subject": subject,
                "content": [{"type": "text/html", "value": html_content}]
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {sendgrid_key}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                )
                if res.status_code in (200, 202):
                    logger.info(f"[SENDGRID LIVE EMAIL SUCCESS] To: {to_email} | Subject: {subject}")
                    return {
                        "success": True,
                        "mode": "live_sendgrid",
                        "status": "sent",
                        "recipient": to_email
                    }
                else:
                    logger.warning(f"[SENDGRID EMAIL ERROR] Status {res.status_code}: {res.text}")
                    return {
                        "success": False,
                        "mode": "live_sendgrid",
                        "status": "failed",
                        "error": res.text,
                        "recipient": to_email
                    }
        except Exception as e:
            logger.error(f"[SENDGRID EMAIL EXCEPTION] {e}")
            return {
                "success": False,
                "mode": "live_sendgrid",
                "status": "failed",
                "error": str(e),
                "recipient": to_email
            }


class CommunicationGatewayService:
    @classmethod
    async def dispatch_customer_notification(
        cls,
        db: AsyncSession,
        notification: CustomerNotification,
        org: Optional[Organization] = None
    ) -> Dict[str, Any]:
        """
        Dispatches a customer notification across its designated channel (SMS or Email).
        Updates notification status in database.
        """
        if not org and notification.organization_id:
            stmt = select(Organization).where(Organization.id == notification.organization_id)
            res = await db.execute(stmt)
            org = res.scalar_one_or_none()

        result = {"success": False, "channel": notification.channel}

        if notification.channel == "sms":
            res = await TwilioSMSGateway.send_sms(
                to_phone=notification.recipient,
                message=notification.message_body,
                org=org
            )
            result.update(res)
        else:
            # Default to Email
            html = EmailNotificationGateway.render_branded_email_html(
                title=notification.title,
                message_body=notification.message_body,
                org=org,
                cta_url=notification.tracking_url,
                cta_text="View Live Delivery Tracking",
                order_number=notification.title.split(":")[-1].strip() if ":" in notification.title else None
            )
            res = await EmailNotificationGateway.send_email(
                to_email=notification.recipient,
                subject=notification.title,
                html_content=html,
                org=org
            )
            result.update(res)

        notification.status = "sent" if result.get("success") else "failed"
        await db.commit()
        await db.refresh(notification)

        return result
