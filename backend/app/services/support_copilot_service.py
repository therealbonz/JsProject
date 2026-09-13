import re
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from sqlalchemy.orm import selectinload

from app.models.tenant import User, Organization
from app.models.crm import ClientAccount, ClientSale, SaaSLicense
from app.models.conversation import Conversation, Message
from app.models.hitl import HumanAssistanceRequest
from app.models.base import get_utc_now
from app.services.gemini_service import gemini_service
from app.schemas.support_copilot import (
    CopilotChatResponse,
    CopilotMessageDTO,
    CopilotConversationSummary,
    CopilotConversationDetail
)

logger = logging.getLogger(__name__)

class SupportCopilotService:

    @classmethod
    async def get_client_by_token(cls, db: AsyncSession, token: str) -> Optional[ClientAccount]:
        stmt = (
            select(ClientAccount)
            .options(
                selectinload(ClientAccount.primary_contact),
                selectinload(ClientAccount.company),
                selectinload(ClientAccount.sales).selectinload(ClientSale.purchase_orders),
                selectinload(ClientAccount.licenses)
            )
            .where(ClientAccount.portal_access_token == token)
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @classmethod
    async def get_or_create_conversation(
        cls,
        db: AsyncSession,
        client: ClientAccount,
        conversation_id: Optional[str] = None
    ) -> Conversation:
        if conversation_id:
            stmt = (
                select(Conversation)
                .options(selectinload(Conversation.messages))
                .where(
                    Conversation.id == conversation_id,
                    Conversation.client_id == client.id
                )
            )
            conv = (await db.execute(stmt)).scalar_one_or_none()
            if conv:
                return conv

        # Find existing active portal conversation
        stmt = (
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(
                Conversation.client_id == client.id,
                Conversation.channel.in_(["customer_portal", "web_chat"]),
                Conversation.status.in_(["active", "waiting_on_lead", "waiting_on_human"])
            )
            .order_by(Conversation.created_at.desc())
        )
        existing = (await db.execute(stmt)).scalars().first()
        if existing:
            return existing

        # Create new
        new_conv = Conversation(
            id=str(uuid.uuid4()),
            organization_id=client.organization_id,
            client_id=client.id,
            lead_id=None,
            channel="customer_portal",
            status="active",
            sentiment="neutral",
            current_objective="portal_support",
            ai_summary="New customer support conversation initiated via self-service portal."
        )
        db.add(new_conv)
        await db.commit()
        await db.refresh(new_conv)

        # Reload with messages relationship
        stmt = select(Conversation).options(selectinload(Conversation.messages)).where(Conversation.id == new_conv.id)
        return (await db.execute(stmt)).scalar_one()

    @classmethod
    def detect_sentiment(cls, text: str) -> str:
        lower = text.lower()
        hostile_keywords = [
            "lawyer", "attorney", "sue", "scam", "fraud", "terrible", "horrible",
            "furious", "unacceptable", "dispute", "broken", "garbage", "trash", "cancel"
        ]
        positive_keywords = [
            "thank", "thanks", "great", "awesome", "perfect", "appreciate",
            "excellent", "good job", "helpful", "love"
        ]
        if any(w in lower for w in hostile_keywords):
            return "hostile"
        if any(w in lower for w in positive_keywords):
            return "positive"
        return "neutral"

    @classmethod
    def should_escalate(cls, text: str, sentiment: str) -> Tuple[bool, Optional[str]]:
        lower = text.lower()
        human_triggers = [
            "talk to a human", "talk to a person", "speak to a person", "human agent",
            "real person", "customer service rep", "account manager", "speak with someone",
            "supervisor", "manager", "escalate", "call me"
        ]
        if any(t in lower for t in human_triggers):
            return True, "Customer explicitly requested human representative"
        if sentiment == "hostile":
            return True, "Hostile or strongly frustrated customer sentiment detected"
        if "dispute charge" in lower or "refund" in lower:
            return True, "Billing dispute or commercial refund request requires human review"
        return False, None

    @classmethod
    async def process_portal_chat(
        cls,
        db: AsyncSession,
        portal_token: str,
        user_message: str,
        conversation_id: Optional[str] = None
    ) -> CopilotChatResponse:
        client = await cls.get_client_by_token(db, portal_token)
        if not client:
            raise ValueError("Invalid or expired portal token")

        conv = await cls.get_or_create_conversation(db, client, conversation_id)
        now = get_utc_now()

        # 1. Log inbound customer message
        client_contact_name = f"{client.primary_contact.first_name} {client.primary_contact.last_name}" if client.primary_contact else client.account_name
        inbound_msg = Message(
            id=str(uuid.uuid4()),
            conversation_id=conv.id,
            sender_type="customer",
            sender_name=client_contact_name,
            direction="inbound",
            body_text=user_message,
            ai_reasoning={},
            created_at=now
        )
        db.add(inbound_msg)

        # 2. Analyze Sentiment & Human Escalation
        sentiment = cls.detect_sentiment(user_message)
        conv.sentiment = sentiment
        must_escalate, escalation_reason = cls.should_escalate(user_message, sentiment)

        tool_calls = []
        reply_text = ""
        hitl_request_id = None

        # 3. Tool Execution Engine
        lower_msg = user_message.lower()

        # Tool: Check for order lookup (e.g. ORD-1001, #1001, order 123)
        order_match = re.search(r'(?:\bORD[-_]([a-zA-Z0-9_-]+)|\b#([a-zA-Z0-9_-]+)|\border\s+(?:#\s*|no\.?\s*|number\s*)?([a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)?))\b', user_message, re.IGNORECASE)
        specific_order_id = None
        if order_match:
            candidate = next((g for g in order_match.groups() if g), None)
            if candidate and candidate.lower() not in ["s", "history", "list", "status", "details", "update", "number", "id"] and len(candidate) >= 2:
                specific_order_id = candidate.upper()

        wants_order_info = any(k in lower_msg for k in ["order", "orders", "tracking", "shipment", "package", "where is", "delivery", "delivered"])
        wants_restock_info = any(k in lower_msg for k in ["restock", "cadence", "safety stock", "replenish", "reorder", "burn rate", "stockout"])
        wants_snooze = any(k in lower_msg for k in ["snooze", "delay", "push back", "postpone"])
        wants_accelerate = any(k in lower_msg for k in ["ship now", "restock now", "rush", "asap", "need stock immediately"])
        wants_billing_info = any(k in lower_msg for k in ["billing", "card", "payment method", "invoice", "charge", "subscription", "license", "tier"])

        if must_escalate:
            # Execute HITL Escalation Tool
            hitl_req = HumanAssistanceRequest(
                id=str(uuid.uuid4()),
                organization_id=client.organization_id,
                conversation_id=conv.id,
                client_id=client.id,
                trigger_reason="human_requested" if "human" in lower_msg else "sentiment_escalation",
                situation_summary=f"Customer '{client.account_name}' requested human support. Last message: \"{user_message}\"",
                suggested_options=[
                    f"Direct phone follow-up by {client.account_manager}",
                    "Review commercial account terms and order history",
                    "Offer immediate restock priority dispatch"
                ],
                ai_recommendation="Acknowledge concern with priority dispatch and route directly to account manager.",
                confidence_score=0.98,
                status="pending"
            )
            db.add(hitl_req)
            hitl_request_id = hitl_req.id
            conv.status = "waiting_on_human"
            conv.current_objective = "human_escalation"

            tool_calls.append({
                "tool_name": "escalate_to_human",
                "parameters": {"reason": escalation_reason, "account_manager": client.account_manager},
                "status": "executed"
            })

            reply_text = (
                f"I have connected your request directly with your dedicated account manager, **{client.account_manager}**.\n\n"
                f"A priority human assistance ticket (`#{hitl_req.id[:8]}`) has been generated with our full conversation history. "
                f"A senior representative will review your inquiry and follow up shortly."
            )

        elif specific_order_id and wants_order_info:
            target_order_query = specific_order_id
            matching_sale = next(
                (s for s in (client.sales or []) if target_order_query in s.order_number.upper() or s.order_number.upper() in target_order_query),
                None
            )

            tool_calls.append({
                "tool_name": "lookup_order_status",
                "parameters": {"query": target_order_query, "matched": bool(matching_sale)},
                "status": "executed"
            })

            if matching_sale:
                carrier_info = "Standard Commercial Carrier"
                tracking_num = "Pending assignment"
                tracking_link = f"/track/{matching_sale.order_number}"
                if matching_sale.purchase_orders:
                    for po in matching_sale.purchase_orders:
                        if hasattr(po, "shipments") and po.shipments:
                            s = po.shipments[0]
                            carrier_info = s.carrier or carrier_info
                            tracking_num = s.tracking_number or tracking_num

                reply_text = (
                    f"Here are the delivery details for **Order #{matching_sale.order_number}**:\n\n"
                    f"- **Status**: `{matching_sale.status.upper()}`\n"
                    f"- **Payment**: `{matching_sale.payment_status.upper()}` (${matching_sale.amount:,.2f})\n"
                    f"- **Carrier**: {carrier_info}\n"
                    f"- **Tracking Number**: `{tracking_num}`\n"
                    f"- **Items**: {matching_sale.items_summary}\n\n"
                    f"You can view live route milestones on the [Delivery Tracking Portal]({tracking_link})."
                )
            else:
                reply_text = (
                    f"I searched your account records but could not find an order matching `#{target_order_query}`. "
                    f"Your most recent completed order on file is **#{client.sales[0].order_number}** if you'd like me to look that up instead."
                    if client.sales else "There are currently no prior orders registered under this account."
                )

        elif wants_snooze:
            # Execute Restock Snooze Tool
            days = 14
            num_match = re.search(r'(\d+)\s*(?:day|week)', lower_msg)
            if num_match:
                days = int(num_match.group(1))
                if "week" in lower_msg:
                    days *= 7

            old_date = client.next_reorder_date or now
            new_date = old_date + timedelta(days=days)
            client.next_reorder_date = new_date

            tool_calls.append({
                "tool_name": "snooze_restock_schedule",
                "parameters": {"days": days, "new_date": new_date.isoformat()},
                "status": "executed"
            })

            reply_text = (
                f"✅ **Replenishment Schedule Updated**\n\n"
                f"I have snoozed your automated inventory restock by **{days} days**.\n"
                f"- **New Estimated Restock Date**: {new_date.strftime('%B %d, %Y')}\n"
                f"- **Current Safety Stock**: {client.safety_stock_buffer_percent}% buffer maintained\n\n"
                f"Our demand monitoring engine will continue auditing your facility burn rate."
            )

        elif wants_accelerate:
            # Accelerate Restock Tool
            tomorrow = now + timedelta(days=1)
            client.next_reorder_date = tomorrow

            tool_calls.append({
                "tool_name": "accelerate_restock_schedule",
                "parameters": {"next_date": tomorrow.isoformat()},
                "status": "executed"
            })

            reply_text = (
                f"🚀 **Restock Accelerated for Priority Dispatch**\n\n"
                f"I have marked your replenishment schedule for immediate processing on **{tomorrow.strftime('%B %d, %Y')}**.\n"
                f"- **Assigned Manager**: {client.account_manager}\n"
                f"- **Card on File**: {client.card_brand.upper() if client.card_brand else 'Card'} ending in `{client.card_last4 or '••••'}`\n\n"
                f"A procurement purchase order will be generated and dispatched automatically."
            )

        elif wants_restock_info:
            # Execute Restock Forecast Tool
            tool_calls.append({
                "tool_name": "check_restock_forecast",
                "parameters": {
                    "cadence_days": client.reorder_cadence_days,
                    "burn_rate": client.predicted_burn_rate,
                    "risk_level": client.stockout_risk_level
                },
                "status": "executed"
            })

            next_date_str = client.next_reorder_date.strftime('%B %d, %Y') if client.next_reorder_date else "Scheduled upon next replenishment run"
            reply_text = (
                f"Here is your active **Inventory Replenishment & Safety Stock** status:\n\n"
                f"- **Next Scheduled Restock**: {next_date_str}\n"
                f"- **Reorder Cadence**: Every {client.reorder_cadence_days} Days\n"
                f"- **Stockout Risk Level**: `{client.stockout_risk_level.upper()}` (Confidence: {int(client.forecast_confidence * 100)}%)\n"
                f"- **Dynamic Safety Buffer**: {client.safety_stock_buffer_percent}% above daily burn\n\n"
                f"You can ask me to *snooze* or *accelerate* this shipment at any time."
            )

        elif wants_billing_info:
            # Execute Billing Status Tool
            license_info = "Pro Plan (Standard Commercial)"
            if client.licenses:
                lic = client.licenses[0]
                license_info = f"{lic.product_name} ({lic.plan_tier.upper()} Tier, Status: `{lic.license_status.upper()}`)"

            tool_calls.append({
                "tool_name": "check_billing_status",
                "parameters": {"has_card": client.has_payment_method_on_file, "license": license_info},
                "status": "executed"
            })

            card_summary = f"{client.card_brand.upper()} ending in `{client.card_last4}`" if client.has_payment_method_on_file else "No payment card currently on file"
            auto_charge_status = "Enabled" if client.auto_charge_enabled else "Disabled (Manual Invoice Settlement)"

            reply_text = (
                f"Here is your commercial billing summary:\n\n"
                f"- **Platform Plan**: {license_info}\n"
                f"- **Payment Method on File**: {card_summary}\n"
                f"- **Auto-Charge**: {auto_charge_status}\n"
                f"- **Account Tier**: `{client.account_tier.upper()}`\n\n"
                f"Let me know if you need past invoice statements or need to update your card on file."
            )

        elif wants_order_info:
            # Execute Recent Orders Tool
            tool_calls.append({
                "tool_name": "get_recent_orders",
                "parameters": {"client_id": client.id, "order_count": len(client.sales or [])},
                "status": "executed"
            })

            if client.sales:
                order_lines = []
                for s in client.sales[:3]:
                    order_lines.append(f"- **#{s.order_number}**: ${s.amount:,.2f} (`{s.status.upper()}`) • {s.items_summary}")
                reply_text = (
                    f"Here are your latest orders on record:\n\n" +
                    "\n".join(order_lines) +
                    f"\n\nWould you like detailed tracking or invoice records for any of these?"
                )
            else:
                reply_text = "You currently do not have any past sales or orders recorded under this account."

        else:
            # General Consultative Response (Call Gemini if live, or consultative local engine)
            if gemini_service.is_live():
                try:
                    sys_prompt = (
                        f"You are the AI Support Copilot for {client.account_name}. "
                        f"You assist the customer with order status, shipments, replenishment schedules, safety stock, and commercial billing. "
                        f"Be professional, concise, and helpful. Format responses in clean Markdown."
                    )
                    prompt = f"Customer Query: {user_message}\nClient Account Tier: {client.account_tier}\nAssigned Manager: {client.account_manager}"
                    raw = await gemini_service._call_gemini(sys_prompt, prompt)
                    reply_text = raw.strip()
                except Exception as e:
                    logger.warning("Gemini live call failed, falling back to local copilot engine: %s", e)

            if not reply_text:
                reply_text = (
                    f"Hello! I am your AI Support Copilot for **{client.account_name}**.\n\n"
                    f"I can assist you directly with:\n"
                    f"- 📦 **Order Tracking**: Ask *\"Where is my latest shipment?\"* or search by order number.\n"
                    f"- ⚡ **Inventory Restock**: Inquire about your replenishment date, snooze, or accelerate shipments.\n"
                    f"- 💳 **Billing & Invoices**: Check your card on file, plan tier, or request invoice copies.\n"
                    f"- 🧑‍💼 **Account Management**: Ask to speak directly with your manager **{client.account_manager}**.\n\n"
                    f"How can I help you today?"
                )

        # 4. Log outbound AI response message
        outbound_msg = Message(
            id=str(uuid.uuid4()),
            conversation_id=conv.id,
            sender_type="ai_agent",
            sender_name="AI Support Copilot",
            direction="outbound",
            body_text=reply_text,
            ai_confidence=0.96,
            ai_reasoning={
                "tool_calls": tool_calls,
                "sentiment": sentiment,
                "escalated": must_escalate,
                "escalation_reason": escalation_reason
            },
            created_at=get_utc_now()
        )
        db.add(outbound_msg)

        conv.ai_summary = f"Handled {conv.channel} query regarding {tool_calls[0]['tool_name'] if tool_calls else 'general support'}. Sentiment: {sentiment}."
        await db.commit()

        return CopilotChatResponse(
            conversation_id=conv.id,
            reply=reply_text,
            sender_type="ai_agent",
            sentiment=sentiment,
            is_escalated=must_escalate,
            escalation_reason=escalation_reason,
            tool_calls=tool_calls,
            confidence_score=0.96,
            created_at=outbound_msg.created_at
        )

    @classmethod
    async def get_portal_chat_history(
        cls,
        db: AsyncSession,
        portal_token: str
    ) -> List[CopilotMessageDTO]:
        client = await cls.get_client_by_token(db, portal_token)
        if not client:
            raise ValueError("Invalid portal token")

        conv_stmt = (
            select(Conversation)
            .where(
                Conversation.client_id == client.id,
                Conversation.channel.in_(["customer_portal", "web_chat"])
            )
            .order_by(Conversation.created_at.desc())
        )
        conv = (await db.execute(conv_stmt)).scalars().first()
        if not conv:
            return []

        msg_stmt = (
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at.asc())
        )
        messages = (await db.execute(msg_stmt)).scalars().all()

        return [
            CopilotMessageDTO(
                id=m.id,
                conversation_id=m.conversation_id,
                sender_type=m.sender_type,
                sender_name=m.sender_name,
                direction=m.direction,
                body_text=m.body_text,
                ai_confidence=m.ai_confidence,
                ai_reasoning=m.ai_reasoning or {},
                created_at=m.created_at
            )
            for m in messages
        ]

    @classmethod
    async def escalate_portal_session(
        cls,
        db: AsyncSession,
        portal_token: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        client = await cls.get_client_by_token(db, portal_token)
        if not client:
            raise ValueError("Invalid portal token")

        conv = await cls.get_or_create_conversation(db, client)
        conv.status = "waiting_on_human"
        conv.current_objective = "human_escalation"

        hitl = HumanAssistanceRequest(
            id=str(uuid.uuid4()),
            organization_id=client.organization_id,
            conversation_id=conv.id,
            client_id=client.id,
            trigger_reason="customer_initiated_escalation",
            situation_summary=f"Customer '{client.account_name}' manually triggered human assistance button: {reason or 'General inquiry'}",
            suggested_options=["Review chat history", "Contact client directly via phone/email"],
            ai_recommendation="Contact client promptly to provide human support.",
            confidence_score=1.0,
            status="pending"
        )
        db.add(hitl)

        # Add confirmation message
        sys_msg = Message(
            id=str(uuid.uuid4()),
            conversation_id=conv.id,
            sender_type="ai_agent",
            sender_name="AI Support Copilot",
            direction="outbound",
            body_text=f"Your request for human assistance has been submitted to **{client.account_manager}** (Ticket `#{hitl.id[:8]}`). A representative will assist you shortly.",
            ai_confidence=1.0,
            ai_reasoning={"escalated": True, "hitl_id": hitl.id},
            created_at=get_utc_now()
        )
        db.add(sys_msg)
        await db.commit()

        return {
            "status": "escalated",
            "hitl_id": hitl.id,
            "conversation_id": conv.id,
            "account_manager": client.account_manager,
            "message": "Human assistance request dispatched."
        }

    @classmethod
    async def list_support_conversations(
        cls,
        db: AsyncSession,
        org_id: str,
        status_filter: Optional[str] = None,
        limit: int = 50
    ) -> List[CopilotConversationSummary]:
        stmt = (
            select(Conversation)
            .options(
                selectinload(Conversation.client).selectinload(ClientAccount.company),
                selectinload(Conversation.messages),
                selectinload(Conversation.assistance_requests)
            )
            .where(
                Conversation.organization_id == org_id,
                Conversation.channel.in_(["customer_portal", "web_chat"])
            )
        )
        if status_filter:
            stmt = stmt.where(Conversation.status == status_filter)

        stmt = stmt.order_by(Conversation.created_at.desc()).limit(limit)
        res = await db.execute(stmt)
        convs = res.scalars().all()

        results = []
        for c in convs:
            msgs = c.messages or []
            last_msg = msgs[-1] if msgs else None
            pending_hitl = next((h for h in (c.assistance_requests or []) if h.status == "pending"), None)

            results.append(CopilotConversationSummary(
                id=c.id,
                client_id=c.client_id,
                client_name=c.client.account_name if c.client else "Unassigned Client",
                company_name=c.client.company.name if c.client and c.client.company else None,
                channel=c.channel,
                status=c.status,
                sentiment=c.sentiment,
                current_objective=c.current_objective,
                message_count=len(msgs),
                last_message=last_msg.body_text[:100] if last_msg else None,
                last_message_at=last_msg.created_at if last_msg else c.created_at,
                is_escalated=(c.status == "waiting_on_human" or pending_hitl is not None),
                hitl_request_id=pending_hitl.id if pending_hitl else None,
                account_manager=c.client.account_manager if c.client else None
            ))
        return results

    @classmethod
    async def get_conversation_detail(
        cls,
        db: AsyncSession,
        conversation_id: str,
        org_id: str
    ) -> Optional[CopilotConversationDetail]:
        stmt = (
            select(Conversation)
            .options(
                selectinload(Conversation.client).selectinload(ClientAccount.company),
                selectinload(Conversation.client).selectinload(ClientAccount.primary_contact),
                selectinload(Conversation.messages),
                selectinload(Conversation.assistance_requests)
            )
            .where(
                Conversation.id == conversation_id,
                Conversation.organization_id == org_id
            )
        )
        res = await db.execute(stmt)
        c = res.scalar_one_or_none()
        if not c:
            return None

        msgs = c.messages or []
        last_msg = msgs[-1] if msgs else None
        pending_hitl = next((h for h in (c.assistance_requests or []) if h.status == "pending"), None)

        summary = CopilotConversationSummary(
            id=c.id,
            client_id=c.client_id,
            client_name=c.client.account_name if c.client else "Unassigned Client",
            company_name=c.client.company.name if c.client and c.client.company else None,
            channel=c.channel,
            status=c.status,
            sentiment=c.sentiment,
            current_objective=c.current_objective,
            message_count=len(msgs),
            last_message=last_msg.body_text[:100] if last_msg else None,
            last_message_at=last_msg.created_at if last_msg else c.created_at,
            is_escalated=(c.status == "waiting_on_human" or pending_hitl is not None),
            hitl_request_id=pending_hitl.id if pending_hitl else None,
            account_manager=c.client.account_manager if c.client else None
        )

        message_dtos = [
            CopilotMessageDTO(
                id=m.id,
                conversation_id=m.conversation_id,
                sender_type=m.sender_type,
                sender_name=m.sender_name,
                direction=m.direction,
                body_text=m.body_text,
                ai_confidence=m.ai_confidence,
                ai_reasoning=m.ai_reasoning or {},
                created_at=m.created_at
            )
            for m in msgs
        ]

        client_summary = None
        if c.client:
            client_summary = {
                "account_name": c.client.account_name,
                "account_tier": c.client.account_tier,
                "total_revenue": c.client.total_revenue,
                "reorder_cadence_days": c.client.reorder_cadence_days,
                "next_reorder_date": c.client.next_reorder_date.isoformat() if c.client.next_reorder_date else None,
                "card_brand": c.client.card_brand,
                "card_last4": c.client.card_last4,
                "account_manager": c.client.account_manager
            }

        return CopilotConversationDetail(
            conversation=summary,
            messages=message_dtos,
            client_account_summary=client_summary
        )

    @classmethod
    async def send_human_rep_reply(
        cls,
        db: AsyncSession,
        conversation_id: str,
        org_id: str,
        user: User,
        reply_text: str,
        resolve_ticket: bool = False
    ) -> CopilotMessageDTO:
        stmt = (
            select(Conversation)
            .options(selectinload(Conversation.assistance_requests))
            .where(
                Conversation.id == conversation_id,
                Conversation.organization_id == org_id
            )
        )
        res = await db.execute(stmt)
        conv = res.scalar_one_or_none()
        if not conv:
            raise ValueError("Conversation not found")

        # Create human message
        msg = Message(
            id=str(uuid.uuid4()),
            conversation_id=conv.id,
            sender_type="human_rep",
            sender_name=user.full_name or "Account Representative",
            direction="outbound",
            body_text=reply_text,
            ai_reasoning={"replied_by_user_id": user.id},
            created_at=get_utc_now()
        )
        db.add(msg)

        # Update HITL requests if any
        now = get_utc_now()
        for hitl in (conv.assistance_requests or []):
            if hitl.status == "pending":
                hitl.status = "resolved" if resolve_ticket else "taken_over"
                hitl.reviewed_by_user_id = user.id
                hitl.reviewer_instructions = reply_text
                hitl.resolved_at = now
                db.add(hitl)

        if resolve_ticket:
            conv.status = "resolved"
        else:
            conv.status = "active"

        await db.commit()
        await db.refresh(msg)

        return CopilotMessageDTO(
            id=msg.id,
            conversation_id=msg.conversation_id,
            sender_type=msg.sender_type,
            sender_name=msg.sender_name,
            direction=msg.direction,
            body_text=msg.body_text,
            ai_confidence=1.0,
            ai_reasoning=msg.ai_reasoning or {},
            created_at=msg.created_at
        )

    @classmethod
    async def resolve_conversation(
        cls,
        db: AsyncSession,
        conversation_id: str,
        org_id: str,
        user: User
    ) -> bool:
        stmt = (
            select(Conversation)
            .options(selectinload(Conversation.assistance_requests))
            .where(
                Conversation.id == conversation_id,
                Conversation.organization_id == org_id
            )
        )
        res = await db.execute(stmt)
        conv = res.scalar_one_or_none()
        if not conv:
            return False

        conv.status = "resolved"
        now = get_utc_now()
        for hitl in (conv.assistance_requests or []):
            if hitl.status == "pending":
                hitl.status = "resolved"
                hitl.reviewed_by_user_id = user.id
                hitl.resolved_at = now
                db.add(hitl)

        await db.commit()
        return True
