import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from app.core.config import settings
from app.services.gemini_service import gemini_service
from app.schemas.residential import (
    TradeType, CarpetCleaningSpecs, LawnCareSpecs, RoofingSpecs,
    QuoteLineItem, ResidentialQuoteRequest, ResidentialQuoteResponse,
    ChatMessage, ResidentialChatResponse
)

logger = logging.getLogger(__name__)

# Valid service ZIP codes (or prefixes)
ALLOWED_ZIP_PREFIXES = ["80", "84", "90", "91", "92", "93", "94", "95", "97", "98", "75", "76", "77", "78", "30", "33", "60", "10", "11"]

class ResidentialSalesEngine:
    """
    Core pricing calculator, guardrail validator, and conversational AI engine
    for residential home services (Carpet Cleaning, Lawn Care, Roofing & Gutters).
    """

    @classmethod
    def calculate_quote(
        cls,
        trade: TradeType,
        carpet: Optional[CarpetCleaningSpecs] = None,
        lawn: Optional[LawnCareSpecs] = None,
        roofing: Optional[RoofingSpecs] = None,
        promo_code: Optional[str] = None,
        zip_code: Optional[str] = None
    ) -> ResidentialQuoteResponse:
        line_items: List[QuoteLineItem] = []
        subtotal = 0.0
        discount_amount = 0.0
        discount_label = None
        is_range = False
        range_low = None
        range_high = None
        emergency_flag = False
        emergency_message = None
        notes = []
        min_callout_applied = False

        # Service territory validation
        service_area_valid = True
        if zip_code:
            clean_zip = re.sub(r"\D", "", zip_code)[:5]
            if len(clean_zip) >= 2:
                prefix = clean_zip[:2]
                if not any(clean_zip.startswith(p) for p in ALLOWED_ZIP_PREFIXES):
                    # Out of prime zone, but still service with travel fee note
                    notes.append(f"Notice: ZIP code {clean_zip} is in our extended territory. A $25 travel dispatch adjustment may apply.")

        # --- CARPET CLEANING PRICING ---
        if trade == TradeType.CARPET_CLEANING:
            specs = carpet or CarpetCleaningSpecs()
            room_rate = 45.0
            hallway_rate = 20.0
            stair_step_rate = 3.0
            pet_rate = 35.0
            scotchgard_rate = 25.0

            # Rooms
            if specs.rooms > 0:
                rooms_cost = specs.rooms * room_rate
                line_items.append(QuoteLineItem(
                    title=f"Standard Room Cleaning ({specs.rooms} rooms)",
                    description="Hot water extraction deep steam cleaning with eco-safe pre-spray",
                    unit_price=room_rate,
                    quantity=specs.rooms,
                    total=rooms_cost
                ))
                subtotal += rooms_cost

            # Hallways
            if specs.hallways > 0:
                hall_cost = specs.hallways * hallway_rate
                line_items.append(QuoteLineItem(
                    title=f"Hallway Deep Clean ({specs.hallways} sections)",
                    description="High-traffic corridor conditioning & extraction",
                    unit_price=hallway_rate,
                    quantity=specs.hallways,
                    total=hall_cost
                ))
                subtotal += hall_cost

            # Stairs
            if specs.stairs > 0:
                stairs_cost = specs.stairs * stair_step_rate
                line_items.append(QuoteLineItem(
                    title=f"Stair Flight Cleaning ({specs.stairs} steps)",
                    description="Riser and tread hand-wand fiber extraction",
                    unit_price=stair_step_rate,
                    quantity=specs.stairs,
                    total=stairs_cost
                ))
                subtotal += stairs_cost

            # Pet Treatment
            if specs.pet_treatment:
                pet_cost = pet_rate
                line_items.append(QuoteLineItem(
                    title="Deep Pet Urine & Odor Extraction",
                    description="Sub-surface enzyme injection to eliminate uric acid crystals & odor",
                    unit_price=pet_rate,
                    quantity=1,
                    total=pet_cost
                ))
                subtotal += pet_cost
                notes.append("Includes 100% odor-elimination pet enzyme warranty.")

            # Scotchgard
            if specs.scotchgard:
                scotch_cost = specs.rooms * scotchgard_rate
                line_items.append(QuoteLineItem(
                    title="Scotchgard™ Fiber Stain Shield",
                    description="Hydrophobic protective barrier against future wine, coffee & dirt spills",
                    unit_price=scotchgard_rate,
                    quantity=specs.rooms,
                    total=scotch_cost
                ))
                subtotal += scotch_cost

            # Deodorizer
            if specs.deodorizer:
                line_items.append(QuoteLineItem(
                    title="Whole-Home Fresh Citrus Botanical Deodorizer",
                    description="Complimentary anti-microbial air and carpet freshener",
                    unit_price=0.0,
                    quantity=1,
                    total=0.0
                ))

            # Minimum callout rule: $120
            if subtotal < 120.0 and subtotal > 0:
                diff = 120.0 - subtotal
                line_items.append(QuoteLineItem(
                    title="Minimum Service Call Adjustment",
                    description="Ensures dedicated technician van dispatch and truckmount equipment mobilization",
                    unit_price=diff,
                    quantity=1,
                    total=diff
                ))
                subtotal = 120.0
                min_callout_applied = True

            trade_title = "Apex Master Carpet & Upholstery Care"
            notes.append("Fast 4-6 hour dry time guarantee with industrial turbo fans.")

        # --- LAWN CARE & LANDSCAPING PRICING ---
        elif trade == TradeType.LAWN_CARE:
            specs = lawn or LawnCareSpecs()
            lot_rates = {
                "small_quarter_acre": (45.0, "Quarter Acre (< 10,800 sq ft)"),
                "medium_half_acre": (65.0, "Half Acre (10,800 - 21,780 sq ft)"),
                "large_one_acre": (95.0, "Full Acre (21,780 - 43,560 sq ft)"),
                "estate_plus": (145.0, "Estate / Acreage (1+ Acres)")
            }
            base_rate, lot_label = lot_rates.get(specs.lot_size_tier, (65.0, "Standard Half Acre"))

            cadence_titles = {
                "weekly": "Weekly Precision Cut & Perimeter Edge (Best Lawn Health)",
                "biweekly": "Bi-Weekly Maintenance Mowing & Edging",
                "one_time": "One-Time Yard Reset & Overgrowth Mow"
            }

            cadence_desc = {
                "weekly": "4 visits/month with blade edging, string trimming, and hardscape blow-off",
                "biweekly": "2 visits/month with edge trimming and driveway clean-sweep",
                "one_time": "Single clearing mow, heavy blade mulch, and debris blow-off"
            }

            # If weekly, customer gets 15% off regular per-visit rate
            if specs.cadence == "weekly":
                discount_amount += round(base_rate * 0.15, 2)
                discount_label = "Weekly Maintenance VIP 15% Discount"

            line_items.append(QuoteLineItem(
                title=f"Mowing & Edging Service - {lot_label}",
                description=f"{cadence_titles.get(specs.cadence, 'Regular Service')} • {cadence_desc.get(specs.cadence, '')}",
                unit_price=base_rate,
                quantity=1,
                total=base_rate
            ))
            subtotal += base_rate

            # Core Aeration & Overseeding Add-On
            if specs.aeration_overseeding:
                aeration_rates = {
                    "small_quarter_acre": 195.0,
                    "medium_half_acre": 249.0,
                    "large_one_acre": 349.0,
                    "estate_plus": 495.0
                }
                aeration_cost = aeration_rates.get(specs.lot_size_tier, 249.0)
                line_items.append(QuoteLineItem(
                    title="Core Aeration & Premium Bluegrass Overseed",
                    description="Decompresses compacted soil, introduces drought-hardy seed & improves root hydration",
                    unit_price=aeration_cost,
                    quantity=1,
                    total=aeration_cost
                ))
                subtotal += aeration_cost
                notes.append("Aeration promotes deep root growth and cuts summer water requirements by up to 30%.")

            # Weed & Feed / Turf Nutrition
            if specs.weed_fertilization:
                feed_cost = 65.0
                line_items.append(QuoteLineItem(
                    title="Turf Shield: Weed Control & Slow-Release Feed",
                    description="Targeted broadleaf herbicide spot-spray + iron-rich nitrogen pellet application",
                    unit_price=feed_cost,
                    quantity=1,
                    total=feed_cost
                ))
                subtotal += feed_cost

            # Edging is always included
            if specs.edge_trim:
                line_items.append(QuoteLineItem(
                    title="Crisp Curb & Driveway Razor Edging",
                    description="Clean mechanical vertical blading along curbs, driveways, and flowerbeds",
                    unit_price=0.0,
                    quantity=1,
                    total=0.0
                ))

            trade_title = "Apex Turf & Estate Lawn Maintenance"
            notes.append("Zero-contract flexibility: skip, pause, or reschedule anytime via SMS.")

        # --- ROOFING & GUTTERS PRICING ---
        elif trade == TradeType.ROOFING:
            specs = roofing or RoofingSpecs()

            if specs.issue_type == "active_leak":
                emergency_flag = True
                emergency_message = "ACTIVE LEAK DETECTED: We prioritize active leaks for immediate same-day technician dispatch to prevent drywall and ceiling collapse!"
                tarp_fee = 299.0
                line_items.append(QuoteLineItem(
                    title="Emergency Leak Triage & Waterproof Tarping Dispatch",
                    description="Rapid dispatch within 2-4 hours, attic moisture scan, safety tarp anchor, and leak containment",
                    unit_price=tarp_fee,
                    quantity=1,
                    total=tarp_fee
                ))
                subtotal += tarp_fee
                notes.append("100% of the $299 emergency triage fee is credited towards permanent repair or replacement.")

            elif specs.issue_type == "storm_damage":
                line_items.append(QuoteLineItem(
                    title="Storm & Hail Damage Forensic Assessment + Insurance Dossier",
                    description="Full 21-point drone roof scan, photo documentation, hail impact count, and line-item insurance adjuster report",
                    unit_price=0.0,
                    quantity=1,
                    total=0.0
                ))
                subtotal += 0.0
                notes.append("We meet your insurance adjuster on-site to ensure full restoration coverage with $0 out-of-pocket beyond deductible.")

            elif specs.issue_type == "replacement":
                is_range = True
                story_mult = 1.0 if specs.stories == 1 else (1.25 if specs.stories == 2 else 1.45)
                pitch_mult = 1.2 if specs.pitch == "steep" else 1.0
                
                # Average squares for 1 story ~22 sq, 2 story ~32 sq
                approx_sq = 22 if specs.stories == 1 else 32
                low_per_sq = 420.0 * story_mult * pitch_mult
                high_per_sq = 650.0 * story_mult * pitch_mult
                range_low = round(approx_sq * low_per_sq, 2)
                range_high = round(approx_sq * high_per_sq, 2)
                
                line_items.append(QuoteLineItem(
                    title=f"Architectural Shingle Roof Replacement ({specs.stories} Story)",
                    description=f"Estimated {approx_sq} squares. Includes tear-off, synthetic underlayment, ice & water shield, ridge vent, and 50-year GAF/Owens Corning warranty",
                    unit_price=round(low_per_sq, 2),
                    quantity=approx_sq,
                    total=range_low
                ))
                subtotal += range_low
                notes.append(f"Estimated full replacement budget range: ${range_low:,.0f} - ${range_high:,.0f} (subject to on-site roof measurement).")
                notes.append("Flexible 0% APR financing available starting at $129/month.")

            elif specs.issue_type == "gutters":
                gutter_fee = 149.0 if specs.stories == 1 else 199.0
                line_items.append(QuoteLineItem(
                    title=f"Full Gutter Cleanout & Downspout Hydro-Flush ({specs.stories} Story)",
                    description="Hand-removal of roof sludge, downspout snaking, elbow flush, and bagged debris haul-away",
                    unit_price=gutter_fee,
                    quantity=1,
                    total=gutter_fee
                ))
                subtotal += gutter_fee

            else:  # Default: Free Inspection
                line_items.append(QuoteLineItem(
                    title="Comprehensive 21-Point Roof & Attic Health Inspection",
                    description="Complimentary drone photography, attic ventilation check, shingle granule loss inspection, flashing seal analysis",
                    unit_price=0.0,
                    quantity=1,
                    total=0.0
                ))
                subtotal += 0.0
                notes.append("100% Free - Zero obligation written diagnostic report with high-res photos.")

            # Gutter cleaning add-on
            if specs.gutter_cleaning and specs.issue_type != "gutters":
                addon_gutter = 125.0
                line_items.append(QuoteLineItem(
                    title="Gutter Debris Cleaning & Downspout Tune-Up (Bundled)",
                    description="Clean all gutters, test downspout pitch, re-secure loose gutter spikes",
                    unit_price=addon_gutter,
                    quantity=1,
                    total=addon_gutter
                ))
                subtotal += addon_gutter

            trade_title = "Apex Elite Roofing & Exterior Defense"

        else:
            # Custom bundle / general
            trade_title = "Apex Multi-Service Home Defense"
            line_items.append(QuoteLineItem(
                title="Multi-Trade Home Service Consultation",
                description="Comprehensive interior & exterior property assessment",
                unit_price=0.0,
                quantity=1,
                total=0.0
            ))

        # Check Promo Codes
        if promo_code:
            code = promo_code.strip().upper()
            if code in ["SPRING20", "SAVE20", "CLEAN20"]:
                promo_disc = round(subtotal * 0.20, 2)
                discount_amount += promo_disc
                discount_label = f"Special Promo ({code}): 20% Off"
            elif code in ["NEIGHBOR10", "WELCOME10", "FIRST10"]:
                promo_disc = round(subtotal * 0.10, 2)
                discount_amount += promo_disc
                discount_label = f"Neighborhood Welcome ({code}): 10% Off"

        total_estimate = max(0.0, round(subtotal - discount_amount, 2))

        return ResidentialQuoteResponse(
            trade=trade.value if hasattr(trade, "value") else str(trade),
            trade_title=trade_title,
            line_items=line_items,
            subtotal=round(subtotal, 2),
            discount_amount=round(discount_amount, 2),
            discount_label=discount_label,
            total_estimate=total_estimate,
            is_range=is_range,
            range_low=range_low,
            range_high=range_high,
            emergency_flag=emergency_flag,
            emergency_message=emergency_message,
            service_area_valid=service_area_valid,
            minimum_callout_applied=min_callout_applied,
            notes=notes
        )

    @classmethod
    def get_dispatch_slots(cls, trade: str, days_ahead: int = 5) -> List[Dict[str, Any]]:
        """
        Generates realistic upcoming available crew dispatch windows.
        """
        slots = []
        now = datetime.now()
        
        # Next 5 days excluding past hours
        for day_offset in range(1, days_ahead + 1):
            day_dt = now + timedelta(days=day_offset)
            date_str = day_dt.strftime("%Y-%m-%d")
            display_day = day_dt.strftime("%A, %b %d")

            slots.append({
                "date": date_str,
                "display_day": display_day,
                "windows": [
                    {
                        "id": f"{date_str}_morning",
                        "label": "Morning Window (8:00 AM - 12:00 PM)",
                        "available": True,
                        "technician": "Crew 1 (Lead: Dave M.)"
                    },
                    {
                        "id": f"{date_str}_afternoon",
                        "label": "Afternoon Window (12:00 PM - 4:00 PM)",
                        "available": True,
                        "technician": "Crew 2 (Lead: Hector R.)"
                    },
                    {
                        "id": f"{date_str}_evening",
                        "label": "Late Afternoon (4:00 PM - 7:00 PM)",
                        "available": (day_offset % 2 == 1), # alternating
                        "technician": "Crew 3 (Lead: Brandon S.)"
                    }
                ]
            })
        return slots

    @classmethod
    async def process_chat(
        cls,
        message: str,
        conversation_id: Optional[str] = None,
        trade: Optional[str] = "carpet_cleaning",
        history: List[ChatMessage] = [],
        current_quote: Optional[ResidentialQuoteResponse] = None,
        homeowner_info: Optional[Dict[str, Any]] = None
    ) -> ResidentialChatResponse:
        """
        Processes a homeowner message via Gemini GenAI (or simulation fallback),
        updates qualification parameters, recalculates quote, and recommends next steps.
        """
        cid = conversation_id or f"resi_{uuid.uuid4().hex[:12]}"
        info = dict(homeowner_info or {})
        trade_str = trade or "carpet_cleaning"

        # Check if user mentioned a trade switch
        msg_lower = message.lower()
        if any(k in msg_lower for k in ["carpet", "rug", "upholstery"]):
            trade_str = "carpet_cleaning"
        elif any(k in msg_lower for k in ["lawn", "grass", "mow", "yard", "aerat", "landscap"]):
            trade_str = "lawn_care"
        elif any(k in msg_lower for k in ["roof", "leak", "gutter", "shingle", "hail"]):
            trade_str = "roofing"

        # Extract contact signals via regex if present
        phone_match = re.search(r"(\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})", message)
        if phone_match and "phone" not in info:
            info["phone"] = phone_match.group(1).strip()

        email_match = re.search(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", message)
        if email_match and "email" not in info:
            info["email"] = email_match.group(1).strip()

        zip_match = re.search(r"\b(\d{5})\b", message)
        if zip_match and "zip_code" not in info:
            info["zip_code"] = zip_match.group(1)

        # Call Gemini if live, or fall back to high-fidelity residential simulator
        if gemini_service.is_live():
            try:
                ai_result = await cls._call_gemini_sales_agent(
                    message=message,
                    trade=trade_str,
                    history=history,
                    current_info=info
                )
                return ai_result
            except Exception as e:
                logger.warning(f"Gemini live call failed in ResidentialSalesEngine: {e}. Executing simulation.")

        # Deterministic simulation fallback
        return cls._simulate_sales_agent(
            message=message,
            conversation_id=cid,
            trade=trade_str,
            history=history,
            current_info=info,
            current_quote=current_quote
        )

    @classmethod
    def _simulate_sales_agent(
        cls,
        message: str,
        conversation_id: str,
        trade: str,
        history: List[ChatMessage],
        current_info: Dict[str, Any],
        current_quote: Optional[ResidentialQuoteResponse]
    ) -> ResidentialChatResponse:
        """
        High-fidelity deterministic conversation engine for residential trades.
        """
        msg_lower = message.lower()
        quick_replies = []
        is_qualified = False
        ready_to_book = False
        emergency_flag = False
        suggested_action = None

        # Build trade specs based on detected tokens
        carpet_specs = CarpetCleaningSpecs()
        lawn_specs = LawnCareSpecs()
        roofing_specs = RoofingSpecs()

        # Update trade specs from info
        if "carpet" in current_info:
            carpet_specs = CarpetCleaningSpecs(**current_info["carpet"])
        if "lawn" in current_info:
            lawn_specs = LawnCareSpecs(**current_info["lawn"])
        if "roofing" in current_info:
            roofing_specs = RoofingSpecs(**current_info["roofing"])

        # Check for trade-specific details in user message
        # 1. Carpet Cleaning
        if trade == "carpet_cleaning":
            # Extract number of rooms
            room_search = re.search(r"(\d+)\s*(?:bed|room|living|dining|area)", msg_lower)
            if room_search:
                carpet_specs.rooms = int(room_search.group(1))

            if any(k in msg_lower for k in ["pet", "dog", "cat", "urine", "stain", "odor", "potty"]):
                carpet_specs.pet_treatment = True
            if any(k in msg_lower for k in ["scotchgard", "protect", "shield"]):
                carpet_specs.scotchgard = True
            if "stair" in msg_lower:
                stair_match = re.search(r"(\d+)\s*stairs?", msg_lower)
                carpet_specs.stairs = int(stair_match.group(1)) if stair_match else 14

            current_info["carpet"] = carpet_specs.model_dump()
            calc_quote = cls.calculate_quote(TradeType.CARPET_CLEANING, carpet=carpet_specs, zip_code=current_info.get("zip_code"))

            # Determine response
            if any(k in msg_lower for k in ["book", "schedule", "tomorrow", "saturday", "morning", "afternoon", "sign me up", "yes"]):
                reply = (
                    f"Fantastic! I have our hot water extraction van reserved for your {carpet_specs.rooms} rooms "
                    f"{'with pet enzyme treatment ' if carpet_specs.pet_treatment else ''}at our guaranteed price of **${calc_quote.total_estimate:,.2f}**. "
                    f"Would you prefer our **Morning window (8am-12pm)** or **Afternoon window (12pm-4pm)**?"
                )
                quick_replies = ["Morning (8am-12pm)", "Afternoon (12pm-4pm)", "Saturday Morning", "What's included in pet treatment?"]
                ready_to_book = True
                is_qualified = True
                suggested_action = "open_booking_modal"
            elif carpet_specs.pet_treatment:
                reply = (
                    f"Got it! For {carpet_specs.rooms} rooms with our hospital-grade pet urine and enzyme odor treatment, "
                    f"your complete upfront estimate is **${calc_quote.total_estimate:,.2f}** (all pre-sprays, deep extraction, and deodorizer included, no hidden fees). "
                    f"We back this with a 100% odor-free guarantee. Would you like me to reserve a technician slot for you this week?"
                )
                quick_replies = ["Let's schedule it!", "Can you do Saturday?", "Add Scotchgard protection", "How long does it take to dry?"]
                is_qualified = True
            else:
                reply = (
                    f"Hello! I can definitely help get your carpets looking brand new. For {carpet_specs.rooms} standard rooms and hallway, "
                    f"our steam extraction package comes out to **${calc_quote.total_estimate:,.2f}**. "
                    f"Do you have any pets or high-traffic stain areas we should treat with our enzyme pre-spray?"
                )
                quick_replies = ["Yes, we have pets / urine stains", "No pets, just normal wear", "We have 4 rooms and stairs", "Ready to book!"]
                is_qualified = True

        # 2. Lawn Care
        elif trade == "lawn_care":
            if any(k in msg_lower for k in ["small", "quarter", "1/4", "< 0.25"]):
                lawn_specs.lot_size_tier = "small_quarter_acre"
            elif any(k in msg_lower for k in ["half", "0.5", "1/2", "medium"]):
                lawn_specs.lot_size_tier = "medium_half_acre"
            elif any(k in msg_lower for k in ["one acre", "full acre", "1 acre", "large"]):
                lawn_specs.lot_size_tier = "large_one_acre"
            elif any(k in msg_lower for k in ["estate", "2 acre", "acreage"]):
                lawn_specs.lot_size_tier = "estate_plus"

            if any(k in msg_lower for k in ["biweekly", "bi-weekly", "every two weeks"]):
                lawn_specs.cadence = "biweekly"
            elif "weekly" in msg_lower:
                lawn_specs.cadence = "weekly"
            elif "one time" in msg_lower:
                lawn_specs.cadence = "one_time"

            if any(k in msg_lower for k in ["aerat", "overseed", "seed", "plugs"]):
                lawn_specs.aeration_overseeding = True
            if any(k in msg_lower for k in ["weed", "fertiliz", "feed", "moss"]):
                lawn_specs.weed_fertilization = True

            current_info["lawn"] = lawn_specs.model_dump()
            calc_quote = cls.calculate_quote(TradeType.LAWN_CARE, lawn=lawn_specs, zip_code=current_info.get("zip_code"))

            if any(k in msg_lower for k in ["book", "schedule", "start", "sign me up", "yes", "saturday"]):
                reply = (
                    f"Awesome! We have our route crew scheduled for your yard at **${calc_quote.total_estimate:,.2f} per service** "
                    f"({'with our 15% VIP Weekly Discount' if lawn_specs.cadence == 'weekly' else ''}). "
                    f"Every visit includes crisp driveway edging and leaf blow-off. What day of the week works best for your initial cut?"
                )
                quick_replies = ["Thursday or Friday", "Monday or Tuesday", "Include Core Aeration", "Can I cancel anytime?"]
                ready_to_book = True
                is_qualified = True
                suggested_action = "open_booking_modal"
            else:
                reply = (
                    f"Welcome to Apex Lawn Care! For a **{lawn_specs.lot_size_tier.replace('_', ' ')}** on our "
                    f"**{lawn_specs.cadence}** schedule, your price is **${calc_quote.total_estimate:,.2f} per cut**. "
                    f"This includes full precision mowing, perimeter string-trimming, weed-whacking, and hardscape blow-off with zero contracts. "
                    f"Would you like weekly maintenance (with our 15% VIP discount) or bi-weekly?"
                )
                quick_replies = ["Weekly (15% off)", "Bi-Weekly", "Add Core Aeration & Seed", "Ready to start this week!"]
                is_qualified = True

        # 3. Roofing & Gutters
        else:
            trade = "roofing"
            if any(k in msg_lower for k in ["leak", "water dripping", "ceiling", "emergency", "attic wet", "bucket"]):
                roofing_specs.issue_type = "active_leak"
                emergency_flag = True
            elif any(k in msg_lower for k in ["hail", "storm", "wind", "insurance", "blown off"]):
                roofing_specs.issue_type = "storm_damage"
            elif any(k in msg_lower for k in ["replace", "new roof", "age", "20 years", "shingles"]):
                roofing_specs.issue_type = "replacement"
            elif any(k in msg_lower for k in ["gutter", "downspout", "clogged"]):
                roofing_specs.issue_type = "gutters"

            if "2 story" in msg_lower or "two story" in msg_lower:
                roofing_specs.stories = 2

            current_info["roofing"] = roofing_specs.model_dump()
            calc_quote = cls.calculate_quote(TradeType.ROOFING, roofing=roofing_specs, zip_code=current_info.get("zip_code"))

            if roofing_specs.issue_type == "active_leak":
                reply = (
                    "⚠️ **URGENT LEAK ALERT**: Because active water intrusion can quickly compromise insulation and drywall, "
                    "I can dispatch an emergency leak technician to your home today. "
                    "Our emergency triage dispatch is **$299** (which includes attic scan and immediate waterproof tarping, "
                    "and 100% of this fee is credited toward your permanent repair). "
                    "Please provide your street address or phone number so dispatch can call you immediately!"
                )
                quick_replies = ["Dispatch a technician now", "Book emergency morning slot", "Where is the leak located?"]
                emergency_flag = True
                ready_to_book = True
                is_qualified = True
                suggested_action = "open_emergency_booking"
            elif roofing_specs.issue_type == "storm_damage":
                reply = (
                    "We specialize in storm & hail recovery! We provide a **100% Free 21-Point Drone & Attic Inspection**, "
                    "documenting granule loss and shingle bruising with high-res photos for your insurance adjuster. "
                    "Most homeowners pay $0 out-of-pocket beyond their deductible. When was the storm?"
                )
                quick_replies = ["Recent hail storm", "Book Free Inspection", "Can you meet my insurance adjuster?"]
                is_qualified = True
                ready_to_book = True
            elif roofing_specs.issue_type == "replacement":
                reply = (
                    f"For a {roofing_specs.stories}-story home, a full architectural shingle replacement with lifetime warranty "
                    f"typically ranges from **${calc_quote.range_low:,.0f} to ${calc_quote.range_high:,.0f}**, with $0 down 0% APR financing available. "
                    f"We'd love to send an exterior specialist for a **Free On-Site Precision Laser Measurement** and exact estimate. "
                    f"Would morning or afternoon suit your schedule?"
                )
                quick_replies = ["Book Free Laser Estimate", "Tell me about 0% financing", "Include Gutter Replacement"]
                is_qualified = True
                ready_to_book = True
            else:
                reply = (
                    "Hello! I can arrange our **Complimentary 21-Point Roof & Gutter Health Inspection** ($0.00). "
                    "Our certified specialist will inspect shingles, flashings, chimney seals, and attic ventilation, "
                    "and provide you with a photo report. Are you noticing any leaks, missing shingles, or just checking the roof's age?"
                )
                quick_replies = ["Schedule Free Inspection", "We have an active leak!", "Recent hail / storm damage", "Need gutters cleaned"]
                is_qualified = True

        return ResidentialChatResponse(
            reply=reply,
            trade=trade,
            conversation_id=conversation_id,
            current_quote=calc_quote,
            quick_replies=quick_replies,
            is_qualified=is_qualified,
            ready_to_book=ready_to_book,
            homeowner_info=current_info,
            emergency_flag=emergency_flag,
            suggested_action=suggested_action
        )

    @classmethod
    async def _call_gemini_sales_agent(
        cls,
        message: str,
        trade: str,
        history: List[ChatMessage],
        current_info: Dict[str, Any]
    ) -> ResidentialChatResponse:
        """Invokes Google Gemini with structured system prompt and parses response."""
        system_prompt = (
            "You are Amber, the Lead Service Coordinator for Apex Home Services. "
            "You quote and book appointments for Carpet Cleaning, Lawn Care, and Roofing & Gutters.\n"
            "Your personality is warm, reassuring, knowledgeable, transparent on pricing, and focused on booking the homeowner's appointment.\n"
            "Analyze the conversation and return ONLY valid JSON matching this schema:\n"
            "{\n"
            '  "reply": "Conversational reply to homeowner",\n'
            '  "detected_trade": "carpet_cleaning" | "lawn_care" | "roofing",\n'
            '  "carpet_specs": {"rooms": 3, "pet_treatment": false, "scotchgard": false, "stairs": 0},\n'
            '  "lawn_specs": {"lot_size_tier": "medium_half_acre", "cadence": "biweekly", "aeration": false},\n'
            '  "roofing_specs": {"issue_type": "inspection" | "active_leak" | "storm_damage" | "replacement", "stories": 1},\n'
            '  "quick_replies": ["option 1", "option 2", "option 3"],\n'
            '  "ready_to_book": boolean,\n'
            '  "is_qualified": boolean,\n'
            '  "emergency_flag": boolean\n'
            "}\n"
            "Do NOT include markdown backticks or commentary."
        )
        
        prompt = f"Current Info: {json.dumps(current_info)}\nHomeowner Message: {message}"
        gemini_text = await gemini_service._call_gemini(system_prompt, prompt)
        clean_json = re.sub(r"```json\s*", "", gemini_text)
        clean_json = re.sub(r"```\s*", "", clean_json).strip()
        data = json.loads(clean_json)

        detected_trade = data.get("detected_trade", trade)
        carpet_data = CarpetCleaningSpecs(**data.get("carpet_specs", {}))
        lawn_data = LawnCareSpecs(**data.get("lawn_specs", {}))
        roofing_data = RoofingSpecs(**data.get("roofing_specs", {}))

        trade_enum = TradeType(detected_trade) if detected_trade in TradeType._value2member_map_ else TradeType.CARPET_CLEANING
        quote = cls.calculate_quote(trade_enum, carpet=carpet_data, lawn=lawn_data, roofing=roofing_data)

        return ResidentialChatResponse(
            reply=data.get("reply", "I can help with that!"),
            trade=detected_trade,
            conversation_id=f"resi_{uuid.uuid4().hex[:12]}",
            current_quote=quote,
            quick_replies=data.get("quick_replies", ["Book Appointment", "Ask a Question"]),
            is_qualified=data.get("is_qualified", True),
            ready_to_book=data.get("ready_to_book", False),
            homeowner_info=current_info,
            emergency_flag=data.get("emergency_flag", False)
        )
