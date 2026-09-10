import csv
import io
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.models.hitl import AuditLog
from app.models.tenant import User

logger = logging.getLogger(__name__)

class AuditService:
    """
    Centralized, immutable enterprise audit trail service.
    Tracks all user, autonomous agent, webhook, and billing activities.
    """

    @staticmethod
    async def log_event(
        db: AsyncSession,
        org_id: str,
        action: str,
        actor_type: str = "user",
        actor_id: Optional[str] = None,
        actor_email: Optional[str] = None,
        actor_role: Optional[str] = None,
        target_entity: Optional[str] = None,
        target_id: Optional[str] = None,
        status: str = "success",
        ip_address: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        auto_commit: bool = False
    ) -> AuditLog:
        """Create and persist an immutable audit trail entry."""
        entry = AuditLog(
            organization_id=org_id,
            actor_type=actor_type,
            actor_id=actor_id,
            actor_email=actor_email,
            actor_role=actor_role,
            action=action,
            target_entity=target_entity,
            target_id=target_id,
            status=status,
            ip_address=ip_address or "127.0.0.1",
            payload=payload or {}
        )
        db.add(entry)
        if auto_commit:
            await db.commit()
            await db.refresh(entry)
        else:
            await db.flush()
        return entry

    @staticmethod
    async def query_logs(
        db: AsyncSession,
        org_id: str,
        action_prefix: Optional[str] = None,
        actor_type: Optional[str] = None,
        actor_email: Optional[str] = None,
        actor_role: Optional[str] = None,
        target_entity: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditLog]:
        """Query audit trail records with multi-dimensional filtering."""
        stmt = select(AuditLog).where(AuditLog.organization_id == org_id)

        if action_prefix:
            stmt = stmt.where(AuditLog.action.like(f"{action_prefix}%"))
        if actor_type:
            stmt = stmt.where(AuditLog.actor_type == actor_type)
        if actor_email:
            stmt = stmt.where(AuditLog.actor_email.ilike(f"%{actor_email}%"))
        if actor_role:
            stmt = stmt.where(AuditLog.actor_role == actor_role)
        if target_entity:
            stmt = stmt.where(AuditLog.target_entity == target_entity)
        if status:
            stmt = stmt.where(AuditLog.status == status)

        stmt = stmt.order_by(desc(AuditLog.created_at)).offset(offset).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_overview_metrics(db: AsyncSession, org_id: str) -> Dict[str, Any]:
        """Compute summary statistics for audit security dashboard."""
        stmt = select(AuditLog).where(AuditLog.organization_id == org_id).order_by(desc(AuditLog.created_at)).limit(50)
        res = await db.execute(stmt)
        recent_logs = list(res.scalars().all())

        # Count total
        total_stmt = select(func.count(AuditLog.id)).where(AuditLog.organization_id == org_id)
        total_count = (await db.execute(total_stmt)).scalar() or 0

        # Actions breakdown
        actions_map: Dict[str, int] = {}
        actors_map: Dict[str, int] = {}
        for log in recent_logs:
            category = log.action.split(".")[0] if "." in log.action else log.action
            actions_map[category] = actions_map.get(category, 0) + 1
            actors_map[log.actor_type] = actors_map.get(log.actor_type, 0) + 1

        return {
            "total_events": total_count,
            "today_events": len(recent_logs),
            "actions_breakdown": actions_map,
            "actors_breakdown": actors_map,
            "recent_logs": recent_logs
        }

    @staticmethod
    def export_to_csv(logs: List[AuditLog]) -> str:
        """Export audit logs to RFC 4180 CSV string for compliance reporting."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Timestamp (UTC)", "Actor Type", "Actor Email", "Actor Role",
            "Action", "Target Entity", "Target ID", "Status", "IP Address", "Details JSON"
        ])
        for log in logs:
            writer.writerow([
                log.created_at.isoformat() if log.created_at else "",
                log.actor_type or "",
                log.actor_email or "",
                log.actor_role or "",
                log.action or "",
                log.target_entity or "",
                log.target_id or "",
                log.status or "success",
                log.ip_address or "",
                json.dumps(log.payload) if log.payload else "{}"
            ])
        return output.getvalue()

audit_service = AuditService()
