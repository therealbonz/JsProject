from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, model_validator

class ApiKeyCreateRequest(BaseModel):
    key_name: Optional[str] = Field(None, description="Descriptive label, e.g., 'NetSuite Sync'")
    name: Optional[str] = Field(None, description="Alias for key_name")
    scopes: Optional[List[str]] = Field(default_factory=lambda: ["*"], description="Permissions list, e.g. ['sales:read']")
    expires_in_days: Optional[int] = Field(None, ge=1, le=365, description="Key validity in days. Null for non-expiring.")
    rate_limit_per_minute: Optional[int] = Field(60, ge=1, le=1000, description="Rate limit per minute")

    @model_validator(mode="before")
    @classmethod
    def reconcile_name(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("key_name") and data.get("name"):
                data["key_name"] = data["name"]
            elif not data.get("name") and data.get("key_name"):
                data["name"] = data["key_name"]
        return data

class ApiKeyCreatedResponse(BaseModel):
    id: str
    key_name: str
    name: Optional[str] = None
    key_prefix: str
    api_key: str = Field(..., description="Raw secret API key. Store this safely as it will not be shown again.")
    scopes: List[str]
    rate_limit_per_minute: int
    created_at: datetime
    expires_at: Optional[datetime] = None

    @model_validator(mode="before")
    @classmethod
    def populate_name_alias(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "key_name" in data and "name" not in data:
                data["name"] = data["key_name"]
        return data

class ApiKeyListItemResponse(BaseModel):
    id: str
    key_name: str
    name: Optional[str] = None
    key_prefix: str
    scopes: List[str]
    rate_limit_per_minute: int
    is_active: bool
    last_used_at: Optional[datetime] = None
    created_at: datetime
    expires_at: Optional[datetime] = None

    @model_validator(mode="before")
    @classmethod
    def populate_name_alias(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "key_name" in data and "name" not in data:
                data["name"] = data["key_name"]
        return data

class WebhookSubscriptionCreateRequest(BaseModel):
    target_url: Optional[str] = Field(None, description="Destination HTTPS URL")
    endpoint_url: Optional[str] = Field(None, description="Alias for target_url")
    description: Optional[str] = Field(None, description="Optional label for this subscription")
    events: List[str] = Field(default_factory=lambda: ["*"], description="Subscribed event types")
    secret_key: Optional[str] = Field(None, description="Optional custom signing secret")

    @model_validator(mode="before")
    @classmethod
    def reconcile_url(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("target_url") and data.get("endpoint_url"):
                data["target_url"] = data["endpoint_url"]
            elif not data.get("endpoint_url") and data.get("target_url"):
                data["endpoint_url"] = data["target_url"]
        return data

class WebhookSubscriptionUpdateRequest(BaseModel):
    target_url: Optional[str] = None
    endpoint_url: Optional[str] = None
    description: Optional[str] = None
    events: Optional[List[str]] = None
    is_active: Optional[bool] = None
    status: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def reconcile_update(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("target_url") and data.get("endpoint_url"):
                data["target_url"] = data["endpoint_url"]
            if data.get("status"):
                data["is_active"] = (data["status"] == "active")
        return data

class WebhookSubscriptionCreatedResponse(BaseModel):
    id: str
    target_url: str
    endpoint_url: Optional[str] = None
    description: Optional[str] = None
    events: List[str]
    secret_key: str = Field(..., description="HMAC-SHA256 signature secret")
    secret_prefix: Optional[str] = None
    is_active: bool
    status: Optional[str] = None
    created_at: datetime

    @model_validator(mode="before")
    @classmethod
    def populate_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "target_url" in data and "endpoint_url" not in data:
                data["endpoint_url"] = data["target_url"]
            if "is_active" in data and "status" not in data:
                data["status"] = "active" if data["is_active"] else "disabled"
            if "secret_key" in data and "secret_prefix" not in data:
                sec = data["secret_key"]
                data["secret_prefix"] = sec[:12] if sec else ""
        return data

class WebhookSubscriptionResponse(BaseModel):
    id: str
    target_url: str
    endpoint_url: Optional[str] = None
    description: Optional[str] = None
    events: List[str]
    secret_prefix: Optional[str] = None
    is_active: bool
    status: Optional[str] = None
    failure_count: int
    created_at: datetime

    @model_validator(mode="before")
    @classmethod
    def populate_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "target_url" in data and "endpoint_url" not in data:
                data["endpoint_url"] = data["target_url"]
            if "is_active" in data and "status" not in data:
                fc = data.get("failure_count", 0)
                if not data["is_active"]:
                    data["status"] = "disabled"
                elif fc >= 5:
                    data["status"] = "failing"
                else:
                    data["status"] = "active"
        return data

class WebhookDeliveryLogResponse(BaseModel):
    id: str
    delivery_uuid: str
    request_id: Optional[str] = None
    event_type: str
    status: str
    success: Optional[bool] = None
    response_status_code: Optional[int] = None
    duration_ms: int
    delivered_at: datetime
    response_body_snippet: Optional[str] = None
    error_message: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def populate_log_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "delivery_uuid" in data and "request_id" not in data:
                data["request_id"] = data["delivery_uuid"]
            if "status" in data and "success" not in data:
                data["success"] = (data["status"] == "delivered")
        return data

class WebhookPingResponse(BaseModel):
    subscription_id: str
    target_url: str
    endpoint_url: Optional[str] = None
    event: str
    status: str
    response_status_code: Optional[int] = None
    duration_ms: int
    delivery_id: str
    success: bool = True
    delivery: Optional[Dict[str, Any]] = None

    @model_validator(mode="before")
    @classmethod
    def populate_ping_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "target_url" in data and "endpoint_url" not in data:
                data["endpoint_url"] = data["target_url"]
        return data

class EventCatalogItemResponse(BaseModel):
    event_type: str
    event_name: Optional[str] = None
    description: str
    example_payload: Dict[str, Any]
    sample_payload: Optional[Dict[str, Any]] = None

    @model_validator(mode="before")
    @classmethod
    def populate_catalog_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "event_type" in data and "event_name" not in data:
                data["event_name"] = data["event_type"]
            elif "event_name" in data and "event_type" not in data:
                data["event_type"] = data["event_name"]
            if "example_payload" in data and "sample_payload" not in data:
                data["sample_payload"] = data["example_payload"]
            elif "sample_payload" in data and "example_payload" not in data:
                data["example_payload"] = data["sample_payload"]
        return data
