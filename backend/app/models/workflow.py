import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import CommonMixin, TenantMixin, get_utc_now

class Workflow(Base, CommonMixin, TenantMixin):
    __tablename__ = "workflows"

    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    trigger_type = Column(String(100), nullable=False, index=True)  # lead_created, order_placed, payment_received, support_escalated, stockout_risk_high, license_renewal_approaching, manual_trigger
    trigger_config = Column(JSON, default=dict, nullable=False)
    status = Column(String(50), default="active", nullable=False, index=True)  # draft, active, paused, archived
    is_active = Column(Boolean, default=True, nullable=False)
    version = Column(Integer, default=1, nullable=False)

    # Visual Drag-and-Drop Canvas Data (node positions, connectors, zoom/pan)
    canvas_data = Column(JSON, default=dict, nullable=False)

    # Executable DAG or sequential steps list
    steps = Column(JSON, default=list, nullable=False)

    # Execution Statistics
    total_runs = Column(Integer, default=0, nullable=False)
    successful_runs = Column(Integer, default=0, nullable=False)
    failed_runs = Column(Integer, default=0, nullable=False)
    last_run_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="workflows")
    runs = relationship("WorkflowExecution", back_populates="workflow", cascade="all, delete-orphan", order_by="desc(WorkflowExecution.started_at)")


class WorkflowExecution(Base, CommonMixin, TenantMixin):
    __tablename__ = "workflow_executions"

    workflow_id = Column(String(36), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    trigger_event_type = Column(String(100), nullable=False, index=True)
    trigger_payload = Column(JSON, default=dict, nullable=False)
    status = Column(String(50), default="running", nullable=False, index=True)  # running, completed, failed, cancelled

    started_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    execution_time_ms = Column(Float, default=0.0, nullable=False)
    error_message = Column(Text, nullable=True)

    # Detailed chronological telemetry of every node/step evaluated
    step_logs = Column(JSON, default=list, nullable=False)

    # Relationships
    workflow = relationship("Workflow", back_populates="runs")
    organization = relationship("Organization")
