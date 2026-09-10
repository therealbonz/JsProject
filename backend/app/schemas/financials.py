from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ExecutiveOverviewResponse(BaseModel):
    mrr: float = Field(..., description="Active Monthly Recurring Revenue from SaaS licenses and replenishment run-rate")
    arr: float = Field(..., description="Annualized Recurring Revenue (MRR * 12)")
    total_collected_revenue: float = Field(..., description="Total actual paid revenue from clients")
    total_unpaid_invoiced: float = Field(..., description="Total outstanding/unpaid B2B client balances")
    total_supplier_cogs: float = Field(..., description="Total Cost of Goods Sold from supplier POs")
    gross_profit: float = Field(..., description="Gross profit = collected revenue minus supplier COGS")
    gross_margin_pct: float = Field(..., description="Gross profit margin percentage")
    total_commissions_earned: float = Field(..., description="Total sales commission liabilities across reps")
    net_settlement_margin: float = Field(..., description="Net settlement after COGS and rep commissions")
    net_margin_pct: float = Field(..., description="Net margin percentage")
    active_client_accounts: int = Field(..., description="Total active client account count")
    arpu: float = Field(..., description="Average monthly revenue per client account")
    at_risk_arr: float = Field(..., description="Annualized revenue associated with churning or high-risk accounts")
    nrr_pct: float = Field(..., description="Estimated Net Revenue Retention percentage")
    top_supplier_expenses: List[Dict[str, Any]] = Field(default_factory=list, description="Top supplier disbursements breakdown")
    currency: str = Field("USD", description="Base reporting currency")

class ReconciliationLineItem(BaseModel):
    date: str
    transaction_type: str  # client_sale_paid, client_sale_invoiced, supplier_po_cost, rep_commission
    reference_id: str
    client_or_vendor: str
    revenue: float = 0.0
    cogs: float = 0.0
    commission: float = 0.0
    net_amount: float = 0.0
    payment_method: str = "credit_terms_30"
    status: str = "settled"

class FinancialReconciliationResponse(BaseModel):
    period_start: str
    period_end: str
    total_revenue: float
    total_cogs: float
    total_commissions: float
    net_settlement: float
    unsettled_discrepancies_count: int
    line_items: List[ReconciliationLineItem]

class RepCommissionSummary(BaseModel):
    user_id: str
    full_name: str
    email: str
    role: str
    commission_rate_pct: float
    deals_count: int
    sales_volume: float
    commission_earned: float
    unpaid_pipeline_volume: float

class RepCommissionLeaderboardResponse(BaseModel):
    reps: List[RepCommissionSummary]
    total_commissions_payable: float
    total_sales_volume: float

class RepCommissionRateUpdateRequest(BaseModel):
    commission_rate_pct: float = Field(..., ge=0.0, le=100.0, description="Commission percentage (0 to 100)")
