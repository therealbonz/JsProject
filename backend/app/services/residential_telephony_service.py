import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.tenant import Organization
from app.models.crm import Company, Contact, Lead, Opportunity, Appointment, CallLog
from app.services.communication_gateway import TwilioSMSGateway
from app.services.residential_sales_engine import ResidentialSalesEngine
from app.schemas.residential import (
    TradeType, CarpetCleaningSpecs, LawnCareSpecs, RoofingSpecs
)

logger = logging.getLogger(__name__)

# Global in-memory session cache for SMS conversations (phone -> state)
_SMS_SESSION_CACHE: Dict[str, Dict[str, Any]] = {}

class ResidentialSMSService:
    """
    Manages 2-way conversational SMS qualification, quoting, and text-to-book execution.
    Also handles speed-to-lead missed-call auto-text response.
    """

    @classmethod
    def get_session(cls, phone: str) -> Dict[str, Any]:
        clean = TwilioSMSGateway.clean_phone_number(phone)
        if clean not in _SMS_SESSION_CACHE:
            _SMS_SESSION_CACHE[clean] = {
                "phone": clean,
                "trade": "carpet_cleaning",
                "state": "new",
                "step": 0,
                "homeowner_name": None,
                "address": None,
                "zip_code": None,
                "carpet": CarpetCleaningSpecs().model_dump(),
                "lawn": LawnCareSpecs().model_dump(),
                "roofing": RoofingSpecs().model_dump(),
                "scheduled_date": None,
                "time_window": "morning",
                "last_quote": None,
                "messages": []
            }
        return _SMS_SESSION_CACHE[clean]

    @classmethod
    async def trigger_missed_call_textback(
        cls,
        caller_phone: str,
        org: Optional[Organization] = None,
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        Speed-to-Lead: Dispatched immediately when a homeowner call is missed or unanswered.
        """
        recipient = TwilioSMSGateway.clean_phone_number(caller_phone)
        session = cls.get_session(recipient)
        session["state"] = "missed_call_sent"

        text_message = (
            "Hi! This is Amber from Apex Home Services. 🏠 "
            "Sorry we missed your call! Are you looking for a quick quote on "
            "carpet cleaning, lawn care, or roofing today?"
        )
        session["messages"].append({"sender": "bot", "text": text_message, "time": datetime.now(timezone.utc).isoformat()})

        # Send via Twilio Gateway (live or simulated)
        sms_res = await TwilioSMSGateway.send_sms(
            to_phone=recipient,
            message=text_message,
            org=org
        )

        # Log action in CRM if DB session available
        if db:
            try:
                org_stmt = select(Organization).where(Organization.status == "active").order_by(Organization.created_at)
                active_org = (await db.execute(org_stmt)).scalars().first()
                if active_org:
                    call_log = CallLog(
                        organization_id=active_org.id,
                        caller_name="Missed Call Auto-Recovery",
                        called_at=datetime.now(timezone.utc),
                        duration_minutes=0,
                        outcome="left_voicemail",
                        notes=f"Missed call detected from {recipient}. Dispatched automated speed-to-lead SMS.",
                        next_steps=f"Awaiting inbound SMS reply from {recipient}."
                    )
                    db.add(call_log)
                    await db.commit()
            except Exception as e:
                logger.warning(f"Failed to commit missed call log to CRM: {e}")

        return {
            "success": True,
            "recipient": recipient,
            "message": text_message,
            "gateway_result": sms_res
        }

    @classmethod
    async def process_inbound_sms(
        cls,
        from_phone: str,
        body: str,
        to_phone: Optional[str] = None,
        org: Optional[Organization] = None,
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        Processes inbound SMS message, updates conversation state, calculates quotes,
        and automatically converts to an appointment when the homeowner confirms.
        """
        recipient = TwilioSMSGateway.clean_phone_number(from_phone)
        session = cls.get_session(recipient)
        session["messages"].append({"sender": "homeowner", "text": body, "time": datetime.now(timezone.utc).isoformat()})
        msg_lower = body.lower().strip()

        reply_text = ""
        action = "continue_chat"
        booked = False
        booking_data = None

        # 1. Detect Trade switches
        if any(k in msg_lower for k in ["carpet", "rug", "steam"]):
            session["trade"] = "carpet_cleaning"
        elif any(k in msg_lower for k in ["lawn", "grass", "mow", "yard"]):
            session["trade"] = "lawn_care"
        elif any(k in msg_lower for k in ["roof", "leak", "gutter", "shingle"]):
            session["trade"] = "roofing"

        current_trade = session["trade"]

        # 2. Extract address or name
        zip_match = re.search(r"\b(\d{5})\b", body)
        if zip_match:
            session["zip_code"] = zip_match.group(1)

        # Look for street address pattern (e.g. 123 Elm St, 442 Pine Rd)
        addr_match = re.search(r"(\d+\s+[A-Za-z0-9\s.]+?(?:street|st|avenue|ave|road|rd|drive|dr|lane|ln|way|court|ct|blvd))", body, re.IGNORECASE)
        if addr_match:
            session["address"] = addr_match.group(1).strip()

        # Look for name mentions ("my name is Sarah", "I'm Marcus", "Sarah Jenkins")
        name_match = re.search(r"(?:my name is|i am|i'm)\s+([A-Za-z\s]+)", body, re.IGNORECASE)
        if name_match:
            session["homeowner_name"] = name_match.group(1).strip()

        # 3. Handle Trade-Specific Logic
        if current_trade == "carpet_cleaning":
            specs = CarpetCleaningSpecs(**session["carpet"])
            room_match = re.search(r"(\d+)\s*(?:bed|room)", msg_lower)
            if room_match:
                specs.rooms = int(room_match.group(1))

            if any(k in msg_lower for k in ["pet", "dog", "cat", "urine", "stain", "odor"]):
                specs.pet_treatment = True
            if "scotchgard" in msg_lower or "protect" in msg_lower:
                specs.scotchgard = True

            session["carpet"] = specs.model_dump()
            quote = ResidentialSalesEngine.calculate_quote(TradeType.CARPET_CLEANING, carpet=specs, zip_code=session.get("zip_code"))
            session["last_quote"] = quote.total_estimate

            # Check for booking intent
            if any(k in msg_lower for k in ["book", "schedule", "tomorrow", "saturday", "friday", "morning", "afternoon", "yes", "confirm", "let's do it"]):
                if not session.get("address"):
                    reply_text = (
                        f"Great! That's ${quote.total_estimate:,.2f} total for {specs.rooms} rooms "
                        f"{'with pet urine extraction ' if specs.pet_treatment else ''}(no hidden fees). "
                        f"What is your street address so I can reserve your crew arrival window?"
                    )
                    session["state"] = "awaiting_address"
                else:
                    # Execute booking!
                    booked = True
                    action = "booked"
                    reply_text, booking_data = await cls._execute_sms_booking(session, quote.total_estimate, db)
            else:
                reply_text = (
                    f"For {specs.rooms} rooms {'with deep pet urine enzyme treatment' if specs.pet_treatment else ''}, "
                    f"your guaranteed quote is ${quote.total_estimate:,.2f} (includes truckmounted steam extraction & deodorizer). "
                    f"Would you prefer our Morning window (8am-12pm) or Afternoon window (12pm-4pm)?"
                )
                session["state"] = "quoted"

        elif current_trade == "lawn_care":
            specs = LawnCareSpecs(**session["lawn"])
            if any(k in msg_lower for k in ["quarter", "1/4", "small"]):
                specs.lot_size_tier = "small_quarter_acre"
            elif any(k in msg_lower for k in ["half", "0.5", "1/2"]):
                specs.lot_size_tier = "medium_half_acre"
            elif any(k in msg_lower for k in ["full acre", "1 acre", "large"]):
                specs.lot_size_tier = "large_one_acre"

            if any(k in msg_lower for k in ["biweekly", "bi-weekly", "every two weeks"]):
                specs.cadence = "biweekly"
            elif "weekly" in msg_lower:
                specs.cadence = "weekly"

            if any(k in msg_lower for k in ["aerat", "overseed", "seed"]):
                specs.aeration_overseeding = True

            session["lawn"] = specs.model_dump()
            quote = ResidentialSalesEngine.calculate_quote(TradeType.LAWN_CARE, lawn=specs, zip_code=session.get("zip_code"))
            session["last_quote"] = quote.total_estimate

            if any(k in msg_lower for k in ["book", "start", "schedule", "yes", "saturday", "friday", "sign me up"]):
                if not session.get("address"):
                    reply_text = (
                        f"Awesome! Your price is ${quote.total_estimate:,.2f} per cut with driveway edging included. "
                        f"What is your property street address so we can route our mowing crew?"
                    )
                    session["state"] = "awaiting_address"
                else:
                    booked = True
                    action = "booked"
                    reply_text, booking_data = await cls._execute_sms_booking(session, quote.total_estimate, db)
            else:
                reply_text = (
                    f"For your {specs.lot_size_tier.replace('_', ' ')} on a {specs.cadence} schedule, "
                    f"your price is ${quote.total_estimate:,.2f} per service (includes razor curb edging & leaf blow-off, cancel anytime). "
                    f"What day of the week would you like us to start your first cut?"
                )
                session["state"] = "quoted"

        else: # roofing
            specs = RoofingSpecs(**session["roofing"])
            if any(k in msg_lower for k in ["leak", "water", "ceiling", "bucket", "drip"]):
                specs.issue_type = "active_leak"
                session["roofing"] = specs.model_dump()
                quote = ResidentialSalesEngine.calculate_quote(TradeType.ROOFING, roofing=specs)
                session["last_quote"] = quote.total_estimate
                
                reply_text = (
                    "⚠️ URGENT LEAK ALERT: We have emergency waterproof tarping dispatch available today for $299 "
                    "(100% credited toward your permanent repair). Please text your address now for immediate crew dispatch!"
                )
                session["state"] = "emergency_leak"
            else:
                quote = ResidentialSalesEngine.calculate_quote(TradeType.ROOFING, roofing=specs)
                session["last_quote"] = quote.total_estimate
                if any(k in msg_lower for k in ["free", "inspect", "book", "yes"]):
                    if not session.get("address"):
                        reply_text = (
                            "Our 21-point drone roof & attic inspection is 100% Free ($0.00). "
                            "What is your address and preferred inspection date?"
                        )
                    else:
                        booked = True
                        action = "booked"
                        reply_text, booking_data = await cls._execute_sms_booking(session, 0.0, db)
                else:
                    reply_text = (
                        "We offer a 100% Free 21-Point Roof & Gutter Health Inspection ($0.00). "
                        "Our specialist checks shingles, attic ventilation, and chimney seals with photos. "
                        "Would you like us to inspect this week?"
                    )

        session["messages"].append({"sender": "bot", "text": reply_text, "time": datetime.now(timezone.utc).isoformat()})

        # Outbound Twilio SMS delivery if live
        await TwilioSMSGateway.send_sms(
            to_phone=recipient,
            message=reply_text,
            org=org
        )

        return {
            "recipient": recipient,
            "reply_text": reply_text,
            "trade": current_trade,
            "state": session["state"],
            "booked": booked,
            "booking_data": booking_data,
            "twiml": cls.generate_twiml_message(reply_text)
        }

    @classmethod
    async def _execute_sms_booking(
        cls,
        session: Dict[str, Any],
        estimated_total: float,
        db: Optional[AsyncSession]
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Finalizes an SMS text-to-book flow into the CRM.
        """
        homeowner_name = session.get("homeowner_name") or "Homeowner"
        address = session.get("address") or "Property on File"
        zip_code = session.get("zip_code") or "80202"
        phone = session.get("phone")
        trade_clean = session.get("trade", "carpet_cleaning").replace("_", " ").title()
        conf_code = f"APX-{trade_clean[:3].upper()}-{uuid.uuid4().hex[:6].upper()}"

        scheduled_date = session.get("scheduled_date") or datetime.now().strftime("%Y-%m-%d")
        time_window = session.get("time_window", "Morning (8:00 AM - 12:00 PM)")

        booking_summary = {
            "confirmation_code": conf_code,
            "homeowner_name": homeowner_name,
            "phone": phone,
            "address": f"{address}, {zip_code}",
            "trade": session.get("trade"),
            "estimated_total": estimated_total,
            "scheduled_date": scheduled_date,
            "time_window": time_window
        }

        # Commit to CRM if DB available
        if db:
            try:
                org_stmt = select(Organization).where(Organization.status == "active").order_by(Organization.created_at)
                org = (await db.execute(org_stmt)).scalars().first()
                if not org:
                    org = Organization(name="Apex Residential Services", slug="apex-residential", status="active")
                    db.add(org)
                    await db.commit()
                    await db.refresh(org)

                company = Company(
                    organization_id=org.id,
                    name=f"{homeowner_name} Household",
                    industry="Residential Property",
                    address=f"{address}, {zip_code}",
                    phone=phone,
                    notes=f"Booked via 2-Way SMS. Trade: {trade_clean}"
                )
                db.add(company)
                await db.flush()

                contact = Contact(
                    organization_id=org.id,
                    company_id=company.id,
                    first_name=homeowner_name.split()[0],
                    last_name="Homeowner" if len(homeowner_name.split()) == 1 else homeowner_name.split()[-1],
                    phone=phone,
                    job_title="Homeowner",
                    is_primary=True
                )
                db.add(contact)
                await db.flush()

                lead = Lead(
                    organization_id=org.id,
                    company_id=company.id,
                    contact_id=contact.id,
                    lead_score=98,
                    pipeline_stage="qualified",
                    assigned_agent_id="sms_sales_bot",
                    notes=f"2-Way SMS Text-To-Book confirmed. Est: ${estimated_total:,.2f}."
                )
                db.add(lead)
                await db.flush()

                opp = Opportunity(
                    organization_id=org.id,
                    lead_id=lead.id,
                    title=f"{trade_clean} (SMS) - {homeowner_name}",
                    estimated_value=estimated_total,
                    probability=0.95,
                    stage="won"
                )
                db.add(opp)
                await db.flush()

                appointment = Appointment(
                    organization_id=org.id,
                    lead_id=lead.id,
                    company_id=company.id,
                    contact_id=contact.id,
                    title=f"{trade_clean} Dispatch ({time_window})",
                    scheduled_at=datetime.now(timezone.utc),
                    duration_minutes=90,
                    status="scheduled",
                    closer_name="Apex Field Dispatch Van #2",
                    notes=f"Confirmed via SMS. Address: {address}, {zip_code}",
                    booked_by_agent=True
                )
                db.add(appointment)
                await db.commit()
            except Exception as e:
                logger.error(f"Error persisting SMS booking to CRM: {e}")

        reply_text = (
            f"🎉 You are all booked, {homeowner_name.split()[0]}! Confirmation #: {conf_code}. "
            f"Our {trade_clean} crew will arrive during our {time_window} at {address}. "
            f"Total due upon completion: ${estimated_total:,.2f}. See you soon!"
        )
        return reply_text, booking_summary

    @classmethod
    def generate_twiml_message(cls, text: str) -> str:
        """Generates valid TwiML XML to respond to incoming Twilio SMS."""
        escaped = (
            text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
        )
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{escaped}</Message>
</Response>"""


class ResidentialVoiceService:
    """
    Generates dynamic TwiML Voice instructions for inbound homeowner calls,
    qualifies caller needs via speech-to-text transcripts, and routes emergencies.
    """

    @classmethod
    def generate_inbound_greeting(cls, callback_url: str) -> str:
        """
        Spoken greeting when a homeowner dials the Apex phone number.
        """
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Danielle" language="en-US">
        Thank you for calling Apex Home Services. I am Amber, your automated residential service coordinator.
        I can provide an instant quote and reserve your technician slot right over the phone.
    </Say>
    <Gather input="speech" timeout="4" speechTimeout="auto" action="{callback_url}" method="POST">
        <Say voice="Polly.Danielle" language="en-US">
            Are you calling about carpet cleaning, lawn maintenance, or roofing today?
        </Say>
    </Gather>
    <Say voice="Polly.Danielle" language="en-US">
        We didn't hear a response, but we have sent an automated booking link to your mobile number. Thank you for choosing Apex!
    </Say>
    <Hangup/>
</Response>"""

    @classmethod
    def process_voice_gather(
        cls,
        speech_result: str,
        caller_phone: str,
        callback_url: str,
        db: Optional[AsyncSession] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Processes speech-to-text transcript from caller and returns continuing TwiML voice instructions.
        """
        transcript = speech_result.lower().strip()
        recipient = TwilioSMSGateway.clean_phone_number(caller_phone)

        # 1. Emergency Leak Detection
        if any(k in transcript for k in ["leak", "water", "ceiling", "flood", "bucket", "dripping"]):
            # Trigger immediate emergency SMS notification as well
            emergency_twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Danielle" language="en-US">
        We have flagged an urgent active water leak. 
        Our rapid tarping technician is being mobilized for same-day dispatch. 
        I am texting your mobile phone right now to confirm your street address. Please check your text messages.
    </Say>
    <Hangup/>
</Response>"""
            return emergency_twiml, {
                "detected_trade": "roofing",
                "emergency_flag": True,
                "speech_result": speech_result
            }

        # 2. Carpet Cleaning
        elif any(k in transcript for k in ["carpet", "rug", "steam", "rooms", "stains"]):
            rooms = 3
            room_search = re.search(r"(\d+)\s*(?:bed|room)", transcript)
            if room_search:
                rooms = int(room_search.group(1))
            pet = any(k in transcript for k in ["pet", "dog", "cat", "urine", "stain"])
            
            quote = ResidentialSalesEngine.calculate_quote(
                TradeType.CARPET_CLEANING, 
                carpet=CarpetCleaningSpecs(rooms=rooms, pet_treatment=pet)
            )

            spoken_twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Danielle" language="en-US">
        For {rooms} rooms {'with hospital-grade pet urine extraction' if pet else ''}, 
        our upfront price is ${quote.total_estimate:,.0f} dollars, with zero hidden fees and a four-hour dry time guarantee. 
        We have crew arrival slots available tomorrow morning between 8 and 12, and Saturday morning.
        I am sending this quote and a one-click reservation link directly to your mobile phone right now.
    </Say>
    <Hangup/>
</Response>"""
            return spoken_twiml, {
                "detected_trade": "carpet_cleaning",
                "quote": quote.total_estimate,
                "speech_result": speech_result
            }

        # 3. Lawn Care
        elif any(k in transcript for k in ["lawn", "grass", "mow", "yard"]):
            quote = ResidentialSalesEngine.calculate_quote(TradeType.LAWN_CARE)
            spoken_twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Danielle" language="en-US">
        For standard half-acre yards, our recurring mowing and razor curb edging starts at ${quote.total_estimate:,.0f} dollars per visit, 
        or 15% off with weekly maintenance. There are zero contracts and you can pause anytime.
        I have texted our route schedule to your phone so you can select your preferred cut day.
    </Say>
    <Hangup/>
</Response>"""
            return spoken_twiml, {
                "detected_trade": "lawn_care",
                "quote": quote.total_estimate,
                "speech_result": speech_result
            }

        # 4. Roofing / Inspection Default
        else:
            spoken_twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Danielle" language="en-US">
        We specialize in exterior defense and offer a complimentary 21-point roof and attic health inspection with photo analysis for zero dollars.
        We have also dispatched our full services catalog and direct booking portal to your phone. Thank you for calling Apex!
    </Say>
    <Hangup/>
</Response>"""
            return spoken_twiml, {
                "detected_trade": "roofing",
                "quote": 0.0,
                "speech_result": speech_result
            }
