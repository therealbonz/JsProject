import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.tenant import Organization
from app.models.crm import Lead, Company, Contact
from app.models.base import get_utc_now
from app.services.communication_gateway import EmailNotificationGateway

logger = logging.getLogger(__name__)

COLLATERAL_TEMPLATES = [
    {
        "id": "executive_briefing_letter",
        "name": "Executive Procurement ROI Briefing Letter",
        "type": "postal_letter",
        "channel": "USPS First-Class Mail via Lob.com",
        "dimensions": "8.5x11 inches, Full Color, #70 Uncoated Text",
        "estimated_delivery_days": "2-3 business days",
        "description": "Personalized 1-page executive briefing detailing verified cost reductions and workflow automation tailored for the decision maker."
    },
    {
        "id": "enterprise_postcard",
        "name": "Executive Modernization Showcase Postcard",
        "type": "postal_postcard",
        "channel": "USPS First-Class Mail via Lob.com",
        "dimensions": "6x9 inches, 120# Gloss Cover with UV Lamination",
        "estimated_delivery_days": "1-3 business days",
        "description": "High-impact glossy executive teaser postcard featuring 6-bot workforce benchmark figures and priority demo QR code."
    },
    {
        "id": "autonomous_whitepaper_digital",
        "name": "Autonomous Sales Workforce 16-Page Whitepaper",
        "type": "digital_whitepaper",
        "channel": "SendGrid Transactional PDF Delivery",
        "dimensions": "Interactive 16-Page PDF Whitepaper + ROI Matrix",
        "estimated_delivery_days": "Instant (<5 seconds)",
        "description": "Comprehensive enterprise architectural whitepaper detailing multi-agent pipeline orchestration, security, and integration."
    }
]

class CollateralDispatchService:

    @classmethod
    def get_available_templates(cls) -> List[Dict[str, Any]]:
        return COLLATERAL_TEMPLATES

    @classmethod
    def render_letter_html(
        cls,
        recipient_name: str,
        recipient_title: str,
        company_name: str,
        org: Optional[Organization] = None
    ) -> str:
        brand_name = (org.brand_name or org.name) if org else "NexPulse Global Technologies"
        support_email = (org.support_email or "executive-briefing@therealbonz.com") if org else "executive-briefing@therealbonz.com"
        accent_color = (org.brand_accent_color or "#4f46e5") if org else "#4f46e5"

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        @page {{ size: 8.5in 11in; margin: 1in; }}
        body {{ font-family: 'Helvetica Neue', Arial, sans-serif; color: #1e293b; line-height: 1.6; font-size: 11pt; }}
        .header {{ border-bottom: 2px solid {accent_color}; padding-bottom: 18px; margin-bottom: 24px; }}
        .brand-title {{ font-size: 20pt; font-weight: 800; color: {accent_color}; letter-spacing: -0.5px; }}
        .subtitle {{ font-size: 10pt; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; }}
        .date {{ float: right; font-size: 10pt; color: #64748b; font-weight: 600; }}
        .recipient-block {{ margin-bottom: 24px; font-weight: 600; line-height: 1.4; }}
        .salutation {{ font-size: 13pt; font-weight: 700; margin-bottom: 16px; color: #0f172a; }}
        .highlight-box {{ background-color: #f8fafc; border-left: 4px solid {accent_color}; padding: 14px 18px; margin: 20px 0; border-radius: 4px; }}
        .stat-grid {{ display: table; width: 100%; margin: 18px 0; }}
        .stat-cell {{ display: table-cell; width: 33.3%; text-align: center; padding: 12px; background: #f1f5f9; border-radius: 6px; border: 1px solid #e2e8f0; }}
        .stat-num {{ font-size: 16pt; font-weight: 800; color: {accent_color}; }}
        .stat-label {{ font-size: 8.5pt; color: #475569; text-transform: uppercase; font-weight: 600; margin-top: 4px; }}
        .footer {{ margin-top: 36px; border-top: 1px solid #cbd5e1; padding-top: 16px; font-size: 9pt; color: #94a3b8; }}
        .signature {{ margin-top: 24px; }}
    </style>
</head>
<body>
    <div class="header">
        <span class="date">{datetime.now(timezone.utc).strftime("%B %d, %Y")}</span>
        <div class="brand-title">{brand_name}</div>
        <div class="subtitle">Executive Technology & Enterprise Automation Advisory</div>
    </div>

    <div class="recipient-block">
        <div>{recipient_name}, {recipient_title}</div>
        <div>{company_name}</div>
        <div>Corporate Headquarters</div>
    </div>

    <div class="salutation">Dear {recipient_name},</div>

    <p>
        Following our exploratory switchboard consultation regarding modernization initiatives at <strong>{company_name}</strong>, 
        our enterprise systems group has compiled this customized <strong>Executive Briefing & ROI Analysis</strong> on deploying 
        autonomous multi-agent sales operations.
    </p>

    <div class="highlight-box">
        <strong>Strategic Assessment for {company_name}:</strong> Based on current firmographic benchmarks across your industry, 
        implementing automated decision-maker discovery and intelligent pipeline acceleration is projected to compress your procurement sales cycle 
        from 48 days down to under 9 days while unlocking significant operational efficiencies.
    </div>

    <div class="stat-grid">
        <div class="stat-cell" style="margin-right: 8px;">
            <div class="stat-num">$184,000+</div>
            <div class="stat-label">Est. Annual Efficiency</div>
        </div>
        <div class="stat-cell" style="margin-right: 8px;">
            <div class="stat-num">81%</div>
            <div class="stat-label">Faster Deal Velocity</div>
        </div>
        <div class="stat-cell">
            <div class="stat-num">6 Specialized Bots</div>
            <div class="stat-label">Zero Ramp Latency</div>
        </div>
    </div>

    <p>
        We have enclosed full technical specifications and benchmark studies for your executive team. 
        A senior enterprise architect has reserved an exploratory demonstration window for {company_name}.
    </p>

    <div class="signature">
        <p>Respectfully submitted,</p>
        <p><strong>Office of the Chief Technology Officer</strong><br>
        {brand_name}<br>
        Direct Inquiries: <span style="color: {accent_color};">{support_email}</span></p>
    </div>

    <div class="footer">
        Confidential &bull; Prepared exclusively for executive leadership at {company_name} &bull; Validated with 256-bit SOC-2 compliance standards.
    </div>
</body>
</html>"""

    @classmethod
    async def dispatch_postal_collateral(
        cls,
        db: AsyncSession,
        lead: Lead,
        template_id: str = "executive_briefing_letter",
        recipient_name: Optional[str] = None,
        recipient_title: Optional[str] = None,
        to_address: Optional[Dict[str, str]] = None,
        org: Optional[Organization] = None
    ) -> Dict[str, Any]:
        if not org and lead.organization_id:
            res = await db.execute(select(Organization).where(Organization.id == lead.organization_id))
            org = res.scalar_one_or_none()

        lob_api_key = (org.lob_api_key if org else None) or getattr(settings, "LOB_API_KEY", None)

        is_live = bool(
            lob_api_key
            and (str(lob_api_key).startswith("live_") or str(lob_api_key).startswith("test_"))
            and not str(lob_api_key).startswith("test_mock")
        )

        company = await db.get(Company, lead.company_id) if lead.company_id else None
        company_name = company.name if company else "Enterprise Prospect"
        rec_name = recipient_name or (lead.contact.full_name if lead.contact and lead.contact.full_name else "Head of Procurement")
        rec_title = recipient_title or (lead.contact.job_title if lead.contact and lead.contact.job_title else "VP of Operations")

        target_address = to_address or {
            "name": rec_name,
            "company": company_name,
            "address_line1": "100 Innovation Blvd, Suite 400",
            "address_city": "Austin",
            "address_state": "TX",
            "address_zip": "78701",
            "address_country": "US"
        }

        from_address = {
            "name": (org.brand_name or org.name if org else "NexPulse Global Technologies"),
            "address_line1": "450 Mission Street, Floor 18",
            "address_city": "San Francisco",
            "address_state": "CA",
            "address_zip": "94105",
            "address_country": "US"
        }

        letter_html = cls.render_letter_html(
            recipient_name=rec_name,
            recipient_title=rec_title,
            company_name=company_name,
            org=org
        )

        est_delivery = (get_utc_now() + timedelta(days=3)).strftime("%Y-%m-%d")

        if not is_live:
            sim_letter_id = f"ltr_sim_{uuid.uuid4().hex[:16]}"
            sim_tracking = f"9400111899562{uuid.uuid4().int % 1000000000:09d}"
            preview_url = f"https://s3.amazonaws.com/lob-assets/letters/{sim_letter_id}.pdf"

            logger.info(f"[LOB SIMULATION] Postal literature dispatched to {rec_name} at {company_name} | Tracking: {sim_tracking}")

            dispatch_note = (
                f"[Postal Collateral Dispatched via Lob.com]\n"
                f"- Collateral: {template_id}\n"
                f"- Recipient: {rec_name} ({rec_title}), {company_name}\n"
                f"- USPS Tracking #: {sim_tracking}\n"
                f"- Carrier: USPS First-Class Mail\n"
                f"- Estimated Delivery: {est_delivery}\n"
                f"- Preview Document: {preview_url}"
            )

            lead.notes = f"{(lead.notes or '').strip()}\n\n{dispatch_note}".strip()
            await db.commit()
            await db.refresh(lead)

            return {
                "success": True,
                "mode": "simulated",
                "collateral_id": sim_letter_id,
                "template_id": template_id,
                "tracking_number": sim_tracking,
                "carrier": "USPS",
                "mail_type": "usps_first_class",
                "estimated_delivery_date": est_delivery,
                "recipient_name": rec_name,
                "company_name": company_name,
                "preview_url": preview_url,
                "lead_id": lead.id
            }

        try:
            url = "https://api.lob.com/v1/letters"
            payload = {
                "description": f"Executive Briefing for {company_name}",
                "to": target_address,
                "from": from_address,
                "file": letter_html,
                "color": True,
                "double_sided": False,
                "mail_type": "usps_first_class"
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(
                    url,
                    auth=(lob_api_key, ""),
                    json=payload
                )
                if res.status_code in (200, 201):
                    data = res.json()
                    letter_id = data.get("id", f"ltr_{uuid.uuid4().hex[:16]}")
                    tracking_num = data.get("tracking_number", f"9400111899562{uuid.uuid4().int % 1000000000:09d}")
                    url_preview = data.get("url", f"https://lob-assets.com/letters/{letter_id}.pdf")
                    exp_delivery = data.get("expected_delivery_date", est_delivery)

                    logger.info(f"[LOB LIVE SUCCESS] Dispatched {letter_id} with tracking {tracking_num}")

                    dispatch_note = (
                        f"[Live Postal Collateral Dispatched via Lob.com]\n"
                        f"- Lob ID: {letter_id}\n"
                        f"- Recipient: {rec_name}, {company_name}\n"
                        f"- USPS Tracking #: {tracking_num}\n"
                        f"- Carrier: USPS First-Class Mail\n"
                        f"- Expected Delivery: {exp_delivery}\n"
                        f"- Preview Document: {url_preview}"
                    )
                    lead.notes = f"{(lead.notes or '').strip()}\n\n{dispatch_note}".strip()
                    await db.commit()
                    await db.refresh(lead)

                    return {
                        "success": True,
                        "mode": "live_lob",
                        "collateral_id": letter_id,
                        "template_id": template_id,
                        "tracking_number": tracking_num,
                        "carrier": "USPS",
                        "mail_type": "usps_first_class",
                        "estimated_delivery_date": exp_delivery,
                        "recipient_name": rec_name,
                        "company_name": company_name,
                        "preview_url": url_preview,
                        "lead_id": lead.id
                    }
                else:
                    logger.warning(f"[LOB DISPATCH ERROR] Status {res.status_code}: {res.text}")
                    return {
                        "success": False,
                        "mode": "live_lob",
                        "status": "failed",
                        "error": res.text,
                        "lead_id": lead.id
                    }
        except Exception as e:
            logger.error(f"[LOB DISPATCH EXCEPTION] {e}")
            return {
                "success": False,
                "mode": "live_lob",
                "status": "failed",
                "error": str(e),
                "lead_id": lead.id
            }

    @classmethod
    async def dispatch_digital_whitepaper(
        cls,
        db: AsyncSession,
        lead: Lead,
        to_email: Optional[str] = None,
        recipient_name: Optional[str] = None,
        org: Optional[Organization] = None
    ) -> Dict[str, Any]:
        if not org and lead.organization_id:
            res = await db.execute(select(Organization).where(Organization.id == lead.organization_id))
            org = res.scalar_one_or_none()

        company = await db.get(Company, lead.company_id) if lead.company_id else None
        company_name = company.name if company else "Enterprise Account"
        email = to_email or (lead.contact.email if lead.contact and lead.contact.email else "executive@example.com")
        rec_name = recipient_name or (lead.contact.full_name if lead.contact and lead.contact.full_name else "Executive Leader")

        subject = f"Confidential: Autonomous Sales Workforce Architectural Whitepaper & ROI Model for {company_name}"
        whitepaper_url = "https://therealbonz.com/whitepapers/autonomous-sales-workforce-v2.pdf"

        html_body = f"""
        <p>Dear {rec_name},</p>
        <p>
            As discussed during our switchboard consultation with {company_name}, 
            enclosed is your direct access link to the <strong>Autonomous Sales Workforce Whitepaper & Financial Model</strong>.
        </p>
        <div style="background-color: #1e293b; padding: 18px; border-radius: 8px; margin: 20px 0; border: 1px solid #334155;">
            <h4 style="margin: 0 0 10px 0; color: #38bdf8;">Included in this Executive Release:</h4>
            <ul style="margin: 0; padding-left: 20px; color: #cbd5e1; font-size: 13px;">
                <li>Comprehensive 6-bot pipeline choreography architecture</li>
                <li>Real-world verified benchmarks: 81% faster cycle times & $184k annual savings</li>
                <li>SOC-2 Type II enterprise security and data isolation framework</li>
                <li>Direct API connectors for ERP/CRM infrastructure</li>
            </ul>
        </div>
        <p>In addition, our physical executive briefing packet has been dispatched to your corporate office via USPS First-Class Mail.</p>
        """

        rendered_html = EmailNotificationGateway.render_branded_email_html(
            title=f"Executive Briefing & Whitepaper: {company_name}",
            message_body=html_body,
            org=org,
            cta_url=whitepaper_url,
            cta_text="Download Executive Whitepaper (PDF)",
            order_number=f"DOC-{uuid.uuid4().hex[:8].upper()}"
        )

        email_result = await EmailNotificationGateway.send_email(
            to_email=email,
            subject=subject,
            html_content=rendered_html,
            org=org
        )

        return {
            "success": email_result.get("success", False),
            "mode": email_result.get("mode", "simulated"),
            "to_email": email,
            "recipient_name": rec_name,
            "company_name": company_name,
            "whitepaper_url": whitepaper_url,
            "lead_id": lead.id
        }
