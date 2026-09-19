import os
import re
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.gemini_service import gemini_service
from app.models.tenant import User, Organization
from app.api.deps import get_current_tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings/ai", tags=["AI Engine Configuration"])

class AISettingsResponse(BaseModel):
    is_live: bool
    model: str
    available_models: List[str]
    has_api_key: bool
    masked_api_key: Optional[str] = None
    mode: str

class AISettingsUpdateRequest(BaseModel):
    api_key: Optional[str] = Field(None, description="Google Gemini API key")
    model: Optional[str] = Field("gemini-2.5-flash", description="Gemini model identifier")
    test_before_save: bool = Field(True, description="Whether to verify connection before saving")

class AITestRequest(BaseModel):
    api_key: Optional[str] = Field(None, description="Optional API key to test. If omitted, uses current key.")
    model: Optional[str] = Field("gemini-2.5-flash", description="Gemini model identifier")

class AITestResponse(BaseModel):
    success: bool
    model: str
    is_live: bool
    latency_ms: float
    response: Optional[str] = None
    error: Optional[str] = None

def _mask_key(key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    cleaned = key.strip()
    if len(cleaned) <= 8:
        return "••••••••"
    return f"{cleaned[:6]}••••••••{cleaned[-4:]}"

def _persist_gemini_to_env(api_key: str, model: str):
    """Safely updates or appends GEMINI_API_KEY and GEMINI_MODEL in backend/.env."""
    env_paths = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        "/home/bonz/JsProject/backend/.env"
    ]
    
    target_env = None
    for p in env_paths:
        if os.path.exists(p):
            target_env = p
            break
            
    if not target_env:
        target_env = env_paths[1]

    try:
        content = ""
        if os.path.exists(target_env):
            with open(target_env, "r", encoding="utf-8") as f:
                content = f.read()

        # Replace or append GEMINI_API_KEY
        if re.search(r"^GEMINI_API_KEY=.*", content, flags=re.MULTILINE):
            content = re.sub(r"^GEMINI_API_KEY=.*", f'GEMINI_API_KEY="{api_key}"', content, flags=re.MULTILINE)
        else:
            content += f'\nGEMINI_API_KEY="{api_key}"'

        # Replace or append GEMINI_MODEL
        if re.search(r"^GEMINI_MODEL=.*", content, flags=re.MULTILINE):
            content = re.sub(r"^GEMINI_MODEL=.*", f'GEMINI_MODEL="{model}"', content, flags=re.MULTILINE)
        else:
            content += f'\nGEMINI_MODEL="{model}"'

        with open(target_env, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n")
            
        logger.info(f"Persisted Gemini configuration to {target_env}")
    except Exception as e:
        logger.error(f"Failed to persist Gemini settings to .env file: {e}")

@router.get("", response_model=AISettingsResponse)
async def get_ai_settings(
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant)
):
    """Returns the current Gemini AI configuration and operational status."""
    has_key = bool(gemini_service.api_key and gemini_service.api_key.strip())
    return AISettingsResponse(
        is_live=gemini_service.is_live(),
        model=gemini_service.model,
        available_models=["gemini-2.5-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
        has_api_key=has_key,
        masked_api_key=_mask_key(gemini_service.api_key) if has_key else None,
        mode="Live Google GenAI Client" if gemini_service.is_live() else "Local-First Simulation & Guardrail Engine"
    )

@router.post("/test", response_model=AITestResponse)
async def test_ai_connection(
    payload: AITestRequest,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant)
):
    """Tests connectivity to Google Gemini and measures response latency."""
    res = await gemini_service.test_connection(api_key=payload.api_key, model=payload.model)
    return AITestResponse(
        success=res.get("success", False),
        model=payload.model or gemini_service.model,
        is_live=res.get("is_live", False),
        latency_ms=res.get("latency_ms", 0.0),
        response=res.get("response"),
        error=res.get("error")
    )

@router.post("", response_model=AISettingsResponse)
async def update_ai_settings(
    payload: AISettingsUpdateRequest,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant)
):
    """
    Updates the Google Gemini API key and model.
    Optionally tests the key first, then reloads the client in memory and writes to .env.
    """
    user, org, role = tenant_context
    if role not in ["super_admin", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization administrators can update AI engine credentials."
        )

    target_key = payload.api_key.strip() if payload.api_key is not None else gemini_service.api_key
    target_model = payload.model.strip() if payload.model else "gemini-2.5-flash"

    if payload.test_before_save and target_key:
        test_res = await gemini_service.test_connection(api_key=target_key, model=target_model)
        if not test_res.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Google Gemini connection test failed: {test_res.get('error')}"
            )

    # Reconfigure in-memory engine
    gemini_service.configure(api_key=target_key, model=target_model)
    settings.GEMINI_API_KEY = target_key
    settings.GEMINI_MODEL = target_model

    # Persist to disk
    _persist_gemini_to_env(target_key, target_model)

    has_key = bool(target_key)
    return AISettingsResponse(
        is_live=gemini_service.is_live(),
        model=gemini_service.model,
        available_models=["gemini-2.5-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
        has_api_key=has_key,
        masked_api_key=_mask_key(target_key) if has_key else None,
        mode="Live Google GenAI Client" if gemini_service.is_live() else "Local-First Simulation & Guardrail Engine"
    )
