from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

class ProspectParsedRow(BaseModel):
    row_index: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    clean_phone: Optional[str] = None
    email: Optional[str] = None
    company_name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    trade_service: Optional[str] = None
    notes: Optional[str] = None
    custom_fields: Dict[str, Any] = Field(default_factory=dict)
    is_valid: bool = True
    validation_error: Optional[str] = None
    is_duplicate: bool = False

class ProspectImportPreview(BaseModel):
    total_rows_detected: int
    detected_columns: Dict[str, str]
    sample_rows: List[ProspectParsedRow]
    valid_count: int
    invalid_count: int
    duplicate_count: int

class ProspectImportResponse(BaseModel):
    success: bool
    campaign_id: str
    campaign_name: str
    trade_service: str
    total_processed: int
    leads_created: int
    duplicates_skipped: int
    errors_count: int
    status: str
    message: str

class ProspectCampaignLeadItem(BaseModel):
    id: str
    homeowner_name: str
    phone: Optional[str]
    email: Optional[str]
    address: Optional[str]
    pipeline_stage: str
    lead_score: int
    created_at: Optional[str]

class ProspectCampaignResponse(BaseModel):
    id: str
    name: str
    trade_service: str
    status: str
    total_rows: int
    valid_count: int
    duplicate_count: int
    error_count: int
    dialed_count: int
    connected_count: int
    booked_count: int
    source_filename: Optional[str] = None
    created_at: Optional[str] = None
    leads_count: Optional[int] = None
