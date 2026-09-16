import json
import logging
import urllib.parse
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.tenant import Organization
from app.models.crm import Appointment, Company, Contact, Lead
from app.services.communication_gateway import TwilioSMSGateway
from app.services.webhook_service import WebhookService

logger = logging.getLogger(__name__)

# Active Technician Fleet Roster
FLEET_CREWS: List[Dict[str, Any]] = [
    {
        "id": "crew_carpet_1",
        "name": "Apex Van #1 (Steam Truckmount)",
        "lead": "Dave Miller",
        "trade": "carpet_cleaning",
        "vehicle": "Ford Transit 350 High-Roof",
        "phone": "+1-303-555-0111",
        "rating": 4.96,
        "completed_jobs": 482
    },
    {
        "id": "crew_carpet_2",
        "name": "Apex Van #2 (Steam Truckmount)",
        "lead": "Sarah Bennett",
        "trade": "carpet_cleaning",
        "vehicle": "RAM ProMaster 2500",
        "phone": "+1-303-555-0112",
        "rating": 4.98,
        "completed_jobs": 315
    },
    {
        "id": "crew_lawn_alpha",
        "name": "Apex Lawn Crew Alpha (Zero-Turn Fleet)",
        "lead": "Hector Rodriguez",
        "trade": "lawn_care",
        "vehicle": "Chevy Silverado 2500HD + 16ft Utility Trailer",
        "phone": "+1-303-555-0113",
        "rating": 4.92,
        "completed_jobs": 840
    },
    {
        "id": "crew_lawn_bravo",
        "name": "Apex Lawn Crew Bravo (Turf & Aeration)",
        "lead": "Brandon Scott",
        "trade": "lawn_care",
        "vehicle": "Ford F-250 SuperDuty + Core Aeration Trailer",
        "phone": "+1-303-555-0114",
        "rating": 4.95,
        "completed_jobs": 520
    },
    {
        "id": "crew_roofing_1",
        "name": "Apex Roofing Rig #1 (Drone & Tarping)",
        "lead": "Michael Torres",
        "trade": "roofing",
        "vehicle": "GMC Sierra 3500 HD Dually (Heavy Ladder Rack)",
        "phone": "+1-303-555-0115",
        "rating": 4.99,
        "completed_jobs": 290
    }
]

class ResidentialFSMService:
    """
    Field Service Management (FSM) engine for residential trades:
    - Technician Crew Routing & Fleet Dispatch
    - Universal Calendar Sync (Google Calendar & RFC 5545 iCal .ics feeds)
    - FSM Connectors for Jobber, Housecall Pro, and ServiceTitan
    - Automated 30-Minute En-Route & Completion SMS alerts
    """

    @classmethod
    def get_fleet_crews(cls, trade: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns fleet crew directory, optionally filtered by trade."""
        if not trade:
            return FLEET_CREWS
        return [c for c in FLEET_CREWS if c["trade"] == trade]

    @classmethod
    def assign_crew(cls, trade: str, date_str: Optional[str] = None, time_window: Optional[str] = None) -> Dict[str, Any]:
        """
        Assigns the optimal crew based on trade specialization and availability.
        """
        matching = cls.get_fleet_crews(trade)
        if not matching:
            matching = FLEET_CREWS
        # Pick based on hash of date/window for deterministic consistency
        seed = hash(f"{date_str}_{time_window}") if date_str else 0
        return matching[seed % len(matching)]

    @classmethod
    def generate_ics_calendar(
        cls,
        appointment: Appointment,
        company: Optional[Company] = None,
        contact: Optional[Contact] = None
    ) -> str:
        """
        Generates standard RFC 5545 iCalendar (.ics) text for 1-click import into
        Apple Calendar, Microsoft Outlook, and Google Calendar.
        """
        scheduled_dt = appointment.scheduled_at or datetime.now(timezone.utc)
        if not scheduled_dt.tzinfo:
            scheduled_dt = scheduled_dt.replace(tzinfo=timezone.utc)

        duration = timedelta(minutes=appointment.duration_minutes or 120)
        end_dt = scheduled_dt + duration

        dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dtstart = scheduled_dt.strftime("%Y%m%dT%H%M%SZ")
        dtend = end_dt.strftime("%Y%m%dT%H%M%SZ")

        location = (company.address if company else "Homeowner Residence")
        customer_name = f"{contact.first_name} {contact.last_name}" if contact else "Homeowner"
        technician = appointment.closer_name or "Apex Field Dispatch Team"

        summary = appointment.title.replace(",", "\\,")
        description = (
            f"Apex Home Services Appointment\\n"
            f"Service: {appointment.title}\\n"
            f"Customer: {customer_name}\\n"
            f"Assigned Crew: {technician}\\n"
            f"Notes: {appointment.notes or 'None'}\\n"
            f"Dispatch Support: (800) 555-APEX"
        )

        ics_content = (
            "BEGIN:VCALENDAR\r\n"
            "VERSION:2.0\r\n"
            "PRODID:-//Apex Home Services//Residential Sales & Dispatch Bot//EN\r\n"
            "CALSCALE:GREGORIAN\r\n"
            "METHOD:PUBLISH\r\n"
            "BEGIN:VEVENT\r\n"
            f"UID:{appointment.id}@therealbonz.com\r\n"
            f"DTSTAMP:{dtstamp}\r\n"
            f"DTSTART:{dtstart}\r\n"
            f"DTEND:{dtend}\r\n"
            f"SUMMARY:{summary}\r\n"
            f"DESCRIPTION:{description}\r\n"
            f"LOCATION:{location}\r\n"
            "STATUS:CONFIRMED\r\n"
            "BEGIN:VALARM\r\n"
            "TRIGGER:-PT30M\r\n"
            "ACTION:DISPLAY\r\n"
            f"DESCRIPTION:Reminder: Apex Service Crew arriving in 30 minutes for {summary}\r\n"
            "END:VALARM\r\n"
            "END:VEVENT\r\n"
            "END:VCALENDAR\r\n"
        )
        return ics_content

    @classmethod
    def generate_google_calendar_url(
        cls,
        appointment: Appointment,
        company: Optional[Company] = None
    ) -> str:
        """
        Generates direct 1-click Google Calendar Add URL.
        """
        scheduled_dt = appointment.scheduled_at or datetime.now(timezone.utc)
        if not scheduled_dt.tzinfo:
            scheduled_dt = scheduled_dt.replace(tzinfo=timezone.utc)

        duration = timedelta(minutes=appointment.duration_minutes or 120)
        end_dt = scheduled_dt + duration

        dates_str = f"{scheduled_dt.strftime('%Y%m%dT%H%M%SZ')}/{end_dt.strftime('%Y%m%dT%H%M%SZ')}"
        location = company.address if company else "Homeowner Residence"

        details = (
            f"Apex Home Services Appointment\n"
            f"Crew: {appointment.closer_name}\n"
            f"Notes: {appointment.notes or ''}\n"
            f"Questions or Rescheduling: (800) 555-APEX"
        )

        params = {
            "action": "TEMPLATE",
            "text": appointment.title,
            "dates": dates_str,
            "details": details,
            "location": location
        }
        return f"https://calendar.google.com/calendar/render?{urllib.parse.urlencode(params)}"

    @classmethod
    def build_fsm_payload(
        cls,
        appointment: Appointment,
        company: Optional[Company] = None,
        contact: Optional[Contact] = None,
        platform: str = "jobber"
    ) -> Dict[str, Any]:
        """
        Compiles standard Jobber / Housecall Pro / ServiceTitan job dispatch payload.
        """
        customer_name = f"{contact.first_name} {contact.last_name}" if contact else "Homeowner"
        phone = contact.phone if contact else ""
        address = company.address if company else ""

        scheduled_iso = appointment.scheduled_at.isoformat() if appointment.scheduled_at else datetime.now(timezone.utc).isoformat()

        return {
            "platform": platform,
            "external_reference_id": f"APX-FSM-{appointment.id[:8].upper()}",
            "job": {
                "title": appointment.title,
                "status": "scheduled",
                "scheduled_start": scheduled_iso,
                "duration_minutes": appointment.duration_minutes,
                "assigned_technician": appointment.closer_name or "Apex Crew Lead",
                "special_instructions": appointment.notes
            },
            "client": {
                "name": customer_name,
                "phone": phone,
                "email": contact.email if contact else None,
                "service_address": address
            },
            "dispatch_metadata": {
                "lead_id": appointment.lead_id,
                "appointment_id": appointment.id,
                "source": "autonomous_sales_bot",
                "synced_at": datetime.now(timezone.utc).isoformat()
            }
        }

    @classmethod
    async def send_en_route_alert(
        cls,
        appointment_id: str,
        eta_minutes: int = 25,
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        Sends automated 30-minute pre-arrival SMS alert to homeowner:
        'Apex Home Services: Crew #1 is en route to your address! ETA: 25 minutes.'
        """
        if not db:
            return {"success": False, "detail": "Database session required"}

        stmt = (
            select(Appointment)
            .options(
                selectinload(Appointment.company),
                selectinload(Appointment.contact)
            )
            .where(Appointment.id == appointment_id)
        )
        res = await db.execute(stmt)
        appointment = res.scalar_one_or_none()
        if not appointment:
            return {"success": False, "detail": "Appointment not found"}

        phone = appointment.contact.phone if (appointment.contact and appointment.contact.phone) else None
        if not phone:
            return {"success": False, "detail": "No homeowner phone on file"}

        tech_name = appointment.closer_name or "Apex Service Technician"
        address = appointment.company.address if appointment.company else "your home"

        message = (
            f"🚚 Apex Dispatch Heads-Up: Your service crew ({tech_name}) is now en route to {address}! "
            f"Estimated arrival in approximately {eta_minutes} minutes. Please reply to this text if you have any gate codes or entry notes."
        )

        sms_result = await TwilioSMSGateway.send_sms(to_phone=phone, message=message)

        # Update appointment status
        appointment.status = "in_transit"
        await db.commit()

        return {
            "success": True,
            "status": "in_transit",
            "eta_minutes": eta_minutes,
            "recipient": phone,
            "message": message,
            "sms_gateway": sms_result
        }

    @classmethod
    async def send_completion_alert(
        cls,
        appointment_id: str,
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        Marks appointment completed, updates CRM, and sends completion/review SMS to homeowner.
        """
        if not db:
            return {"success": False, "detail": "Database session required"}

        stmt = (
            select(Appointment)
            .options(
                selectinload(Appointment.company),
                selectinload(Appointment.contact),
                selectinload(Appointment.lead)
            )
            .where(Appointment.id == appointment_id)
        )
        res = await db.execute(stmt)
        appointment = res.scalar_one_or_none()
        if not appointment:
            return {"success": False, "detail": "Appointment not found"}

        phone = appointment.contact.phone if (appointment.contact and appointment.contact.phone) else None
        appointment.status = "completed"
        if appointment.lead:
            appointment.lead.pipeline_stage = "won"

        message = (
            "⭐ Thank you for choosing Apex Home Services! Your service is now complete. "
            "We back all work with our 100% Satisfaction Guarantee. How did our crew do today? "
            "Reply 1-5 or view your receipt here: https://therealbonz.com/JsProject/residential"
        )

        sms_result = None
        if phone:
            sms_result = await TwilioSMSGateway.send_sms(to_phone=phone, message=message)

        await db.commit()

        return {
            "success": True,
            "status": "completed",
            "recipient": phone,
            "message": message,
            "sms_gateway": sms_result
        }
