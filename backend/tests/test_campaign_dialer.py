import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from main import app
from app.core.database import engine, Base
from app.models.tenant import Organization
from app.models.crm import ProspectCampaign, Lead, Company, Contact, Appointment, CallLog
from app.services.prospect_import_service import ProspectImportService
from app.services.campaign_dialer_service import CampaignDialerService
from app.schemas.dialer import CampaignDialRequest

@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_trade_script_personalization():
    carpet_script = CampaignDialerService.get_trade_script(
        trade="carpet_cleaning",
        homeowner_name="Marcus Vance",
        address="123 Alpine Way"
    )
    assert "Marcus" in carpet_script["greeting"]
    assert "$45 per room" in carpet_script["pitch"]
    assert "123 Alpine Way" in carpet_script["pitch"]
    assert "voicemail" in carpet_script["voicemail_message"].lower() or "amber" in carpet_script["voicemail_message"].lower()

    lawn_script = CampaignDialerService.get_trade_script(
        trade="lawn_care",
        homeowner_name="Samantha Reed",
        address="456 Pine Ln"
    )
    assert "Samantha" in lawn_script["greeting"]
    assert "15% season discount" in lawn_script["pitch"]

    roof_script = CampaignDialerService.get_trade_script(
        trade="roofing",
        homeowner_name="Robert Sterling",
        address="789 Summit Dr"
    )
    assert "Robert" in roof_script["greeting"]
    assert "21-point" in roof_script["pitch"]


@pytest.mark.asyncio
async def test_dial_single_lead_booking_flow():
    async with AsyncSession(engine, expire_on_commit=False) as session:
        org = Organization(name="Dialer Test Org", slug="dialer-test-org", status="active")
        session.add(org)
        await session.commit()
        org_id = org.id

        campaign = ProspectCampaign(
            organization_id=org_id,
            name="Denver Carpet Campaign",
            trade_service="carpet_cleaning",
            status="ready",
            total_rows=1
        )
        session.add(campaign)
        await session.commit()
        campaign_id = campaign.id

        company = Company(
            organization_id=org_id,
            name="Vance Residence",
            phone="+13035559001",
            address="123 Alpine Way",
            industry="Residential Services"
        )
        session.add(company)
        await session.flush()
        company_id = company.id

        contact = Contact(
            organization_id=org_id,
            company_id=company_id,
            first_name="Marcus",
            last_name="Vance",
            phone="+13035559001",
            email="marcus@example.com",
            decision_maker_role="homeowner"
        )
        session.add(contact)
        await session.flush()
        contact_id = contact.id

        lead = Lead(
            organization_id=org_id,
            company_id=company_id,
            contact_id=contact_id,
            campaign_id=campaign_id,
            pipeline_stage="ready_contact",
            status="active"
        )
        session.add(lead)
        await session.commit()
        lead_id = lead.id

        # Dial lead with simulated booking
        result = await CampaignDialerService.dial_single_lead(
            lead_id=lead_id,
            campaign_id=campaign_id,
            db=session,
            simulate=True,
            simulated_outcome="booked"
        )

        assert result.outcome == "booked"
        assert result.appointment_id is not None
        assert result.appointment_slot is not None
        assert "Marcus" in result.contact_name

        # Verify DB records
        appt = await session.get(Appointment, result.appointment_id)
        assert appt is not None
        assert appt.booked_by_agent is True
        assert appt.status == "scheduled"

        refreshed_lead = await session.get(Lead, lead_id)
        assert refreshed_lead.pipeline_stage == "won"
        assert refreshed_lead.last_call_outcome == "booked"

        # Verify CallLog
        call_logs = (await session.execute(select(CallLog).where(CallLog.lead_id == lead_id))).scalars().all()
        assert len(call_logs) == 1
        assert call_logs[0].outcome == "booked"


@pytest.mark.asyncio
async def test_dial_single_lead_voicemail_flow():
    async with AsyncSession(engine, expire_on_commit=False) as session:
        org = Organization(name="Voicemail Test Org", slug="vm-test-org", status="active")
        session.add(org)
        await session.commit()
        org_id = org.id

        campaign = ProspectCampaign(
            organization_id=org_id,
            name="Boulder Lawn Campaign",
            trade_service="lawn_care",
            status="ready",
            total_rows=1
        )
        session.add(campaign)
        await session.commit()
        campaign_id = campaign.id

        company = Company(organization_id=org_id, name="Reed Residence", phone="+13035559002")
        session.add(company)
        await session.flush()
        company_id = company.id

        contact = Contact(organization_id=org_id, company_id=company_id, first_name="Samantha", last_name="Reed", phone="+13035559002")
        session.add(contact)
        await session.flush()
        contact_id = contact.id

        lead = Lead(organization_id=org_id, company_id=company_id, contact_id=contact_id, campaign_id=campaign_id, pipeline_stage="ready_contact", status="active")
        session.add(lead)
        await session.commit()
        lead_id = lead.id

        result = await CampaignDialerService.dial_single_lead(
            lead_id=lead_id,
            campaign_id=campaign_id,
            db=session,
            simulate=True,
            simulated_outcome="voicemail"
        )

        assert result.outcome == "voicemail"
        assert result.appointment_id is None
        assert result.sms_followup_sent is True

        refreshed_lead = await session.get(Lead, lead_id)
        assert refreshed_lead.pipeline_stage == "contacted"
        assert refreshed_lead.last_call_outcome == "voicemail"


@pytest.mark.asyncio
async def test_dial_single_lead_dnc_flow():
    async with AsyncSession(engine, expire_on_commit=False) as session:
        org = Organization(name="DNC Test Org", slug="dnc-test-org", status="active")
        session.add(org)
        await session.commit()
        org_id = org.id

        campaign = ProspectCampaign(organization_id=org_id, name="Roofing Campaign", trade_service="roofing", status="ready")
        session.add(campaign)
        await session.commit()
        campaign_id = campaign.id

        company = Company(organization_id=org_id, name="Sterling Residence", phone="+13035559003")
        session.add(company)
        await session.flush()
        company_id = company.id

        contact = Contact(organization_id=org_id, company_id=company_id, first_name="Robert", last_name="Sterling", phone="+13035559003")
        session.add(contact)
        await session.flush()
        contact_id = contact.id

        lead = Lead(organization_id=org_id, company_id=company_id, contact_id=contact_id, campaign_id=campaign_id, pipeline_stage="ready_contact", status="active")
        session.add(lead)
        await session.commit()
        lead_id = lead.id

        result = await CampaignDialerService.dial_single_lead(
            lead_id=lead_id,
            campaign_id=campaign_id,
            db=session,
            simulate=True,
            simulated_outcome="dnc"
        )

        assert result.outcome == "dnc"
        refreshed_lead = await session.get(Lead, lead_id)
        assert refreshed_lead.status == "dnc"
        assert refreshed_lead.pipeline_stage == "lost"


@pytest.mark.asyncio
async def test_batch_campaign_execution():
    async with AsyncSession(engine, expire_on_commit=False) as session:
        org = Organization(name="Batch Test Org", slug="batch-test-org", status="active")
        session.add(org)
        await session.commit()
        org_id = org.id

        csv_data = (
            "Name,Phone,Email,Address,Service\r\n"
            "Dave Miller,3035551111,dave@example.com,100 High St,Carpet Cleaning\r\n"
            "Sarah Connor,3035552222,sarah@example.com,200 Elm St,Carpet Cleaning\r\n"
            "Kyle Reese,3035553333,kyle@example.com,300 Oak St,Carpet Cleaning\r\n"
        )

        import_res = await ProspectImportService.execute_import(
            file_bytes=csv_data.encode("utf-8"),
            campaign_name="Terminator Carpet Blast",
            trade_service="carpet_cleaning",
            organization=org,
            db=session,
            skip_duplicates=True
        )
        campaign_id = import_res.campaign_id

        # Batch dial all 3
        progress = await CampaignDialerService.run_campaign_batch(
            campaign_id=campaign_id,
            organization_id=org_id,
            db=session,
            batch_size=10,
            simulate=True,
            simulated_outcome="booked"
        )

        assert progress.total_leads == 3
        assert progress.dialed_count == 3
        assert progress.pending_leads == 0
        assert progress.booked_count == 3
        assert progress.status == "completed"
        assert len(progress.results) == 3


@pytest.mark.asyncio
async def test_campaign_dialer_api_endpoints():
    transport = ASGITransport(app=app)
    campaign_id = None

    async with AsyncSession(engine, expire_on_commit=False) as session:
        org = Organization(name="API Test Org", slug="api-test-org", status="active")
        session.add(org)
        await session.commit()

        csv_data = (
            "Name,Phone,Email,Service\r\n"
            "James Bond,3035550007,007@example.com,Carpet Cleaning\r\n"
        )
        import_res = await ProspectImportService.execute_import(
            file_bytes=csv_data.encode("utf-8"),
            campaign_name="Secret Agent Promo",
            trade_service="carpet_cleaning",
            organization=org,
            db=session
        )
        campaign_id = import_res.campaign_id

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Test dial_next
        dial_res = await client.post(
            f"/api/v1/residential/campaigns/{campaign_id}/dial_next",
            json={"simulate": True, "simulated_outcome": "booked"}
        )
        assert dial_res.status_code == 200
        dial_data = dial_res.json()
        assert dial_data["outcome"] == "booked"
        assert dial_data["appointment_id"] is not None

        # Test progress endpoint
        prog_res = await client.get(f"/api/v1/residential/campaigns/{campaign_id}/progress")
        assert prog_res.status_code == 200
        prog_data = prog_res.json()
        assert prog_data["total_leads"] == 1
        assert prog_data["dialed_count"] == 1
        assert prog_data["booked_count"] == 1
        assert prog_data["status"] == "completed"
