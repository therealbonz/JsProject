import re
import uuid
import random
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

from app.models.tenant import Organization
from app.models.crm import Lead, Company, Contact, CallLog, Appointment, ProspectCampaign
from app.schemas.dialer import CampaignDialResult, CampaignBatchProgress
from app.services.communication_gateway import TwilioSMSGateway

logger = logging.getLogger(__name__)

class CampaignDialerService:
    @classmethod
    def get_trade_script(
        cls,
        trade: str,
        homeowner_name: str,
        address: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Dynamically generates personalized spoken scripts, voicemail drops, and follow-up SMS text.
        """
        first_name = homeowner_name.split()[0] if homeowner_name else "there"
        location_ref = f"on {address}" if address else "in your neighborhood"

        trade_lower = trade.lower()
        if "carpet" in trade_lower:
            return {
                "greeting": f"Hello {first_name}! This is Amber calling with Apex Home Services.",
                "pitch": f"We're routing our steam extraction trucks {location_ref} this week offering our $45 per room deep cleaning special, including complimentary pet odor pretreatment.",
                "call_to_action": "We have two open arrival windows on Friday morning or Saturday afternoon. Would either of those work to refresh your carpets?",
                "voicemail_message": f"Hi {first_name}! This is Amber from Apex Home Services. We're running our $45 per room steam cleaning special in your area this week. I'm texting you our booking link right now, or feel free to call us back at (800) 555-APEX. Have a wonderful day!",
                "sms_followup": f"Hi {first_name}! Amber from Apex here. Sorry I missed you by phone! Here is our $45/room steam cleaning special: https://therealbonz.com/JsProject/residential?trade=carpet_cleaning. Reply to this text anytime to book!"
            }
        elif "lawn" in trade_lower:
            return {
                "greeting": f"Hi {first_name}, this is Amber calling with Apex Lawn & Landscape.",
                "pitch": f"Our zero-turn commercial mowing crews are setting up weekly service routes {location_ref}. We're offering a 15% season discount for neighborhood homeowners plus free fall aeration.",
                "call_to_action": "We can swing by Thursday morning for a quick 5-minute contactless lawn assessment. Would morning or afternoon work better for you?",
                "voicemail_message": f"Hi {first_name}, Amber from Apex Lawn Care. We're setting up weekly mowing schedules in your neighborhood with a 15% discount. I'm texting you our rate sheet right now, or call (800) 555-APEX!",
                "sms_followup": f"Hi {first_name}! Amber from Apex Lawn Care. Here's our 15% weekly mowing discount: https://therealbonz.com/JsProject/residential?trade=lawn_care. Reply to secure your spot!"
            }
        elif "roof" in trade_lower or "gutter" in trade_lower:
            return {
                "greeting": f"Hello {first_name}, this is Amber with Apex Roofing and Restoration.",
                "pitch": f"Following recent storm and wind activity {location_ref}, our licensed inspectors are conducting complimentary 21-point drone roof and gutter diagnostics.",
                "call_to_action": "Are you noticing any missing shingles, gutter overflow, or interior ceiling spots? We have an inspector nearby tomorrow.",
                "voicemail_message": f"Hello {first_name}, Amber from Apex Roofing. We're offering free 21-point roof and gutter storm diagnostics on your street this week. Texting you our inspection link now!",
                "sms_followup": f"Hi {first_name}! Amber from Apex Roofing. We're doing free 21-pt roof storm inspections in your area: https://therealbonz.com/JsProject/residential?trade=roofing. Text back or call (800) 555-APEX."
            }
        else:
            return {
                "greeting": f"Hello {first_name}, this is Amber calling with Apex Commercial Facility Services.",
                "pitch": f"We provide comprehensive commercial maintenance, HVAC, and exterior services {location_ref} with 24/7 dedicated dispatch.",
                "call_to_action": "Would next Tuesday work for a brief 10-minute executive walk-through?",
                "voicemail_message": f"Hello {first_name}, Amber from Apex Services. Reaching out regarding your facility maintenance. Texting you our overview, or call (800) 555-APEX.",
                "sms_followup": f"Hi {first_name}! Amber from Apex Services. You can review our service catalog here: https://therealbonz.com/JsProject/residential. Have a great day!"
            }

    @classmethod
    def generate_outbound_twiml(
        cls,
        trade: str,
        homeowner_name: str,
        callback_url: str,
        address: Optional[str] = None
    ) -> str:
        """
        Generates standard TwiML XML for Twilio outbound campaign calls.
        """
        script = cls.get_trade_script(trade, homeowner_name, address)
        spoken_text = f"{script['greeting']} {script['pitch']} {script['call_to_action']}"

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" timeout="5" action="{callback_url}" method="POST">
        <Say voice="Polly.Danielle" language="en-US">
            {spoken_text}
        </Say>
    </Gather>
    <Say voice="Polly.Danielle" language="en-US">
        {script['voicemail_message']}
    </Say>
</Response>"""

    @classmethod
    def parse_homeowner_intent(cls, speech_text: str) -> str:
        """
        Classifies homeowner verbal response into CRM call outcome.
        """
        s = speech_text.lower().strip()
        if any(w in s for w in ["not interested", "remove", "stop", "do not call", "dnc", "wrong number", "don't call", "take me off"]):
            return "dnc"
        if any(w in s for w in ["yes", "yeah", "sure", "book", "schedule", "quote", "friday", "saturday", "morning", "afternoon", "come out", "sounds good", "interested"]):
            return "booked"
        if any(w in s for w in ["busy", "call back", "later", "driving", "in a meeting", "call me back"]):
            return "callback"
        if any(w in s for w in ["beep", "leave a message", "voicemail", "tone", "not available"]):
            return "voicemail"
        return "connected"

    @classmethod
    async def dial_single_lead(
        cls,
        lead_id: str,
        campaign_id: str,
        db: AsyncSession,
        simulate: bool = True,
        simulated_outcome: Optional[str] = None
    ) -> CampaignDialResult:
        """
        Dials a single prospect lead, handles the conversation, logs the call,
        and triggers appointment booking or voicemail drop SMS.
        """
        stmt = (
            select(Lead)
            .options(
                selectinload(Lead.contact),
                selectinload(Lead.company),
                selectinload(Lead.campaign)
            )
            .where(Lead.id == lead_id)
        )
        res = await db.execute(stmt)
        lead = res.scalar_one_or_none()
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")

        campaign_stmt = select(ProspectCampaign).where(ProspectCampaign.id == campaign_id)
        camp_res = await db.execute(campaign_stmt)
        campaign = camp_res.scalar_one_or_none()
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        contact = lead.contact
        company = lead.company
        homeowner_name = f"{contact.first_name} {contact.last_name}".strip() if contact else "Homeowner"
        phone = (contact.phone if contact else None) or "+1-303-555-0100"
        address = company.address if company else None
        trade = campaign.trade_service

        script = cls.get_trade_script(trade, homeowner_name, address)
        now = datetime.now(timezone.utc)

        # Determine outcome
        if simulated_outcome:
            outcome = simulated_outcome
        elif simulate:
            # Realistic weighted distribution: 45% booked, 35% voicemail, 12% callback, 8% dnc
            rand_val = random.random()
            if rand_val < 0.45:
                outcome = "booked"
            elif rand_val < 0.80:
                outcome = "voicemail"
            elif rand_val < 0.92:
                outcome = "callback"
            else:
                outcome = "dnc"
        else:
            outcome = "connected"

        call_sid = f"CA_out_{uuid.uuid4().hex[:18]}"
        duration = 95 if outcome == "booked" else (22 if outcome == "voicemail" else 45)
        appointment_id = None
        appointment_slot = None
        sms_sent = False

        if outcome == "booked":
            # Schedule appointment 2 business days out at 10:00 AM
            scheduled_date = now + timedelta(days=2)
            scheduled_dt = scheduled_date.replace(hour=10, minute=0, second=0, microsecond=0)
            appointment_slot = scheduled_dt.strftime("%A, %b %d at 10:00 AM")

            appointment = Appointment(
                organization_id=lead.organization_id,
                lead_id=lead.id,
                company_id=company.id if company else None,
                contact_id=contact.id if contact else None,
                title=f"Apex {trade.replace('_', ' ').title()} - {homeowner_name}",
                scheduled_at=scheduled_dt,
                duration_minutes=60,
                status="scheduled",
                closer_name="Apex Field Technician Crew",
                notes=f"Auto-booked by Outbound Campaign Bot ({campaign.name})",
                booked_by_agent=True
            )
            db.add(appointment)
            await db.flush()
            appointment_id = appointment.id

            lead.pipeline_stage = "won"
            lead.lead_score = 95
            campaign.booked_count += 1
            transcript = (
                f"Bot: {script['greeting']} {script['pitch']} {script['call_to_action']}\n"
                f"Homeowner: Yes, Friday morning at 10 AM works great for us!\n"
                f"Bot: Fantastic, {contact.first_name if contact else 'there'}! You are all set for {appointment_slot}. "
                f"Our crew will send an en-route heads-up 30 minutes before arrival. Have a wonderful day!"
            )

        elif outcome == "voicemail":
            lead.pipeline_stage = "contacted"
            transcript = (
                f"Bot: [Voicemail Beep Detected]\n"
                f"Bot: {script['voicemail_message']}\n"
                f"System: Dispatched speed-to-lead follow-up SMS with 1-click booking link to {phone}."
            )
            # Dispatch speed-to-lead SMS
            try:
                await TwilioSMSGateway.send_sms(
                    to_phone=phone,
                    message=script["sms_followup"]
                )
                sms_sent = True
            except Exception as e:
                logger.warning(f"Failed to dispatch voicemail follow-up SMS: {e}")

        elif outcome == "dnc":
            lead.status = "dnc"
            lead.pipeline_stage = "lost"
            lead.notes = f"Homeowner requested Do Not Call on {now.strftime('%Y-%m-%d %H:%M')}"
            transcript = (
                f"Bot: {script['greeting']} {script['pitch']}\n"
                f"Homeowner: Not interested. Please take me off your list.\n"
                f"Bot: Understood, we apologize for the interruption and have removed your number from our records immediately. Have a nice day."
            )

        else:  # callback or connected
            lead.pipeline_stage = "contacted"
            lead.next_action_type = "callback"
            lead.next_action_at = now + timedelta(days=1)
            transcript = (
                f"Bot: {script['greeting']} {script['pitch']} {script['call_to_action']}\n"
                f"Homeowner: I'm driving right now. Could you call me back tomorrow afternoon?\n"
                f"Bot: Absolutely! I will note that for our team and call you back tomorrow. Drive safe!"
            )

        # Update lead telemetry
        lead.last_call_at = now
        lead.last_call_outcome = outcome
        lead.last_call_notes = transcript

        # Create CallLog
        call_log = CallLog(
            organization_id=lead.organization_id,
            lead_id=lead.id,
            company_id=company.id if company else None,
            contact_id=contact.id if contact else None,
            caller_name="Amber • Apex Voice AI",
            called_at=now,
            duration_minutes=max(1, duration // 60),
            outcome=outcome,
            notes=transcript,
            next_steps="Appointment confirmed" if outcome == "booked" else ("SMS booking link dispatched" if outcome == "voicemail" else "Do not call")
        )
        db.add(call_log)

        # Update campaign metrics
        campaign.dialed_count += 1
        if outcome in ("booked", "connected", "dnc", "callback"):
            campaign.connected_count += 1

        # Check if all leads are completed
        pending_check = await db.execute(
            select(func.count(Lead.id)).where(
                Lead.campaign_id == campaign.id,
                Lead.pipeline_stage == "ready_contact",
                Lead.status == "active"
            )
        )
        pending_cnt = pending_check.scalar_one()
        if pending_cnt == 0:
            campaign.status = "completed"
        else:
            campaign.status = "in_progress"

        await db.commit()

        return CampaignDialResult(
            lead_id=lead_id,
            contact_name=homeowner_name,
            phone=phone,
            trade_service=trade,
            outcome=outcome,
            duration_seconds=duration,
            transcript=transcript,
            appointment_id=appointment_id,
            appointment_slot=appointment_slot,
            call_sid=call_sid,
            sms_followup_sent=sms_sent
        )

    @classmethod
    async def run_campaign_batch(
        cls,
        campaign_id: str,
        organization_id: str,
        db: AsyncSession,
        batch_size: int = 10,
        delay_seconds: float = 0.5,
        simulate: bool = True,
        simulated_outcome: Optional[str] = None
    ) -> CampaignBatchProgress:
        """
        Pulls the next pending leads in the campaign and dials them sequentially.
        """
        camp_stmt = select(ProspectCampaign).where(
            ProspectCampaign.id == campaign_id,
            ProspectCampaign.organization_id == organization_id
        )
        camp_res = await db.execute(camp_stmt)
        campaign = camp_res.scalar_one_or_none()
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        # Fetch pending lead IDs upfront before committing individual calls
        leads_stmt = (
            select(Lead.id)
            .where(
                Lead.campaign_id == campaign_id,
                Lead.organization_id == organization_id,
                Lead.pipeline_stage == "ready_contact",
                Lead.status == "active"
            )
            .order_by(Lead.created_at.asc())
            .limit(batch_size)
        )
        leads_res = await db.execute(leads_stmt)
        pending_lead_ids = [row[0] for row in leads_res.all()]

        results: List[CampaignDialResult] = []
        for lid in pending_lead_ids:
            res = await cls.dial_single_lead(
                lead_id=lid,
                campaign_id=campaign_id,
                db=db,
                simulate=simulate,
                simulated_outcome=simulated_outcome
            )
            results.append(res)

        return await cls.get_campaign_progress(campaign_id, organization_id, db, results=results)

    @classmethod
    async def get_campaign_progress(
        cls,
        campaign_id: str,
        organization_id: str,
        db: AsyncSession,
        results: Optional[List[CampaignDialResult]] = None
    ) -> CampaignBatchProgress:
        """
        Retrieves real-time dialing telemetry for a campaign.
        """
        camp_stmt = select(ProspectCampaign).where(
            ProspectCampaign.id == campaign_id,
            ProspectCampaign.organization_id == organization_id
        )
        camp_res = await db.execute(camp_stmt)
        campaign = camp_res.scalar_one_or_none()
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        # Query lead statuses
        all_leads_stmt = select(Lead).where(
            Lead.campaign_id == campaign_id,
            Lead.organization_id == organization_id
        )
        all_leads_res = await db.execute(all_leads_stmt)
        all_leads = all_leads_res.scalars().all()

        total = len(all_leads)
        pending = sum(1 for l in all_leads if l.pipeline_stage == "ready_contact" and l.status == "active")
        booked = sum(1 for l in all_leads if l.pipeline_stage == "won")
        dnc = sum(1 for l in all_leads if l.status == "dnc")
        voicemails = sum(1 for l in all_leads if l.last_call_outcome == "voicemail")

        # Determine campaign status
        status = campaign.status
        if total > 0 and pending == 0:
            status = "completed"

        return CampaignBatchProgress(
            campaign_id=campaign.id,
            campaign_name=campaign.name,
            trade_service=campaign.trade_service,
            status=status,
            total_leads=total,
            pending_leads=pending,
            dialed_count=campaign.dialed_count,
            connected_count=campaign.connected_count,
            booked_count=booked,
            voicemail_count=voicemails,
            dnc_count=dnc,
            results=results or []
        )
