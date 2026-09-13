from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

class WorkflowNode(BaseModel):
    id: str
    type: str  # trigger, condition, action, ai_agent, notification, webhook, hitl_approval
    label: str
    position: Dict[str, float] = Field(default_factory=lambda: {"x": 100.0, "y": 100.0})
    config: Dict[str, Any] = Field(default_factory=dict)

class WorkflowEdge(BaseModel):
    id: str
    source: str
    target: str
    label: Optional[str] = None

class WorkflowCanvasData(BaseModel):
    nodes: List[WorkflowNode] = Field(default_factory=list)
    edges: List[WorkflowEdge] = Field(default_factory=list)
    zoom: float = 1.0

class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    trigger_type: str = Field(..., description="lead_created, order_placed, payment_received, support_escalated, stockout_risk_high, manual_trigger")
    trigger_config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    status: Optional[str] = "active"
    is_active: Optional[bool] = True
    canvas_data: Optional[Dict[str, Any]] = Field(default_factory=dict)
    steps: Optional[List[Dict[str, Any]]] = Field(default_factory=list)

class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_config: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None
    canvas_data: Optional[Dict[str, Any]] = None
    steps: Optional[List[Dict[str, Any]]] = None

class WorkflowSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    name: str
    description: Optional[str] = None
    trigger_type: str
    status: str
    is_active: bool
    version: int
    node_count: int = 0
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    success_rate_pct: float = 100.0
    last_run_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

class WorkflowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    name: str
    description: Optional[str] = None
    trigger_type: str
    trigger_config: Dict[str, Any] = Field(default_factory=dict)
    status: str
    is_active: bool
    version: int
    canvas_data: Dict[str, Any] = Field(default_factory=dict)
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    success_rate_pct: float = 100.0
    last_run_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class WorkflowStepLog(BaseModel):
    step_id: str
    node_type: str
    label: str
    status: str  # success, skipped, failed
    duration_ms: float = 0.0
    input: Optional[Dict[str, Any]] = None
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class WorkflowTestRunRequest(BaseModel):
    trigger_payload: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Sample event payload for test simulation")

class WorkflowTestRunResponse(BaseModel):
    workflow_id: str
    status: str  # completed, failed
    execution_time_ms: float
    steps_executed: int
    step_logs: List[WorkflowStepLog]
    error_message: Optional[str] = None

class WorkflowExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workflow_id: str
    workflow_name: Optional[str] = None
    trigger_event_type: str
    status: str
    execution_time_ms: float = 0.0
    started_at: datetime
    completed_at: Optional[datetime] = None
    step_count: int = 0
    error_message: Optional[str] = None

class WorkflowExecutionDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workflow_id: str
    workflow_name: Optional[str] = None
    trigger_event_type: str
    trigger_payload: Dict[str, Any] = Field(default_factory=dict)
    status: str
    execution_time_ms: float = 0.0
    started_at: datetime
    completed_at: Optional[datetime] = None
    step_logs: List[Dict[str, Any]] = Field(default_factory=list)
    error_message: Optional[str] = None

class WorkflowTemplateResponse(BaseModel):
    id: str
    name: str
    category: str
    description: str
    trigger_type: str
    icon: str
    canvas_data: Dict[str, Any]
    steps: List[Dict[str, Any]]
