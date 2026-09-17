import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from main import app
from app.core.database import engine, Base

@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_landing_page_routes():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Test /landing route
        res = await client.get("/landing")
        assert res.status_code == 200
        assert "text/html" in res.headers["content-type"]
        assert "NexFlow" in res.text
        assert "7 Specialized Sales Bots" in res.text

        # 2. Test /JsProject/landing route
        res_sub = await client.get("/JsProject/landing")
        assert res_sub.status_code == 200
        assert "Management Console" in res_sub.text

@pytest.mark.asyncio
async def test_landing_page_spotlights_sales_ai_bots():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/landing")
        assert res.status_code == 200
        html = res.text

        # Verify all 7 Sales AI Agents are documented in the page
        assert "The Lead Developer" in html
        assert "Decision-Maker" in html
        assert "Literature" in html
        assert "The Appointment Setter" in html
        assert "Cold Outreach SDR" in html
        assert "The Executive Sales Bot" in html
        assert "The Objection Closer" in html
        assert "Outbound Campaign Power Dialer" in html
        assert "btn-test-discovery" in html
        assert "btn-test-dialer" in html
        assert "chk-discovery" in html
        assert "chk-dialer" in html
        assert "7 Specialized Sales Bots" in html

        # Verify agent capabilities and business impacts
        assert "Autonomous Sales Skills" in html
        assert "Live Agent Telemetry Feed" in html
        assert "Demos" in html

@pytest.mark.asyncio
async def test_landing_page_pricing_and_metered_billing():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/landing")
        assert res.status_code == 200
        html = res.text

        # Verify 4 Tier packages
        assert "$199" in html
        assert "$499" in html
        assert "$1,499" in html
        assert "Custom" in html

        # Verify transparent metered overage rates
        assert "$0.005" in html  # AI Turn rate
        assert "$0.001" in html  # API call rate
        assert "Automated Metered Overage Protection" in html

@pytest.mark.asyncio
async def test_console_routes_and_navigation_toggle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Default root should serve the Landing Page
        root_res = await client.get("/")
        assert root_res.status_code == 200
        assert "NexFlow" in root_res.text
        assert "7 Specialized Sales Bots" in root_res.text

        # ?view=console parameter should switch to CRM Management Console
        console_view_res = await client.get("/?view=console")
        assert console_view_res.status_code == 200
        assert "CRM 1: Prospects & Pipeline" in console_view_res.text
        assert "SaaS Landing Page" in console_view_res.text

        # ?console=1 parameter should switch to CRM Management Console
        console_flag_res = await client.get("/JsProject/?console=1")
        assert console_flag_res.status_code == 200
        assert "CRM 1: Prospects & Pipeline" in console_flag_res.text

        # Direct /console route
        direct_console = await client.get("/console")
        assert direct_console.status_code == 200
        assert "CRM 1: Prospects & Pipeline" in direct_console.text

        # Direct /JsProject/console route
        direct_jsproject_console = await client.get("/JsProject/console")
        assert direct_jsproject_console.status_code == 200
        assert "CRM 1: Prospects & Pipeline" in direct_jsproject_console.text
