import json
import logging
import re
from typing import Optional, List, Dict, Any
from app.core.config import settings
from app.schemas.ai import LeadResearchResult, OutreachDraftResult, InboundReplyAnalysis

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model = settings.GEMINI_MODEL or "gemini-2.5-flash"
        self._client = None

        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
                logger.info("Initialized Google GenAI client successfully.")
            except Exception as e:
                logger.warning(f"Failed to initialize Google GenAI client: {e}. Falling back to local simulation.")

    def is_live(self) -> bool:
        return self._client is not None

    async def _call_gemini(self, system_instruction: str, prompt: str) -> str:
        """Helper to invoke Gemini with system instruction."""
        if not self._client:
            raise RuntimeError("Gemini client not initialized")
        
        # google-genai SDK call
        response = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={
                "system_instruction": system_instruction,
                "temperature": 0.3,
            }
        )
        return response.text

    async def research_and_score_lead(
        self,
        company_name: str,
        domain: Optional[str],
        industry: Optional[str],
        contact_name: str,
        job_title: Optional[str],
        product_summary: str
    ) -> LeadResearchResult:
        """
        Researches the company and scores the lead using Gemini.
        """
        system_instruction = (
            "You are a Senior B2B Sales Research AI. Analyze the target company and decision-maker.\n"
            "Return valid JSON matching this schema:\n"
            "{\n"
            '  "lead_score": integer (0-100),\n'
            '  "company_overview": string,\n'
            '  "decision_maker_analysis": string,\n'
            '  "suggested_angle": string,\n'
            '  "pain_points": [string, string],\n'
            '  "confidence_score": float (0.0-1.0)\n'
            "}\n"
            "Do NOT include markdown backticks or commentary, only raw JSON."
        )

        prompt = (
            f"Company: {company_name}\n"
            f"Domain: {domain or 'N/A'}\n"
            f"Industry: {industry or 'B2B General'}\n"
            f"Contact: {contact_name}, Title: {job_title or 'Purchasing / Office Manager'}\n"
            f"Our Product/Service Offering: {product_summary}\n"
        )

        if self.is_live():
            try:
                raw = await self._call_gemini(system_instruction, prompt)
                cleaned = self._clean_json(raw)
                data = json.loads(cleaned)
                return LeadResearchResult(**data)
            except Exception as e:
                logger.error(f"Gemini live call error: {e}. Falling back to simulation logic.")

        # Local simulation fallback
        score = 82 if ("supply" in (industry or "").lower() or "clean" in (industry or "").lower() or "office" in (industry or "").lower()) else 74
        return LeadResearchResult(
            lead_score=score,
            company_overview=f"{company_name} is an active regional business operating in {industry or 'the commercial B2B space'}.",
            decision_maker_analysis=f"{contact_name} ({job_title or 'Decision Maker'}) likely controls recurring operating budgets and supplier selection.",
            suggested_angle="Direct cost savings on consolidated supplier invoices and next-day scheduled fulfillment.",
            pain_points=[
                "High fragmented costs with multiple vendors",
                "Supply stockouts and unpredictable delivery turnaround"
            ],
            confidence_score=0.88
        )

    async def generate_outreach_email(
        self,
        company_name: str,
        contact_name: str,
        job_title: Optional[str],
        product_catalog_str: str,
        company_profile: str,
        tone: str = "professional and consultative"
    ) -> OutreachDraftResult:
        """
        Drafts a tailored B2B cold outreach email grounded strictly in the product catalog.
        """
        system_instruction = (
            "You are an expert B2B Sales Representative. Write a concise, personalized outreach email.\n"
            "CRITICAL RULES:\n"
            "1. You MUST ONLY reference products, pricing, and services from the provided catalog. Never invent discounts, guarantees, or features.\n"
            "2. Keep the email under 120 words. Focus on one clear value proposition and a low-friction call to action.\n"
            "Return valid JSON:\n"
            "{\n"
            '  "subject": string,\n'
            '  "body_text": string,\n'
            '  "value_proposition": string,\n'
            '  "call_to_action": string,\n'
            '  "confidence_score": float (0.0-1.0)\n'
            "}"
        )

        prompt = (
            f"Tone: {tone}\n"
            f"Target Company: {company_name}\n"
            f"Target Contact: {contact_name} ({job_title or 'Operations'})\n"
            f"Our Company: {company_profile}\n"
            f"Approved Product Catalog:\n{product_catalog_str}\n"
        )

        if self.is_live():
            try:
                raw = await self._call_gemini(system_instruction, prompt)
                cleaned = self._clean_json(raw)
                data = json.loads(cleaned)
                return OutreachDraftResult(**data)
            except Exception as e:
                logger.error(f"Gemini live call error: {e}. Falling back to simulation logic.")

        # Local simulation fallback
        return OutreachDraftResult(
            subject=f"Question regarding {company_name}'s supplies procurement",
            body_text=(
                f"Hi {contact_name},\n\n"
                f"I noticed {company_name} is actively expanding operations. "
                "Managing multiple commercial suppliers often leads to unexpected line-item markups and delivery delays.\n\n"
                "We partner with companies in your sector to streamline recurring office, janitorial, and business supplies "
                "with wholesale volume pricing and guaranteed next-day dispatch.\n\n"
                "Would you be open to a brief 5-minute comparison against your current procurement invoice this Thursday?\n\n"
                "Best regards,\nSales Team"
            ),
            value_proposition="Streamlined commercial supplier consolidation with wholesale volume discounts.",
            call_to_action="5-minute invoice comparison review call.",
            confidence_score=0.92
        )

    async def analyze_inbound_reply(
        self,
        conversation_history: str,
        inbound_message: str,
        max_discount_pct: float,
        product_catalog_str: str,
        ai_guidelines: Optional[str] = None
    ) -> InboundReplyAnalysis:
        """
        Analyzes a customer reply, detects intents/objections/discounts,
        and determines if Human-in-the-Loop (HITL) escalation is required.
        """
        system_instruction = (
            "You are an AI Sales Orchestration Supervisor. Analyze the incoming customer reply.\n"
            f"CRITICAL RULE: The AI agent is authorized to grant a maximum discount of {max_discount_pct}%.\n"
            "If the customer asks for a discount HIGHER than this limit, or becomes angry, or threatens legal action, "
            "or asks for custom contracts beyond the catalog, set requires_hitl = true with a specific hitl_reason.\n"
            "Return valid JSON:\n"
            "{\n"
            '  "intent": "interested" | "inquiry" | "objection" | "out_of_office" | "not_interested" | "gatekeeper_referral" | "unsubscribe",\n'
            '  "sentiment": "positive" | "neutral" | "hesitant" | "hostile",\n'
            '  "summary": string,\n'
            '  "requires_hitl": boolean,\n'
            '  "hitl_reason": string or null,\n'
            '  "suggested_reply": string or null,\n'
            '  "confidence_score": float (0.0-1.0),\n'
            '  "detected_discount_request": float or null\n'
            "}"
        )

        prompt = (
            f"Conversation History:\n{conversation_history}\n\n"
            f"New Inbound Customer Message:\n{inbound_message}\n\n"
            f"Approved Catalog:\n{product_catalog_str}\n"
            f"Company Guidelines:\n{ai_guidelines or 'None'}\n"
        )

        if self.is_live():
            try:
                raw = await self._call_gemini(system_instruction, prompt)
                cleaned = self._clean_json(raw)
                data = json.loads(cleaned)
                return InboundReplyAnalysis(**data)
            except Exception as e:
                logger.error(f"Gemini live call error: {e}. Falling back to deterministic guardrail analysis.")

        # Deterministic Guardrail Check (Local First)
        lower_msg = inbound_message.lower()
        
        # Check discount regex (e.g. "20% off", "15% discount")
        discount_match = re.search(r'(\d+(?:\.\d+)?)\s*%\s*(?:off|discount)', lower_msg)
        detected_discount = float(discount_match.group(1)) if discount_match else None

        if detected_discount and detected_discount > max_discount_pct:
            return InboundReplyAnalysis(
                intent="inquiry",
                sentiment="neutral",
                summary=f"Customer requested {detected_discount}% discount, which exceeds company policy limit of {max_discount_pct}%.",
                requires_hitl=True,
                hitl_reason=f"Customer requested a {detected_discount}% discount (Max allowed without approval: {max_discount_pct}%).",
                suggested_reply=f"Thank you for considering a partnership. We can offer our standard volume tier of {max_discount_pct}%, but I am checking with our sales director for approval on {detected_discount}%.",
                confidence_score=0.95,
                detected_discount_request=detected_discount
            )

        if any(w in lower_msg for w in ["sue", "lawyer", "attorney", "illegal", "report you", "scam"]):
            return InboundReplyAnalysis(
                intent="unsubscribe",
                sentiment="hostile",
                summary="Hostile message or legal dispute detected.",
                requires_hitl=True,
                hitl_reason="Hostile language or legal dispute detected. Immediate human takeover required.",
                suggested_reply=None,
                confidence_score=0.98,
                detected_discount_request=None
            )

        if any(w in lower_msg for w in ["unsubscribe", "remove me", "stop emailing", "do not contact"]):
            return InboundReplyAnalysis(
                intent="unsubscribe",
                sentiment="neutral",
                summary="Customer requested opt-out / unsubscribe.",
                requires_hitl=False,
                hitl_reason=None,
                suggested_reply="You have been unsubscribed and will receive no further messages.",
                confidence_score=0.99,
                detected_discount_request=None
            )

        if any(w in lower_msg for w in ["send info", "pricing", "catalog", "send details", "interested", "call me"]):
            return InboundReplyAnalysis(
                intent="interested",
                sentiment="positive",
                summary="Prospect expressed interest in pricing and product details.",
                requires_hitl=False,
                hitl_reason=None,
                suggested_reply="I'm delighted to share our commercial catalog. I've attached our tier-one pricing guide. What day this week would work best for a short introductory call?",
                confidence_score=0.91,
                detected_discount_request=None
            )

        # Default neutral reply
        return InboundReplyAnalysis(
            intent="inquiry",
            sentiment="neutral",
            summary="Customer sent a general reply asking for clarification.",
            requires_hitl=False,
            hitl_reason=None,
            suggested_reply="Thank you for getting back to us! Could you share a bit more about your current monthly supply volume so we can tailor the exact quote?",
            confidence_score=0.85,
            detected_discount_request=None
        )

    def _clean_json(self, raw_text: str) -> str:
        text = raw_text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\n", "", text)
            text = re.sub(r"\n```$", "", text)
        return text.strip()

gemini_service = GeminiService()
