import io
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from main import app
from app.core.database import engine, Base
from app.models.tenant import Organization
from app.models.crm import ProspectCampaign, Lead, Company, Contact
from app.services.prospect_import_service import ProspectImportService

@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_fuzzy_header_detection():
    raw_headers = [
        "Homeowner Full Name",
        "Cell Phone Number",
        "E-Mail Address",
        "Service Street Address",
        "City",
        "State",
        "Postal Code",
        "Trade Service",
        "Special Job Instructions",
        "Square Footage"
    ]
    mapping = ProspectImportService.detect_headers(raw_headers)

    assert mapping["Homeowner Full Name"] == "full_name"
    assert mapping["Cell Phone Number"] == "phone"
    assert mapping["E-Mail Address"] == "email"
    assert mapping["Service Street Address"] == "address"
    assert mapping["City"] == "city"
    assert mapping["Postal Code"] == "zip_code"
    assert mapping["Trade Service"] == "trade_service"
    assert mapping["Special Job Instructions"] == "notes"
    assert mapping["Square Footage"] == "custom"


@pytest.mark.asyncio
async def test_phone_number_sanitization():
    # 10 digits formatted
    clean1, ok1 = ProspectImportService.clean_phone_number("(303) 555-0199")
    assert ok1 is True
    assert clean1 == "+13035550199"

    # 11 digits with leading 1
    clean2, ok2 = ProspectImportService.clean_phone_number("1-720-555-0144")
    assert ok2 is True
    assert clean2 == "+17205550144"

    # Pure digits
    clean3, ok3 = ProspectImportService.clean_phone_number("3035558822")
    assert ok3 is True
    assert clean3 == "+13035558822"

    # Too short / invalid
    clean4, ok4 = ProspectImportService.clean_phone_number("555-12")
    assert ok4 is False
    assert clean4 is None


@pytest.mark.asyncio
async def test_dry_run_preview():
    csv_content = (
        "Name,Phone,Email,Street,City,State,Zip,Service,Notes\r\n"
        "Alice Cooper,3035551111,alice@example.com,100 High St,Denver,CO,80202,Carpet Cleaning,Living room and stairs\r\n"
        "Bob Dylan,3035552222,bob@example.com,200 Low St,Boulder,CO,80301,Lawn Care,Weekly mow\r\n"
        "Invalid Person,123,invalid@example.com,300 Mid St,Aurora,CO,80010,Roofing,Leaky shingle\r\n"
    )

    preview = await ProspectImportService.preview_import(
        file_bytes=csv_content.encode("utf-8"),
        default_trade="carpet_cleaning",
        sample_limit=5
    )

    assert preview.total_rows_detected == 3
    assert preview.valid_count == 2
    assert preview.invalid_count == 1
    assert len(preview.sample_rows) == 3
    assert preview.sample_rows[0].first_name == "Alice"
    assert preview.sample_rows[0].clean_phone == "+13035551111"
    assert preview.sample_rows[2].is_valid is False


@pytest.mark.asyncio
async def test_batch_ingestion_and_lead_creation():
    transport = ASGITransport(app=app)
    async with AsyncSession(engine) as session:
        # Create an active organization
        org = Organization(name="Apex Test Org", slug="apex-test-org", status="active")
        session.add(org)
        await session.commit()
        await session.refresh(org)

    csv_data = (
        "First Name,Last Name,Phone,Email,Address,City,State,Zip,Service,Notes\r\n"
        "Marcus,Vance,+1-303-555-9001,marcus.vance@example.com,123 Alpine Way,Denver,CO,80202,Carpet Cleaning,Whole home carpet steam\r\n"
        "Samantha,Reed,303-555-9002,samantha.reed@example.com,456 Pine Ln,Boulder,CO,80302,Lawn Care,Front and back yard aeration\r\n"
    )

    files = {
        "file": ("prospects.csv", csv_data.encode("utf-8"), "text/csv")
    }
    data = {
        "campaign_name": "Test Spring Outreach",
        "trade_service": "carpet_cleaning",
        "skip_duplicates": "true",
        "dry_run": "false"
    }

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/v1/residential/prospects/upload", files=files, data=data)
        assert response.status_code == 200
        json_data = response.json()

        assert json_data["success"] is True
        assert json_data["leads_created"] == 2
        assert json_data["duplicates_skipped"] == 0
        assert json_data["campaign_id"] is not None

        campaign_id = json_data["campaign_id"]

    # Verify database records
    async with AsyncSession(engine) as session:
        camp_res = await session.execute(select(ProspectCampaign).where(ProspectCampaign.id == campaign_id))
        campaign = camp_res.scalar_one_or_none()
        assert campaign is not None
        assert campaign.name == "Test Spring Outreach"
        assert campaign.valid_count == 2

        leads_res = await session.execute(select(Lead).where(Lead.campaign_id == campaign_id))
        leads = leads_res.scalars().all()
        assert len(leads) == 2
        for l in leads:
            assert l.pipeline_stage == "ready_contact"
            assert l.campaign_id == campaign_id


@pytest.mark.asyncio
async def test_deduplication_handling():
    async with AsyncSession(engine) as session:
        org = Organization(name="Apex Dedup Org", slug="apex-dedup-org", status="active")
        session.add(org)
        await session.commit()
        await session.refresh(org)

        # CSV with identical phone numbers
        csv_data = (
            "Name,Phone,Email\r\n"
            "John Doe,303-555-7777,john@example.com\r\n"
            "Johnny D,3035557777,johnny@example.com\r\n"  # Duplicate phone
            "Jane Smith,303-555-8888,jane@example.com\r\n"
        )

        result = await ProspectImportService.execute_import(
            file_bytes=csv_data.encode("utf-8"),
            campaign_name="Dedup Test Campaign",
            trade_service="lawn_care",
            organization=org,
            db=session,
            skip_duplicates=True
        )

        assert result.leads_created == 2
        assert result.duplicates_skipped == 1


@pytest.mark.asyncio
async def test_template_download():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/crm/prospects/template")
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type")
        content = response.text
        assert "First Name" in content
        assert "Phone Number" in content
        assert "Carpet Cleaning" in content
        assert "Lawn Care" in content
