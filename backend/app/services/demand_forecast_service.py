import math
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.models.tenant import Organization
from app.models.crm import ClientAccount, ClientSale, DemandForecastLog
from app.services.gemini_service import GeminiService

logger = logging.getLogger(__name__)

class DemandForecastService:
    """
    AI-Driven Demand Forecasting & Dynamic Safety Stock Optimization Engine.
    Combines consumption run-rate statistical analytics (Reorder Point & Dynamic Safety Buffer)
    with Google Gemini GenAI intelligence to predict stockouts and recommend optimal replenishment.
    """

    @staticmethod
    def _calculate_statistical_metrics(
        client: ClientAccount,
        sales: List[ClientSale],
        lead_time_days: int = 7,
        service_level_z: float = 1.65  # 95% service level
    ) -> Dict[str, Any]:
        """
        Executes consumption run-rate modeling, standard deviations, and ROP safety stock formulas.
        """
        now = datetime.now(timezone.utc)
        completed_sales = [s for s in sales if s.status not in ("cancelled", "replenishment_pending")]

        if len(completed_sales) >= 2:
            # Multi-order history: analyze intervals and spend velocity
            intervals = []
            amounts = [s.amount for s in completed_sales]
            for i in range(len(completed_sales) - 1):
                d1 = completed_sales[i].sale_date
                d2 = completed_sales[i + 1].sale_date
                if d1.tzinfo is None:
                    d1 = d1.replace(tzinfo=timezone.utc)
                if d2.tzinfo is None:
                    d2 = d2.replace(tzinfo=timezone.utc)
                diff = abs((d1.date() - d2.date()).days)
                intervals.append(max(diff, 1))

            avg_interval = sum(intervals) / len(intervals)
            avg_amount = sum(amounts) / len(amounts)

            # Standard deviations
            variance_amt = sum((a - avg_amount) ** 2 for a in amounts) / len(amounts)
            std_dev_demand = math.sqrt(variance_amt)
            std_dev_lead_time = 2.0  # 2 days variance in supplier dropship
            burn_rate = round(avg_amount / max(avg_interval, 1.0), 2)
            last_sale_date = completed_sales[0].sale_date
        elif len(completed_sales) == 1:
            # Single baseline sale
            s = completed_sales[0]
            avg_interval = float(client.reorder_cadence_days or 30)
            avg_amount = float(s.amount)
            std_dev_demand = avg_amount * 0.20
            std_dev_lead_time = 2.0
            burn_rate = round(avg_amount / max(avg_interval, 1.0), 2)
            last_sale_date = s.sale_date
        else:
            # New account defaults
            avg_interval = float(client.reorder_cadence_days or 30)
            avg_amount = 850.0
            std_dev_demand = avg_amount * 0.25
            std_dev_lead_time = 2.0
            burn_rate = round(avg_amount / max(avg_interval, 1.0), 2)
            last_sale_date = client.contract_start_date or (now - timedelta(days=int(avg_interval * 0.7)))

        if last_sale_date and last_sale_date.tzinfo is None:
            last_sale_date = last_sale_date.replace(tzinfo=timezone.utc)

        elapsed_days = (now.date() - last_sale_date.date()).days if last_sale_date else 15
        days_until_stockout = max(int(avg_interval - elapsed_days), 0)

        # Dynamic Safety Stock Formula: SS = Z * sqrt(L * sigma_D^2 + D^2 * sigma_L^2)
        # We model daily demand variance in $ terms
        daily_demand = burn_rate
        daily_demand_sigma = std_dev_demand / max(avg_interval, 1.0)
        ss_term = (lead_time_days * (daily_demand_sigma ** 2)) + ((daily_demand ** 2) * (std_dev_lead_time ** 2))
        safety_stock_dollar = service_level_z * math.sqrt(max(ss_term, 1.0))
        
        # Buffer % between 10% and 35%
        raw_buffer_pct = (safety_stock_dollar / max(avg_amount, 1.0)) * 100.0
        buffer_percent = round(min(max(raw_buffer_pct, 10.0), 35.0), 1)

        # Recommended restock amount includes safety buffer
        recommended_amount = round(avg_amount * (1.0 + (buffer_percent / 100.0)), 2)
        recommended_cadence_days = max(min(int(round(avg_interval)), 90), 7)

        # Stockout Risk Scoring (0 - 100)
        if days_until_stockout <= 0:
            risk_score = 95
            risk_level = "critical"
        elif days_until_stockout <= lead_time_days:
            risk_score = 80
            risk_level = "high"
        elif days_until_stockout <= lead_time_days + 7:
            risk_score = 50
            risk_level = "moderate"
        else:
            risk_score = 15
            risk_level = "low"

        # Recommended restock date considers lead time buffer
        target_reorder_offset = max(days_until_stockout - lead_time_days, 0)
        recommended_reorder_date = now + timedelta(days=target_reorder_offset)

        return {
            "burn_rate": burn_rate,
            "avg_interval": avg_interval,
            "avg_amount": avg_amount,
            "elapsed_days": elapsed_days,
            "days_until_stockout": days_until_stockout,
            "safety_stock_dollar": round(safety_stock_dollar, 2),
            "safety_stock_buffer_percent": buffer_percent,
            "recommended_amount": recommended_amount,
            "recommended_cadence_days": recommended_cadence_days,
            "stockout_risk_score": risk_score,
            "stockout_risk_level": risk_level,
            "recommended_reorder_date": recommended_reorder_date,
            "lead_time_days": lead_time_days
        }

    @staticmethod
    async def generate_forecast_for_client(
        db: AsyncSession,
        org_id: str,
        client_id: str
    ) -> Dict[str, Any]:
        """
        Performs AI demand forecasting for a client account, integrates Gemini reasoning,
        persists metrics, records a historical forecast log, and returns the forecast dossier.
        """
        stmt = (
            select(ClientAccount)
            .options(
                selectinload(ClientAccount.primary_contact),
                selectinload(ClientAccount.company),
                selectinload(ClientAccount.sales)
            )
            .where(
                ClientAccount.id == client_id,
                ClientAccount.organization_id == org_id
            )
        )
        result = await db.execute(stmt)
        client = result.scalar_one_or_none()
        if not client:
            raise ValueError(f"Client account {client_id} not found")

        sales = client.sales or []
        stat_metrics = DemandForecastService._calculate_statistical_metrics(
            client=client,
            sales=sales
        )

        now = datetime.now(timezone.utc)
        gemini = GeminiService()
        confidence = 0.90 if len(sales) >= 2 else (0.82 if len(sales) == 1 else 0.75)
        model_used = "gemini-2.5-flash" if gemini.is_live() else "statistical-rop-engine"

        # AI Synthesis Rationale
        industry_name = client.company.industry if (client.company and client.company.industry) else "Commercial Enterprise"
        rationale = ""
        if gemini.is_live():
            try:
                system_prompt = (
                    "You are an expert Autonomous Supply Chain & Inventory Demand Intelligence AI. "
                    "Analyze the client's consumption telemetry and provide a concise, professional "
                    "2-sentence executive rationale explaining demand velocity, safety buffer recommendation, "
                    "and restocking urgency."
                )
                user_prompt = (
                    f"Client Account: {client.account_name}\n"
                    f"Industry: {industry_name}\n"
                    f"Daily Burn Rate: ${stat_metrics['burn_rate']}/day\n"
                    f"Configured Cadence: {client.reorder_cadence_days} days\n"
                    f"Calculated Consumption Cycle: {stat_metrics['avg_interval']} days\n"
                    f"Days Until Stockout: {stat_metrics['days_until_stockout']} days\n"
                    f"Stockout Risk: {stat_metrics['stockout_risk_level'].upper()} ({stat_metrics['stockout_risk_score']}/100)\n"
                    f"Safety Stock Buffer: {stat_metrics['safety_stock_buffer_percent']}%\n"
                    f"Recommended Order Amount: ${stat_metrics['recommended_amount']}\n"
                )
                ai_text = await gemini._call_gemini(system_instruction=system_prompt, prompt=user_prompt)
                if ai_text and len(ai_text.strip()) > 10:
                    rationale = ai_text.strip()
            except Exception as e:
                logger.warning(f"Gemini live call failed in demand forecast: {e}. Falling back to simulation.")

        if not rationale:
            # Deterministic simulation rationale
            if stat_metrics["stockout_risk_level"] in ("critical", "high"):
                rationale = (
                    f"Consumption run-rate (${stat_metrics['burn_rate']}/day in {industry_name}) indicates depleted buffer "
                    f"with only {stat_metrics['days_until_stockout']} days remaining. An immediate replenishment order with a "
                    f"{stat_metrics['safety_stock_buffer_percent']}% safety buffer (${stat_metrics['recommended_amount']}) is "
                    f"recommended to prevent operational downtime."
                )
            elif stat_metrics["stockout_risk_level"] == "moderate":
                rationale = (
                    f"Demand velocity is stable at ${stat_metrics['burn_rate']}/day. Reorder is approaching in "
                    f"{stat_metrics['days_until_stockout']} days; dynamic safety stock of {stat_metrics['safety_stock_buffer_percent']}% "
                    f"protects against supplier fulfillment lead time variability."
                )
            else:
                rationale = (
                    f"Inventory reserves are well-balanced for {client.account_name} at an average consumption of "
                    f"${stat_metrics['burn_rate']}/day. Scheduled cadence aligns with current order patterns."
                )

        # Update ClientAccount entity
        client.predicted_burn_rate = stat_metrics["burn_rate"]
        client.safety_stock_buffer_percent = stat_metrics["safety_stock_buffer_percent"]
        client.stockout_risk_score = stat_metrics["stockout_risk_score"]
        client.stockout_risk_level = stat_metrics["stockout_risk_level"]
        client.recommended_reorder_date = stat_metrics["recommended_reorder_date"]
        client.forecast_confidence = confidence
        client.forecast_rationale = rationale
        client.forecast_updated_at = now

        # Prepare serializable telemetry for DB JSON column and API response
        serializable_telemetry = dict(stat_metrics)
        if isinstance(serializable_telemetry.get("recommended_reorder_date"), datetime):
            serializable_telemetry["recommended_reorder_date"] = serializable_telemetry["recommended_reorder_date"].isoformat()

        # Create DemandForecastLog entry
        rec_items = f"[AI Optimized Restock] Suggested inventory replenishment based on ${stat_metrics['burn_rate']}/day run-rate ({stat_metrics['safety_stock_buffer_percent']}% buffer)"
        log = DemandForecastLog(
            organization_id=org_id,
            client_id=client.id,
            forecast_date=now,
            predicted_burn_rate=stat_metrics["burn_rate"],
            recommended_reorder_date=stat_metrics["recommended_reorder_date"],
            recommended_amount=stat_metrics["recommended_amount"],
            recommended_items=rec_items,
            stockout_risk_score=stat_metrics["stockout_risk_score"],
            stockout_risk_level=stat_metrics["stockout_risk_level"],
            safety_stock_buffer_percent=stat_metrics["safety_stock_buffer_percent"],
            confidence_score=confidence,
            model_used=model_used,
            rationale=rationale,
            telemetry_json=serializable_telemetry
        )
        db.add(log)
        await db.commit()
        await db.refresh(client)

        return {
            "client_id": client.id,
            "account_name": client.account_name,
            "predicted_burn_rate": client.predicted_burn_rate,
            "reorder_cadence_days": client.reorder_cadence_days,
            "recommended_cadence_days": stat_metrics["recommended_cadence_days"],
            "next_reorder_date": client.next_reorder_date,
            "recommended_reorder_date": client.recommended_reorder_date,
            "days_until_stockout": stat_metrics["days_until_stockout"],
            "stockout_risk_score": client.stockout_risk_score,
            "stockout_risk_level": client.stockout_risk_level,
            "safety_stock_buffer_percent": client.safety_stock_buffer_percent,
            "recommended_restock_amount": stat_metrics["recommended_amount"],
            "forecast_confidence": client.forecast_confidence,
            "forecast_rationale": client.forecast_rationale,
            "model_used": model_used,
            "telemetry": serializable_telemetry,
            "last_updated": client.forecast_updated_at
        }

    @staticmethod
    async def apply_forecast_to_cadence(
        db: AsyncSession,
        org_id: str,
        client_id: str,
        apply_cadence_days: bool = True,
        apply_reorder_date: bool = True
    ) -> Dict[str, Any]:
        """
        Adopts the AI-recommended restock date and cadence on the client account.
        """
        stmt = select(ClientAccount).where(
            ClientAccount.id == client_id,
            ClientAccount.organization_id == org_id
        )
        res = await db.execute(stmt)
        client = res.scalar_one_or_none()
        if not client:
            raise ValueError(f"Client account {client_id} not found")

        # If forecast has never been run or is stale, run it first
        if not client.recommended_reorder_date:
            await DemandForecastService.generate_forecast_for_client(db=db, org_id=org_id, client_id=client_id)
            await db.refresh(client)

        now = datetime.now(timezone.utc)
        if apply_reorder_date and client.recommended_reorder_date:
            rec_date = client.recommended_reorder_date
            if rec_date.tzinfo is None:
                rec_date = rec_date.replace(tzinfo=timezone.utc)
            # Ensure not set in past
            client.next_reorder_date = max(rec_date, now)

        if apply_cadence_days and client.predicted_burn_rate > 0:
            # Estimate cadence from burn rate and average amount
            if client.order_count > 0:
                avg_amt = client.total_revenue / client.order_count
                new_cadence = max(min(int(round(avg_amt / client.predicted_burn_rate)), 90), 7)
                client.reorder_cadence_days = new_cadence

        await db.commit()
        await db.refresh(client)

        return {
            "success": True,
            "client_id": client.id,
            "account_name": client.account_name,
            "reorder_cadence_days": client.reorder_cadence_days,
            "next_reorder_date": client.next_reorder_date.isoformat() if client.next_reorder_date else None,
            "applied_forecast_rationale": client.forecast_rationale
        }

    @staticmethod
    async def get_overview_stats(
        db: AsyncSession,
        org_id: str
    ) -> Dict[str, Any]:
        """
        Aggregates tenant-wide demand forecasting and stockout risk metrics.
        """
        stmt = select(ClientAccount).where(
            ClientAccount.organization_id == org_id,
            ClientAccount.status == "active"
        )
        res = await db.execute(stmt)
        clients = res.scalars().all()

        monitored = len(clients)
        high_risk = 0
        mod_risk = 0
        safe = 0
        total_burn = 0.0
        projected_30d = 0.0
        conf_sum = 0.0

        for c in clients:
            score = c.stockout_risk_score or 0
            if score >= 70:
                high_risk += 1
            elif score >= 35:
                mod_risk += 1
            else:
                safe += 1

            burn = c.predicted_burn_rate or 0.0
            total_burn += burn
            projected_30d += burn * 30.0
            conf_sum += c.forecast_confidence or 0.85

        avg_burn = round(total_burn / max(monitored, 1), 2)
        avg_conf = round(conf_sum / max(monitored, 1), 2)

        return {
            "monitored_accounts": monitored,
            "high_risk_accounts": high_risk,
            "moderate_risk_accounts": mod_risk,
            "safe_accounts": safe,
            "average_burn_rate": avg_burn,
            "projected_30d_demand": round(projected_30d, 2),
            "average_forecast_confidence": avg_conf
        }
