import hmac
import hashlib
import time
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from sqlalchemy import select

from main import app
from app.core.database import engine, Base, AsyncSessionLocal
from app.models.developer import ApiKey, WebhookSubscription, WebhookDeliveryLog
from app.models.crm import ClientAccount, ClientSale, Company
from app.services.webhook_service import WebhookService

@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_api_key_generation_and_authentication():
    """Verify admin can generate a scoped API key and authenticate via X-API-Key header."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register Admin
        reg = await client.post("/api/v1/auth/register", json={
            "email": "dev.admin@nexuscloud.io",
            "password": "SecurePassword123!",
            "full_name": "Dev Admin",
            "organization_name": "NexusCloud Systems"
        })
        assert reg.status_code == 200
        admin_token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        auth_headers = {"Authorization": f"Bearer {admin_token}", "X-Organization-Id": org_id}

        # 2. Generate API Key
        key_res = await client.post("/api/v1/developer/keys", headers=auth_headers, json={
            "name": "Production ERP Integration",
            "scopes": ["sales:read", "sales:write"],
            "expires_in_days": 90,
            "rate_limit_per_minute": 120
        })
        assert key_res.status_code == 200
        key_data = key_res.json()
        raw_key = key_data["api_key"]
        assert raw_key.startswith("jsp_live_")
        assert key_data["name"] == "Production ERP Integration"
        assert key_data["key_prefix"] == raw_key[:16]
        assert key_data["rate_limit_per_minute"] == 120

        # 3. List API Keys (only prefixes and metadata, never raw secrets)
        list_res = await client.get("/api/v1/developer/keys", headers=auth_headers)
        assert list_res.status_code == 200
        keys_list = list_res.json()
        assert len(keys_list) == 1
        assert "api_key" not in keys_list[0]
        assert keys_list[0]["key_prefix"] == raw_key[:16]

        # 4. Authenticate using X-API-Key header (bypassing Bearer JWT)
        api_headers = {"X-API-Key": raw_key, "X-Organization-Id": org_id}
        protected_res = await client.get("/api/v1/developer/keys", headers=api_headers)
        assert protected_res.status_code == 200
        assert len(protected_res.json()) == 1

        # Verify last_used_at was updated in DB
        async with AsyncSessionLocal() as session:
            db_key_res = await session.execute(select(ApiKey).where(ApiKey.id == key_data["id"]))
            db_key = db_key_res.scalar_one()
            assert db_key.last_used_at is not None

@pytest.mark.asyncio
async def test_api_key_revocation():
    """Verify revoked API keys are immediately rejected with HTTP 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Register Admin
        reg = await client.post("/api/v1/auth/register", json={
            "email": "sec.ops@nexuscloud.io",
            "password": "SecurePassword123!",
            "full_name": "Security Officer",
            "organization_name": "NexusCloud Systems"
        })
        admin_token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        auth_headers = {"Authorization": f"Bearer {admin_token}", "X-Organization-Id": org_id}

        # Generate Key
        key_res = await client.post("/api/v1/developer/keys", headers=auth_headers, json={
            "name": "Temporary Worker Key",
            "scopes": ["*"]
        })
        raw_key = key_res.json()["api_key"]
        key_id = key_res.json()["id"]

        # Confirm valid
        valid_res = await client.get("/api/v1/developer/keys", headers={"X-API-Key": raw_key})
        assert valid_res.status_code == 200

        # Revoke Key
        revoke_res = await client.delete(f"/api/v1/developer/keys/{key_id}", headers=auth_headers)
        assert revoke_res.status_code == 200
        assert revoke_res.json()["is_active"] is False

        # Attempt to use revoked key
        rejected_res = await client.get("/api/v1/developer/keys", headers={"X-API-Key": raw_key})
        assert rejected_res.status_code == 401
        assert "revoked" in rejected_res.json()["detail"].lower()

@pytest.mark.asyncio
async def test_developer_platform_rbac_guards():
    """Verify non-admin/sales_manager roles cannot create keys or webhooks."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Register Admin
        reg = await client.post("/api/v1/auth/register", json={
            "email": "owner@corp.com",
            "password": "Password123!",
            "full_name": "Corp Owner",
            "organization_name": "Corp HQ"
        })
        admin_token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        admin_headers = {"Authorization": f"Bearer {admin_token}", "X-Organization-Id": org_id}

        # Invite Viewer
        invite = await client.post("/api/v1/team/invite", headers=admin_headers, json={
            "email": "auditor.viewer@corp.com",
            "password": "Password123!",
            "full_name": "External Auditor",
            "role": "viewer"
        })
        assert invite.status_code == 200

        # Login as Viewer
        login = await client.post("/api/v1/auth/login", json={
            "email": "auditor.viewer@corp.com",
            "password": "Password123!"
        })
        assert login.status_code == 200
        viewer_token = login.json()["access_token"]
        viewer_headers = {"Authorization": f"Bearer {viewer_token}", "X-Organization-Id": org_id}

        # Attempt to generate key as viewer
        denied_key = await client.post("/api/v1/developer/keys", headers=viewer_headers, json={
            "name": "Unauthorized Key"
        })
        assert denied_key.status_code == 403

        # Attempt to register webhook as viewer
        denied_wh = await client.post("/api/v1/developer/webhooks", headers=viewer_headers, json={
            "endpoint_url": "https://attacker.com/webhook",
            "events": ["order.created"]
        })
        assert denied_wh.status_code == 403

@pytest.mark.asyncio
async def test_webhook_subscription_lifecycle():
    """Verify registering, updating, and deleting webhook endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Register Admin
        reg = await client.post("/api/v1/auth/register", json={
            "email": "dev@logistics.com",
            "password": "Password123!",
            "full_name": "Integration Engineer",
            "organization_name": "Apex Logistics"
        })
        admin_token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {admin_token}", "X-Organization-Id": org_id}

        # 1. Create Webhook Subscription
        create_res = await client.post("/api/v1/developer/webhooks", headers=headers, json={
            "endpoint_url": "https://erp.apexlogistics.com/hooks/orders",
            "description": "Enterprise order processor",
            "events": ["order.created", "payment.succeeded"]
        })
        assert create_res.status_code == 200
        sub_data = create_res.json()
        sub_id = sub_data["id"]
        assert sub_data["endpoint_url"] == "https://erp.apexlogistics.com/hooks/orders"
        assert "secret_key" in sub_data
        assert sub_data["status"] == "active"
        assert "order.created" in sub_data["events"]

        # 2. List Webhooks
        list_res = await client.get("/api/v1/developer/webhooks", headers=headers)
        assert list_res.status_code == 200
        assert len(list_res.json()) == 1
        assert list_res.json()[0]["secret_prefix"].startswith("whsec_")

        # 3. Update Webhook Subscription
        update_res = await client.patch(f"/api/v1/developer/webhooks/{sub_id}", headers=headers, json={
            "events": ["order.created", "payment.succeeded", "shipment.delivered"],
            "status": "disabled"
        })
        assert update_res.status_code == 200
        assert update_res.json()["status"] == "disabled"
        assert len(update_res.json()["events"]) == 3

        # 4. Delete Webhook Subscription
        del_res = await client.delete(f"/api/v1/developer/webhooks/{sub_id}", headers=headers)
        assert del_res.status_code == 200

        # Verify list is empty
        list_after = await client.get("/api/v1/developer/webhooks", headers=headers)
        assert len(list_after.json()) == 0

@pytest.mark.asyncio
async def test_webhook_ping_and_hmac_signature_verification():
    """Verify diagnostic test ping creates delivery logs and verifies HMAC-SHA256 signature."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Register Admin
        reg = await client.post("/api/v1/auth/register", json={
            "email": "sec@fintech.io",
            "password": "Password123!",
            "full_name": "Security Architect",
            "organization_name": "Fintech Global"
        })
        admin_token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {admin_token}", "X-Organization-Id": org_id}

        # Create Webhook with known custom secret
        test_secret = "whsec_custom_secret_key_1234567890"
        create_res = await client.post("/api/v1/developer/webhooks", headers=headers, json={
            "endpoint_url": "https://webhook.site/diagnostic-test",
            "events": ["order.created"],
            "secret_key": test_secret
        })
        assert create_res.status_code == 200
        sub_id = create_res.json()["id"]

        # Mock external outbound webhook post during ping without affecting test client
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.text = '{"status": "ok"}'

        recorded_calls = []
        orig_post = AsyncClient.post

        async def mock_selective_post(self_client, url, *args, **kwargs):
            if "webhook.site" in str(url):
                recorded_calls.append({"url": str(url), "args": args, "kwargs": kwargs})
                return mock_response
            return await orig_post(self_client, url, *args, **kwargs)

        with patch.object(AsyncClient, "post", new=mock_selective_post):
            ping_res = await client.post(f"/api/v1/developer/webhooks/{sub_id}/ping", headers=headers)
            assert ping_res.status_code == 200
            data = ping_res.json()
            assert data["success"] is True
            assert data["delivery"]["event_type"] == "ping.test"
            assert data["delivery"]["response_status_code"] == 200
            assert data["delivery"]["success"] is True

            # Verify the headers that were sent to mock_post
            assert len(recorded_calls) == 1
            sent_headers = recorded_calls[0]["kwargs"]["headers"]
            assert "X-JsProject-Signature" in sent_headers
            assert "X-JsProject-Event" in sent_headers
            assert sent_headers["X-JsProject-Event"] == "ping.test"

            # Verify HMAC signature calculation
            sig_header = sent_headers["X-JsProject-Signature"]
            parts = dict(kv.split("=", 1) for kv in sig_header.split(","))
            t = parts["t"]
            v1 = parts["v1"]
            payload_bytes = recorded_calls[0]["kwargs"]["content"]
            expected_sig = hmac.new(
                test_secret.encode("utf-8"),
                f"{t}.".encode("utf-8") + payload_bytes,
                hashlib.sha256
            ).hexdigest()
            assert hmac.compare_digest(v1, expected_sig)

        # Retrieve deliveries list for subscription
        deliveries_res = await client.get(f"/api/v1/developer/webhooks/{sub_id}/deliveries", headers=headers)
        assert deliveries_res.status_code == 200
        deliveries = deliveries_res.json()
        assert len(deliveries) >= 1
        assert deliveries[0]["event_type"] == "ping.test"
        assert deliveries[0]["success"] is True

@pytest.mark.asyncio
async def test_event_catalog_public_endpoint():
    """Verify public developer event catalog endpoint returns supported system events."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/api/v1/developer/events")
        assert res.status_code == 200
        events = res.json()
        assert len(events) >= 6

        event_names = [e["event_name"] for e in events]
        assert "order.created" in event_names
        assert "payment.succeeded" in event_names
        assert "shipment.updated" in event_names
        assert "shipment.delivered" in event_names
        assert "license.provisioned" in event_names
        assert "restock.triggered" in event_names

        for e in events:
            assert "description" in e
            assert "sample_payload" in e
            assert isinstance(e["sample_payload"], dict)
