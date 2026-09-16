import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from main import app
from app.core.database import engine, Base
from app.services.residential_telephony_service import (
    ResidentialSMSService, ResidentialVoiceService, _SMS_SESSION_CACHE
)

@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    _SMS_SESSION_CACHE.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_speed_to_lead_missed_call_trigger():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Simulate missed call via simulator endpoint
        caller = "+13035550199"
        res = await client.post("/api/v1/residential/simulate/missed_call", json={
            "caller_phone": caller
        })
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "Sorry we missed your call" in data["dispatched_sms"]
        assert "carpet cleaning, lawn care, or roofing" in data["dispatched_sms"]

        # Verify session state was created
        session = ResidentialSMSService.get_session(caller)
        assert session["state"] == "missed_call_sent"
        assert len(session["messages"]) >= 1

@pytest.mark.asyncio
async def test_inbound_sms_multi_turn_carpet_qualification():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        caller = "+17205559812"

        # 1. Homeowner texts requirements
        res = await client.post("/api/v1/residential/sms/webhook", data={
            "From": caller,
            "Body": "Hi, I have 3 bedrooms with heavy pet urine stains that need deep steam cleaning"
        })
        assert res.status_code == 200
        assert "application/xml" in res.headers["content-type"]
        xml_text = res.text
        assert "$190.00" in xml_text
        assert "pet urine" in xml_text.lower()
        assert "Morning window (8am-12pm) or Afternoon" in xml_text

        # 2. Check session cache
        session = ResidentialSMSService.get_session(caller)
        assert session["carpet"]["rooms"] == 3
        assert session["carpet"]["pet_treatment"] is True
        assert session["last_quote"] == 190.0

@pytest.mark.asyncio
async def test_inbound_sms_text_to_book_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        caller = "+13035554433"

        # 1. Initial inquiry for lawn care
        res1 = await client.post("/api/v1/residential/simulate/sms", json={
            "from_phone": caller,
            "body": "Need bi-weekly mowing for my 0.5 acre lawn"
        })
        assert res1.status_code == 200
        d1 = res1.json()
        assert "$65.00" in d1["reply"]
        assert d1["booked"] is False

        # 2. Confirm booking with address
        res2 = await client.post("/api/v1/residential/simulate/sms", json={
            "from_phone": caller,
            "body": "Saturday works great. Address is 819 Willowbrook Lane, 80014. My name is Marcus Vance."
        })
        assert res2.status_code == 200
        d2 = res2.json()
        assert d2["booked"] is True
        assert "all booked" in d2["reply"].lower()
        assert "APX-LAW-" in d2["reply"]
        assert d2["booking_data"]["estimated_total"] == 65.0
        assert d2["booking_data"]["address"] == "819 Willowbrook Lane, 80014"

        # 3. Verify bookings list in CRM
        res_list = await client.get("/api/v1/residential/bookings")
        assert res_list.status_code == 200
        b_data = res_list.json()
        assert b_data["count"] >= 1
        assert any("Marcus Vance" in b["homeowner"] for b in b_data["bookings"])

@pytest.mark.asyncio
async def test_inbound_voice_twiml_generation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.post("/api/v1/residential/voice/inbound")
        assert res.status_code == 200
        assert "application/xml" in res.headers["content-type"]
        xml = res.text
        assert "<Response>" in xml
        assert "Polly.Danielle" in xml
        assert "Apex Home Services" in xml
        assert "<Gather" in xml
        assert "voice/gather" in xml

@pytest.mark.asyncio
async def test_voice_gather_emergency_leak_triage():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Inbound speech reporting active roof leak
        res = await client.post("/api/v1/residential/voice/gather", data={
            "From": "+13035559999",
            "SpeechResult": "Emergency: we have water leaking through our kitchen ceiling light right now!"
        })
        assert res.status_code == 200
        xml = res.text
        assert "urgent active water leak" in xml.lower()
        assert "rapid tarping technician" in xml.lower()

@pytest.mark.asyncio
async def test_telephony_simulator_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        caller = "+13035558888"

        # Voice simulator
        res_v = await client.post("/api/v1/residential/simulate/voice", json={
            "speech": "I need carpet steam cleaning for 3 bedrooms",
            "caller_phone": caller
        })
        assert res_v.status_code == 200
        v_data = res_v.json()
        assert "spoken_text" in v_data
        assert "carpet_cleaning" in v_data["metadata"]["detected_trade"]

        # Messages list
        res_m = await client.get(f"/api/v1/residential/simulate/messages?phone={caller}")
        assert res_m.status_code == 200
        assert "messages" in res_m.json()
