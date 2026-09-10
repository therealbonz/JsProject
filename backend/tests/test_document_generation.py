import pytest
import pytest_asyncio
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from main import app
from app.core.database import engine, Base
from app.models.tenant import Organization
from app.models.crm import ClientAccount, ClientSale
from app.services.document_service import DocumentService

@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_qr_code_svg_generation():
    url = "https://therealbonz.com/JsProject/checkout/pay/cs_test_12345"
    svg = DocumentService.generate_qr_code_svg(url)
    assert svg.startswith("<svg") or "<svg" in svg
    assert "</svg>" in svg
    assert "viewBox" in svg
    assert "<path" in svg

@pytest.mark.asyncio
async def test_printable_invoice_html_rendering():
    org = Organization(
        id="org_doc_test",
        name="Vanguard Logistics Co",
        slug="vanguard-logistics",
        brand_name="Vanguard Supply Chain",
        brand_accent_color="#2563eb",
        brand_logo_url="https://vanguard.example/logo.svg",
        support_email="billing@vanguard.example",
        support_phone="+1 800-555-VANGUARD",
        custom_footer_text="Vanguard Supply Chain - ISO Certified B2B Partner"
    )

    client = ClientAccount(
        id="client_doc_test",
        organization_id=org.id,
        company_id=None,
        account_name="Frontier Aerospace Inc",
        status="active"
    )

    sale_unpaid = ClientSale(
        id="sale_unpaid_123",
        organization_id=org.id,
        client_id=client.id,
        order_number="SO-2026-VANG-001",
        amount=4750.00,
        sale_date=datetime(2026, 9, 10, tzinfo=timezone.utc),
        status="completed",
        payment_method="credit_terms_30",
        payment_status="unpaid",
        stripe_session_id="cs_test_vanguard_9988",
        customer_email="procurement@frontier.example",
        customer_phone="+1 555-888-7766",
        items_summary="10x Carbon Fiber Composite Panels, 5x Titanium Fastener Kits",
        client=client
    )

    # Render unpaid invoice
    html_unpaid = DocumentService.render_invoice_html(
        sale=sale_unpaid,
        org=org,
        base_url="https://therealbonz.com/JsProject",
        auto_print=True
    )
    assert "Vanguard Supply Chain" in html_unpaid
    assert "#2563eb" in html_unpaid
    assert "SO-2026-VANG-001" in html_unpaid
    assert "Frontier Aerospace Inc" in html_unpaid
    assert "Carbon Fiber Composite Panels" in html_unpaid
    assert "Titanium Fastener Kits" in html_unpaid
    assert "$4,750.00" in html_unpaid
    assert "PAYMENT DUE" in html_unpaid
    assert "cs_test_vanguard_9988" in html_unpaid
    assert "<svg" in html_unpaid
    assert "window.print()" in html_unpaid

    # Render paid invoice
    sale_paid = ClientSale(
        id="sale_paid_456",
        organization_id=org.id,
        client_id=client.id,
        order_number="SO-2026-VANG-002",
        amount=1200.00,
        sale_date=datetime(2026, 9, 10, tzinfo=timezone.utc),
        status="delivered",
        payment_method="credit_card",
        payment_status="paid",
        items_summary="2x Precision Calibrators",
        client=client
    )
    html_paid = DocumentService.render_invoice_html(
        sale=sale_paid,
        org=org,
        base_url="https://therealbonz.com/JsProject",
        auto_print=False
    )
    assert "PAID IN FULL" in html_paid
    assert "$1,200.00" in html_paid
    assert "SO-2026-VANG-002" in html_paid

@pytest.mark.asyncio
async def test_printable_packing_slip_html_rendering():
    org = Organization(
        id="org_slip_test",
        name="Apex Distro",
        slug="apex-distro",
        brand_name="Apex Logistics Network",
        brand_accent_color="#059669"
    )

    client = ClientAccount(
        id="client_slip_test",
        organization_id=org.id,
        company_id=None,
        account_name="Rocky Mountain Hardware",
        status="active"
    )

    sale = ClientSale(
        id="sale_slip_test_789",
        organization_id=org.id,
        client_id=client.id,
        order_number="SO-2026-APEX-990",
        amount=890.00,
        sale_date=datetime(2026, 9, 10, tzinfo=timezone.utc),
        status="shipped",
        items_summary="25x Industrial Fasteners, 10x Heavy Duty Clamps",
        customer_email="receiving@rockymountain.example",
        client=client
    )

    html_slip = DocumentService.render_packing_slip_html(
        sale=sale,
        org=org,
        base_url="https://therealbonz.com/JsProject",
        auto_print=True
    )
    assert "PACKING SLIP" in html_slip
    assert "Apex Logistics Network" in html_slip
    assert "SO-2026-APEX-990" in html_slip
    assert "Rocky Mountain Hardware" in html_slip
    assert "Industrial Fasteners" in html_slip
    assert "Heavy Duty Clamps" in html_slip
    assert "Dock Inspector Signature" in html_slip
    assert "<svg" in html_slip
    assert "window.print()" in html_slip

@pytest.mark.asyncio
async def test_documents_endpoints_e2e():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register tenant
        reg_res = await client.post("/api/v1/auth/register", json={
            "email": "docs@distrocorp.com",
            "password": "Password123!",
            "full_name": "Documentation Admin",
            "organization_name": "DistroCorp Global"
        })
        assert reg_res.status_code == 200
        reg_data = reg_res.json()
        token = reg_data["access_token"]
        org_id = reg_data["organization_id"]
        auth_headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # 2. Update branding
        await client.put("/api/v1/orgs/settings", json={
            "brand_name": "DistroCorp Premier",
            "brand_accent_color": "#7c3aed",
            "support_email": "invoices@distrocorp.com",
            "support_phone": "+1 800-555-DISTRO"
        }, headers=auth_headers)

        # 3. Create client and sale
        client_res = await client.post("/api/v1/crm/clients", json={
            "account_name": "Pacific Industrial Supplies",
            "contact_first_name": "Elena",
            "contact_last_name": "Rostova",
            "contact_email": "elena@pacificind.example",
            "contact_phone": "+1 555-777-8899",
            "company_domain": "pacificind.example",
            "industry": "Heavy Equipment",
            "reorder_cadence_days": 30,
            "status": "active"
        }, headers=auth_headers)
        assert client_res.status_code == 200
        client_id = client_res.json()["id"]

        sale_res = await client.post(f"/api/v1/crm/clients/{client_id}/sales", json={
            "items_summary": "4x Hydraulic Pump Assembly, 12x O-Ring Seal Packs",
            "amount": 3450.00,
            "payment_method": "credit_terms_30",
            "auto_fulfill_on_payment": True,
            "customer_email": "purchasing@pacificind.example",
            "customer_phone": "+1 555-777-8899"
        }, headers=auth_headers)
        assert sale_res.status_code == 200
        sale_data = sale_res.json()
        sale_id = sale_data["id"]
        order_number = sale_data["order_number"]

        # 4. Test invoice endpoint by sale ID
        inv_id_res = await client.get(f"/api/v1/documents/invoice/{sale_id}")
        assert inv_id_res.status_code == 200
        assert "text/html" in inv_id_res.headers["content-type"]
        assert "DistroCorp Premier" in inv_id_res.text
        assert order_number in inv_id_res.text
        assert "Hydraulic Pump Assembly" in inv_id_res.text
        assert "3,450.00" in inv_id_res.text
        assert "<svg" in inv_id_res.text

        # 5. Test invoice endpoint by Order Number with auto_print
        inv_order_res = await client.get(f"/api/v1/documents/invoice/{order_number}?print=true")
        assert inv_order_res.status_code == 200
        assert order_number in inv_order_res.text
        assert "window.print()" in inv_order_res.text

        # 6. Test packing slip endpoint by sale ID
        slip_id_res = await client.get(f"/api/v1/documents/packing-slip/{sale_id}")
        assert slip_id_res.status_code == 200
        assert "PACKING SLIP" in slip_id_res.text
        assert "Pacific Industrial Supplies" in slip_id_res.text
        assert "Hydraulic Pump Assembly" in slip_id_res.text
        assert "<svg" in slip_id_res.text

        # 7. Test packing slip endpoint by Order Number with auto_print
        slip_order_res = await client.get(f"/api/v1/documents/packing-slip/{order_number}?print=true")
        assert slip_order_res.status_code == 200
        assert "window.print()" in slip_order_res.text

        # 8. Test 404 for non-existent order
        not_found_res = await client.get("/api/v1/documents/invoice/NON-EXISTENT-ORDER-999")
        assert not_found_res.status_code == 404
