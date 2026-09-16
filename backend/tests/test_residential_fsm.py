import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from main import app
from app.core.database import engine, Base
from app.services.residential_fsm_service import ResidentialFSMService

@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_fsm_fleet_roster_and_trade_filtering():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # All crews
        res = await client.get("/api/v1/residential/fsm/crews")
        assert res.status_code == 200
        data = res.json()
        assert len(data["crews"]) >= 5
        assert any(c["lead"] == "Dave Miller" for c in data["crews"])
        assert any(c["lead"] == "Hector Rodriguez" for c in data["crews"])
        assert any(c["lead"] == "Michael Torres" for c in data["crews"])

        # Filter by trade
        res_carpet = await client.get("/api/v1/residential/fsm/crews?trade=carpet_cleaning")
        assert res_carpet.status_code == 200
        carpet_crews = res_carpet.json()["crews"]
        assert len(carpet_crews) == 2
        assert all(c["trade"] == "carpet_cleaning" for c in carpet_crews)

@pytest.mark.asyncio
async def test_fsm_crew_assignment_router():
    carpet_crew = ResidentialFSMService.assign_crew("carpet_cleaning")
    assert carpet_crew["trade"] == "carpet_cleaning"
    assert "Van" in carpet_crew["name"]

    lawn_crew = ResidentialFSMService.assign_crew("lawn_care")
    assert lawn_crew["trade"] == "lawn_care"
    assert "Lawn" in lawn_crew["name"]

    roofing_crew = ResidentialFSMService.assign_crew("roofing")
    assert roofing_crew["trade"] == "roofing"
    assert "Roofing" in roofing_crew["name"]

@pytest.mark.asyncio
async def test_appointment_calendar_ics_and_google():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Book test appointment
        booking_payload = {
            "trade": "carpet_cleaning",
            "service_summary": "Master Carpet Steam Extraction (3 Rooms)",
            "homeowner_name": "Elena Rostova",
            "phone": "+1-303-555-0922",
            "email": "elena.rostova@example.com",
            "address": "772 Aspen Creek Rd",
            "zip_code": "80204",
            "scheduled_date": "2026-09-24",
            "time_window": "morning",
            "estimated_total": 190.0,
            "special_instructions": "Please be careful with hardwood transitions."
        }
        res_book = await client.post("/api/v1/residential/book", json=booking_payload)
        assert res_book.status_code == 200
        appt_id = res_book.json()["appointment_id"]

        # 2. Download .ics calendar file
        res_ics = await client.get(f"/api/v1/residential/calendar/{appt_id}.ics")
        assert res_ics.status_code == 200
        assert "text/calendar" in res_ics.headers["content-type"]
        ics_text = res_ics.text
        assert "BEGIN:VCALENDAR" in ics_text
        assert "VERSION:2.0" in ics_text
        assert "BEGIN:VEVENT" in ics_text
        assert "STATUS:CONFIRMED" in ics_text
        assert "772 Aspen Creek Rd" in ics_text
        assert "Elena Rostova" in ics_text
        assert "END:VCALENDAR" in ics_text

        # 3. Google Calendar link
        res_google = await client.get(f"/api/v1/residential/calendar/{appt_id}/google")
        assert res_google.status_code == 200
        g_data = res_google.json()
        assert "google_calendar_url" in g_data
        assert "https://calendar.google.com/calendar/render?action=TEMPLATE" in g_data["google_calendar_url"]
        assert "772+Aspen+Creek" in g_data["google_calendar_url"]

@pytest.mark.asyncio
async def test_fsm_jobber_sync_payload():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Book appointment
        booking_payload = {
            "trade": "lawn_care",
            "service_summary": "Bi-Weekly Lawn Care (0.5 Acre)",
            "homeowner_name": "Marcus Vance",
            "phone": "+1-720-555-4819",
            "address": "819 Willowbrook Lane",
            "zip_code": "80014",
            "scheduled_date": "2026-09-25",
            "time_window": "afternoon",
            "estimated_total": 65.0
        }
        res_book = await client.post("/api/v1/residential/book", json=booking_payload)
        appt_id = res_book.json()["appointment_id"]

        # Sync to Jobber
        res_sync = await client.post(f"/api/v1/residential/fsm/sync/{appt_id}?platform=jobber")
        assert res_sync.status_code == 200
        sync_data = res_sync.json()
        assert sync_data["success"] is True
        assert sync_data["platform"] == "jobber"
        assert sync_data["payload"]["client"]["name"] == "Marcus Vance"
        assert sync_data["payload"]["client"]["service_address"] == "819 Willowbrook Lane, 80014"

@pytest.mark.asyncio
async def test_technician_en_route_and_completion_alerts():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Book appointment
        booking_payload = {
            "trade": "roofing",
            "service_summary": "Emergency Active Leak Waterproof Tarping Dispatch",
            "homeowner_name": "Dave Robinson",
            "phone": "+1-303-555-9921",
            "address": "1042 Evergreen Terrace",
            "zip_code": "80123",
            "scheduled_date": "2026-09-18",
            "time_window": "morning",
            "estimated_total": 299.0
        }
        res_book = await client.post("/api/v1/residential/book", json=booking_payload)
        appt_id = res_book.json()["appointment_id"]

        # 1. Dispatch 30-min en-route alert
        res_route = await client.post("/api/v1/residential/fsm/en_route", json={
            "appointment_id": appt_id,
            "eta_minutes": 20
        })
        assert res_route.status_code == 200
        route_data = res_route.json()
        assert route_data["success"] is True
        assert route_data["status"] == "in_transit"
        assert "en route" in route_data["message"].lower()
        assert "20 minutes" in route_data["message"]

        # 2. Dispatch completion alert
        res_comp = await client.post("/api/v1/residential/fsm/complete", json={
            "appointment_id": appt_id
        })
        assert res_comp.status_code == 200
        comp_data = res_comp.json()
        assert comp_data["success"] is True
        assert comp_data["status"] == "completed"
        assert "Satisfaction Guarantee" in comp_data["message"]
