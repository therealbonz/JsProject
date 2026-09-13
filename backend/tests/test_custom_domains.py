import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from main import app
from app.core.database import engine, Base, AsyncSessionLocal
from app.models.tenant import Organization
from app.models.custom_domain import CustomDomain

@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_public_resolve_default_platform_branding():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/api/v1/domains/public/resolve?host=therealbonz.com")
        assert res.status_code == 200
        data = res.json()
        assert data["is_custom_domain"] is False
        assert data["brand_name"] == "AI Sales Platform"
        assert data["ssl_active"] is True

@pytest.mark.asyncio
async def test_register_custom_domain_and_validations():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Register test org & admin
        reg = await client.post("/api/v1/auth/register", json={
            "email": "domainsadmin@acme.example",
            "password": "Password123!",
            "full_name": "Alice Enterprise",
            "organization_name": "Acme Global Industries"
        })
        assert reg.status_code == 200
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # 1. Attempt to register reserved platform host
        bad_res = await client.post("/api/v1/domains", headers=headers, json={
            "domain": "therealbonz.com",
            "verification_method": "cname"
        })
        assert bad_res.status_code == 400
        assert "reserved platform host" in bad_res.json()["detail"]

        # 2. Attempt to register invalid domain format
        bad_res2 = await client.post("/api/v1/domains", headers=headers, json={
            "domain": "invalid_domain_no_tld",
            "verification_method": "cname"
        })
        assert bad_res2.status_code == 400
        assert "not a valid fully qualified domain name" in bad_res2.json()["detail"]

        # 3. Successfully register custom domain
        create_res = await client.post("/api/v1/domains", headers=headers, json={
            "domain": "portal.acmeglobal.com",
            "verification_method": "cname",
            "custom_theme_overrides": {
                "brand_name": "Acme Global Portal",
                "brand_accent_color": "#059669",
                "support_email": "support@acmeglobal.com"
            }
        })
        assert create_res.status_code == 201
        domain_data = create_res.json()
        assert domain_data["domain"] == "portal.acmeglobal.com"
        assert domain_data["cname_target"] == "therealbonz.com"
        assert domain_data["verification_status"] == "pending"
        assert domain_data["ssl_status"] == "pending"
        assert domain_data["is_primary"] is True
        assert domain_data["verification_token"].startswith("jsp-verify-")
        assert "CNAME" in domain_data["cname_instruction"]

        # 4. Duplicate registration rejected
        dup_res = await client.post("/api/v1/domains", headers=headers, json={
            "domain": "portal.acmeglobal.com",
            "verification_method": "cname"
        })
        assert dup_res.status_code == 400
        assert "already registered" in dup_res.json()["detail"]

@pytest.mark.asyncio
async def test_verify_domain_dns_simulation_and_public_resolution():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Register tenant
        reg = await client.post("/api/v1/auth/register", json={
            "email": "corp@apexbrands.example",
            "password": "Password123!",
            "full_name": "Bob Apex",
            "organization_name": "Apex Brands Corp"
        })
        assert reg.status_code == 200
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # Register domain
        reg_domain = await client.post("/api/v1/domains", headers=headers, json={
            "domain": "portal.apexbrands.test",
            "verification_method": "cname",
            "custom_theme_overrides": {
                "brand_name": "Apex Supply Portal",
                "brand_accent_color": "#0284c7",
                "support_email": "help@apexbrands.test"
            }
        })
        assert reg_domain.status_code == 201
        domain_id = reg_domain.json()["id"]

        # Before verification: public resolution returns is_custom_domain = False
        res_unverified = await client.get("/api/v1/domains/public/resolve?host=portal.apexbrands.test")
        assert res_unverified.status_code == 200
        assert res_unverified.json()["is_custom_domain"] is False

        # Run simulated DNS verification
        verify_res = await client.post(f"/api/v1/domains/{domain_id}/verify?simulate=true", headers=headers)
        assert verify_res.status_code == 200
        vdata = verify_res.json()
        assert vdata["success"] is True
        assert vdata["verification_status"] == "verified"
        assert vdata["resolved_target"] == "therealbonz.com"

        # Check domain details endpoint
        get_res = await client.get(f"/api/v1/domains/{domain_id}", headers=headers)
        assert get_res.status_code == 200
        d_details = get_res.json()
        assert d_details["verification_status"] == "verified"
        assert d_details["ssl_status"] == "active"
        assert d_details["verified_at"] is not None

        # After verification: public resolution matches tenant custom branding!
        res_verified = await client.get("/api/v1/domains/public/resolve?host=portal.apexbrands.test")
        assert res_verified.status_code == 200
        v_brand = res_verified.json()
        assert v_brand["is_custom_domain"] is True
        assert v_brand["organization_id"] == org_id
        assert v_brand["brand_name"] == "Apex Supply Portal"
        assert v_brand["brand_accent_color"] == "#0284c7"
        assert v_brand["support_email"] == "help@apexbrands.test"
        assert v_brand["ssl_active"] is True

@pytest.mark.asyncio
async def test_primary_domain_switching_and_listing():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Register tenant
        reg = await client.post("/api/v1/auth/register", json={
            "email": "primarytest@enterprise.example",
            "password": "Password123!",
            "full_name": "Charlie Manager",
            "organization_name": "Summit Logistics"
        })
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # Domain 1
        d1_res = await client.post("/api/v1/domains", headers=headers, json={
            "domain": "portal.summitlogistics.io"
        })
        d1_id = d1_res.json()["id"]
        assert d1_res.json()["is_primary"] is True

        # Domain 2
        d2_res = await client.post("/api/v1/domains", headers=headers, json={
            "domain": "orders.summitlogistics.io"
        })
        d2_id = d2_res.json()["id"]
        assert d2_res.json()["is_primary"] is False

        # Switch primary to Domain 2
        set_prim = await client.post(f"/api/v1/domains/{d2_id}/primary", headers=headers)
        assert set_prim.status_code == 200
        assert set_prim.json()["is_primary"] is True

        # Verify list: Domain 2 is primary, Domain 1 is not
        list_res = await client.get("/api/v1/domains", headers=headers)
        assert list_res.status_code == 200
        all_domains = list_res.json()
        assert len(all_domains) == 2

        d2_found = next(d for d in all_domains if d["id"] == d2_id)
        d1_found = next(d for d in all_domains if d["id"] == d1_id)
        assert d2_found["is_primary"] is True
        assert d1_found["is_primary"] is False

@pytest.mark.asyncio
async def test_domain_nginx_config_and_deletion():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        reg = await client.post("/api/v1/auth/register", json={
            "email": "devops@acme.example",
            "password": "Password123!",
            "full_name": "DevOps Engineer",
            "organization_name": "DevOps Cloud"
        })
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        d_res = await client.post("/api/v1/domains", headers=headers, json={
            "domain": "app.devopscloud.io"
        })
        domain_id = d_res.json()["id"]

        # Fetch Nginx config snippet
        nginx_res = await client.get(f"/api/v1/domains/{domain_id}/nginx-config", headers=headers)
        assert nginx_res.status_code == 200
        nginx_data = nginx_res.json()
        assert "server_name app.devopscloud.io;" in nginx_data["nginx_server_block"]
        assert "proxy_pass http://127.0.0.1:8000;" in nginx_data["nginx_server_block"]
        assert "sudo certbot --nginx -d app.devopscloud.io" in nginx_data["certbot_command"]
        assert nginx_data["config_filename"] == "custom_domain_app_devopscloud_io.conf"

        # Delete domain
        del_res = await client.delete(f"/api/v1/domains/{domain_id}", headers=headers)
        assert del_res.status_code == 200

        # Verify not found after deletion
        get_res = await client.get(f"/api/v1/domains/{domain_id}", headers=headers)
        assert get_res.status_code == 404

@pytest.mark.asyncio
async def test_host_routing_middleware_scoping():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Register org
        reg = await client.post("/api/v1/auth/register", json={
            "email": "hosttest@tenant.example",
            "password": "Password123!",
            "full_name": "Host Tester",
            "organization_name": "Host Scoped Tenant"
        })
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # Register and verify custom domain
        d_res = await client.post("/api/v1/domains", headers=headers, json={
            "domain": "tenant.customhost.test"
        })
        d_id = d_res.json()["id"]
        await client.post(f"/api/v1/domains/{d_id}/verify?simulate=true", headers=headers)

        # Make authenticated request with Host header set to the verified domain,
        # but WITHOUT the X-Organization-Id header!
        host_headers = {
            "Authorization": f"Bearer {token}",
            "Host": "tenant.customhost.test"
        }
        domains_res = await client.get("/api/v1/domains", headers=host_headers)
        assert domains_res.status_code == 200
        domains = domains_res.json()
        assert len(domains) >= 1
        assert domains[0]["domain"] == "tenant.customhost.test"
