from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict

class TradeType(str, Enum):
    CARPET_CLEANING = "carpet_cleaning"
    LAWN_CARE = "lawn_care"
    ROOFING = "roofing"
    CUSTOM_BUNDLE = "custom_bundle"

class CarpetCleaningSpecs(BaseModel):
    rooms: int = Field(default=3, description="Number of standard bedrooms / living rooms / dining rooms")
    stairs: int = Field(default=0, description="Number of stair steps")
    hallways: int = Field(default=1, description="Number of hallway sections")
    pet_treatment: bool = Field(default=False, description="Specialty deep enzyme urine and odor extraction")
    scotchgard: bool = Field(default=False, description="Stain-resistant fiber protection application")
    deodorizer: bool = Field(default=True, description="Citrus/fresh deodorizing spray")

class LawnCareSpecs(BaseModel):
    lot_size_tier: str = Field(
        default="medium_half_acre", 
        description="small_quarter_acre (<0.25 acre), medium_half_acre (0.25-0.5 acre), large_one_acre (0.5-1.0 acre), estate_plus (>1.0 acre)"
    )
    cadence: str = Field(default="biweekly", description="weekly, biweekly, one_time")
    aeration_overseeding: bool = Field(default=False, description="Core aeration & premium overseed add-on")
    weed_fertilization: bool = Field(default=False, description="Custom 6-step turf feed and pre-emergent program")
    edge_trim: bool = Field(default=True, description="Precision sidewalk and driveway perimeter edging")

class RoofingSpecs(BaseModel):
    issue_type: str = Field(
        default="inspection", 
        description="inspection, active_leak, storm_damage, replacement, gutters"
    )
    roof_age_years: Optional[int] = Field(default=None, description="Approximate age of current roof in years")
    stories: int = Field(default=1, description="Number of stories (1, 2, 3)")
    pitch: str = Field(default="standard", description="standard, steep, flat")
    gutter_cleaning: bool = Field(default=False, description="Full gutter scoop, downspout flush, and debris haul")
    insurance_claim: bool = Field(default=False, description="Recent hail, wind, or fallen limb insurance claim filing")

class QuoteLineItem(BaseModel):
    title: str
    description: str
    unit_price: float
    quantity: float
    total: float

class ResidentialQuoteRequest(BaseModel):
    trade: TradeType = TradeType.CARPET_CLEANING
    carpet: Optional[CarpetCleaningSpecs] = None
    lawn: Optional[LawnCareSpecs] = None
    roofing: Optional[RoofingSpecs] = None
    zip_code: Optional[str] = None
    promo_code: Optional[str] = None

class ResidentialQuoteResponse(BaseModel):
    trade: str
    trade_title: str
    line_items: List[QuoteLineItem]
    subtotal: float
    discount_amount: float = 0.0
    discount_label: Optional[str] = None
    total_estimate: float
    is_range: bool = False
    range_low: Optional[float] = None
    range_high: Optional[float] = None
    emergency_flag: bool = False
    emergency_message: Optional[str] = None
    service_area_valid: bool = True
    minimum_callout_applied: bool = False
    notes: List[str] = []

class ChatMessage(BaseModel):
    role: str = Field(description="'user', 'assistant', or 'system'")
    content: str
    timestamp: Optional[str] = None

class HomeownerContactInfo(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    zip_code: Optional[str] = None

class ResidentialChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    trade: Optional[str] = "carpet_cleaning"
    history: List[ChatMessage] = []
    current_quote: Optional[ResidentialQuoteResponse] = None
    homeowner_info: Optional[Dict[str, Any]] = None

class ResidentialChatResponse(BaseModel):
    reply: str
    trade: str
    conversation_id: str
    current_quote: ResidentialQuoteResponse
    quick_replies: List[str]
    is_qualified: bool
    ready_to_book: bool
    homeowner_info: Dict[str, Any]
    emergency_flag: bool = False
    suggested_action: Optional[str] = None

class ResidentialBookingRequest(BaseModel):
    conversation_id: Optional[str] = None
    trade: str
    service_summary: str
    homeowner_name: str
    phone: str
    email: Optional[str] = None
    address: str
    zip_code: str
    scheduled_date: str  # YYYY-MM-DD
    time_window: str     # e.g., "morning_8_12", "afternoon_12_4", "evening_4_7"
    estimated_total: float
    special_instructions: Optional[str] = None

class ResidentialBookingConfirmation(BaseModel):
    booking_id: str
    appointment_id: str
    lead_id: str
    company_id: str
    trade: str
    homeowner_name: str
    address: str
    scheduled_at: str
    time_window: str
    status: str = "confirmed"
    estimated_total: float
    confirmation_number: str
    message: str
