import hmac
import hashlib
import json
import time
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.developer import WebhookSubscription, WebhookDeliveryLog
from app.schemas.developer import WebhookPingResponse

logger = logging.getLogger(__name__)

class WebhookService:
    """
    Outbound event webhook dispatch engine.
    Supports HMAC-SHA256 signature verification, automated delivery logging, and diagnostic pings.
    """

    @staticmethod
    def generate_signature(secret_key: str, payload_bytes: bytes, timestamp: int) -> str:
        """
        Generates HMAC-SHA256 signature header matching standard format:
        X-JsProject-Signature: t={timestamp},v1={hex_signature}
        """
        signed_payload = f"{timestamp}.".encode("utf-8") + payload_bytes
        signature = hmac.new(
            secret_key.encode("utf-8"),
            signed_payload,
            hashlib.sha256
        ).hexdigest()
        return f"t={timestamp},v1={signature}"

    @staticmethod
    async def dispatch_event(
        org_id: Optional[str] = None,
        event_type: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        db: Optional[AsyncSession] = None,
        *,
        event_name: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[WebhookDeliveryLog]:
        """
        Dispatches real-time outbound webhooks to all active subscriptions matching event_type.
        Executes without raising exceptions on target connection failures.
        """
        target_org_id = org_id or kwargs.get("org_id")
        target_event = event_type or event_name or kwargs.get("event")
        target_data = data if data is not None else (payload if payload is not None else kwargs.get("payload", {}))
        target_db = db or kwargs.get("db")

        if not target_org_id or not target_event or target_db is None:
            logger.warning(f"dispatch_event called with missing parameters: org_id={target_org_id}, event={target_event}")
            return []

        try:
            stmt = select(WebhookSubscription).where(
                WebhookSubscription.organization_id == target_org_id,
                WebhookSubscription.is_active == True
            )
            result = await target_db.execute(stmt)
            all_subs = result.scalars().all()

            matching_subs = [
                s for s in all_subs
                if "*" in s.events or target_event in s.events
            ]

            if not matching_subs:
                return []

            now = datetime.now(timezone.utc)
            timestamp = int(now.timestamp())
            envelope = {
                "id": f"evt_{uuid.uuid4().hex[:16]}",
                "event": target_event,
                "created_at": now.isoformat(),
                "organization_id": target_org_id,
                "data": target_data
            }
            payload_bytes = json.dumps(envelope, default=str).encode("utf-8")

            logs = []
            async with httpx.AsyncClient(timeout=5.0) as client:
                for sub in matching_subs:
                    delivery_uuid = str(uuid.uuid4())
                    sig_header = WebhookService.generate_signature(sub.secret_key, payload_bytes, timestamp)
                    headers = {
                        "Content-Type": "application/json",
                        "User-Agent": "JsProject-Webhooks/1.0",
                        "X-JsProject-Delivery": delivery_uuid,
                        "X-JsProject-Event": target_event,
                        "X-JsProject-Signature": sig_header,
                    }

                    status_code = None
                    response_text = ""
                    delivery_status = "delivered"
                    start_time = time.perf_counter()

                    try:
                        res = await client.post(sub.target_url, content=payload_bytes, headers=headers)
                        duration_ms = int((time.perf_counter() - start_time) * 1000)
                        status_code = res.status_code
                        response_text = res.text[:1000] if res.text else ""

                        if res.is_success:
                            sub.failure_count = 0
                            delivery_status = "delivered"
                        else:
                            sub.failure_count += 1
                            delivery_status = "failed"
                    except Exception as ex:
                        duration_ms = int((time.perf_counter() - start_time) * 1000)
                        delivery_status = "failed"
                        response_text = f"Connection error: {str(ex)}"
                        sub.failure_count += 1

                    log_entry = WebhookDeliveryLog(
                        organization_id=target_org_id,
                        subscription_id=sub.id,
                        event_type=target_event,
                        delivery_uuid=delivery_uuid,
                        payload_json=envelope,
                        response_status_code=status_code,
                        response_body=response_text,
                        duration_ms=duration_ms,
                        status=delivery_status,
                        delivered_at=now
                    )
                    target_db.add(log_entry)
                    target_db.add(sub)
                    logs.append(log_entry)

            await target_db.commit()
            return logs
        except Exception as err:
            logger.warning(f"Error during webhook dispatch for event {target_event}: {err}")
            return []

    @staticmethod
    async def ping_subscription(
        sub_id: str,
        org_id: str,
        db: AsyncSession
    ) -> WebhookPingResponse:
        """
        Sends an immediate diagnostic test ping to a webhook subscription endpoint.
        """
        stmt = select(WebhookSubscription).where(
            WebhookSubscription.id == sub_id,
            WebhookSubscription.organization_id == org_id
        )
        res = await db.execute(stmt)
        sub = res.scalar_one_or_none()
        if not sub:
            raise ValueError(f"Webhook subscription '{sub_id}' not found.")

        now = datetime.now(timezone.utc)
        timestamp = int(now.timestamp())
        delivery_uuid = str(uuid.uuid4())
        ping_envelope = {
            "id": f"evt_test_{uuid.uuid4().hex[:12]}",
            "event": "ping.test",
            "created_at": now.isoformat(),
            "organization_id": org_id,
            "data": {
                "message": "Webhook connectivity test ping from JsProject Developer Platform",
                "subscription_id": sub.id,
                "target_url": sub.target_url,
                "timestamp": now.isoformat()
            }
        }
        payload_bytes = json.dumps(ping_envelope, default=str).encode("utf-8")
        sig_header = WebhookService.generate_signature(sub.secret_key, payload_bytes, timestamp)
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "JsProject-Webhooks/1.0",
            "X-JsProject-Delivery": delivery_uuid,
            "X-JsProject-Event": "ping.test",
            "X-JsProject-Signature": sig_header,
        }

        status_code = None
        response_text = ""
        delivery_status = "delivered"
        start_time = time.perf_counter()

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(sub.target_url, content=payload_bytes, headers=headers)
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                status_code = resp.status_code
                response_text = resp.text[:1000] if resp.text else ""
                delivery_status = "delivered" if resp.is_success else "failed"
        except Exception as ex:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            delivery_status = "failed"
            response_text = f"Connection error: {str(ex)}"

        log_entry = WebhookDeliveryLog(
            organization_id=org_id,
            subscription_id=sub.id,
            event_type="ping.test",
            delivery_uuid=delivery_uuid,
            payload_json=ping_envelope,
            response_status_code=status_code,
            response_body=response_text,
            duration_ms=duration_ms,
            status=delivery_status,
            delivered_at=now
        )
        db.add(log_entry)
        await db.commit()
        await db.refresh(log_entry)

        is_success = (status_code is not None and 200 <= status_code < 300)
        return WebhookPingResponse(
            subscription_id=sub.id,
            target_url=sub.target_url,
            endpoint_url=sub.target_url,
            event="ping.test",
            status=delivery_status,
            response_status_code=status_code,
            duration_ms=duration_ms,
            delivery_id=log_entry.id,
            success=is_success,
            delivery={
                "id": log_entry.id,
                "event_type": "ping.test",
                "status": delivery_status,
                "response_status_code": status_code,
                "duration_ms": duration_ms,
                "success": is_success
            }
        )
