import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from main import app
from app.core.database import engine, Base
from app.services.residential_sales_engine import ResidentialSalesEngine
from app.schemas.residential import (
    TradeType, CarpetCleaningSpecs, LawnCareSpecs, RoofingSpecs
)

@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_residential_web_portal_route():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Test root /residential
        res = await client.get("/residential")
        assert res.status_code == 200
        assert "text/html" in res.headers["content-type"]
        assert "Apex Home Services" in res.text
        assert "Carpet Cleaning" in res.text
        assert "Lawn Care" in res.text
        assert "Roofing & Gutters" in res.text
        assert "Amber • Lead Service Coordinator" in res.text

        # Test sub-path /JsProject/residential
        res_sub = await client.get("/JsProject/residential")
        assert res_sub.status_code == 200
        assert "1-Click Test Scenarios" in res_sub.text

@pytest.mark.asyncio
async def test_carpet_cleaning_quote_calculation():
    # 1. Standard 3 rooms + 1 hallway + pet urine treatment
    specs = CarpetCleaningSpecs(rooms=3, hallways=1, pet_treatment=True, scotchgard=False)
    quote = ResidentialSalesEngine.calculate_quote(TradeType.CARPET_CLEANING, carpet=specs)
    
    # 3 rooms * 45 = 135; 1 hallway = 20; pet treatment = 35; total = 190.0
    assert quote.subtotal == 190.0
    assert quote.total_estimate == 190.0
    assert any("Pet Urine" in item.title for item in quote.line_items)

    # 2. Minimum callout fee: 1 room ($45) < $120 minimum callout
    min_specs = CarpetCleaningSpecs(rooms=1, hallways=0, pet_treatment=False)
    min_quote = ResidentialSalesEngine.calculate_quote(TradeType.CARPET_CLEANING, carpet=min_specs)
    assert min_quote.total_estimate == 120.0
    assert min_quote.minimum_callout_applied is True
    assert any("Minimum Service Call" in item.title for item in min_quote.line_items)

    # 3. Promo code discount (SPRING20 = 20% off)
    promo_quote = ResidentialSalesEngine.calculate_quote(
        TradeType.CARPET_CLEANING, 
        carpet=specs, 
        promo_code="SPRING20"
    )
    assert promo_quote.discount_amount == 38.0  # 20% of 190
    assert promo_quote.total_estimate == 152.0
    assert "20% Off" in promo_quote.discount_label

@pytest.mark.asyncio
async def test_lawn_care_quote_calculation():
    # 1. Medium half acre, bi-weekly
    specs = LawnCareSpecs(lot_size_tier="medium_half_acre", cadence="biweekly")
    quote = ResidentialSalesEngine.calculate_quote(TradeType.LAWN_CARE, lawn=specs)
    assert quote.total_estimate == 65.0
    assert quote.discount_amount == 0.0

    # 2. Weekly maintenance gets 15% VIP discount
    weekly_specs = LawnCareSpecs(lot_size_tier="medium_half_acre", cadence="weekly")
    weekly_quote = ResidentialSalesEngine.calculate_quote(TradeType.LAWN_CARE, lawn=weekly_specs)
    assert weekly_quote.total_estimate == 55.25
    assert weekly_quote.discount_amount == 9.75
    assert "15% Discount" in weekly_quote.discount_label

    # 3. Add core aeration & overseeding
    aeration_specs = LawnCareSpecs(lot_size_tier="medium_half_acre", cadence="biweekly", aeration_overseeding=True)
    aeration_quote = ResidentialSalesEngine.calculate_quote(TradeType.LAWN_CARE, lawn=aeration_specs)
    assert aeration_quote.total_estimate == 65.0 + 249.0
    assert any("Core Aeration" in item.title for item in aeration_quote.line_items)

@pytest.mark.asyncio
async def test_roofing_quote_and_emergency_active_leak():
    # 1. Free 21-point inspection
    insp_specs = RoofingSpecs(issue_type="inspection")
    insp_quote = ResidentialSalesEngine.calculate_quote(TradeType.ROOFING, roofing=insp_specs)
    assert insp_quote.total_estimate == 0.0
    assert insp_quote.emergency_flag is False

    # 2. Active leak triggers emergency flag & $299 triage
    leak_specs = RoofingSpecs(issue_type="active_leak")
    leak_quote = ResidentialSalesEngine.calculate_quote(TradeType.ROOFING, roofing=leak_specs)
    assert leak_quote.emergency_flag is True
    assert leak_quote.total_estimate == 299.0
    assert "ACTIVE LEAK DETECTED" in leak_quote.emergency_message

    # 3. Full replacement budget range
    rep_specs = RoofingSpecs(issue_type="replacement", stories=1)
    rep_quote = ResidentialSalesEngine.calculate_quote(TradeType.ROOFING, roofing=rep_specs)
    assert rep_quote.is_range is True
    assert rep_quote.range_low > 5000.0
    assert rep_quote.range_high > rep_quote.range_low

@pytest.mark.asyncio
async def test_residential_sales_bot_chat_turns():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Carpet cleaning turn
        res_carpet = await client.post("/api/v1/residential/chat", json={
            "message": "Hi, I have 3 bedrooms and two pet dogs with urine stains. Can you give me a price?",
            "trade": "carpet_cleaning"
        })
        assert res_carpet.status_code == 200
        data_carpet = res_carpet.json()
        assert data_carpet["trade"] == "carpet_cleaning"
        assert data_carpet["current_quote"]["total_estimate"] == 190.0
        assert data_carpet["is_qualified"] is True
        assert len(data_carpet["quick_replies"]) > 0

        # Lawn care turn
        res_lawn = await client.post("/api/v1/residential/chat", json={
            "message": "I need weekly mowing for my half acre yard. Can we schedule this week?",
            "trade": "lawn_care"
        })
        assert res_lawn.status_code == 200
        data_lawn = res_lawn.json()
        assert data_lawn["trade"] == "lawn_care"
        assert data_lawn["ready_to_book"] is True
        assert data_lawn["current_quote"]["total_estimate"] == 55.25

        # Emergency leak turn
        res_leak = await client.post("/api/v1/residential/chat", json={
            "message": "HELP: Water is leaking through my ceiling light right now!",
            "trade": "roofing"
        })
        assert res_leak.status_code == 200
        data_leak = res_leak.json()
        assert data_leak["emergency_flag"] is True
        assert data_leak["current_quote"]["total_estimate"] == 299.0
        assert "URGENT LEAK ALERT" in data_leak["reply"]

@pytest.mark.asyncio
async def test_residential_appointment_booking_and_crm_sync():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Book appointment
        booking_payload = {
            "trade": "carpet_cleaning",
            "service_summary": "Apex Master Carpet Care (3 Bedrooms + Pet Treatment)",
            "homeowner_name": "Sarah Jenkins",
            "phone": "(303) 555-0192",
            "email": "sarah.jenkins@example.com",
            "address": "4182 Ridgeview Dr",
            "zip_code": "80202",
            "scheduled_date": "2026-09-20",
            "time_window": "morning",
            "estimated_total": 190.0,
            "special_instructions": "Gate code #4412. Please ring doorbell upon arrival."
        }
        res_book = await client.post("/api/v1/residential/book", json=booking_payload)
        assert res_book.status_code == 200
        conf = res_book.json()
        assert conf["status"] == "confirmed"
        assert conf["homeowner_name"] == "Sarah Jenkins"
        assert conf["estimated_total"] == 190.0
        assert conf["confirmation_number"].startswith("APX-")
        assert "appointment_id" in conf
        assert "lead_id" in conf

        # 2. Check bookings list
        res_list = await client.get("/api/v1/residential/bookings")
        assert res_list.status_code == 200
        bookings_data = res_list.json()
        assert bookings_data["count"] >= 1
        first_b = bookings_data["bookings"][0]
        assert "Sarah Jenkins" in first_b["homeowner"]
        assert "Carpet Cleaning Service Dispatch" in first_b["title"]

        # 3. Check catalog endpoint
        res_cat = await client.get("/api/v1/residential/catalog")
        assert res_cat.status_code == 200
        cat = res_cat.json()
        assert "carpet_cleaning" in cat
        assert "lawn_care" in cat
        assert "roofing" in cat

        # 4. Check available slots endpoint
        res_slots = await client.get("/api/v1/residential/slots?trade=carpet_cleaning&days_ahead=3")
        assert res_slots.status_code == 200
        slots_data = res_slots.json()
        assert len(slots_data["days"]) == 3
