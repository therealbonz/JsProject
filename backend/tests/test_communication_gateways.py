import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from main import app
from app.core.database import engine, Base, AsyncSessionLocal
from app.models.tenant import Organization
from app.models.crm import ClientAccount, ClientSale
from app.services.communication_gateway import TwilioSMSGateway, EmailNotificationGateway
from app.services.notification_service import NotificationService

@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_twilio_phone_sanitization():
    assert TwilioSMSGateway.clean_phone_number('(555) 123-4567') == '+15551234567'
    assert TwilioSMSGateway.clean_phone_number('555.123.4567') == '+15551234567'
    assert TwilioSMSGateway.clean_phone_number('1-555-123-4567') == '+15551234567'
    assert TwilioSMSGateway.clean_phone_number('+44 20 7183 8750') == '+442071838750'

@pytest.mark.asyncio
async def test_sms_gateway_simulation_fallback():
    res = await TwilioSMSGateway.send_sms(
        to_phone='555-234-5678',
        message='Your package SO-TEST-123 has shipped.'
    )
    assert res['success'] is True
    assert res['mode'] == 'simulated'
    assert res['sid'].startswith('SM_sim_')
    assert res['recipient'] == '+15552345678'

@pytest.mark.asyncio
async def test_email_template_rendering_and_simulation():
    org = Organization(
        id='org_test_email',
        name='Titan Logistics',
        slug='titan-logistics',
        brand_name='Titan Express Freight',
        brand_accent_color='#e11d48',
        brand_logo_url='https://titan.example/logo.svg',
        support_email='dispatch@titan.example',
        support_phone='+1 888-555-TITAN',
        custom_footer_text='Titan Express Logistics Network'
    )

    html = EmailNotificationGateway.render_branded_email_html(
        title='Delivery Dispatched: SO-TITAN-001',
        message_body='Your order of 50 Pallets has been dispatched.',
        org=org,
        cta_url='https://therealbonz.com/JsProject/track/SO-TITAN-001',
        cta_text='Track Live Shipment',
        order_number='SO-TITAN-001'
    )

    assert 'Titan Express Freight' in html
    assert '#e11d48' in html
    assert 'https://therealbonz.com/JsProject/track/SO-TITAN-001' in html
    assert 'dispatch@titan.example' in html
    assert 'SO-TITAN-001' in html

    send_res = await EmailNotificationGateway.send_email(
        to_email='customer@client.example',
        subject='Your shipment is on the way',
        html_content=html,
        org=org
    )
    assert send_res['success'] is True
    assert send_res['mode'] == 'simulated'
    assert send_res['message_id'].startswith('msg_sim_')

@pytest.mark.asyncio
async def test_notification_gateways_settings_and_test_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://testserver') as client:
        reg_res = await client.post('/api/v1/auth/register', json={
            'email': 'telecom@gatewaytest.com',
            'password': 'Password123!',
            'full_name': 'Gateway Manager',
            'organization_name': 'Nexus Direct Freight'
        })
        assert reg_res.status_code == 200
        reg_data = reg_res.json()
        token = reg_data['access_token']
        org_id = reg_data['organization_id']
        auth_headers = {'Authorization': f'Bearer {token}', 'X-Organization-Id': org_id}

        get_res = await client.get('/api/v1/orgs/settings', headers=auth_headers)
        assert get_res.status_code == 200
        data = get_res.json()
        assert data['is_sms_configured'] is False
        assert data['is_email_configured'] is False

        update_res = await client.put('/api/v1/orgs/settings', json={
            'twilio_account_sid': 'AC_mock_1234567890abcdef123456',
            'twilio_auth_token': 'secret_auth_token_xyz987654321',
            'twilio_from_number': '+15559876543',
            'sendgrid_api_key': 'SG.mock_sendgrid_api_key_test_123456',
            'email_from_address': 'notifications@nexusfreight.com',
            'email_from_name': 'Nexus Freight Dispatch'
        }, headers=auth_headers)
        assert update_res.status_code == 200
        updated = update_res.json()
        assert updated['twilio_account_sid'] == 'AC_mock_1234567890abcdef123456'
        assert updated['is_sms_configured'] is True
        assert updated['is_email_configured'] is True
        assert '••••' in updated['masked_twilio_token']
        assert 'secret_auth_token_xyz987654321' not in updated['masked_twilio_token']
        assert '••••' in updated['masked_sendgrid_key']
        assert 'SG.mock_sendgrid_api_key_test_123456' not in updated['masked_sendgrid_key']
        assert updated['email_from_address'] == 'notifications@nexusfreight.com'
        assert updated['email_from_name'] == 'Nexus Freight Dispatch'

        test_sms_res = await client.post('/api/v1/orgs/notifications/test-sms', json={
            'recipient': '+15553334444',
            'channel': 'sms',
            'message': 'Automated verification test SMS from Nexus Freight'
        }, headers=auth_headers)
        assert test_sms_res.status_code == 200
        sms_data = test_sms_res.json()
        assert sms_data['success'] is True

        test_email_res = await client.post('/api/v1/orgs/notifications/test-email', json={
            'recipient': 'buyer@hardwarecorp.example',
            'channel': 'email',
            'message': 'Automated verification test email from Nexus Freight'
        }, headers=auth_headers)
        assert test_email_res.status_code == 200
        email_data = test_email_res.json()
        assert email_data['success'] is True

@pytest.mark.asyncio
async def test_autonomous_notification_dispatch_and_history():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://testserver') as client:
        reg_res = await client.post('/api/v1/auth/register', json={
            'email': 'ops@autologistics.com',
            'password': 'Password123!',
            'full_name': 'Ops Lead',
            'organization_name': 'Auto Logistics Inc'
        })
        assert reg_res.status_code == 200
        reg_data = reg_res.json()
        token = reg_data['access_token']
        org_id = reg_data['organization_id']
        auth_headers = {'Authorization': f'Bearer {token}', 'X-Organization-Id': org_id}

        client_res = await client.post('/api/v1/crm/clients', json={
            'account_name': 'Denver Fastener Supply',
            'contact_first_name': 'Alex',
            'contact_last_name': 'Rivera',
            'contact_email': 'alex@denverfastener.example',
            'contact_phone': '+1 555-444-3322',
            'company_domain': 'denverfastener.example',
            'industry': 'Commercial Supplies',
            'reorder_cadence_days': 14,
            'status': 'active'
        }, headers=auth_headers)
        assert client_res.status_code == 200
        client_id = client_res.json()['id']

        sale_res = await client.post(f'/api/v1/crm/clients/{client_id}/sales', json={
            'items_summary': '50x Titanium Bolts Set',
            'amount': 1250.00,
            'payment_method': 'stripe',
            'auto_fulfill_on_payment': True,
            'customer_email': 'purchasing@denverfastener.example',
            'customer_phone': '+1 555-444-3322'
        }, headers=auth_headers)
        assert sale_res.status_code == 200
        sale_data = sale_res.json()
        sale_id = sale_data['id']

        async with AsyncSessionLocal() as db:
            sale = await db.get(ClientSale, sale_id)
            email_notif = await NotificationService.create_and_send_notification(
                db=db,
                sale=sale,
                event_type='order_confirmed',
                channel='email'
            )
            assert email_notif.status == 'sent'
            assert email_notif.channel == 'email'

            sms_notif = await NotificationService.create_and_send_notification(
                db=db,
                sale=sale,
                event_type='dispatched',
                channel='sms',
                carrier='FedEx Freight',
                tracking_number='FX-99887766'
            )
            assert sms_notif.status == 'sent'
            assert sms_notif.channel == 'sms'

        history_res = await client.get('/api/v1/orgs/notifications/history', headers=auth_headers)
        assert history_res.status_code == 200
        history = history_res.json()
        assert len(history) >= 2
        channels = [h['channel'] for h in history]
        assert 'email' in channels
        assert 'sms' in channels
        assert any('order_confirmed' in h['event_type'] for h in history)
        assert any('dispatched' in h['event_type'] for h in history)

@pytest.mark.asyncio
async def test_live_api_execution_with_httpx_mock(monkeypatch):
    import httpx

    org = Organization(
        id='org_live_mock',
        name='Live Test Org',
        slug='live-test-org',
        twilio_account_sid='AC99999999999999999999999999999999',
        twilio_auth_token='secret_auth_live_12345',
        twilio_from_number='+15551112233',
        sendgrid_api_key='SG.live_sendgrid_key_realformat',
        email_from_address='dispatch@liveorg.com',
        email_from_name='Live Org Logistics'
    )

    # Mock httpx.AsyncClient.post for Twilio
    async def mock_twilio_post(self, url, **kwargs):
        if 'twilio.com' in str(url):
            return httpx.Response(201, json={'sid': 'SM_live_real_sid_1234567890', 'status': 'queued'})
        elif 'sendgrid.com' in str(url):
            return httpx.Response(202, text='Accepted')
        return httpx.Response(404)

    monkeypatch.setattr(httpx.AsyncClient, 'post', mock_twilio_post)

    sms_res = await TwilioSMSGateway.send_sms(
        to_phone='+15558889999',
        message='Live SMS test via mocked Twilio',
        org=org
    )
    assert sms_res['success'] is True
    assert sms_res['mode'] == 'live_twilio'
    assert sms_res['sid'] == 'SM_live_real_sid_1234567890'

    email_res = await EmailNotificationGateway.send_email(
        to_email='recipient@liveorg.com',
        subject='Live Email test via mocked SendGrid',
        html_content='<p>Test HTML</p>',
        org=org
    )
    assert email_res['success'] is True
    assert email_res['mode'] == 'live_sendgrid'
    assert email_res['status'] == 'sent'

