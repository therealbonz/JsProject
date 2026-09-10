import html as html_lib
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from app.core.config import settings
from app.core.database import engine, Base
from app.api.v1 import auth, crm, agent, hitl, conversations, fulfillment, payments, public_tracking, replenishments, organization_settings, documents, customer_portal
from app.services.gemini_service import gemini_service

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        def migrate_sqlite_columns(sync_conn):
            from sqlalchemy import inspect, text
            inspector = inspect(sync_conn)
            tables = inspector.get_table_names()
            if "organizations" in tables:
                cols = [c["name"] for c in inspector.get_columns("organizations")]
                org_cols = [
                    ("brand_name", "VARCHAR(255)"),
                    ("brand_logo_url", "VARCHAR(500)"),
                    ("brand_accent_color", "VARCHAR(50) DEFAULT '#4f46e5'"),
                    ("support_email", "VARCHAR(255)"),
                    ("support_phone", "VARCHAR(100)"),
                    ("custom_footer_text", "VARCHAR(500)"),
                    ("tracking_portal_notice", "TEXT"),
                    ("stripe_publishable_key", "VARCHAR(255)"),
                    ("stripe_secret_key", "VARCHAR(255)"),
                    ("stripe_webhook_secret", "VARCHAR(255)"),
                    ("twilio_account_sid", "VARCHAR(100)"),
                    ("twilio_auth_token", "VARCHAR(100)"),
                    ("twilio_from_number", "VARCHAR(50)"),
                    ("sendgrid_api_key", "VARCHAR(100)"),
                    ("email_from_address", "VARCHAR(255)"),
                    ("email_from_name", "VARCHAR(255)")
                ]
                for col_name, col_type in org_cols:
                    if col_name not in cols:
                        sync_conn.execute(text(f"ALTER TABLE organizations ADD COLUMN {col_name} {col_type}"))
            if "leads" in tables:
                cols = [c["name"] for c in inspector.get_columns("leads")]
                new_cols = [
                    ("notes", "TEXT"),
                    ("last_call_at", "DATETIME"),
                    ("last_call_notes", "TEXT"),
                    ("last_call_outcome", "VARCHAR(100)")
                ]
                for col_name, col_type in new_cols:
                    if col_name not in cols:
                        sync_conn.execute(text(f"ALTER TABLE leads ADD COLUMN {col_name} {col_type}"))
            if "companies" in tables:
                cols = [c["name"] for c in inspector.get_columns("companies")]
                if "notes" not in cols:
                    sync_conn.execute(text("ALTER TABLE companies ADD COLUMN notes TEXT"))
            if "client_sales" in tables:
                cols = [c["name"] for c in inspector.get_columns("client_sales")]
                sale_cols = [
                    ("payment_status", "VARCHAR(50) DEFAULT 'unpaid'"),
                    ("stripe_session_id", "VARCHAR(255)"),
                    ("stripe_payment_intent_id", "VARCHAR(255)"),
                    ("stripe_checkout_url", "VARCHAR(500)"),
                    ("auto_fulfill_on_payment", "BOOLEAN DEFAULT 1"),
                    ("customer_email", "VARCHAR(255)"),
                    ("customer_phone", "VARCHAR(50)")
                ]
                for col_name, col_type in sale_cols:
                    if col_name not in cols:
                        sync_conn.execute(text(f"ALTER TABLE client_sales ADD COLUMN {col_name} {col_type}"))
            if "client_accounts" in tables:
                cols = [c["name"] for c in inspector.get_columns("client_accounts")]
                client_cols = [
                    ("stripe_customer_id", "VARCHAR(255)"),
                    ("has_payment_method_on_file", "BOOLEAN DEFAULT 0"),
                    ("card_brand", "VARCHAR(50)"),
                    ("card_last4", "VARCHAR(10)"),
                    ("auto_charge_enabled", "BOOLEAN DEFAULT 0"),
                    ("auto_charge_limit", "FLOAT"),
                    ("payment_method_type", "VARCHAR(50) DEFAULT 'card'"),
                    ("portal_access_token", "VARCHAR(100)"),
                    ("portal_token_expires_at", "DATETIME")
                ]
                for col_name, col_type in client_cols:
                    if col_name not in cols:
                        sync_conn.execute(text(f"ALTER TABLE client_accounts ADD COLUMN {col_name} {col_type}"))
        await conn.run_sync(migrate_sqlite_columns)
    logger.info("Database initialized successfully.")
    yield
    logger.info("Shutting down AI Sales Automation Platform...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Multi-Tenant B2B Sales Automation Platform powered by Google Gemini & PostgreSQL",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers (support root and /JsProject sub-directory path)
for prefix in ["/api/v1", "/JsProject/api/v1"]:
    app.include_router(auth.router, prefix=prefix)
    app.include_router(crm.router, prefix=prefix)
    app.include_router(agent.router, prefix=prefix)
    app.include_router(hitl.router, prefix=prefix)
    app.include_router(conversations.router, prefix=prefix)
    app.include_router(fulfillment.router, prefix=prefix)
    app.include_router(payments.router, prefix=prefix)
    app.include_router(public_tracking.router, prefix=prefix)
    app.include_router(replenishments.router, prefix=prefix)
    app.include_router(organization_settings.router, prefix=prefix)
    app.include_router(documents.router, prefix=prefix)
    app.include_router(customer_portal.router, prefix=prefix)

@app.get("/health")
@app.get("/JsProject/health")
async def health_check():
    return {
        "status": "online",
        "project": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "database": "postgresql/sqlite" if "sqlite" in settings.DATABASE_URL else "postgresql",
        "gemini_ai": {
            "model": settings.GEMINI_MODEL,
            "is_live_key_configured": gemini_service.is_live(),
            "mode": "Live Google GenAI Client" if gemini_service.is_live() else "Local-First Simulation & Guardrail Engine"
        }
    }

@app.get("/track/{order_number}", response_class=HTMLResponse)
@app.get("/JsProject/track/{order_number}", response_class=HTMLResponse)
async def customer_tracking_portal(order_number: str):
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Order #{order_number} Delivery Status • Acme Logistics</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    </head>
    <body class="bg-slate-950 text-slate-100 min-h-screen font-sans flex flex-col items-center p-4 md:p-8">
        <div class="w-full max-w-3xl space-y-6">
            <!-- Header Card -->
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl flex flex-wrap items-center justify-between gap-4">
                <div class="flex items-center gap-3.5">
                    <div id="brand-logo-container" class="h-12 w-12 rounded-xl bg-indigo-600/20 border border-indigo-500/40 text-indigo-400 flex items-center justify-center text-xl shadow-lg shrink-0 overflow-hidden">
                        <i class="fa-solid fa-truck-ramp-box" id="brand-default-icon"></i>
                    </div>
                    <div>
                        <div class="flex items-center gap-2">
                            <h1 class="font-mono font-black text-xl text-white tracking-wide">#{order_number}</h1>
                            <span id="badge-status" class="px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wider bg-slate-800 text-slate-300 border border-slate-700">Loading...</span>
                        </div>
                        <p class="text-xs text-slate-400 mt-0.5 flex items-center gap-2">
                            <span id="text-brand-header">Acme Supply Delivery Tracking</span> • 
                            <span id="text-client-name" class="font-medium text-slate-300">Customer Recipient</span>
                        </p>
                    </div>
                </div>
                <div class="flex items-center gap-2">
                    <button onclick="fetchTrackingData()" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition flex items-center gap-1.5 cursor-pointer">
                        <i class="fa-solid fa-rotate-right" id="btn-refresh-icon"></i> Refresh
                    </button>
                    <span id="badge-payment" class="px-3 py-1.5 rounded-lg text-xs font-bold font-mono">...</span>
                </div>
            </div>

            <!-- Custom Tenant Notice Banner (shown if tenant provided custom text) -->
            <div id="banner-tracking-notice" class="hidden p-4 rounded-2xl bg-indigo-950/40 border border-indigo-700/50 text-xs text-indigo-200 flex items-center gap-3 shadow-lg">
                <i class="fa-solid fa-circle-info text-indigo-400 text-base shrink-0"></i>
                <span id="text-tracking-notice-body"></span>
            </div>

            <!-- Interactive 5-Stage Stepper -->
            <div class="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-3">
                <div class="flex items-center justify-between text-xs pb-1 border-b border-slate-800/80">
                    <span class="font-bold text-slate-300 uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                        <i class="fa-solid fa-route text-amber-400"></i> Shipment Progress
                    </span>
                    <span id="text-progress-pct" class="font-mono font-bold text-emerald-400">0%</span>
                </div>
                <div id="stepper-container" class="flex items-center justify-between pt-3 pb-2 relative">
                    <!-- Dynamic Stepper Dots -->
                </div>
            </div>

            <!-- Two-Column Information Cards -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <!-- Shipping & Logistics Card -->
                <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-3">
                    <h2 class="font-bold text-xs uppercase tracking-wider text-slate-400 flex items-center gap-2">
                        <i class="fa-solid fa-truck-fast text-indigo-400"></i> Carrier Logistics
                    </h2>
                    <div class="space-y-2 text-xs divide-y divide-slate-800/60">
                        <div class="pt-1 flex justify-between items-center">
                            <span class="text-slate-400">Carrier Service:</span>
                            <span id="text-carrier" class="font-bold text-slate-200">Processing</span>
                        </div>
                        <div class="pt-2 flex justify-between items-center">
                            <span class="text-slate-400">Tracking Number:</span>
                            <span id="text-tracking-num" class="font-mono font-bold text-cyan-400">Awaiting Label</span>
                        </div>
                        <div class="pt-2">
                            <span class="text-slate-400 block mb-0.5">Destination Facility:</span>
                            <span id="text-delivery-addr" class="font-medium text-slate-200 block text-[11px]">Commercial Receiving Facility</span>
                        </div>
                        <div class="pt-2 flex justify-between items-center">
                            <span class="text-slate-400">Routing Mode:</span>
                            <span id="text-routing-mode" class="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300">Direct Dropship</span>
                        </div>
                    </div>
                </div>

                <!-- Order Details & Payment Card -->
                <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-3">
                    <h2 class="font-bold text-xs uppercase tracking-wider text-slate-400 flex items-center gap-2">
                        <i class="fa-solid fa-box text-emerald-400"></i> Package &amp; Payment
                    </h2>
                    <div class="space-y-2 text-xs divide-y divide-slate-800/60">
                        <div class="pt-1 flex justify-between items-center">
                            <span class="text-slate-400">Order Placed:</span>
                            <span id="text-order-date" class="text-slate-200 font-mono">—</span>
                        </div>
                        <div class="pt-2">
                            <span class="text-slate-400 block mb-0.5">Items in Package:</span>
                            <span id="text-items-summary" class="text-slate-200 text-[11px] font-medium block bg-slate-950 p-2 rounded border border-slate-800/80">—</span>
                        </div>
                        <div id="payment-action-box" class="pt-2">
                            <!-- Pay online button or paid confirmation -->
                        </div>
                    </div>
                </div>
            </div>

            <!-- Activity Log Card -->
            <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-3">
                <div class="flex items-center justify-between">
                    <h2 class="font-bold text-xs uppercase tracking-wider text-slate-400 flex items-center gap-2">
                        <i class="fa-solid fa-timeline text-amber-400"></i> Live Transit Scan History
                    </h2>
                    <span class="text-[10px] text-slate-500">Live Telemetry</span>
                </div>
                <div id="activity-log-list" class="space-y-2 pt-1">
                    <div class="text-center py-4 text-slate-500 text-xs italic">Awaiting first scan...</div>
                </div>
            </div>

            <!-- Support Footer -->
            <div class="text-center text-xs text-slate-500 pt-2 pb-6 space-y-1">
                <p><span id="text-footer-brand">Acme Supply</span> • Questions? Contact <a id="link-support-email" href="mailto:support@therealbonz.com" class="text-indigo-400 hover:underline">support@therealbonz.com</a> <span id="span-support-phone" class="hidden">• Phone: <span id="text-support-phone" class="text-slate-300 font-mono"></span></span></p>
                <p id="text-footer-custom" class="text-[11px] text-slate-600">Generated securely by AI Sales Platform</p>
            </div>
        </div>

        <script>
            const orderNumber = "{order_number}";
            const apiPrefix = window.location.pathname.startsWith("/JsProject") ? "/JsProject" : "";

            async function fetchTrackingData() {
                const icon = document.getElementById("btn-refresh-icon");
                if (icon) icon.classList.add("fa-spin");
                try {
                    const res = await fetch(apiPrefix + "/api/v1/public/tracking/" + encodeURIComponent(orderNumber));
                    if (!res.ok) {
                        document.getElementById("badge-status").innerText = "Order Not Found";
                        document.getElementById("badge-status").className = "px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-950 text-rose-300 border border-rose-800";
                        return;
                    }
                    const data = await res.json();
                    renderTrackingView(data);
                } catch(e) {
                    console.error("Error loading tracking data:", e);
                } finally {
                    if (icon) icon.classList.remove("fa-spin");
                }
            }

            function renderTrackingView(data) {
                // White-label dynamic branding & theming
                const brandName = data.brand_name || "Order Bot Distribution";
                document.title = `Order #${orderNumber} Delivery Status • ${brandName}`;
                const brandHeaderEl = document.getElementById("text-brand-header");
                if (brandHeaderEl) brandHeaderEl.innerText = `${brandName} Delivery Tracking`;
                const footerBrandEl = document.getElementById("text-footer-brand");
                if (footerBrandEl) footerBrandEl.innerText = brandName;

                if (data.brand_logo_url) {
                    const logoBox = document.getElementById("brand-logo-container");
                    if (logoBox) logoBox.innerHTML = `<img src="${data.brand_logo_url}" alt="${brandName}" class="h-full w-full object-contain p-1">`;
                }

                if (data.support_email) {
                    const emailLink = document.getElementById("link-support-email");
                    if (emailLink) {
                        emailLink.href = "mailto:" + data.support_email;
                        emailLink.innerText = data.support_email;
                    }
                }

                if (data.support_phone) {
                    const phoneSpan = document.getElementById("span-support-phone");
                    const phoneText = document.getElementById("text-support-phone");
                    if (phoneSpan && phoneText) {
                        phoneSpan.classList.remove("hidden");
                        phoneText.innerText = data.support_phone;
                    }
                }

                if (data.tracking_portal_notice) {
                    const noticeBanner = document.getElementById("banner-tracking-notice");
                    const noticeText = document.getElementById("text-tracking-notice-body");
                    if (noticeBanner && noticeText) {
                        noticeBanner.classList.remove("hidden");
                        noticeText.innerText = data.tracking_portal_notice;
                    }
                }

                if (data.custom_footer_text) {
                    const footerCustom = document.getElementById("text-footer-custom");
                    if (footerCustom) footerCustom.innerText = data.custom_footer_text;
                }

                if (data.brand_accent_color) {
                    document.documentElement.style.setProperty('--brand-accent', data.brand_accent_color);
                }

                // Header & Badges
                document.getElementById("text-client-name").innerText = data.client_name || "Customer";
                const isDelivered = data.is_delivered || data.current_status === "delivered";

                const badgeStatus = document.getElementById("badge-status");
                if (isDelivered) {
                    badgeStatus.innerText = "✓ Delivered";
                    badgeStatus.className = "px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider bg-emerald-950 text-emerald-300 border border-emerald-600/50 shadow-emerald-500/20 shadow-sm";
                } else {
                    badgeStatus.innerText = (data.current_status || "Processing").replace(/_/g, " ");
                    badgeStatus.className = "px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider bg-indigo-950 text-indigo-300 border border-indigo-600/50";
                }

                // Payment badge & action
                const badgePayment = document.getElementById("badge-payment");
                const payBox = document.getElementById("payment-action-box");
                if (data.payment_status === "paid") {
                    badgePayment.innerText = "✓ Paid";
                    badgePayment.className = "px-3 py-1 rounded-lg text-xs font-bold bg-emerald-950/80 text-emerald-300 border border-emerald-700/50 flex items-center gap-1";
                    payBox.innerHTML = `
                        <div class="p-2.5 rounded-xl bg-emerald-950/40 border border-emerald-600/30 text-emerald-300 text-xs font-semibold flex items-center justify-between">
                            <span class="flex items-center gap-1.5"><i class="fa-solid fa-circle-check text-emerald-400"></i> Invoice Paid Online</span>
                            <span class="text-[10px] text-slate-400 font-mono">Secured with Stripe</span>
                        </div>
                    `;
                } else {
                    badgePayment.innerText = "Unpaid";
                    badgePayment.className = "px-3 py-1 rounded-lg text-xs font-bold bg-amber-950/80 text-amber-300 border border-amber-700/50";
                    const checkoutUrl = data.stripe_checkout_url ? (apiPrefix + data.stripe_checkout_url) : "#";
                    payBox.innerHTML = `
                        <div class="space-y-2">
                            <div class="flex items-center justify-between text-[11px] text-amber-300">
                                <span><i class="fa-solid fa-receipt mr-1"></i> Awaiting Customer Payment</span>
                                <span class="font-bold">Due upon receipt</span>
                            </div>
                            <a href="${checkoutUrl}" class="w-full block text-center py-2.5 px-4 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold rounded-xl text-xs shadow-lg shadow-emerald-600/30 transition">
                                <i class="fa-solid fa-credit-card mr-1"></i> Pay Online with Stripe Checkout
                            </a>
                        </div>
                    `;
                }

                // Stepper
                const stages = [
                    { id: 'label_created', label: 'Label Created' },
                    { id: 'picked_up', label: 'Picked Up' },
                    { id: 'in_transit', label: 'In Transit' },
                    { id: 'out_for_delivery', label: 'Out for Delivery' },
                    { id: 'delivered', label: 'Delivered' }
                ];
                const stageIds = stages.map(s => s.id);
                const currentIdx = stageIds.indexOf(data.current_status);
                document.getElementById("text-progress-pct").innerText = (data.shipping_stage_pct || 0) + "%";

                let stepperHtml = "";
                stages.forEach((s, idx) => {
                    const isDone = idx <= currentIdx || isDelivered;
                    const isCurrent = idx === currentIdx && !isDelivered;
                    const dotBg = isDone ? 'bg-emerald-500 text-slate-950 font-bold' : 'bg-slate-800 text-slate-500 border border-slate-700';
                    const lineBg = idx <= currentIdx ? 'bg-emerald-500' : 'bg-slate-800';

                    stepperHtml += `
                        <div class="flex-1 flex flex-col items-center relative">
                            ${idx > 0 ? `<div class="absolute top-3.5 right-1/2 w-full h-0.5 ${lineBg} -z-0"></div>` : ''}
                            <div class="h-7 w-7 rounded-full flex items-center justify-center text-xs font-bold z-10 ${dotBg} ${isCurrent ? 'ring-4 ring-emerald-400/30 animate-pulse' : ''}">
                                ${isDone ? '<i class="fa-solid fa-check"></i>' : (idx + 1)}
                            </div>
                            <span class="text-[10px] mt-1.5 text-center font-medium ${isDone ? 'text-emerald-300 font-bold' : 'text-slate-500'}">${s.label}</span>
                        </div>
                    `;
                });
                document.getElementById("stepper-container").innerHTML = stepperHtml;

                // Logistics & Order details
                document.getElementById("text-carrier").innerText = data.carrier || "Assigned by Order Bot";
                if (data.tracking_number) {
                    const trackLink = data.tracking_url ? `<a href="${data.tracking_url}" target="_blank" class="hover:underline flex items-center gap-1">${data.tracking_number} <i class="fa-solid fa-arrow-up-right-from-square text-[9px]"></i></a>` : data.tracking_number;
                    document.getElementById("text-tracking-num").innerHTML = trackLink;
                } else {
                    document.getElementById("text-tracking-num").innerText = "Generating Label...";
                }
                document.getElementById("text-delivery-addr").innerText = data.delivery_address || "Customer Receiving Facility";
                document.getElementById("text-routing-mode").innerText = data.destination_type === 'customer_dropship' ? 'Direct Customer Dropship' : 'Warehouse Restock';
                document.getElementById("text-order-date").innerText = new Date(data.sale_date).toLocaleDateString([], {month:'short', day:'numeric', year:'numeric'});
                document.getElementById("text-items-summary").innerText = data.items_summary || "Commercial supplies package";

                // Activity logs
                const logContainer = document.getElementById("activity-log-list");
                if (data.history_events && data.history_events.length > 0) {
                    logContainer.innerHTML = data.history_events.map(ev => `
                        <div class="flex items-start gap-3 p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/80 text-xs">
                            <div class="h-6 w-6 rounded bg-indigo-500/20 text-indigo-400 flex items-center justify-center text-[11px] shrink-0 mt-0.5">
                                <i class="fa-solid fa-location-dot"></i>
                            </div>
                            <div class="flex-1 min-w-0">
                                <div class="flex items-center justify-between gap-2">
                                    <span class="font-bold text-slate-200 text-xs">${ev.location || 'Terminal'}</span>
                                    <span class="font-mono text-[10px] text-slate-500">${new Date(ev.timestamp).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}</span>
                                </div>
                                <p class="text-slate-400 text-[11px] mt-0.5">${ev.description || ''}</p>
                            </div>
                        </div>
                    `).reverse().join("");
                } else {
                    logContainer.innerHTML = `<div class="p-3 text-center text-slate-500 text-xs italic bg-slate-950/40 rounded-lg">Manifest created. Waiting for carrier transit checkpoint.</div>`;
                }
            }

            fetchTrackingData();
            setInterval(fetchTrackingData, 12000);
        </script>
    </body>
    </html>
    """
    safe_order = html_lib.escape(order_number)
    return HTMLResponse(content=html.replace("{order_number}", safe_order))

@app.get("/checkout/pay/{session_id}", response_class=HTMLResponse)
@app.get("/JsProject/checkout/pay/{session_id}", response_class=HTMLResponse)
async def customer_checkout_portal(session_id: str):
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Secure Checkout • Acme Supply Corp</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    </head>
    <body class="bg-slate-950 text-slate-100 min-h-screen font-sans flex items-center justify-center p-4">
        <div class="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-6">
            <!-- Brand & Stripe Header -->
            <div class="flex items-center justify-between pb-4 border-b border-slate-800">
                <div class="flex items-center gap-2.5">
                    <div id="checkout-logo-box" class="h-9 w-9 rounded-lg bg-emerald-600/20 text-emerald-400 flex items-center justify-center font-bold text-sm overflow-hidden shrink-0">
                        <i class="fa-solid fa-shield-halved"></i>
                    </div>
                    <div>
                        <h1 id="text-checkout-brand" class="font-bold text-sm text-slate-100">Acme Supply Checkout</h1>
                        <p class="text-[10px] text-slate-400">Encrypted 256-bit SSL Payment</p>
                    </div>
                </div>
                <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-indigo-950 text-indigo-300 border border-indigo-700/50 font-semibold flex items-center gap-1">
                    <i class="fa-brands fa-stripe text-indigo-400"></i> Stripe Verified
                </span>
            </div>

            <!-- Order Summary Section -->
            <div id="order-summary-box" class="bg-slate-950 rounded-xl p-4 border border-slate-800/80 space-y-2 text-xs">
                <div class="flex justify-between items-center">
                    <span class="text-slate-400">Order Reference:</span>
                    <span id="text-order-num" class="font-mono font-bold text-slate-200">Loading...</span>
                </div>
                <div class="flex justify-between items-center">
                    <span class="text-slate-400">Billed To:</span>
                    <span id="text-client-name" class="font-semibold text-slate-200">Customer</span>
                </div>
                <div class="pt-2 border-t border-slate-800/80 flex justify-between items-center">
                    <span class="text-slate-300 font-bold">Total Amount Due:</span>
                    <span id="text-amount" class="font-mono font-black text-lg text-emerald-400">$0.00</span>
                </div>
            </div>

            <!-- Payment Form -->
            <div id="payment-form-box" class="space-y-4 text-xs">
                <div>
                    <label class="block text-slate-400 mb-1 font-semibold">Cardholder Full Name</label>
                    <input type="text" id="in-card-name" value="Finance Purchasing Dept" class="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-slate-100 focus:outline-none focus:border-emerald-500">
                </div>
                <div>
                    <label class="block text-slate-400 mb-1 font-semibold">Card Number</label>
                    <div class="relative">
                        <input type="text" id="in-card-num" value="•••• •••• •••• 4242" class="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-slate-100 font-mono focus:outline-none focus:border-emerald-500 pl-9">
                        <i class="fa-brands fa-cc-visa text-indigo-400 absolute left-3 top-3 text-sm"></i>
                    </div>
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-slate-400 mb-1 font-semibold">Expiration</label>
                        <input type="text" id="in-card-exp" value="12/28" class="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-slate-100 font-mono text-center focus:outline-none focus:border-emerald-500">
                    </div>
                    <div>
                        <label class="block text-slate-400 mb-1 font-semibold">CVC / CVV</label>
                        <input type="text" id="in-card-cvc" value="123" class="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-slate-100 font-mono text-center focus:outline-none focus:border-emerald-500">
                    </div>
                </div>

                <button id="btn-pay" onclick="submitPayment()" class="w-full py-3 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold rounded-xl text-sm shadow-xl shadow-emerald-600/30 transition flex items-center justify-center gap-2 cursor-pointer mt-2">
                    <i class="fa-solid fa-lock"></i> <span id="btn-pay-text">Complete Secure Payment</span>
                </button>
            </div>

            <!-- Success State Box (Initially hidden) -->
            <div id="success-box" class="hidden text-center py-6 space-y-4">
                <div class="h-16 w-16 bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 rounded-full flex items-center justify-center text-3xl mx-auto shadow-lg shadow-emerald-500/20 animate-bounce">
                    <i class="fa-solid fa-check"></i>
                </div>
                <div>
                    <h3 class="font-bold text-lg text-white">Payment Confirmed!</h3>
                    <p class="text-xs text-slate-400 mt-1 max-w-xs mx-auto">
                        Your transaction has been processed. The AI Order Bot has immediately triggered autonomous dropshipping and carrier dispatch.
                    </p>
                </div>
                <a id="link-track-order" href="#" class="inline-block py-2.5 px-5 bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs rounded-xl shadow-lg transition">
                    <i class="fa-solid fa-truck-ramp-box mr-1"></i> View Live Delivery Portal ➔
                </a>
            </div>
        </div>

        <script>
            const sessionId = "{session_id}";
            const apiPrefix = window.location.pathname.startsWith("/JsProject") ? "/JsProject" : "";
            let currentOrderNumber = "";

            async function loadSessionDetails() {
                try {
                    const res = await fetch(apiPrefix + "/api/v1/public/checkout/" + encodeURIComponent(sessionId));
                    if (res.ok) {
                        const data = await res.json();
                        currentOrderNumber = data.order_number;

                        // Brand theming
                        const brandName = data.brand_name || data.organization_name || "Merchant";
                        document.title = `Secure Checkout • ${brandName}`;
                        const brandTitle = document.getElementById("text-checkout-brand");
                        if (brandTitle) brandTitle.innerText = `${brandName} Checkout`;

                        if (data.brand_logo_url) {
                            const logoBox = document.getElementById("checkout-logo-box");
                            if (logoBox) logoBox.innerHTML = `<img src="${data.brand_logo_url}" alt="Logo" class="h-full w-full object-contain p-0.5">`;
                        }

                        if (data.brand_accent_color) {
                            const btnPay = document.getElementById("btn-pay");
                            if (btnPay) {
                                btnPay.style.background = data.brand_accent_color;
                            }
                        }

                        document.getElementById("text-order-num").innerText = "#" + data.order_number;
                        document.getElementById("text-client-name").innerText = data.client_name;
                        document.getElementById("text-amount").innerText = "$" + data.amount.toFixed(2);
                        document.getElementById("btn-pay-text").innerText = "Pay $" + data.amount.toFixed(2) + " with Card";
                        if (data.payment_status === "paid") {
                            showSuccessState();
                        }
                    }
                } catch(e) {
                    console.error("Error loading checkout session:", e);
                }
            }

            async function submitPayment() {
                const btn = document.getElementById("btn-pay");
                btn.disabled = true;
                btn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Authorizing Card...`;

                try {
                    const res = await fetch(apiPrefix + "/api/v1/payments/stripe/webhook", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            type: "checkout.session.completed",
                            data: {
                                object: {
                                    id: sessionId,
                                    payment_intent: "pi_test_" + Math.random().toString(36).substring(2, 12)
                                }
                            }
                        })
                    });

                    if (res.ok) {
                        showSuccessState();
                    } else {
                        alert("Payment authorization failed. Please try again.");
                        btn.disabled = false;
                        btn.innerHTML = `<i class="fa-solid fa-lock"></i> Complete Secure Payment`;
                    }
                } catch(err) {
                    alert("Error authorizing payment: " + err.message);
                    btn.disabled = false;
                    btn.innerHTML = `<i class="fa-solid fa-lock"></i> Complete Secure Payment`;
                }
            }

            function showSuccessState() {
                document.getElementById("payment-form-box").classList.add("hidden");
                document.getElementById("order-summary-box").classList.add("hidden");
                document.getElementById("success-box").classList.remove("hidden");
                document.getElementById("link-track-order").href = apiPrefix + "/track/" + currentOrderNumber;
            }

            loadSessionDetails();
        </script>
    </body>
    </html>
    """
    safe_session = html_lib.escape(session_id)
    return HTMLResponse(content=html.replace("{session_id}", safe_session))

@app.get("/portal/{token}", response_class=HTMLResponse)
@app.get("/JsProject/portal/{token}", response_class=HTMLResponse)
async def customer_portal_page(token: str):
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Customer Account &amp; Replenishment Portal</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    </head>
    <body class="bg-slate-950 text-slate-100 min-h-screen font-sans flex flex-col items-center p-4 md:p-8">
        <div class="w-full max-w-5xl space-y-6">
            <!-- Header Card -->
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl flex flex-wrap items-center justify-between gap-4">
                <div class="flex items-center gap-3.5">
                    <div id="brand-logo-container" class="h-12 w-12 rounded-xl bg-indigo-600/20 border border-indigo-500/40 text-indigo-400 flex items-center justify-center text-xl shadow-lg shrink-0 overflow-hidden">
                        <i class="fa-solid fa-cube" id="brand-default-icon"></i>
                    </div>
                    <div>
                        <div class="flex items-center gap-2">
                            <h1 id="brand-name" class="font-black text-xl text-white tracking-wide">Customer Account Portal</h1>
                            <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-950 text-emerald-300 border border-emerald-700/50">SECURE ACCESS</span>
                        </div>
                        <p id="portal-subheading" class="text-xs text-slate-400 mt-0.5">Enterprise Automated Replenishment &amp; Commercial Billing Hub</p>
                    </div>
                </div>
                <div class="text-right">
                    <div id="account-name" class="font-bold text-base text-slate-100">Loading Account...</div>
                    <div id="contact-info" class="text-xs text-slate-400 mt-0.5">—</div>
                </div>
            </div>

            <!-- Restock Cadence Hero Banner -->
            <div class="bg-gradient-to-r from-indigo-950/70 via-slate-900 to-amber-950/60 border border-indigo-500/30 rounded-2xl p-6 shadow-xl space-y-4">
                <div class="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-800">
                    <div>
                        <div class="flex items-center gap-2">
                            <span class="h-2.5 w-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
                            <h2 class="font-bold text-lg text-white">Automated Restock &amp; Inventory Replenishment</h2>
                        </div>
                        <p class="text-xs text-slate-400 mt-1">Autonomous cadence monitoring ensures your facility never encounters unexpected supply stockouts.</p>
                    </div>
                    <div class="flex items-center gap-2">
                        <button onclick="accelerateRestock()" class="px-3.5 py-2 bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-white font-semibold rounded-lg text-xs flex items-center gap-2 shadow-lg shadow-emerald-600/20 transition cursor-pointer">
                            <i class="fa-solid fa-bolt text-amber-300"></i> Ship Restock Now
                        </button>
                        <button onclick="snoozeRestock(14)" class="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer">
                            <i class="fa-solid fa-clock-rotate-left text-amber-400"></i> Snooze 14 Days
                        </button>
                        <button onclick="openCadenceModal()" class="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer">
                            <i class="fa-solid fa-calendar-days text-indigo-400"></i> Adjust Cadence
                        </button>
                    </div>
                </div>

                <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div class="bg-slate-950/70 border border-slate-800/80 rounded-xl p-4">
                        <span class="text-[11px] text-slate-400">Next Estimated Restock</span>
                        <div id="stat-next-date" class="font-bold text-base text-amber-300 font-mono mt-1">—</div>
                    </div>
                    <div class="bg-slate-950/70 border border-slate-800/80 rounded-xl p-4">
                        <span class="text-[11px] text-slate-400">Schedule Status</span>
                        <div id="stat-status-badge" class="font-bold text-base text-emerald-400 font-mono mt-1">—</div>
                    </div>
                    <div class="bg-slate-950/70 border border-slate-800/80 rounded-xl p-4">
                        <span class="text-[11px] text-slate-400">Reorder Frequency</span>
                        <div id="stat-cadence-days" class="font-bold text-base text-indigo-300 font-mono mt-1">30 Days</div>
                    </div>
                    <div class="bg-slate-950/70 border border-slate-800/80 rounded-xl p-4">
                        <span class="text-[11px] text-slate-400">Account Tier</span>
                        <div id="stat-account-tier" class="font-bold text-base text-purple-300 font-mono mt-1 uppercase">STANDARD</div>
                    </div>
                </div>

                <div id="pending-proposal-banner" class="hidden bg-amber-950/50 border border-amber-500/50 rounded-xl p-4 flex flex-wrap items-center justify-between gap-3">
                    <div class="flex items-center gap-3">
                        <i class="fa-solid fa-bell text-amber-400 text-xl"></i>
                        <div>
                            <div class="font-bold text-sm text-amber-200" id="proposal-title">Scheduled Restock Order Prepared</div>
                            <div class="text-xs text-amber-300/80 mt-0.5" id="proposal-items">—</div>
                        </div>
                    </div>
                    <div class="flex items-center gap-2">
                        <span class="font-mono font-bold text-amber-300 text-sm" id="proposal-amount">$0.00</span>
                        <a id="proposal-pay-btn" href="#" target="_blank" class="px-3 py-1.5 bg-amber-600 hover:bg-amber-500 text-white font-semibold rounded-lg text-xs flex items-center gap-1.5 transition">
                            <i class="fa-brands fa-stripe"></i> Pay Online
                        </a>
                    </div>
                </div>
            </div>

            <!-- Two-Column Strip: Card on File & Delivery Address -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <!-- Stored Payment Method Card -->
                <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
                    <div class="flex items-center justify-between pb-3 border-b border-slate-800">
                        <div class="flex items-center gap-2 text-indigo-400">
                            <i class="fa-solid fa-credit-card"></i>
                            <h3 class="font-bold text-sm text-slate-100">Payment Method on File</h3>
                        </div>
                        <span id="card-auto-badge" class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-800 text-slate-400 border border-slate-700">No Card</span>
                    </div>
                    <div class="flex items-center gap-4">
                        <div class="w-12 h-12 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-center text-2xl text-slate-300" id="card-brand-icon">
                            <i class="fa-regular fa-credit-card"></i>
                        </div>
                        <div>
                            <div class="font-mono font-bold text-sm text-slate-100" id="card-display-text">No Payment Method Stored</div>
                            <div class="text-xs text-slate-400 mt-0.5" id="card-subtext">Add a corporate credit card for hands-free automated restock billing.</div>
                        </div>
                    </div>
                    <div class="flex items-center justify-between pt-2 border-t border-slate-800/80 text-xs">
                        <span class="text-slate-400" id="card-limit-text">Safety Spend Cap: None</span>
                        <div class="flex items-center gap-2">
                            <button onclick="openCardModal()" class="px-2.5 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded text-xs flex items-center gap-1 cursor-pointer transition">
                                <i class="fa-solid fa-pen-to-square"></i> <span id="btn-card-action-text">Add Card</span>
                            </button>
                            <button id="btn-detach-card" onclick="detachCard()" class="hidden px-2.5 py-1.5 bg-rose-950 hover:bg-rose-900 text-rose-300 border border-rose-800 rounded text-xs font-semibold flex items-center gap-1 cursor-pointer transition">
                                <i class="fa-solid fa-trash-can"></i>
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Receiving Dock & Delivery Address Card -->
                <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
                    <div class="flex items-center justify-between pb-3 border-b border-slate-800">
                        <div class="flex items-center gap-2 text-amber-400">
                            <i class="fa-solid fa-location-dot"></i>
                            <h3 class="font-bold text-sm text-slate-100">Receiving Dock &amp; Delivery Site</h3>
                        </div>
                        <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-400 border border-slate-700">VERIFIED HUB</span>
                    </div>
                    <div class="flex items-start gap-3">
                        <div class="w-10 h-10 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-center text-amber-400 text-lg shrink-0 mt-0.5">
                            <i class="fa-solid fa-warehouse"></i>
                        </div>
                        <div class="text-xs space-y-1">
                            <div class="font-bold text-slate-200" id="delivery-company-name">—</div>
                            <div class="text-slate-400" id="delivery-address-text">—</div>
                            <div class="text-slate-500 text-[11px] pt-1" id="delivery-contact-line">Receiving Lead: —</div>
                        </div>
                    </div>
                    <div class="pt-2 border-t border-slate-800/80 text-[11px] text-slate-500 flex items-center gap-1.5">
                        <i class="fa-solid fa-shield-halved text-emerald-400"></i> Standard freight carrier appointments dispatched automatically.
                    </div>
                </div>
            </div>

            <!-- Orders, Invoices & Telemetry History Ledger -->
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
                <div class="flex justify-between items-center pb-3 border-b border-slate-800">
                    <div class="flex items-center gap-2 text-emerald-400">
                        <i class="fa-solid fa-receipt text-base"></i>
                        <h3 class="font-bold text-sm text-slate-100">Orders, Commercial Invoices &amp; Tracking History</h3>
                    </div>
                    <span id="sales-count-badge" class="text-xs font-mono text-slate-400">0 Orders</span>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-xs border-collapse">
                        <thead>
                            <tr class="border-b border-slate-800 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                                <th class="pb-2.5 font-medium">Date</th>
                                <th class="pb-2.5 font-medium">Order #</th>
                                <th class="pb-2.5 font-medium">Items Summary</th>
                                <th class="pb-2.5 font-medium">Payment</th>
                                <th class="pb-2.5 font-medium">Fulfillment &amp; Carrier</th>
                                <th class="pb-2.5 font-medium">Documents</th>
                                <th class="pb-2.5 font-medium text-right">Amount</th>
                            </tr>
                        </thead>
                        <tbody id="sales-table-body" class="divide-y divide-slate-800/60">
                            <tr>
                                <td colspan="7" class="py-6 text-center text-slate-500 italic">Loading order history...</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Footer -->
            <div class="text-center py-4 text-xs text-slate-500 space-y-1">
                <div id="footer-brand-text">Enterprise Automated Restock &amp; Supply Chain Portal</div>
                <div class="flex items-center justify-center gap-3 text-[11px] text-slate-400 pt-1">
                    <span id="footer-support-email"><i class="fa-solid fa-envelope mr-1"></i>support@therealbonz.com</span>
                    <span>&bull;</span>
                    <span id="footer-support-phone"><i class="fa-solid fa-phone mr-1"></i>+1 (800) 555-0199</span>
                    <span>&bull;</span>
                    <span><i class="fa-solid fa-lock text-emerald-400 mr-1"></i>256-Bit Encrypted Portal</span>
                </div>
            </div>
        </div>

        <!-- Modal: Update Card on File -->
        <div id="modal-card" class="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
            <div class="bg-slate-900 border border-indigo-500/50 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
                <div class="flex justify-between items-center pb-3 border-b border-slate-800">
                    <div class="flex items-center gap-2 text-indigo-400">
                        <i class="fa-solid fa-credit-card text-lg"></i>
                        <h3 class="font-bold text-sm text-slate-100">Corporate Card Authorization</h3>
                    </div>
                    <button onclick="closeCardModal()" class="text-slate-400 hover:text-white cursor-pointer"><i class="fa-solid fa-xmark text-lg"></i></button>
                </div>
                <form id="form-card" onsubmit="handleSaveCard(event)" class="space-y-3 text-xs">
                    <div>
                        <label class="block text-slate-400 mb-1">Card Brand</label>
                        <select id="modal-card-brand" class="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-100">
                            <option value="visa" selected>Visa Commercial</option>
                            <option value="mastercard">Mastercard Corporate</option>
                            <option value="amex">American Express Corporate</option>
                            <option value="discover">Discover</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-slate-400 mb-1">Last 4 Digits</label>
                        <input id="modal-card-last4" type="text" maxlength="4" pattern="[0-9]{4}" required value="4242" class="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-100 font-mono">
                    </div>
                    <div class="pt-1">
                        <label class="flex items-center gap-2 cursor-pointer">
                            <input id="modal-card-auto" type="checkbox" checked class="w-4 h-4 rounded text-indigo-600 bg-slate-950 border-slate-700">
                            <span class="text-slate-200 font-semibold">Authorize Automatic Settlement on Cadence Restock</span>
                        </label>
                        <p class="text-[11px] text-slate-400 ml-6 mt-0.5">Recurring restocks trigger immediate order dispatch without manual paperwork.</p>
                    </div>
                    <div>
                        <label class="block text-slate-400 mb-1">Safety Spend Ceiling ($) (Optional)</label>
                        <input id="modal-card-limit" type="number" step="1" min="1" placeholder="Leave blank for unlimited" class="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-100 font-mono">
                    </div>
                    <div class="flex justify-end gap-2 pt-3 border-t border-slate-800">
                        <button type="button" onclick="closeCardModal()" class="py-2 px-3 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs font-semibold cursor-pointer">Cancel</button>
                        <button type="submit" class="py-2 px-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-xs font-semibold flex items-center gap-1.5 shadow-md cursor-pointer">
                            <i class="fa-solid fa-lock"></i> Save Payment Method
                        </button>
                    </div>
                </form>
            </div>
        </div>

        <!-- Modal: Adjust Restock Cadence -->
        <div id="modal-cadence" class="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
            <div class="bg-slate-900 border border-indigo-500/50 rounded-2xl max-w-sm w-full p-6 shadow-2xl space-y-4">
                <div class="flex justify-between items-center pb-3 border-b border-slate-800">
                    <div class="flex items-center gap-2 text-indigo-400">
                        <i class="fa-solid fa-calendar-days text-lg"></i>
                        <h3 class="font-bold text-sm text-slate-100">Adjust Reorder Frequency</h3>
                    </div>
                    <button onclick="closeCadenceModal()" class="text-slate-400 hover:text-white cursor-pointer"><i class="fa-solid fa-xmark text-lg"></i></button>
                </div>
                <form onsubmit="handleSaveCadence(event)" class="space-y-3 text-xs">
                    <div>
                        <label class="block text-slate-400 mb-1">Restock Cycle (Days)</label>
                        <select id="modal-cadence-select" class="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-100">
                            <option value="7">Weekly (7 Days)</option>
                            <option value="14">Bi-Weekly (14 Days)</option>
                            <option value="21">Every 3 Weeks (21 Days)</option>
                            <option value="30" selected>Monthly (30 Days)</option>
                            <option value="45">Every 45 Days</option>
                            <option value="60">Bi-Monthly (60 Days)</option>
                            <option value="90">Quarterly (90 Days)</option>
                        </select>
                    </div>
                    <div class="flex justify-end gap-2 pt-3 border-t border-slate-800">
                        <button type="button" onclick="closeCadenceModal()" class="py-2 px-3 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs font-semibold cursor-pointer">Cancel</button>
                        <button type="submit" class="py-2 px-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-xs font-semibold cursor-pointer">Update Cadence</button>
                    </div>
                </form>
            </div>
        </div>

        <script>
            const PORTAL_TOKEN = "{token}";
            const SUB_PATH = window.location.pathname.startsWith("/JsProject") ? "/JsProject" : "";
            const API_BASE = SUB_PATH + "/api/v1";

            let portalData = null;

            async function loadPortal() {
                try {
                    const res = await fetch(`${API_BASE}/portal/session/${PORTAL_TOKEN}`);
                    if (!res.ok) {
                        document.body.innerHTML = `
                            <div class="min-h-screen flex flex-col items-center justify-center p-4 text-center">
                                <div class="w-16 h-16 rounded-2xl bg-rose-950 border border-rose-700/60 flex items-center justify-center text-rose-400 text-2xl mb-4">
                                    <i class="fa-solid fa-link-slash"></i>
                                </div>
                                <h1 class="text-xl font-bold text-white mb-1">Access Link Expired or Invalid</h1>
                                <p class="text-xs text-slate-400 max-w-sm">This customer portal access token is invalid or has been revoked. Please contact your account executive for a renewed link.</p>
                            </div>
                        `;
                        return;
                    }
                    portalData = await res.json();
                    renderPortal(portalData);
                } catch(e) {
                    console.error("Error loading portal:", e);
                }
            }

            function renderPortal(data) {
                const { tenant, account, payment_method, pending_replenishment, sales_ledger } = data;

                // Brand
                document.getElementById("brand-name").innerText = tenant.brand_name || "Customer Account Portal";
                if (tenant.brand_logo_url) {
                    document.getElementById("brand-logo-container").innerHTML = `<img src="${tenant.brand_logo_url}" class="h-full w-full object-contain p-1" alt="Logo">`;
                }
                document.getElementById("footer-brand-text").innerText = tenant.custom_footer_text || `${tenant.brand_name} • B2B Supply Chain & Replenishment Portal`;
                document.getElementById("footer-support-email").innerHTML = `<i class="fa-solid fa-envelope mr-1"></i>${tenant.support_email || 'support@therealbonz.com'}`;
                document.getElementById("footer-support-phone").innerHTML = `<i class="fa-solid fa-phone mr-1"></i>${tenant.support_phone || '+1 (800) 555-0199'}`;

                // Account
                document.getElementById("account-name").innerText = account.account_name;
                document.getElementById("contact-info").innerText = `${account.contact_name} • ${account.contact_email || ''}`;
                document.getElementById("stat-account-tier").innerText = account.account_tier || 'STANDARD';
                document.getElementById("stat-cadence-days").innerText = `${account.reorder_cadence_days} Days`;
                document.getElementById("modal-cadence-select").value = String(account.reorder_cadence_days);

                // Cadence Stats
                if (account.next_reorder_date) {
                    const d = new Date(account.next_reorder_date);
                    document.getElementById("stat-next-date").innerText = d.toLocaleDateString([], {month:'short', day:'numeric', year:'numeric'});
                } else {
                    document.getElementById("stat-next-date").innerText = "—";
                }

                const days = account.days_until_reorder;
                const statusBadge = document.getElementById("stat-status-badge");
                if (days !== null) {
                    if (days <= 0) {
                        statusBadge.className = "font-bold text-base text-rose-400 font-mono mt-1";
                        statusBadge.innerHTML = `<i class="fa-solid fa-triangle-exclamation mr-1"></i>Due Today`;
                    } else if (days <= 7) {
                        statusBadge.className = "font-bold text-base text-amber-300 font-mono mt-1";
                        statusBadge.innerHTML = `<i class="fa-solid fa-hourglass-half mr-1"></i>${days} Days Left`;
                    } else {
                        statusBadge.className = "font-bold text-base text-emerald-400 font-mono mt-1";
                        statusBadge.innerHTML = `<i class="fa-solid fa-calendar-check mr-1"></i>In ${days} Days`;
                    }
                } else {
                    statusBadge.innerText = "Scheduled";
                }

                // Proposal
                const propBanner = document.getElementById("pending-proposal-banner");
                if (pending_replenishment) {
                    propBanner.classList.remove("hidden");
                    document.getElementById("proposal-title").innerText = `Restock Order #${pending_replenishment.order_number} Prepared`;
                    document.getElementById("proposal-items").innerText = pending_replenishment.items_summary;
                    document.getElementById("proposal-amount").innerText = "$" + Number(pending_replenishment.amount).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                    const payUrl = pending_replenishment.checkout_url.startsWith("http") ? pending_replenishment.checkout_url : (SUB_PATH + pending_replenishment.checkout_url);
                    document.getElementById("proposal-pay-btn").href = payUrl;
                } else {
                    propBanner.classList.add("hidden");
                }

                // Payment Method
                const cardBadge = document.getElementById("card-auto-badge");
                const cardText = document.getElementById("card-display-text");
                const cardSubtext = document.getElementById("card-subtext");
                const cardLimit = document.getElementById("card-limit-text");
                const btnCardAction = document.getElementById("btn-card-action-text");
                const btnDetach = document.getElementById("btn-detach-card");

                if (payment_method.has_payment_method_on_file) {
                    const brand = (payment_method.card_brand || "CARD").toUpperCase();
                    const last4 = payment_method.card_last4 || "••••";
                    const isAuto = payment_method.auto_charge_enabled;
                    cardBadge.className = isAuto
                        ? "px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-950 text-emerald-300 border border-emerald-600/60"
                        : "px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-950 text-amber-300 border border-amber-600/60";
                    cardBadge.innerText = isAuto ? "AUTO-BILLING ACTIVE" : "AUTO-BILLING PAUSED";
                    cardText.innerText = `${brand} ending in ${last4}`;
                    cardSubtext.innerText = isAuto
                        ? "Authorized for hands-free settlement when cadence restocks trigger."
                        : "Card stored on file; auto-billing currently paused.";
                    cardLimit.innerText = payment_method.auto_charge_limit
                        ? `Safety Spend Ceiling: $${Number(payment_method.auto_charge_limit).toLocaleString(undefined, {minimumFractionDigits: 2})}`
                        : "Safety Spend Ceiling: Unlimited";
                    btnCardAction.innerText = "Update Card";
                    btnDetach.classList.remove("hidden");
                } else {
                    cardBadge.className = "px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-800 text-slate-400 border border-slate-700";
                    cardBadge.innerText = "No Card Stored";
                    cardText.innerText = "No Corporate Card Stored";
                    cardSubtext.innerText = "Authorize a card on file to enable hands-free automated replenishment.";
                    cardLimit.innerText = "Safety Spend Ceiling: None";
                    btnCardAction.innerText = "Add Card";
                    btnDetach.classList.add("hidden");
                }

                // Delivery Site
                document.getElementById("delivery-company-name").innerText = account.company_name;
                document.getElementById("delivery-address-text").innerText = account.delivery_address;
                document.getElementById("delivery-contact-line").innerText = `Receiving Contact: ${account.contact_name} (${account.contact_phone || 'Direct Line'})`;

                // Ledger
                document.getElementById("sales-count-badge").innerText = `${sales_ledger.length} Order${sales_ledger.length === 1 ? '' : 's'}`;
                const tbody = document.getElementById("sales-table-body");
                tbody.innerHTML = "";

                if (!sales_ledger.length) {
                    tbody.innerHTML = `<tr><td colspan="7" class="py-6 text-center text-slate-500 italic">No past transactions found. Your next scheduled delivery will appear here upon creation.</td></tr>`;
                    return;
                }

                sales_ledger.forEach(s => {
                    const tr = document.createElement("tr");
                    tr.className = "hover:bg-slate-900/60 transition";
                    const saleDate = s.sale_date ? new Date(s.sale_date).toLocaleDateString([], {month:'short', day:'numeric', year:'numeric'}) : '—';
                    const amt = "$" + (s.amount || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                    const isPaid = s.payment_status === 'paid';

                    let carrierHtml = `<span class="text-slate-500">Pending Dispatch</span>`;
                    if (s.tracking_number) {
                        const trackUrl = SUB_PATH + s.tracking_url;
                        carrierHtml = `
                            <div>
                                <span class="font-bold text-cyan-400">${escapeHtml(s.carrier || 'Carrier')}:</span>
                                <a href="${trackUrl}" target="_blank" class="text-cyan-300 font-mono hover:underline font-semibold">${escapeHtml(s.tracking_number)}</a>
                                <div class="text-[10px] text-slate-400 uppercase">${escapeHtml(s.shipping_status || 'in_transit')}</div>
                            </div>
                        `;
                    }

                    tr.innerHTML = `
                        <td class="py-3 text-slate-400 font-mono whitespace-nowrap">${saleDate}</td>
                        <td class="py-3 whitespace-nowrap">
                            <span class="font-mono text-indigo-300 font-bold">${escapeHtml(s.order_number)}</span>
                        </td>
                        <td class="py-3 text-slate-200">
                            <div class="font-medium max-w-xs">${escapeHtml(s.items_summary)}</div>
                        </td>
                        <td class="py-3 whitespace-nowrap">
                            <span class="px-2 py-0.5 rounded text-[10px] font-bold ${isPaid ? 'bg-emerald-950 text-emerald-300 border border-emerald-700/50' : 'bg-amber-950 text-amber-300 border border-amber-700/50'}">${isPaid ? '✓ PAID' : 'UNPAID'}</span>
                        </td>
                        <td class="py-3 whitespace-nowrap">${carrierHtml}</td>
                        <td class="py-3 whitespace-nowrap">
                            <div class="flex items-center gap-2">
                                <a href="${SUB_PATH}${s.invoice_url}" target="_blank" class="text-[11px] text-indigo-400 hover:text-indigo-300 font-semibold flex items-center gap-1">
                                    <i class="fa-solid fa-file-invoice"></i> Invoice
                                </a>
                                <span class="text-slate-600">&bull;</span>
                                <a href="${SUB_PATH}${s.packing_slip_url}" target="_blank" class="text-[11px] text-amber-400 hover:text-amber-300 font-semibold flex items-center gap-1">
                                    <i class="fa-solid fa-box-open"></i> Slip
                                </a>
                            </div>
                        </td>
                        <td class="py-3 text-right font-mono font-bold text-emerald-400 whitespace-nowrap">${amt}</td>
                    `;
                    tbody.appendChild(tr);
                });
            }

            function openCardModal() {
                if (portalData && portalData.payment_method) {
                    const pm = portalData.payment_method;
                    if (pm.card_brand) document.getElementById("modal-card-brand").value = pm.card_brand.toLowerCase();
                    if (pm.card_last4) document.getElementById("modal-card-last4").value = pm.card_last4;
                    document.getElementById("modal-card-auto").checked = pm.auto_charge_enabled;
                    document.getElementById("modal-card-limit").value = pm.auto_charge_limit || "";
                }
                document.getElementById("modal-card").classList.remove("hidden");
            }

            function closeCardModal() {
                document.getElementById("modal-card").classList.add("hidden");
            }

            async function handleSaveCard(e) {
                e.preventDefault();
                const brand = document.getElementById("modal-card-brand").value;
                const last4 = document.getElementById("modal-card-last4").value;
                const isAuto = document.getElementById("modal-card-auto").checked;
                const limitVal = document.getElementById("modal-card-limit").value;
                const limit = limitVal ? parseFloat(limitVal) : null;

                try {
                    const res = await fetch(`${API_BASE}/portal/session/${PORTAL_TOKEN}/payment-method`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            card_brand: brand,
                            card_last4: last4,
                            enable_auto_charge: isAuto,
                            auto_charge_limit: limit
                        })
                    });
                    if (res.ok) {
                        closeCardModal();
                        await loadPortal();
                    } else {
                        const err = await res.json();
                        alert("Error updating payment method: " + (err.detail || res.statusText));
                    }
                } catch(err) {
                    alert("Error: " + err.message);
                }
            }

            async function detachCard() {
                if (!confirm("Are you sure you want to remove your card on file? Automatic replenishment settlements will be paused.")) return;
                try {
                    const res = await fetch(`${API_BASE}/portal/session/${PORTAL_TOKEN}/payment-method`, {
                        method: "DELETE"
                    });
                    if (res.ok) {
                        await loadPortal();
                    }
                } catch(e) {
                    alert("Error: " + e.message);
                }
            }

            function openCadenceModal() {
                document.getElementById("modal-cadence").classList.remove("hidden");
            }

            function closeCadenceModal() {
                document.getElementById("modal-cadence").classList.add("hidden");
            }

            async function handleSaveCadence(e) {
                e.preventDefault();
                const days = parseInt(document.getElementById("modal-cadence-select").value);
                try {
                    const res = await fetch(`${API_BASE}/portal/session/${PORTAL_TOKEN}/cadence`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ reorder_cadence_days: days })
                    });
                    if (res.ok) {
                        closeCadenceModal();
                        await loadPortal();
                    } else {
                        const err = await res.json();
                        alert("Error updating cadence: " + (err.detail || res.statusText));
                    }
                } catch(e) {
                    alert("Error: " + e.message);
                }
            }

            async function snoozeRestock(days) {
                if (!confirm(`Push scheduled restock delivery date forward by ${days} days?`)) return;
                try {
                    const res = await fetch(`${API_BASE}/portal/session/${PORTAL_TOKEN}/cadence`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ snooze_days: days })
                    });
                    if (res.ok) {
                        await loadPortal();
                    } else {
                        const err = await res.json();
                        alert("Error snoozing restock: " + (err.detail || res.statusText));
                    }
                } catch(e) {
                    alert("Error: " + e.message);
                }
            }

            async function accelerateRestock() {
                if (!confirm("Initiate restock order immediately? If you have auto-billing authorized, payment and autonomous supplier dispatch will trigger right now.")) return;
                try {
                    const res = await fetch(`${API_BASE}/portal/session/${PORTAL_TOKEN}/accelerate-restock`, {
                        method: "POST"
                    });
                    if (res.ok) {
                        const data = await res.json();
                        alert(data.message);
                        await loadPortal();
                    } else {
                        const err = await res.json();
                        alert("Error processing restock: " + (err.detail || res.statusText));
                    }
                } catch(e) {
                    alert("Error: " + e.message);
                }
            }

            function escapeHtml(str) {
                if (!str) return '';
                const div = document.createElement('div');
                div.innerText = str;
                return div.innerHTML;
            }

            loadPortal();
        </script>
    </body>
    </html>
    """
    safe_token = html_lib.escape(token)
    return HTMLResponse(content=html.replace("{token}", safe_token))

@app.get("/", response_class=HTMLResponse)
@app.get("/JsProject", response_class=HTMLResponse)
@app.get("/JsProject/", response_class=HTMLResponse)
async def dashboard_home():
    """
    Local-First Interactive Web Dashboard
    Allows immediate interaction with Leads, Gemini AI Agent, and HITL Queue right out of the box.
    """
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AI Sales Automation Platform - Local Console</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    </head>
    <body class="bg-slate-900 text-slate-100 min-h-screen font-sans">
        <!-- Global Notification Toast Container -->
        <div id="toast-container" class="fixed top-5 right-5 z-50 flex flex-col gap-2 max-w-md pointer-events-none"></div>

        <nav class="border-b border-slate-800 bg-slate-950 px-6 py-4 flex items-center justify-between">
            <div class="flex items-center space-x-3">
                <div class="h-9 w-9 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-white shadow-lg shadow-indigo-500/30">
                    <i class="fa-solid fa-brain"></i>
                </div>
                <div>
                    <h1 class="font-bold text-lg leading-tight">AI Sales Automation Platform</h1>
                    <p class="text-xs text-slate-400">Multi-Tenant SaaS • Powered by Google Gemini & PostgreSQL</p>
                </div>
            </div>
            <div class="flex items-center space-x-4">
                <button onclick="switchCrmMode('settings')" class="px-3 py-1.5 bg-gradient-to-r from-purple-600/30 to-indigo-600/30 hover:from-purple-600/50 hover:to-indigo-600/50 border border-purple-500/50 rounded-lg text-xs font-semibold text-purple-200 transition flex items-center gap-1.5 cursor-pointer">
                    <i class="fa-solid fa-palette text-purple-400"></i> White-Label &amp; Stripe
                </button>
                <span id="gemini-badge" class="px-3 py-1 text-xs rounded-full bg-emerald-950 border border-emerald-700/50 text-emerald-400 flex items-center gap-2">
                    <span class="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span> Gemini 1.5 Pro Active
                </span>
                <a href="/docs" target="_blank" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-xs font-semibold text-slate-300 transition flex items-center gap-1.5 border border-slate-700">
                    <i class="fa-solid fa-code"></i> OpenAPI Docs
                </a>
            </div>
        </nav>

        <!-- Dual CRM Switcher Header Bar -->
        <div class="border-b border-slate-800 bg-slate-950/80 px-6 py-3 sticky top-0 z-30 backdrop-blur">
            <div class="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">
                <!-- Switcher Tabs (4 Modes) -->
                <div class="flex items-center space-x-2 bg-slate-900 p-1 rounded-xl border border-slate-800">
                    <button id="tab-prospects" onclick="switchCrmMode('prospects')" class="px-4 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-2 bg-indigo-600 text-white shadow-md">
                        <i class="fa-solid fa-crosshairs text-indigo-200"></i>
                        <span>🎯 CRM 1: Prospects & Pipeline</span>
                    </button>
                    <button id="tab-clients" onclick="switchCrmMode('clients')" class="px-4 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800/60">
                        <i class="fa-solid fa-briefcase text-emerald-400"></i>
                        <span>💼 CRM 2: Client Accounts & Sales</span>
                        <span id="nav-badge-clients" class="px-2 py-0.5 rounded-full text-[10px] bg-slate-800 text-slate-300 font-mono">0</span>
                    </button>
                    <button id="tab-fulfillment" onclick="switchCrmMode('fulfillment')" class="px-4 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800/60">
                        <i class="fa-solid fa-truck-fast text-amber-400"></i>
                        <span>⚡ CRM 3: AI Order Filler &amp; Logistics</span>
                        <span id="nav-badge-shipments" class="px-2 py-0.5 rounded-full text-[10px] bg-amber-950/80 text-amber-300 font-mono border border-amber-700/50">0</span>
                    </button>
                    <button id="tab-settings" onclick="switchCrmMode('settings')" class="px-4 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800/60">
                        <i class="fa-solid fa-palette text-purple-400"></i>
                        <span>⚙️ CRM 4: Brand &amp; Stripe Connect</span>
                        <span id="nav-badge-payment-status" class="px-2 py-0.5 rounded-full text-[10px] bg-purple-950/80 text-purple-300 font-mono border border-purple-700/50">Ready</span>
                    </button>
                </div>

                <!-- Live Sales & Account KPIs Strip -->
                <div class="flex items-center gap-5 text-xs bg-slate-900/90 border border-slate-800/80 px-4 py-2 rounded-xl">
                    <div class="flex items-center gap-2">
                        <span class="text-slate-400 text-[11px]"><i class="fa-solid fa-chart-line text-emerald-400 mr-1"></i>Total Revenue:</span>
                        <span id="kpi-nav-rev" class="font-bold text-emerald-400 font-mono text-sm">$0.00</span>
                    </div>
                    <div class="h-4 w-px bg-slate-800"></div>
                    <div class="flex items-center gap-2">
                        <span class="text-slate-400 text-[11px]"><i class="fa-solid fa-users text-indigo-400 mr-1"></i>Active Clients:</span>
                        <span id="kpi-nav-clients" class="font-bold text-indigo-300 font-mono">0</span>
                    </div>
                    <div class="h-4 w-px bg-slate-800"></div>
                    <div class="flex items-center gap-2">
                        <span class="text-slate-400 text-[11px]"><i class="fa-solid fa-bag-shopping text-purple-400 mr-1"></i>Orders:</span>
                        <span id="kpi-nav-orders" class="font-bold text-purple-300 font-mono">0</span>
                    </div>
                    <div class="h-4 w-px bg-slate-800"></div>
                    <div class="flex items-center gap-2">
                        <span class="text-slate-400 text-[11px]"><i class="fa-solid fa-receipt text-amber-400 mr-1"></i>Avg Order:</span>
                        <span id="kpi-nav-aov" class="font-bold text-amber-300 font-mono">$0.00</span>
                    </div>
                    <div class="h-4 w-px bg-slate-800"></div>
                    <div class="flex items-center gap-2">
                        <span class="text-slate-400 text-[11px]"><i class="fa-solid fa-truck-ramp-box text-cyan-400 mr-1"></i>Bot Shipping Success:</span>
                        <span id="kpi-nav-bot-success" class="font-bold text-emerald-400 font-mono text-sm">100.0%</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- View 1: Prospects & Pipeline CRM -->
        <div id="view-prospects">
            <!-- Active Convert Won Lead Action Bar -->
            <div class="max-w-7xl mx-auto px-6 pt-6">
                <div class="p-4 rounded-2xl bg-gradient-to-r from-amber-950/80 via-slate-900 to-emerald-950/80 border-2 border-amber-500/70 shadow-2xl flex flex-col md:flex-row items-center justify-between gap-4 ring-1 ring-amber-400/20">
                    <div class="flex items-center gap-3.5">
                        <div class="h-12 w-12 rounded-xl bg-amber-500/20 text-amber-400 border border-amber-500/50 flex items-center justify-center text-2xl shadow-inner shrink-0">
                            <i class="fa-solid fa-trophy animate-pulse"></i>
                        </div>
                        <div>
                            <div class="flex items-center gap-2">
                                <span class="text-[10px] font-bold uppercase tracking-wider text-amber-300 bg-amber-900/60 px-2 py-0.5 rounded border border-amber-700/50">Deal Closer Action Bar</span>
                                <h3 class="font-bold text-sm md:text-base text-white">Convert Won Lead &amp; Transfer to Client CRM (CRM 2)</h3>
                            </div>
                            <p class="text-xs text-slate-300 mt-0.5">
                                Target Account: <strong id="action-bar-lead-name" class="text-amber-300 font-mono font-bold">Titan Logistics &amp; Distribution</strong>
                                <span class="text-slate-400 text-[11px] ml-1.5">• 1-click transfers company, contact details, notes, and records initial sales order in Client CRM.</span>
                            </p>
                        </div>
                    </div>
                    <div class="flex flex-wrap items-center gap-2.5 w-full md:w-auto shrink-0">
                        <button onclick="triggerGatherIntelligence()" class="px-3.5 py-2.5 bg-purple-600 hover:bg-purple-500 text-white font-bold rounded-xl text-xs shadow-md transition flex items-center justify-center gap-1.5 cursor-pointer border border-purple-400/40">
                            <i class="fa-solid fa-sitemap"></i> Gather BI &amp; Owners
                        </button>
                        <button onclick="triggerBookAppointment()" class="px-3.5 py-2.5 bg-teal-600 hover:bg-teal-500 text-white font-bold rounded-xl text-xs shadow-md transition flex items-center justify-center gap-1.5 cursor-pointer border border-teal-400/40">
                            <i class="fa-solid fa-calendar-check"></i> AI Book Closer Call
                        </button>
                        <button onclick="triggerExecutiveSalesProgram()" class="px-3.5 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-bold rounded-xl text-xs shadow-md transition flex items-center justify-center gap-1.5 cursor-pointer border border-blue-400/40">
                            <i class="fa-solid fa-briefcase"></i> Executive Sales Program
                        </button>
                        <button id="btn-action-fast-convert" onclick="executeFastConversion()" class="flex-1 md:flex-none px-4 py-2.5 bg-gradient-to-r from-amber-500 via-emerald-500 to-emerald-600 hover:from-amber-400 hover:to-emerald-500 text-slate-950 font-extrabold rounded-xl text-xs shadow-lg transition flex items-center justify-center gap-2 cursor-pointer transform hover:scale-[1.02] border border-amber-300/40">
                            <i class="fa-solid fa-bolt text-slate-950"></i> Transfer to Client CRM
                        </button>
                        <button onclick="openConvertModal()" class="px-3 py-2.5 bg-slate-800/90 hover:bg-slate-700 border border-amber-500/40 text-amber-300 rounded-xl text-xs font-semibold transition flex items-center justify-center gap-1.5 cursor-pointer">
                            <i class="fa-solid fa-sliders"></i> Customize Order
                        </button>
                    </div>
                </div>
            </div>
        <main class="max-w-7xl mx-auto p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
            <!-- Left Column: Tenant Auth & CRM Leads -->
            <div class="space-y-6">
                <!-- Auth & Organization Card -->
                <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-5 shadow-xl">
                    <h2 class="font-semibold text-sm uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
                        <i class="fa-solid fa-building text-indigo-400"></i> Organization & Auth
                    </h2>
                    <div id="auth-status" class="space-y-2">
                        <div class="p-3 bg-slate-900/90 rounded-lg border border-slate-700/50 text-xs">
                            <div class="flex justify-between items-center mb-1">
                                <span class="text-slate-400">Tenant:</span>
                                <span id="tenant-name" class="font-semibold text-slate-200">Acme Supply Corp</span>
                            </div>
                            <div class="flex justify-between items-center">
                                <span class="text-slate-400">User:</span>
                                <span id="user-email" class="font-mono text-indigo-300">admin@acme.com</span>
                            </div>
                        </div>
                        <button onclick="seedAndLogin()" class="w-full py-2 px-3 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-xs font-semibold shadow-md transition flex items-center justify-center gap-2">
                            <i class="fa-solid fa-key"></i> Connect / Authenticate Default Tenant
                        </button>
                    </div>
                </div>

                <!-- Create Lead Form -->
                <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-5 shadow-xl">
                    <h2 class="font-semibold text-sm uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
                        <i class="fa-solid fa-user-plus text-indigo-400"></i> Quick Add B2B Account
                    </h2>
                    <form id="lead-form" onsubmit="handleCreateLead(event)" class="space-y-3 text-xs">
                        <div>
                            <label class="block text-slate-400 mb-1">Company Name</label>
                            <input id="in-company" type="text" required value="Titan Logistics & Distribution" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-indigo-500">
                        </div>
                        <div class="grid grid-cols-2 gap-2">
                            <div>
                                <label class="block text-slate-400 mb-1">Industry</label>
                                <input id="in-industry" type="text" value="Warehousing & Janitorial" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-indigo-500">
                            </div>
                            <div>
                                <label class="block text-slate-400 mb-1">Domain</label>
                                <input id="in-domain" type="text" value="titanlogistics.com" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-indigo-500">
                            </div>
                        </div>
                        <div class="grid grid-cols-2 gap-2">
                            <div>
                                <label class="block text-slate-400 mb-1">Contact First Name</label>
                                <input id="in-fname" type="text" required value="Marcus" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-indigo-500">
                            </div>
                            <div>
                                <label class="block text-slate-400 mb-1">Contact Last Name</label>
                                <input id="in-lname" type="text" required value="Vance" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-indigo-500">
                            </div>
                        </div>
                        <div class="grid grid-cols-2 gap-2">
                            <div>
                                <label class="block text-slate-400 mb-1">Contact Email</label>
                                <input id="in-email" type="email" required value="mvance@titanlogistics.com" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-indigo-500">
                            </div>
                            <div>
                                <label class="block text-slate-400 mb-1">Job Title</label>
                                <input id="in-title" type="text" value="VP of Procurement" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-indigo-500">
                            </div>
                        </div>

                        <!-- Account Notes Field -->
                        <div>
                            <div class="flex justify-between items-center mb-1">
                                <label class="text-slate-400 flex items-center gap-1 font-medium">
                                    <i class="fa-regular fa-note-sticky text-amber-400"></i> Account Notes
                                </label>
                                <span class="text-[10px] text-slate-500">Account context & needs</span>
                            </div>
                            <textarea id="in-notes" rows="2" placeholder="e.g. 3 facility locations. Dissatisfied with current distributor delivery windows. Seeking volume tier pricing." class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-indigo-500 text-xs">Dissatisfied with incumbent vendor price hikes. Marcus is primary decision maker for all 3 hubs.</textarea>
                        </div>

                        <!-- Call Tracking (Initial / Last Call) -->
                        <div class="border-t border-slate-700/60 pt-2.5">
                            <div class="flex items-center justify-between mb-1.5">
                                <label class="text-slate-300 font-medium flex items-center gap-1.5 cursor-pointer select-none">
                                    <input type="checkbox" id="chk-log-call" checked onchange="toggleCallInputs()" class="rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-0">
                                    <i class="fa-solid fa-phone-volume text-emerald-400"></i> Track Initial / Last Call
                                </label>
                                <span class="text-[10px] text-emerald-400/90 font-mono">Enabled</span>
                            </div>
                            <div id="call-tracking-fields" class="space-y-2 mt-2 bg-slate-900/60 p-2.5 rounded-lg border border-slate-700/40">
                                <div class="grid grid-cols-2 gap-2">
                                    <div>
                                        <div class="flex justify-between items-center mb-1">
                                            <label class="text-slate-400 text-[11px]">When Last Call Was</label>
                                            <button type="button" onclick="setCallTimeNow('in-call-time')" class="text-[10px] text-indigo-400 hover:text-indigo-300">Set Now</button>
                                        </div>
                                        <input id="in-call-time" type="datetime-local" class="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-slate-100 focus:outline-none focus:border-indigo-500 text-[11px]">
                                    </div>
                                    <div>
                                        <label class="block text-slate-400 mb-1 text-[11px]">Call Outcome</label>
                                        <select id="in-call-outcome" class="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-slate-100 focus:outline-none focus:border-indigo-500 text-[11px]">
                                            <option value="connected">Connected • Spoke with Contact</option>
                                            <option value="scheduled_demo">Demo / Follow-up Scheduled</option>
                                            <option value="gatekeeper">Gatekeeper Reached</option>
                                            <option value="left_voicemail">Left Voicemail</option>
                                            <option value="busy">Busy / No Answer</option>
                                        </select>
                                    </div>
                                </div>
                                <div>
                                    <label class="block text-slate-400 mb-1 text-[11px]">What Was Said / Discussion Summary</label>
                                    <textarea id="in-call-notes" rows="2" placeholder="e.g. Spoke with Marcus. Interested in bulk commercial discounts. Follow up in 3 days." class="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-slate-100 focus:outline-none focus:border-indigo-500 text-[11px]">Spoke with Marcus for 10 mins. Confirmed annual supply budget $120k. Requested catalog comparison and discount schedule.</textarea>
                                </div>
                                <div class="flex items-center justify-between text-[11px] text-slate-400">
                                    <span>Call Duration (min):</span>
                                    <input id="in-call-duration" type="number" value="10" min="0" max="240" class="w-16 bg-slate-900 border border-slate-700 rounded p-1 text-center text-slate-100 focus:outline-none focus:border-indigo-500 text-[11px]">
                                </div>
                            </div>
                        </div>

                        <button type="submit" class="w-full py-2 bg-emerald-600 hover:bg-emerald-500 rounded text-xs font-semibold transition flex items-center justify-center gap-1.5 shadow-md">
                            <i class="fa-solid fa-plus"></i> Quick Add Account to Pipeline
                        </button>
                    </form>
                </div>

                <!-- Pipeline Leads List -->
                <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-5 shadow-xl">
                    <div class="flex justify-between items-center mb-3">
                        <h2 class="font-semibold text-sm uppercase tracking-wider text-slate-400 flex items-center gap-2">
                            <i class="fa-solid fa-users text-indigo-400"></i> Active Leads & Accounts
                        </h2>
                        <button onclick="fetchLeads()" class="text-xs text-slate-400 hover:text-white"><i class="fa-solid fa-rotate"></i></button>
                    </div>
                    <div id="leads-list" class="space-y-2 max-h-72 overflow-y-auto pr-1">
                        <p class="text-xs text-slate-500 italic">Click "Connect Default Tenant" to load leads.</p>
                    </div>
                </div>
            </div>

            <!-- Middle Column: Account Tracking & AI Sales Agent Console -->
            <div class="space-y-6">
                <!-- Account Notes & Call Tracking Hub -->
                <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-5 shadow-xl space-y-4">
                    <div class="flex justify-between items-center pb-2 border-b border-slate-700/60">
                        <h2 class="font-semibold text-sm uppercase tracking-wider text-slate-400 flex items-center gap-2">
                            <i class="fa-solid fa-clipboard-user text-indigo-400"></i> Account Notes & Call Tracking
                        </h2>
                        <span id="account-lead-pill" class="text-xs font-mono text-slate-400 italic">Select an account</span>
                    </div>

                    <div class="space-y-3">
                        <!-- Account Notes Section -->
                        <div>
                            <div class="flex justify-between items-center mb-1">
                                <label class="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                                    <i class="fa-regular fa-note-sticky text-amber-400"></i> Account Notes
                                </label>
                                <button id="btn-save-notes" onclick="saveLeadNotes()" disabled class="text-[11px] text-indigo-400 hover:text-indigo-300 font-semibold disabled:text-slate-600 flex items-center gap-1">
                                    <i class="fa-solid fa-floppy-disk"></i> Save Notes
                                </button>
                            </div>
                            <textarea id="hub-notes" rows="2" placeholder="Select an account to view and update notes..." class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"></textarea>
                        </div>

                        <!-- Last Call Summary Card -->
                        <div class="bg-slate-950/80 rounded-lg p-3 border border-slate-800 text-xs space-y-2">
                            <div class="flex justify-between items-center">
                                <span class="font-semibold text-slate-300 flex items-center gap-1.5">
                                    <i class="fa-solid fa-phone text-emerald-400"></i> When Last Call Was
                                </span>
                                <span id="last-call-badge" class="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400 border border-slate-700 font-mono">No calls logged</span>
                            </div>
                            <div>
                                <div class="text-[11px] text-slate-400 font-semibold mb-0.5">What Was Said:</div>
                                <div id="last-call-what-said" class="text-slate-300 text-xs italic bg-slate-900/60 p-2 rounded border border-slate-800/80 whitespace-pre-wrap">
Select an account from the active leads list to inspect call tracking details.
                                </div>
                            </div>
                        </div>

                        <!-- Log Follow-up Call Button & Accordion -->
                        <div class="pt-1">
                            <div class="flex justify-between items-center">
                                <button id="btn-toggle-log-call" onclick="toggleLogCallForm()" disabled class="py-1.5 px-3 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded text-xs font-semibold transition flex items-center gap-1.5">
                                    <i class="fa-solid fa-phone-plus"></i> + Log Follow-up Call
                                </button>
                                <span id="call-count-label" class="text-[11px] text-slate-400">0 Calls Recorded</span>
                            </div>

                            <!-- Log New Call Form (Hidden by default) -->
                            <form id="new-call-form" onsubmit="handleLogNewCall(event)" class="hidden mt-3 p-3 bg-slate-900 rounded-lg border border-indigo-500/40 space-y-2.5 text-xs">
                                <div class="font-semibold text-indigo-300 flex items-center justify-between text-[11px]">
                                    <span>Record New Call for <span id="log-call-target-name">Account</span></span>
                                    <button type="button" onclick="toggleLogCallForm()" class="text-slate-400 hover:text-white"><i class="fa-solid fa-xmark"></i></button>
                                </div>
                                <div class="grid grid-cols-2 gap-2">
                                    <div>
                                        <div class="flex justify-between items-center mb-1">
                                            <label class="text-slate-400 text-[11px]">Call Date/Time</label>
                                            <button type="button" onclick="setCallTimeNow('modal-call-time')" class="text-[10px] text-indigo-400">Now</button>
                                        </div>
                                        <input id="modal-call-time" type="datetime-local" required class="w-full bg-slate-950 border border-slate-700 rounded p-1.5 text-slate-100 text-[11px]">
                                    </div>
                                    <div>
                                        <label class="block text-slate-400 mb-1 text-[11px]">Outcome</label>
                                        <select id="modal-call-outcome" class="w-full bg-slate-950 border border-slate-700 rounded p-1.5 text-slate-100 text-[11px]">
                                            <option value="connected">Connected • Spoke with DM</option>
                                            <option value="scheduled_demo">Demo / Follow-up Scheduled</option>
                                            <option value="gatekeeper">Gatekeeper Reached</option>
                                            <option value="left_voicemail">Left Voicemail</option>
                                            <option value="busy">Busy / No Answer</option>
                                        </select>
                                    </div>
                                </div>
                                <div>
                                    <label class="block text-slate-400 mb-1 text-[11px]">What Was Said / Discussion Notes *</label>
                                    <textarea id="modal-call-notes" required rows="2" placeholder="Summary of what was said, questions raised, agreements..." class="w-full bg-slate-950 border border-slate-700 rounded p-1.5 text-slate-100 text-[11px]"></textarea>
                                </div>
                                <div class="flex justify-between items-center pt-1">
                                    <div class="flex items-center gap-1.5 text-[11px] text-slate-400">
                                        <span>Duration:</span>
                                        <input id="modal-call-duration" type="number" value="15" min="1" class="w-16 bg-slate-950 border border-slate-700 rounded p-1 text-center text-slate-100 text-[11px]">
                                        <span>min</span>
                                    </div>
                                    <button type="submit" class="py-1.5 px-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-semibold">
                                        Save Call Log
                                    </button>
                                </div>
                            </form>
                        </div>

                        <!-- Chronological Call History Timeline -->
                        <div class="space-y-2 pt-2 border-t border-slate-700/60">
                            <div class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                                <i class="fa-solid fa-timeline text-indigo-400"></i> Account Call History Timeline
                            </div>
                            <div id="call-history-timeline" class="space-y-2 max-h-44 overflow-y-auto pr-1 text-xs">
                                <p class="text-slate-500 italic text-[11px]">No call history recorded yet.</p>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Gemini AI Agent Actions Card -->
                <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-5 shadow-xl">
                    <div class="flex justify-between items-center mb-3">
                        <h2 class="font-semibold text-sm uppercase tracking-wider text-slate-400 flex items-center gap-2">
                            <i class="fa-solid fa-robot text-indigo-400"></i> Gemini AI Agent Actions
                        </h2>
                        <span id="selected-lead-name" class="text-xs font-mono text-indigo-300">No lead selected</span>
                    </div>

                    <div class="space-y-3">
                        <div class="grid grid-cols-2 gap-2">
                            <button id="btn-research" onclick="triggerResearch()" disabled class="py-2 px-3 bg-slate-700 text-slate-400 rounded text-xs font-semibold transition flex items-center justify-center gap-1.5">
                                <i class="fa-solid fa-magnifying-glass"></i> AI Lead Research
                            </button>
                            <button id="btn-draft" onclick="triggerDraftOutreach()" disabled class="py-2 px-3 bg-slate-700 text-slate-400 rounded text-xs font-semibold transition flex items-center justify-center gap-1.5">
                                <i class="fa-solid fa-envelope-open-text"></i> Draft Cold Outreach
                            </button>
                            <button id="btn-gather-bi" onclick="triggerGatherIntelligence()" class="py-2.5 px-3 bg-purple-600 hover:bg-purple-500 text-white rounded-lg text-xs font-bold transition flex items-center justify-center gap-1.5 cursor-pointer shadow border border-purple-400/40">
                                <i class="fa-solid fa-sitemap text-purple-200"></i> Gather BI &amp; Owners
                            </button>
                            <button id="btn-book-appointment" onclick="triggerBookAppointment()" class="py-2.5 px-3 bg-teal-600 hover:bg-teal-500 text-white rounded-lg text-xs font-bold transition flex items-center justify-center gap-1.5 cursor-pointer shadow border border-teal-400/40">
                                <i class="fa-solid fa-calendar-check text-teal-200"></i> AI Book Closer Call
                            </button>
                            <button id="btn-executive-sales" onclick="triggerExecutiveSalesProgram()" class="col-span-2 py-2.5 px-3 bg-gradient-to-r from-blue-700 via-indigo-600 to-violet-700 hover:from-blue-600 hover:to-violet-600 text-white rounded-lg text-xs font-bold transition flex items-center justify-center gap-2 shadow border border-blue-400/40 cursor-pointer">
                                <i class="fa-solid fa-briefcase text-blue-200"></i> Executive Sales Program (C-Suite Pitch &amp; Proposal)
                            </button>
                            <button id="btn-convert" onclick="executeFastConversion()" class="col-span-2 py-2 px-3 bg-gradient-to-r from-amber-600 via-amber-500 to-emerald-600 hover:from-amber-500 hover:to-emerald-500 text-white rounded-lg text-xs font-bold transition flex items-center justify-center gap-2 shadow-md cursor-pointer border border-amber-400/40">
                                <i class="fa-solid fa-trophy text-amber-200"></i> 🏆 Convert Won Lead to Client Account (CRM 2)
                            </button>
                        </div>

                        <!-- AI Output Panel -->
                        <div class="p-3 bg-slate-950 rounded-lg border border-slate-800 min-h-[220px] max-h-[300px] overflow-y-auto">
                            <div class="text-xs font-semibold text-slate-400 mb-1 flex items-center justify-between">
                                <span>Agent Reasoning & Output</span>
                                <span id="confidence-pill" class="hidden px-2 py-0.5 rounded text-[10px] bg-indigo-900/60 text-indigo-300">92% Confidence</span>
                            </div>
                            <div id="ai-output" class="text-xs text-slate-300 font-mono whitespace-pre-wrap leading-relaxed">
Select a lead from the left to trigger autonomous research or outreach email drafting.
                            </div>
                        </div>

                        <!-- Simulate Customer Inbound Reply -->
                        <div class="pt-3 border-t border-slate-700/60">
                            <label class="block text-xs text-slate-400 mb-1">Simulate Customer Inbound Reply (Test Guardrails)</label>
                            <div class="flex gap-2">
                                <input id="in-reply-text" type="text" placeholder="e.g. Can you give us a 20% discount on 500 cases?" value="Can you give us a 20% discount on 500 cases?" class="flex-1 bg-slate-900 border border-slate-700 rounded p-2 text-xs text-slate-100 focus:outline-none focus:border-indigo-500">
                                <button id="btn-simulate" onclick="simulateInbound()" disabled class="px-3 py-2 bg-purple-600 hover:bg-purple-500 disabled:bg-slate-700 disabled:text-slate-500 rounded text-xs font-semibold transition">
                                    Send Reply
                                </button>
                            </div>
                            <p class="text-[10px] text-slate-500 mt-1">Tenant policy max discount: 10%. Requesting 20% will automatically trigger a Human Assistance Request!</p>
                        </div>
                    </div>
                </div>

                <!-- Conversation History -->
                <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-5 shadow-xl">
                    <h2 class="font-semibold text-sm uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
                        <i class="fa-solid fa-comments text-indigo-400"></i> Conversation History
                    </h2>
                    <div id="conversation-thread" class="space-y-2 max-h-56 overflow-y-auto pr-1 text-xs">
                        <p class="text-slate-500 italic">No messages sent yet.</p>
                    </div>
                </div>
            </div>

            <!-- Right Column: Closer Appointments, Human-in-the-Loop (HITL) Queue & Audit Logs -->
            <div class="space-y-6">
                <!-- Scheduled Closer Appointments Card -->
                <div class="bg-slate-800/80 border border-emerald-600/40 rounded-xl p-5 shadow-xl">
                    <div class="flex justify-between items-center mb-3">
                        <h2 class="font-semibold text-sm uppercase tracking-wider text-emerald-400 flex items-center gap-2">
                            <i class="fa-solid fa-calendar-check"></i> Closer Appointments & Briefings
                        </h2>
                        <span id="appointments-count" class="px-2 py-0.5 text-xs font-bold rounded-full bg-emerald-950 text-emerald-300 border border-emerald-600/50">0 Booked</span>
                    </div>
                    <div id="appointments-list" class="space-y-2.5 max-h-72 overflow-y-auto">
                        <p class="text-xs text-slate-500 italic">No appointments scheduled yet. The AI SDR books qualified meetings here.</p>
                    </div>
                </div>

                <!-- HITL Approval Inbox -->
                <div class="bg-slate-800/80 border border-amber-600/40 rounded-xl p-5 shadow-xl">
                    <div class="flex justify-between items-center mb-3">
                        <h2 class="font-semibold text-sm uppercase tracking-wider text-amber-400 flex items-center gap-2">
                            <i class="fa-solid fa-triangle-exclamation"></i> Human Assistance Requests (HITL)
                        </h2>
                        <span id="hitl-count" class="px-2 py-0.5 text-xs font-bold rounded-full bg-amber-900/60 text-amber-300 border border-amber-600/50">0 Pending</span>
                    </div>
                    <div id="hitl-list" class="space-y-3 max-h-80 overflow-y-auto">
                        <p class="text-xs text-slate-500 italic">No pending human approval requests. System operating autonomously.</p>
                    </div>
                </div>

                <!-- Real-time Audit Stream -->
                <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-5 shadow-xl">
                    <div class="flex justify-between items-center mb-3">
                        <h2 class="font-semibold text-sm uppercase tracking-wider text-slate-400 flex items-center gap-2">
                            <i class="fa-solid fa-list-check text-indigo-400"></i> System Audit Stream
                        </h2>
                        <button onclick="fetchAuditLogs()" class="text-xs text-slate-400 hover:text-white"><i class="fa-solid fa-rotate"></i></button>
                    </div>
                    <div id="audit-list" class="space-y-2 max-h-64 overflow-y-auto pr-1 text-xs font-mono">
                        <p class="text-slate-500 italic">Audit log initialized.</p>
                    </div>
                </div>
            </div>
        </main>
        </div>

        <!-- View 2: Client Accounts & Sales CRM -->
        <div id="view-clients" class="hidden max-w-7xl mx-auto p-6 space-y-6">
            <!-- Client Sales KPI Highlights -->
            <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div class="bg-slate-800/80 border border-emerald-500/30 rounded-xl p-4 shadow-xl flex items-center justify-between">
                    <div>
                        <p class="text-xs text-slate-400 uppercase tracking-wider font-semibold">Total Sales Revenue</p>
                        <h3 id="client-stat-rev" class="text-2xl font-bold text-emerald-400 font-mono mt-1">$0.00</h3>
                        <p class="text-[10px] text-emerald-400/80 mt-1 flex items-center gap-1"><i class="fa-solid fa-arrow-trend-up"></i> Accumulated LTV</p>
                    </div>
                    <div class="h-11 w-11 rounded-xl bg-emerald-950 border border-emerald-700/50 flex items-center justify-center text-emerald-400 text-lg">
                        <i class="fa-solid fa-dollar-sign"></i>
                    </div>
                </div>

                <div class="bg-slate-800/80 border border-indigo-500/30 rounded-xl p-4 shadow-xl flex items-center justify-between">
                    <div>
                        <p class="text-xs text-slate-400 uppercase tracking-wider font-semibold">Active Client Accounts</p>
                        <h3 id="client-stat-count" class="text-2xl font-bold text-indigo-300 font-mono mt-1">0</h3>
                        <p class="text-[10px] text-indigo-400/80 mt-1 flex items-center gap-1"><i class="fa-solid fa-handshake"></i> Retained relationships</p>
                    </div>
                    <div class="h-11 w-11 rounded-xl bg-indigo-950 border border-indigo-700/50 flex items-center justify-center text-indigo-400 text-lg">
                        <i class="fa-solid fa-building-circle-check"></i>
                    </div>
                </div>

                <div class="bg-slate-800/80 border border-purple-500/30 rounded-xl p-4 shadow-xl flex items-center justify-between">
                    <div>
                        <p class="text-xs text-slate-400 uppercase tracking-wider font-semibold">Completed Orders</p>
                        <h3 id="client-stat-orders" class="text-2xl font-bold text-purple-300 font-mono mt-1">0</h3>
                        <p class="text-[10px] text-purple-400/80 mt-1 flex items-center gap-1"><i class="fa-solid fa-boxes-stacked"></i> Sales transactions</p>
                    </div>
                    <div class="h-11 w-11 rounded-xl bg-purple-950 border border-purple-700/50 flex items-center justify-center text-purple-400 text-lg">
                        <i class="fa-solid fa-cart-shopping"></i>
                    </div>
                </div>

                <div class="bg-slate-800/80 border border-amber-500/30 rounded-xl p-4 shadow-xl flex items-center justify-between">
                    <div>
                        <p class="text-xs text-slate-400 uppercase tracking-wider font-semibold">Avg Order Value (AOV)</p>
                        <h3 id="client-stat-aov" class="text-2xl font-bold text-amber-300 font-mono mt-1">$0.00</h3>
                        <p class="text-[10px] text-amber-400/80 mt-1 flex items-center gap-1"><i class="fa-solid fa-receipt"></i> Per purchase average</p>
                    </div>
                    <div class="h-11 w-11 rounded-xl bg-amber-950 border border-amber-700/50 flex items-center justify-center text-amber-400 text-lg">
                        <i class="fa-solid fa-coins"></i>
                    </div>
                </div>
            </div>

            <!-- Autonomous Replenishment Notification Banner / Control Strip -->
            <div id="replenishment-alert-banner" class="bg-gradient-to-r from-indigo-950/80 via-slate-900 to-amber-950/70 border border-amber-500/30 rounded-2xl p-4 shadow-xl flex flex-wrap items-center justify-between gap-4">
                <div class="flex items-center gap-3.5">
                    <div class="h-10 w-10 rounded-xl bg-amber-500/20 border border-amber-500/40 text-amber-400 flex items-center justify-center text-lg shadow-lg">
                        <i class="fa-solid fa-arrows-rotate animate-spin" style="animation-duration: 12s;"></i>
                    </div>
                    <div>
                        <div class="flex items-center gap-2">
                            <h4 class="font-bold text-sm text-slate-100">Autonomous Restock &amp; Replenishment Engine</h4>
                            <span id="badge-replenishment-count" class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-950 text-amber-300 border border-amber-700/50">0 Due</span>
                        </div>
                        <p class="text-xs text-slate-400 mt-0.5">Monitors client reorder cadences, predicts stockouts, and drafts 1-click Stripe reorder proposals.</p>
                    </div>
                </div>
                <div class="flex items-center gap-2">
                    <button onclick="fetchDueReplenishments()" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer">
                        <i class="fa-solid fa-rotate text-[10px]"></i> Check Due
                    </button>
                    <button onclick="processDueReplenishments()" class="px-3.5 py-1.5 bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 text-white font-semibold rounded-lg text-xs flex items-center gap-1.5 shadow-md shadow-amber-500/20 transition cursor-pointer">
                        <i class="fa-solid fa-bolt text-amber-200"></i> Process All Due Restocks
                    </button>
                </div>
            </div>

            <!-- Client Grid Layout -->
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <!-- Left Column: Quick Add Client & Directory -->
                <div class="space-y-6">
                    <!-- Quick Add Client Account Form -->
                    <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-5 shadow-xl">
                        <h2 class="font-semibold text-sm uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
                            <i class="fa-solid fa-building-circle-check text-emerald-400"></i> Quick Add Client Account
                        </h2>
                        <form id="client-form" onsubmit="handleCreateClient(event)" class="space-y-3 text-xs">
                            <div>
                                <label class="block text-slate-400 mb-1">Company / Client Name *</label>
                                <input id="in-client-name" type="text" required value="Apex Manufacturing Solutions" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-emerald-500">
                            </div>
                            <div class="grid grid-cols-2 gap-2">
                                <div>
                                    <label class="block text-slate-400 mb-1">Industry</label>
                                    <input id="in-client-industry" type="text" value="Industrial Equipment" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-emerald-500">
                                </div>
                                <div>
                                    <label class="block text-slate-400 mb-1">Domain</label>
                                    <input id="in-client-domain" type="text" value="apexmanufacturing.com" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-emerald-500">
                                </div>
                            </div>
                            <div class="grid grid-cols-2 gap-2">
                                <div>
                                    <label class="block text-slate-400 mb-1">Contact First Name *</label>
                                    <input id="in-client-fname" type="text" required value="Rachel" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-emerald-500">
                                </div>
                                <div>
                                    <label class="block text-slate-400 mb-1">Contact Last Name *</label>
                                    <input id="in-client-lname" type="text" required value="Chen" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-emerald-500">
                                </div>
                            </div>
                            <div class="grid grid-cols-2 gap-2">
                                <div>
                                    <label class="block text-slate-400 mb-1">Contact Email *</label>
                                    <input id="in-client-email" type="email" required value="rchen@apexmanufacturing.com" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-emerald-500">
                                </div>
                                <div>
                                    <label class="block text-slate-400 mb-1">Phone</label>
                                    <input id="in-client-phone" type="text" value="+1 (555) 234-8901" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-emerald-500">
                                </div>
                            </div>
                            <div class="grid grid-cols-2 gap-2">
                                <div>
                                    <label class="block text-slate-400 mb-1">Account Tier</label>
                                    <select id="in-client-tier" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-emerald-500">
                                        <option value="standard">Standard Client</option>
                                        <option value="premium">Premium Client</option>
                                        <option value="enterprise" selected>Enterprise Client</option>
                                        <option value="vip">VIP Strategic</option>
                                    </select>
                                </div>
                                <div>
                                    <label class="block text-slate-400 mb-1">Reorder Cadence (Days)</label>
                                    <input id="in-client-cadence" type="number" value="30" min="1" max="365" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-emerald-500">
                                </div>
                            </div>
                            <div>
                                <label class="block text-slate-400 mb-1">Account Notes & Terms</label>
                                <textarea id="in-client-notes" rows="2" placeholder="Contract terms, net 30 agreement, preferred logistics dock, etc." class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-emerald-500 text-xs">Standard Net 30 payment terms. Requires monthly consolidated billing for Midwest warehouse.</textarea>
                            </div>

                            <button type="submit" class="w-full py-2 bg-emerald-600 hover:bg-emerald-500 rounded text-xs font-semibold transition flex items-center justify-center gap-1.5 shadow-md">
                                <i class="fa-solid fa-plus"></i> Create Client Account
                            </button>
                        </form>
                    </div>

                    <!-- Client Accounts Directory List -->
                    <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-5 shadow-xl">
                        <div class="flex justify-between items-center mb-3">
                            <h2 class="font-semibold text-sm uppercase tracking-wider text-slate-400 flex items-center gap-2">
                                <i class="fa-solid fa-address-book text-emerald-400"></i> Active Client Accounts
                            </h2>
                            <button onclick="fetchClients()" class="text-xs text-slate-400 hover:text-white"><i class="fa-solid fa-rotate"></i></button>
                        </div>
                        <div id="clients-list" class="space-y-2 max-h-96 overflow-y-auto pr-1">
                            <p class="text-xs text-slate-500 italic">Loading client accounts...</p>
                        </div>
                    </div>
                </div>

                <!-- Middle & Right Columns (Span 2): Client Detail, Notes & Sales Ledger -->
                <div class="lg:col-span-2 space-y-6">
                    <!-- Client Detail & Relationship Management Card -->
                    <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-5 shadow-xl space-y-4">
                        <div class="flex flex-wrap justify-between items-center pb-3 border-b border-slate-700/60 gap-3">
                            <div>
                                <div class="flex items-center gap-2">
                                    <h2 id="detail-client-name" class="font-bold text-lg text-slate-100">Select a Client Account</h2>
                                    <span id="detail-client-tier" class="hidden px-2 py-0.5 rounded text-[11px] font-semibold uppercase"></span>
                                    <span id="detail-client-status" class="hidden px-2 py-0.5 rounded text-[11px] font-mono"></span>
                                </div>
                                <p id="detail-client-contact" class="text-xs text-slate-400 mt-0.5">Click an account on the left to review contracts, notes, and log sales transactions.</p>
                            </div>
                            <div class="flex items-center gap-2">
                                <button id="btn-trigger-replenishment" onclick="triggerClientReplenishmentProposal()" disabled class="py-2 px-3 bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 disabled:from-slate-700 disabled:to-slate-700 disabled:text-slate-500 text-white rounded text-xs font-semibold transition flex items-center gap-1.5 shadow-md cursor-pointer" title="Generate an autonomous restock proposal with Stripe checkout link">
                                    <i class="fa-solid fa-rotate text-amber-200"></i> Restock Proposal
                                </button>
                                <button id="btn-portal-link" onclick="openClientPortalLink()" disabled class="py-2 px-3 bg-cyan-950/80 hover:bg-cyan-900 border border-cyan-700/60 disabled:bg-slate-800 disabled:text-slate-600 text-cyan-300 rounded text-xs font-semibold transition flex items-center gap-1.5 shadow-md cursor-pointer" title="Open or copy customer self-service portal link">
                                    <i class="fa-solid fa-arrow-up-right-from-square text-cyan-300"></i> Customer Portal
                                </button>
                                <button id="btn-toggle-sale" onclick="toggleLogSaleForm()" disabled class="py-2 px-3 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded text-xs font-semibold transition flex items-center gap-2 shadow-md">
                                    <i class="fa-solid fa-plus-circle"></i> Log New Sale / Order
                                </button>
                            </div>
                        </div>

                        <!-- Client Summary Metrics Strip -->
                        <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
                            <div class="bg-slate-900/90 border border-slate-800 rounded-lg p-3">
                                <span class="text-[11px] text-slate-400">Total Account Revenue</span>
                                <div id="detail-client-rev" class="font-bold text-base text-emerald-400 font-mono mt-0.5">$0.00</div>
                            </div>
                            <div class="bg-slate-900/90 border border-slate-800 rounded-lg p-3">
                                <span class="text-[11px] text-slate-400">Orders Processed</span>
                                <div id="detail-client-orders" class="font-bold text-base text-purple-300 font-mono mt-0.5">0</div>
                            </div>
                            <div class="bg-slate-900/90 border border-slate-800 rounded-lg p-3">
                                <span class="text-[11px] text-slate-400">Reorder Cadence</span>
                                <div id="detail-client-cadence" class="font-bold text-base text-indigo-300 font-mono mt-0.5">30 Days</div>
                            </div>
                            <div class="bg-slate-900/90 border border-slate-800 rounded-lg p-3">
                                <span class="text-[11px] text-slate-400">Next Estimated Reorder</span>
                                <div id="detail-client-next-reorder" class="font-bold text-base text-amber-300 font-mono mt-0.5">—</div>
                            </div>
                        </div>

                        <!-- Card-on-File & Stripe Recurring Settlement Strip -->
                        <div class="bg-slate-900/90 border border-slate-700/60 rounded-xl p-3.5 flex flex-wrap items-center justify-between gap-3 shadow-inner">
                            <div class="flex items-center gap-3">
                                <div class="w-10 h-10 rounded-lg bg-indigo-950 border border-indigo-700/50 flex items-center justify-center text-indigo-400 text-lg shadow-sm">
                                    <i class="fa-solid fa-credit-card"></i>
                                </div>
                                <div>
                                    <div class="flex items-center gap-2">
                                        <h4 class="text-xs font-bold text-slate-200">Stripe Card-on-File &amp; Recurring Settlement</h4>
                                        <span id="detail-card-status-badge" class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-800 text-slate-400 border border-slate-700">No Card</span>
                                    </div>
                                    <p id="detail-card-description" class="text-[11px] text-slate-400 mt-0.5">Attach a corporate card for automated recurring replenishment billing.</p>
                                </div>
                            </div>
                            <div class="flex items-center gap-2">
                                <button id="btn-attach-card" onclick="openAttachCardModal()" disabled class="px-2.5 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-600 text-white rounded text-xs font-semibold flex items-center gap-1.5 transition shadow-sm cursor-pointer">
                                    <i class="fa-solid fa-plus-circle"></i> <span id="btn-attach-card-text">Store Card</span>
                                </button>
                                <button id="btn-toggle-auto-charge" onclick="toggleAutoCharge()" disabled class="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:text-slate-600 text-slate-300 border border-slate-700 rounded text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer">
                                    <i class="fa-solid fa-bolt text-amber-400"></i> Auto-Charge
                                </button>
                                <button id="btn-detach-card" onclick="detachPaymentMethod()" disabled class="hidden px-2.5 py-1.5 bg-rose-950/60 hover:bg-rose-900 text-rose-300 border border-rose-800/60 rounded text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer">
                                    <i class="fa-solid fa-trash-can"></i> Remove
                                </button>
                            </div>
                        </div>

                        <!-- Editable Client Notes & Contract Hub -->
                        <div class="space-y-2">
                            <div class="flex justify-between items-center">
                                <label class="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                                    <i class="fa-regular fa-note-sticky text-amber-400"></i> Client Account Notes & Commercial Agreements
                                </label>
                                <button id="btn-save-client-notes" onclick="saveClientNotes()" disabled class="text-[11px] text-emerald-400 hover:text-emerald-300 font-semibold disabled:text-slate-600 flex items-center gap-1">
                                    <i class="fa-solid fa-floppy-disk"></i> Save Client Notes
                                </button>
                            </div>
                            <textarea id="detail-client-notes" rows="3" placeholder="Select a client to view and update notes, pricing agreements, special shipping instructions..." class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-xs text-slate-200 focus:outline-none focus:border-emerald-500"></textarea>
                        </div>

                        <!-- Log New Sale Accordion Form -->
                        <div id="log-sale-panel" class="hidden bg-slate-900 border border-emerald-500/40 rounded-xl p-4 space-y-3">
                            <div class="flex justify-between items-center pb-2 border-b border-slate-800">
                                <h3 class="font-semibold text-xs uppercase tracking-wider text-emerald-300 flex items-center gap-2">
                                    <i class="fa-solid fa-file-invoice-dollar"></i> Record New Sales Transaction
                                </h3>
                                <button type="button" onclick="toggleLogSaleForm()" class="text-slate-400 hover:text-white"><i class="fa-solid fa-xmark"></i></button>
                            </div>
                            <form id="sale-form" onsubmit="handleLogSale(event)" class="space-y-3 text-xs">
                                <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
                                    <div>
                                        <label class="block text-slate-400 mb-1">Sale Amount ($) *</label>
                                        <input id="in-sale-amount" type="number" step="0.01" min="0.01" required value="4500.00" class="w-full bg-slate-950 border border-slate-700 rounded p-2 text-emerald-300 font-mono font-bold focus:outline-none focus:border-emerald-500">
                                    </div>
                                    <div>
                                        <label class="block text-slate-400 mb-1">Order # (Optional)</label>
                                        <input id="in-sale-ordernum" type="text" placeholder="Auto-generated if blank" class="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-100 font-mono focus:outline-none focus:border-emerald-500">
                                    </div>
                                    <div>
                                        <label class="block text-slate-400 mb-1">Sale Date</label>
                                        <input id="in-sale-date" type="datetime-local" class="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-emerald-500">
                                    </div>
                                </div>
                                <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
                                    <div>
                                        <label class="block text-slate-400 mb-1">Order Status</label>
                                        <select id="in-sale-status" class="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-emerald-500">
                                            <option value="completed" selected>Completed • Delivered</option>
                                            <option value="invoiced">Invoiced • Awaiting Payment</option>
                                            <option value="pending">Pending Fulfillment</option>
                                            <option value="cancelled">Cancelled</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label class="block text-slate-400 mb-1">Payment Method / Terms</label>
                                        <select id="in-sale-payment" class="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-emerald-500">
                                            <option value="credit_terms_30" selected>Net 30 Terms</option>
                                            <option value="credit_card">Credit Card (Stripe)</option>
                                            <option value="wire_transfer">Wire / ACH Transfer</option>
                                            <option value="check">Corporate Check</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label class="block text-slate-400 mb-1">Account Executive / Rep</label>
                                        <input id="in-sale-rep" type="text" value="Sarah Jenkins" class="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-emerald-500">
                                    </div>
                                </div>
                                <div>
                                    <label class="block text-slate-400 mb-1">Items / Products Summary *</label>
                                    <input id="in-sale-items" type="text" required value="50x Commercial HEPA Air Scrubbers, 12x Replacement Filters" class="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-emerald-500">
                                </div>
                                <div>
                                    <label class="block text-slate-400 mb-1">Transaction Notes</label>
                                    <textarea id="in-sale-notes" rows="2" placeholder="PO #, special discounts applied, freight tracking info..." class="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-emerald-500 text-xs">Customer PO-88912. Standard delivery dock B.</textarea>
                                </div>
                                <div class="flex justify-end gap-2 pt-1">
                                    <button type="button" onclick="toggleLogSaleForm()" class="py-2 px-3 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs font-semibold">Cancel</button>
                                    <button type="submit" class="py-2 px-4 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-semibold flex items-center gap-1.5 shadow-md">
                                        <i class="fa-solid fa-check"></i> Post Sale & Update Client Revenue
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>

                    <!-- Client Sales Transactions Ledger Table -->
                    <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-5 shadow-xl space-y-3">
                        <div class="flex justify-between items-center">
                            <h2 class="font-semibold text-sm uppercase tracking-wider text-slate-400 flex items-center gap-2">
                                <i class="fa-solid fa-receipt text-emerald-400"></i> Sales Transactions & Orders Ledger
                            </h2>
                            <span id="sales-count-badge" class="text-xs font-mono text-slate-400">0 Transactions</span>
                        </div>
                        <div class="overflow-x-auto">
                            <table class="w-full text-left text-xs border-collapse">
                                <thead>
                                    <tr class="border-b border-slate-700/80 text-slate-400 uppercase text-[10px] tracking-wider bg-slate-900/60">
                                        <th class="p-2.5">Date</th>
                                        <th class="p-2.5">Order #</th>
                                        <th class="p-2.5">Items Summary</th>
                                        <th class="p-2.5">Terms</th>
                                        <th class="p-2.5">Sales Rep</th>
                                        <th class="p-2.5">Bot Fulfillment &amp; Tracking</th>
                                        <th class="p-2.5">Status</th>
                                        <th class="p-2.5 text-right">Amount</th>
                                    </tr>
                                </thead>
                                <tbody id="sales-ledger-body" class="divide-y divide-slate-800 font-sans">
                                    <tr>
                                        <td colspan="8" class="p-4 text-center text-slate-500 italic">Select a client account to inspect sales history.</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- View 3: AI Order Filler & Supply Chain Logistics Hub -->
        <div id="view-fulfillment" class="hidden max-w-7xl mx-auto p-6 space-y-6">
            <!-- Order Bot Complete Shipping & Fulfillment Lifecycle Hub Banner -->
            <div class="bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 border border-indigo-500/40 rounded-2xl p-5 shadow-2xl space-y-5 ring-1 ring-indigo-400/20">
                <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-3 border-b border-slate-800/80">
                    <div class="flex items-center gap-3.5">
                        <div class="h-12 w-12 rounded-xl bg-gradient-to-br from-amber-500 to-indigo-600 text-white flex items-center justify-center text-xl shadow-lg shadow-indigo-500/20 shrink-0">
                            <i class="fa-solid fa-truck-ramp-box"></i>
                        </div>
                        <div>
                            <div class="flex items-center gap-2">
                                <span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-emerald-950 border border-emerald-600/50 text-emerald-300">Order Bot Telemetry</span>
                                <h2 class="font-bold text-base text-slate-100">Order Bot: Complete Shipping &amp; Fulfillment Success Hub</h2>
                            </div>
                            <p class="text-xs text-slate-400 mt-0.5">
                                End-to-end telemetry correlating customer sales, supplier purchasing, carrier tracking milestones, and drop shipping delivery success.
                            </p>
                        </div>
                    </div>
                    <div class="flex items-center gap-2">
                        <span class="px-3 py-1 rounded-full text-xs font-semibold bg-indigo-950 border border-indigo-700/50 text-indigo-300 flex items-center gap-1.5">
                            <span class="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span> Gemini Logistics Engine Active
                        </span>
                        <button onclick="fetchPurchaseOrders(); fetchProcurementStats();" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 cursor-pointer">
                            <i class="fa-solid fa-rotate text-amber-400"></i> Sync Bot Telemetry
                        </button>
                    </div>
                </div>

                <!-- 6 Telemetry KPI Cards -->
                <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3">
                    <!-- 1. Bot Shipping Success Rate -->
                    <div class="bg-slate-900/90 border border-emerald-500/40 rounded-xl p-3.5 shadow flex flex-col justify-between">
                        <div class="flex items-center justify-between text-slate-400 text-xs">
                            <span class="uppercase tracking-wider font-semibold text-[10px]">Shipping Success Rate</span>
                            <i class="fa-solid fa-circle-check text-emerald-400"></i>
                        </div>
                        <div class="mt-2">
                            <h3 id="bot-stat-success-rate" class="text-2xl font-extrabold text-emerald-400 font-mono">100.0%</h3>
                            <p class="text-[10px] text-emerald-400/80 mt-0.5"><span id="bot-stat-delivered-count">0</span> Orders Delivered</p>
                        </div>
                    </div>

                    <!-- 2. Sales Revenue Fulfilled -->
                    <div class="bg-slate-900/90 border border-emerald-500/30 rounded-xl p-3.5 shadow flex flex-col justify-between">
                        <div class="flex items-center justify-between text-slate-400 text-xs">
                            <span class="uppercase tracking-wider font-semibold text-[10px]">Sales Fulfilled</span>
                            <i class="fa-solid fa-hand-holding-dollar text-emerald-400"></i>
                        </div>
                        <div class="mt-2">
                            <h3 id="bot-stat-sales-rev" class="text-2xl font-extrabold text-emerald-400 font-mono">$0.00</h3>
                            <p class="text-[10px] text-slate-400 mt-0.5">Customer Sales Volume</p>
                        </div>
                    </div>

                    <!-- 3. Purchasing Cost -->
                    <div class="bg-slate-900/90 border border-amber-500/30 rounded-xl p-3.5 shadow flex flex-col justify-between">
                        <div class="flex items-center justify-between text-slate-400 text-xs">
                            <span class="uppercase tracking-wider font-semibold text-[10px]">Purchasing Spend</span>
                            <i class="fa-solid fa-cart-shopping text-amber-400"></i>
                        </div>
                        <div class="mt-2">
                            <h3 id="proc-kpi-spend" class="text-2xl font-extrabold text-amber-300 font-mono">$0.00</h3>
                            <p class="text-[10px] text-amber-400/80 mt-0.5">Supplier Procurement Cost</p>
                        </div>
                    </div>

                    <!-- 4. Gross Margin & Profit -->
                    <div class="bg-slate-900/90 border border-cyan-500/30 rounded-xl p-3.5 shadow flex flex-col justify-between">
                        <div class="flex items-center justify-between text-slate-400 text-xs">
                            <span class="uppercase tracking-wider font-semibold text-[10px]">Net Bot Margin</span>
                            <i class="fa-solid fa-chart-line text-cyan-400"></i>
                        </div>
                        <div class="mt-2">
                            <h3 id="bot-stat-margin" class="text-2xl font-extrabold text-cyan-300 font-mono">$0.00</h3>
                            <p class="text-[10px] text-cyan-400/80 mt-0.5"><span id="bot-stat-margin-pct" class="font-bold">0.0%</span> Gross Margin</p>
                        </div>
                    </div>

                    <!-- 5. Drop Shipping vs Warehouse -->
                    <div class="bg-slate-900/90 border border-purple-500/30 rounded-xl p-3.5 shadow flex flex-col justify-between">
                        <div class="flex items-center justify-between text-slate-400 text-xs">
                            <span class="uppercase tracking-wider font-semibold text-[10px]">Drop Ship / Staging</span>
                            <i class="fa-solid fa-dolly text-purple-400"></i>
                        </div>
                        <div class="mt-2">
                            <h3 id="bot-stat-dropship-split" class="text-xs font-bold text-purple-300 font-mono leading-tight">0 Drop Ships<br><span class="text-slate-400">0 Warehouse</span></h3>
                            <p class="text-[10px] text-purple-400/80 mt-0.5">Fulfillment Channels</p>
                        </div>
                    </div>

                    <!-- 6. Active In-Transit Shipments -->
                    <div class="bg-slate-900/90 border border-indigo-500/30 rounded-xl p-3.5 shadow flex flex-col justify-between">
                        <div class="flex items-center justify-between text-slate-400 text-xs">
                            <span class="uppercase tracking-wider font-semibold text-[10px]">Live In-Transit</span>
                            <i class="fa-solid fa-truck-moving text-indigo-400"></i>
                        </div>
                        <div class="mt-2">
                            <h3 id="proc-kpi-transit" class="text-2xl font-extrabold text-indigo-300 font-mono">0</h3>
                            <p class="text-[10px] text-indigo-400/80 mt-0.5">Carrier Scans Active</p>
                        </div>
                    </div>
                </div>

                <!-- Complete Shipping Success Ledger & Tracking Matrix Table -->
                <div class="bg-slate-950/70 border border-slate-800 rounded-xl p-4 space-y-3">
                    <div class="flex flex-wrap items-center justify-between gap-3">
                        <div class="flex items-center gap-2">
                            <i class="fa-solid fa-table-list text-amber-400"></i>
                            <h3 class="font-bold text-sm text-slate-200 uppercase tracking-wider">Order Bot Complete Shipping Success Ledger</h3>
                            <span id="bot-matrix-count" class="px-2 py-0.5 rounded-full text-[10px] bg-slate-800 text-slate-300 font-mono">0 Orders</span>
                        </div>
                        <div class="text-xs text-slate-400 flex flex-wrap items-center gap-3">
                            <span class="flex items-center gap-1.5"><span class="h-2 w-2 rounded-full bg-emerald-400"></span> Delivered (100% Success)</span>
                            <span class="flex items-center gap-1.5"><span class="h-2 w-2 rounded-full bg-indigo-400"></span> In Transit</span>
                            <span class="flex items-center gap-1.5"><span class="h-2 w-2 rounded-full bg-amber-400"></span> Awaiting Approval</span>
                        </div>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left text-xs border-collapse">
                            <thead>
                                <tr class="border-b border-slate-800 text-slate-400 uppercase text-[10px] tracking-wider bg-slate-900/80">
                                    <th class="p-2.5">Customer Sale</th>
                                    <th class="p-2.5">Bot Purchasing (PO)</th>
                                    <th class="p-2.5">Supplier &amp; Cost</th>
                                    <th class="p-2.5">Margin &amp; ROI</th>
                                    <th class="p-2.5">Drop Shipping Mode</th>
                                    <th class="p-2.5">Carrier Tracking</th>
                                    <th class="p-2.5">Shipping Success Status</th>
                                    <th class="p-2.5 text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody id="orders-matrix-body" class="divide-y divide-slate-800/80 font-sans">
                                <tr>
                                    <td colspan="8" class="p-4 text-center text-slate-500 italic">No purchase orders executed yet. Run the AI Order Filler below to process orders.</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- Legacy Suppliers & Units Indicator Pills for compatibility -->
            <div class="hidden">
                <span id="proc-kpi-suppliers">4</span>
                <span id="proc-kpi-units">0 Units</span>
            </div>

            <!-- Main Fulfillment Grid -->
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <!-- Left Column: AI Order Filler & Supplier Integrations -->
                <div class="space-y-6">
                    <!-- AI Order Filler Launchpad -->
                    <div class="bg-slate-800/80 border border-amber-500/50 rounded-xl p-5 shadow-2xl space-y-4 ring-1 ring-amber-400/20">
                        <div class="flex items-center justify-between">
                            <h2 class="font-bold text-sm uppercase tracking-wider text-amber-300 flex items-center gap-2">
                                <i class="fa-solid fa-robot text-amber-400"></i> AI Automated Order Filler
                            </h2>
                            <span class="px-2 py-0.5 rounded text-[10px] bg-amber-950 border border-amber-600/50 text-amber-300 font-mono">Autonomous</span>
                        </div>
                        <p class="text-xs text-slate-300 leading-relaxed">
                            Specify an inventory or customer requirement. The AI bot compares catalogs across Amazon Business, Grainger, DigiKey, and connected sites, enforces spending thresholds, places the order, and activates live carrier tracking.
                        </p>

                        <form id="form-autofill-order" onsubmit="handleAutoFillOrder(event)" class="space-y-3 text-xs">
                            <div>
                                <label class="block text-slate-300 font-semibold mb-1 flex items-center justify-between">
                                    <span>Link to Customer Sale / Order (Optional)</span>
                                    <span class="text-[10px] text-amber-400 font-normal">Auto-fills prompt &amp; drop-ship address</span>
                                </label>
                                <select id="in-autofill-client-sale" onchange="handleClientSaleSelection(this.value)" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-100 focus:outline-none focus:border-amber-500 text-xs">
                                    <option value="">⚡ Direct Autonomous Procurement (No Client Sale)</option>
                                </select>
                            </div>

                            <div>
                                <label class="block text-slate-300 font-semibold mb-1">Requirement Prompt / Items to Order *</label>
                                <textarea id="in-autofill-prompt" rows="3" required placeholder="E.g. Order 25 boxes of heavy-duty corrugated cartons (24x18x18) and 6 rolls of 3M shipping packaging tape" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-amber-500 leading-relaxed">Order 25 boxes of heavy-duty corrugated moving &amp; shipping boxes (24x18x18) and 6 rolls of 3M packaging tape</textarea>
                            </div>

                            <div class="grid grid-cols-2 gap-2">
                                <div>
                                    <label class="block text-slate-400 mb-1">Fulfillment Mode</label>
                                    <select id="in-autofill-dest-type" onchange="toggleFulfillmentMode(this.value)" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-amber-500 text-xs">
                                        <option value="warehouse">🏭 Warehouse Restock</option>
                                        <option value="customer_dropship">🚀 Customer Drop Ship</option>
                                    </select>
                                </div>
                                <div>
                                    <label class="block text-slate-400 mb-1">Target Supplier</label>
                                    <select id="in-autofill-supplier" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-amber-500 text-xs">
                                        <option value="auto">⚡ AI Auto-Route (Best Price/Stock)</option>
                                        <option value="amazon_business">Amazon Business (Packaging &amp; Office)</option>
                                        <option value="grainger">W.W. Grainger (Industrial MRO &amp; Safety)</option>
                                        <option value="digikey">DigiKey (Electronics &amp; Hardware)</option>
                                        <option value="mcmaster">McMaster-Carr (Raw Parts &amp; CAD)</option>
                                    </select>
                                </div>
                            </div>

                            <div class="grid grid-cols-2 gap-2">
                                <div>
                                    <label class="block text-slate-400 mb-1">Max Auto-Spend ($)</label>
                                    <input id="in-autofill-budget" type="number" step="10" value="500.00" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-amber-300 font-mono focus:outline-none focus:border-amber-500 text-xs">
                                </div>
                                <div>
                                    <label class="block text-slate-400 mb-1">Destination Address</label>
                                    <input id="in-autofill-destination" type="text" value="Main Logistics Warehouse (Bay 4), 100 Supply Chain Blvd" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-slate-200 focus:outline-none focus:border-amber-500 text-xs">
                                </div>
                            </div>

                            <div class="p-2.5 rounded-lg bg-slate-900/90 border border-slate-700/60 flex items-center justify-between text-[11px] text-slate-400">
                                <span><i class="fa-solid fa-shield-halved text-emerald-400 mr-1"></i> Guardrail Protection:</span>
                                <span class="text-amber-300 font-medium">Orders &gt; $500 halt for approval</span>
                            </div>

                            <button id="btn-run-autofill" type="submit" class="w-full py-2.5 px-4 bg-gradient-to-r from-amber-600 via-amber-500 to-emerald-600 hover:from-amber-500 hover:to-emerald-500 text-slate-950 font-extrabold rounded-xl shadow-lg transition flex items-center justify-center gap-2 cursor-pointer transform hover:scale-[1.01]">
                                <i class="fa-solid fa-cart-shopping"></i> Run AI Auto-Fill &amp; Purchase
                            </button>
                        </form>

                        <!-- Live Agent Log Container -->
                        <div id="autofill-agent-log" class="hidden p-3 rounded-lg bg-slate-950 border border-amber-500/40 text-[11px] font-mono text-amber-200/90 space-y-1">
                            <!-- Populated dynamically -->
                        </div>
                    </div>

                    <!-- Connected Business Supply Websites -->
                    <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-5 shadow-xl space-y-3">
                        <div class="flex items-center justify-between">
                            <h2 class="font-semibold text-sm uppercase tracking-wider text-slate-300 flex items-center gap-2">
                                <i class="fa-solid fa-globe text-indigo-400"></i> Connected Supply Portals
                            </h2>
                            <button onclick="openAddSupplierModal()" class="px-2.5 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-xs font-semibold transition flex items-center gap-1 cursor-pointer">
                                <i class="fa-solid fa-plus"></i> Add Website
                            </button>
                        </div>
                        <div id="suppliers-list" class="space-y-2 max-h-72 overflow-y-auto pr-1">
                            <!-- Populated via JS -->
                        </div>
                    </div>
                </div>

                <!-- Right 2 Columns: Live Purchase Orders & Real-time Shipment Tracking -->
                <div class="lg:col-span-2 space-y-6">
                    <!-- POs and Tracking Center -->
                    <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-5 shadow-xl space-y-4">
                        <div class="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-700/60">
                            <div>
                                <h2 class="font-bold text-base text-slate-100 flex items-center gap-2">
                                    <i class="fa-solid fa-truck-fast text-amber-400"></i> Purchase Orders &amp; Shipment Tracking
                                </h2>
                                <p class="text-xs text-slate-400">Autonomous purchasing ledger, live carrier tracking milestones, and inventory receipts</p>
                            </div>
                            <div class="flex items-center gap-2">
                                <button onclick="fetchPurchaseOrders(); fetchProcurementStats();" class="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 cursor-pointer">
                                    <i class="fa-solid fa-rotate"></i> Refresh Feed
                                </button>
                            </div>
                        </div>

                        <!-- Purchase Orders Feed Container -->
                        <div id="orders-feed-container" class="space-y-4">
                            <div class="p-8 text-center text-slate-500 italic">
                                <i class="fa-solid fa-box-open text-3xl mb-2 block text-slate-600"></i>
                                Loading active purchase orders and live shipment trackings...
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Modal: Add New Business Supply Website -->
        <div id="modal-add-supplier" class="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
            <div class="bg-slate-900 border border-indigo-500/50 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
                <div class="flex justify-between items-center pb-3 border-b border-slate-800">
                    <h3 class="font-bold text-sm text-slate-100 flex items-center gap-2">
                        <i class="fa-solid fa-plus-circle text-indigo-400"></i> Connect New Supply Website / API
                    </h3>
                    <button onclick="closeAddSupplierModal()" class="text-slate-400 hover:text-white"><i class="fa-solid fa-xmark text-lg"></i></button>
                </div>
                <form id="form-new-supplier" onsubmit="handleCreateSupplier(event)" class="space-y-3 text-xs">
                    <div>
                        <label class="block text-slate-400 mb-1">Company / Supplier Name *</label>
                        <input id="in-sup-name" type="text" required placeholder="E.g. Fastenal Industrial Supply" class="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-indigo-500">
                    </div>
                    <div>
                        <label class="block text-slate-400 mb-1">Website URL *</label>
                        <input id="in-sup-url" type="url" required placeholder="https://www.fastenal.com" class="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-indigo-500">
                    </div>
                    <div class="grid grid-cols-2 gap-2">
                        <div>
                            <label class="block text-slate-400 mb-1">Adapter / Access Type</label>
                            <select id="in-sup-adapter" class="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-indigo-500">
                                <option value="web_automation">Web Automation / Crawler</option>
                                <option value="api">Direct B2B REST API</option>
                                <option value="punchout">cXML / PunchOut</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-slate-400 mb-1">Category Specialty</label>
                            <input id="in-sup-category" type="text" value="Fasteners &amp; MRO" class="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-indigo-500">
                        </div>
                    </div>
                    <div>
                        <label class="block text-slate-400 mb-1">Integration Notes / API Credentials (Optional)</label>
                        <textarea id="in-sup-notes" rows="2" placeholder="Account #, Net-30 billing terms, or automated cart instructions" class="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-indigo-500"></textarea>
                    </div>
                    <div class="flex justify-end gap-2 pt-2 border-t border-slate-800">
                        <button type="button" onclick="closeAddSupplierModal()" class="py-2 px-3 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs font-semibold">Cancel</button>
                        <button type="submit" class="py-2 px-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-xs font-semibold flex items-center gap-1.5 shadow-md">
                            <i class="fa-solid fa-plug"></i> Save Supplier Portal
                        </button>
                    </div>
                </form>
            </div>
        </div>

        <!-- Modal: Dispatch / Ship Purchased Inventory to Client -->
        <div id="modal-dispatch" class="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
            <div class="bg-slate-900 border border-emerald-500/50 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
                <div class="flex justify-between items-center pb-3 border-b border-slate-800">
                    <h3 class="font-bold text-sm text-slate-100 flex items-center gap-2">
                        <i class="fa-solid fa-dolly text-emerald-400"></i> Dispatch Purchased Inventory Outbound
                    </h3>
                    <button onclick="closeDispatchModal()" class="text-slate-400 hover:text-white"><i class="fa-solid fa-xmark text-lg"></i></button>
                </div>
                <form id="form-dispatch-shipment" onsubmit="handleDispatchShipment(event)" class="space-y-3 text-xs">
                    <input type="hidden" id="dispatch-po-id" value="">
                    <div class="p-3 bg-slate-950 rounded-lg border border-slate-800 text-xs">
                        <span class="text-slate-400 block text-[11px] mb-0.5">Purchased Order Source:</span>
                        <div id="dispatch-po-label" class="font-mono font-bold text-amber-300">PO-XXXX</div>
                        <div id="dispatch-items-label" class="text-slate-300 text-[11px] mt-1">Items in inventory</div>
                    </div>
                    <div class="grid grid-cols-2 gap-2">
                        <div>
                            <label class="block text-slate-400 mb-1">Outbound Carrier</label>
                            <select id="dispatch-carrier" class="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-emerald-500">
                                <option value="UPS">UPS Ground</option>
                                <option value="FEDEX">FedEx Express</option>
                                <option value="USPS">USPS Priority</option>
                                <option value="FREIGHT">Direct LTL Freight</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-slate-400 mb-1">Assign to Client Account</label>
                            <select id="dispatch-client-select" onchange="populateClientAddress(this.value)" class="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-emerald-500">
                                <option value="">Select Client Account...</option>
                            </select>
                        </div>
                    </div>
                    <div>
                        <label class="block text-slate-400 mb-1">Destination Address *</label>
                        <input id="dispatch-address" type="text" required placeholder="E.g. 742 Evergreen Terrace, Springfield, OR" class="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-emerald-500">
                    </div>
                    <div class="flex justify-end gap-2 pt-2 border-t border-slate-800">
                        <button type="button" onclick="closeDispatchModal()" class="py-2 px-3 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs font-semibold">Cancel</button>
                        <button type="submit" class="py-2 px-4 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-semibold flex items-center gap-1.5 shadow-md">
                            <i class="fa-solid fa-paper-plane"></i> Dispatch &amp; Generate Manifest
                        </button>
                    </div>
                </form>
            </div>
        </div>

        <!-- Modal: Convert Won Lead to Active Client Account -->
        <div id="convert-modal" class="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
            <div class="bg-slate-900 border border-amber-500/50 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
                <div class="flex justify-between items-center pb-3 border-b border-slate-800">
                    <div class="flex items-center gap-2">
                        <div class="h-8 w-8 rounded-lg bg-amber-500/20 text-amber-400 flex items-center justify-center font-bold text-base">
                            <i class="fa-solid fa-trophy"></i>
                        </div>
                        <div>
                            <h3 class="font-bold text-sm text-slate-100">Convert Lead to Active Client Account</h3>
                            <p class="text-[11px] text-slate-400">Promotes prospect from CRM 1 into CRM 2 Sales Ledger</p>
                        </div>
                    </div>
                    <button onclick="closeConvertModal()" class="text-slate-400 hover:text-white"><i class="fa-solid fa-xmark text-lg"></i></button>
                </div>

                <form id="convert-lead-form" onsubmit="handleConvertLead(event)" class="space-y-3 text-xs">
                    <div class="p-3 bg-slate-950 rounded-lg border border-slate-800">
                        <span class="text-slate-400 block text-[11px] mb-1">Converting Prospect:</span>
                        <div id="modal-convert-lead-name" class="font-bold text-sm text-indigo-300">Company Name</div>
                        <div id="modal-convert-lead-contact" class="text-slate-400 text-xs mt-0.5">Contact: Marcus Vance (mvance@titanlogistics.com)</div>
                    </div>

                    <div class="grid grid-cols-2 gap-3">
                        <div>
                            <label class="block text-slate-400 mb-1">Client Tier</label>
                            <select id="modal-convert-tier" class="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-amber-500">
                                <option value="standard">Standard Client</option>
                                <option value="premium">Premium Client</option>
                                <option value="enterprise" selected>Enterprise Client</option>
                                <option value="vip">VIP Strategic</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-slate-400 mb-1">Reorder Cadence (Days)</label>
                            <input id="modal-convert-cadence" type="number" value="30" min="1" max="365" class="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-amber-500">
                        </div>
                    </div>

                    <div class="border-t border-slate-800 pt-3">
                        <label class="block font-semibold text-slate-300 mb-1 flex items-center gap-1.5">
                            <i class="fa-solid fa-cart-arrow-down text-emerald-400"></i> Record Initial Closed Sale (Optional)
                        </label>
                        <div class="grid grid-cols-2 gap-2 mt-1.5">
                            <div>
                                <label class="block text-slate-400 text-[11px] mb-0.5">Sale Amount ($)</label>
                                <input id="modal-convert-sale-amount" type="number" step="0.01" value="7500.00" class="w-full bg-slate-950 border border-slate-700 rounded p-2 text-emerald-300 font-mono font-bold focus:outline-none focus:border-amber-500">
                            </div>
                            <div>
                                <label class="block text-slate-400 text-[11px] mb-0.5">Items Summary</label>
                                <input id="modal-convert-sale-items" type="text" value="Initial B2B Supply Agreement" class="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-amber-500">
                            </div>
                        </div>
                    </div>

                    <div>
                        <label class="block text-slate-400 mb-1">Conversion Notes & Terms</label>
                        <textarea id="modal-convert-notes" rows="2" class="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-amber-500 text-xs">Won via cold outreach negotiation. 3-location commercial account.</textarea>
                    </div>

                    <div class="flex justify-end gap-2 pt-2 border-t border-slate-800">
                        <button type="button" onclick="closeConvertModal()" class="py-2 px-3 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs font-semibold">Cancel</button>
                        <button type="submit" class="py-2 px-4 bg-amber-600 hover:bg-amber-500 text-white rounded text-xs font-semibold flex items-center gap-1.5 shadow-md">
                            <i class="fa-solid fa-trophy"></i> Complete Conversion & Launch CRM 2
                        </button>
                    </div>
                </form>
            </div>
        </div>

        <!-- Modal: Attach / Update Card on File for Client Account -->
        <div id="modal-attach-card" class="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
            <div class="bg-slate-900 border border-indigo-500/50 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
                <div class="flex justify-between items-center pb-3 border-b border-slate-800">
                    <div class="flex items-center gap-2 text-indigo-400">
                        <i class="fa-solid fa-credit-card text-lg"></i>
                        <h3 class="font-bold text-sm text-slate-100">Store Corporate Card on File</h3>
                    </div>
                    <button onclick="closeAttachCardModal()" class="text-slate-400 hover:text-white cursor-pointer"><i class="fa-solid fa-xmark text-lg"></i></button>
                </div>
                <form id="form-attach-card" onsubmit="handleAttachPaymentMethod(event)" class="space-y-3 text-xs">
                    <div>
                        <label class="block text-slate-400 mb-1">Card Brand</label>
                        <select id="in-card-brand" class="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-indigo-500">
                            <option value="visa" selected>Visa Corporate</option>
                            <option value="mastercard">Mastercard Commercial</option>
                            <option value="amex">American Express Corporate</option>
                            <option value="discover">Discover</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-slate-400 mb-1">Last 4 Digits</label>
                        <input id="in-card-last4" type="text" maxlength="4" pattern="[0-9]{4}" required placeholder="4242" value="4242" class="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-100 font-mono focus:outline-none focus:border-indigo-500">
                    </div>
                    <div class="pt-1">
                        <label class="flex items-center gap-2 cursor-pointer">
                            <input id="in-auto-charge-enabled" type="checkbox" checked class="w-4 h-4 rounded text-indigo-600 bg-slate-950 border-slate-700">
                            <span class="text-slate-200 font-semibold">Enable Automatic Settlement on Restock Due</span>
                        </label>
                        <p class="text-[11px] text-slate-400 ml-6 mt-0.5">When enabled, the replenishment engine charges this card automatically when cadence restocks trigger.</p>
                    </div>
                    <div>
                        <label class="block text-slate-400 mb-1">Safety Auto-Charge Limit ($) (Optional)</label>
                        <input id="in-auto-charge-limit" type="number" step="1" min="1" placeholder="e.g. 5000 (Leave blank for unlimited)" class="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-100 font-mono focus:outline-none focus:border-indigo-500">
                        <p class="text-[10px] text-slate-500 mt-0.5">Orders exceeding this limit will pause for manual authorization before charging.</p>
                    </div>
                    <div class="flex justify-end gap-2 pt-3 border-t border-slate-800">
                        <button type="button" onclick="closeAttachCardModal()" class="py-2 px-3 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs font-semibold cursor-pointer">Cancel</button>
                        <button type="submit" class="py-2 px-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-xs font-semibold flex items-center gap-1.5 shadow-md cursor-pointer">
                            <i class="fa-solid fa-lock text-indigo-200"></i> Authorize &amp; Store Card
                        </button>
                    </div>
                </form>
            </div>
        </div>

        <!-- CRM 4: Multi-Tenant White-Labeling & Stripe Connect Hub -->
        <div id="view-settings" class="hidden max-w-7xl mx-auto p-6 space-y-6">
            <!-- Header Banner -->
            <div class="bg-gradient-to-r from-purple-950/40 via-indigo-950/40 to-slate-900 border border-purple-500/40 rounded-2xl p-5 shadow-2xl space-y-4 ring-1 ring-purple-400/20">
                <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-3 border-b border-slate-800/80">
                    <div class="flex items-center gap-3.5">
                        <div class="h-12 w-12 rounded-xl bg-gradient-to-br from-purple-500 to-indigo-600 text-white flex items-center justify-center text-xl shadow-lg shadow-purple-500/20 shrink-0">
                            <i class="fa-solid fa-palette"></i>
                        </div>
                        <div>
                            <div class="flex items-center gap-2">
                                <h1 class="font-black text-xl text-white tracking-wide">Multi-Tenant White-Labeling &amp; Stripe Connect</h1>
                                <span id="badge-tenant-live" class="px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wider bg-purple-950 text-purple-300 border border-purple-700/50">
                                    Enterprise Tenant
                                </span>
                            </div>
                            <p class="text-xs text-slate-400 mt-0.5">
                                Customize your client-facing brand identity, custom portal styling, and configure your direct merchant Stripe payment gateways.
                            </p>
                        </div>
                    </div>
                    <div class="flex items-center gap-2.5">
                        <button onclick="fetchOrganizationSettings()" class="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition flex items-center gap-1.5 cursor-pointer">
                            <i class="fa-solid fa-rotate" id="btn-settings-refresh-icon"></i> Reload
                        </button>
                        <button onclick="saveOrganizationSettings()" class="px-4 py-2 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-bold transition flex items-center gap-2 shadow-lg shadow-purple-600/30 cursor-pointer">
                            <i class="fa-solid fa-floppy-disk"></i> Save All Settings
                        </button>
                    </div>
                </div>

                <!-- Status Ribbon -->
                <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                    <div class="p-3 bg-slate-900/90 rounded-xl border border-slate-800 flex items-center justify-between">
                        <span class="text-slate-400"><i class="fa-solid fa-building text-purple-400 mr-1.5"></i>Active Tenant:</span>
                        <span id="label-settings-org-id" class="font-mono font-bold text-slate-200 text-[11px]">Loading...</span>
                    </div>
                    <div class="p-3 bg-slate-900/90 rounded-xl border border-slate-800 flex items-center justify-between">
                        <span class="text-slate-400"><i class="fa-solid fa-credit-card text-emerald-400 mr-1.5"></i>Payment Gateway:</span>
                        <span id="label-settings-payment-mode" class="font-semibold text-emerald-400 flex items-center gap-1">
                            <i class="fa-solid fa-circle-check"></i> Simulation Ready
                        </span>
                    </div>
                    <div class="p-3 bg-slate-900/90 rounded-xl border border-slate-800 flex items-center justify-between">
                        <span class="text-slate-400"><i class="fa-solid fa-eye text-cyan-400 mr-1.5"></i>Portal Theme:</span>
                        <span id="label-settings-accent-preview" class="font-mono font-semibold text-cyan-300 flex items-center gap-1.5">
                            <span id="swatch-accent-small" class="h-3 w-3 rounded-full inline-block bg-indigo-600"></span> <span id="text-accent-hex-val">#4f46e5</span>
                        </span>
                    </div>
                </div>
            </div>

            <!-- Two-Column Form & Real-Time Preview -->
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <!-- Left 2 Cols: Configuration Inputs -->
                <div class="lg:col-span-2 space-y-6">
                    <!-- Brand & Portal Styling Section -->
                    <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 space-y-5 shadow-xl">
                        <div class="flex items-center justify-between pb-3 border-b border-slate-800">
                            <h2 class="font-bold text-sm text-slate-200 flex items-center gap-2">
                                <i class="fa-solid fa-brush text-purple-400"></i> Corporate Brand &amp; Portal Theming
                            </h2>
                            <span class="text-[11px] text-slate-500">Public Customer Facing</span>
                        </div>

                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                            <div>
                                <label class="block text-slate-400 mb-1.5 font-semibold">Tenant Business Name</label>
                                <input type="text" id="setting-org-name" placeholder="Acme Logistics Inc" class="w-full bg-slate-950 border border-slate-700 rounded-xl p-2.5 text-slate-100 focus:outline-none focus:border-purple-500 text-xs">
                            </div>
                            <div>
                                <label class="block text-slate-400 mb-1.5 font-semibold">Customer-Facing Brand Name</label>
                                <input type="text" id="setting-brand-name" placeholder="Acme Supply Co." oninput="updateLiveBrandPreview()" class="w-full bg-slate-950 border border-slate-700 rounded-xl p-2.5 text-slate-100 focus:outline-none focus:border-purple-500 text-xs">
                            </div>
                        </div>

                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                            <div>
                                <label class="block text-slate-400 mb-1.5 font-semibold">Brand Logo URL</label>
                                <input type="text" id="setting-brand-logo-url" placeholder="https://example.com/logo.png" oninput="updateLiveBrandPreview()" class="w-full bg-slate-950 border border-slate-700 rounded-xl p-2.5 text-slate-100 focus:outline-none focus:border-purple-500 text-xs font-mono">
                            </div>
                            <div>
                                <label class="block text-slate-400 mb-1.5 font-semibold">Brand Accent Color</label>
                                <div class="flex items-center gap-2">
                                    <input type="color" id="setting-accent-picker" value="#4f46e5" oninput="syncAccentColorFromPicker(this.value)" class="h-9 w-12 rounded-lg bg-slate-950 border border-slate-700 cursor-pointer p-0.5">
                                    <input type="text" id="setting-accent-hex" value="#4f46e5" oninput="syncAccentColorFromText(this.value)" placeholder="#4f46e5" class="flex-1 bg-slate-950 border border-slate-700 rounded-xl p-2.5 text-slate-100 font-mono text-xs focus:outline-none focus:border-purple-500">
                                </div>
                            </div>
                        </div>

                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                            <div>
                                <label class="block text-slate-400 mb-1.5 font-semibold">Support Email Address</label>
                                <input type="email" id="setting-support-email" placeholder="support@acmesupply.com" oninput="updateLiveBrandPreview()" class="w-full bg-slate-950 border border-slate-700 rounded-xl p-2.5 text-slate-100 focus:outline-none focus:border-purple-500 text-xs">
                            </div>
                            <div>
                                <label class="block text-slate-400 mb-1.5 font-semibold">Support Phone Number</label>
                                <input type="text" id="setting-support-phone" placeholder="+1 (800) 555-0199" oninput="updateLiveBrandPreview()" class="w-full bg-slate-950 border border-slate-700 rounded-xl p-2.5 text-slate-100 focus:outline-none focus:border-purple-500 text-xs">
                            </div>
                        </div>

                        <div class="space-y-3 text-xs">
                            <div>
                                <label class="block text-slate-400 mb-1.5 font-semibold">Public Tracking Portal Custom Notice (Optional)</label>
                                <textarea id="setting-tracking-notice" rows="2" placeholder="e.g. Orders placed after 4 PM EST ship the next business morning. Need emergency expedited dispatch? Call our hotline." oninput="updateLiveBrandPreview()" class="w-full bg-slate-950 border border-slate-700 rounded-xl p-2.5 text-slate-100 focus:outline-none focus:border-purple-500 text-xs"></textarea>
                            </div>
                            <div>
                                <label class="block text-slate-400 mb-1.5 font-semibold">Custom Invoicing &amp; Portal Footer Note</label>
                                <input type="text" id="setting-custom-footer" placeholder="Thank you for partnering with Acme Supply Co. Direct B2B Distribution Division." oninput="updateLiveBrandPreview()" class="w-full bg-slate-950 border border-slate-700 rounded-xl p-2.5 text-slate-100 focus:outline-none focus:border-purple-500 text-xs">
                            </div>
                        </div>
                    </div>

                    <!-- Stripe Connect & Payment Gateway Section -->
                    <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 space-y-5 shadow-xl">
                        <div class="flex items-center justify-between pb-3 border-b border-slate-800">
                            <div class="flex items-center gap-2">
                                <div class="h-6 w-6 rounded bg-indigo-500/20 text-indigo-400 flex items-center justify-center text-xs">
                                    <i class="fa-brands fa-stripe"></i>
                                </div>
                                <h2 class="font-bold text-sm text-slate-200">Merchant Stripe Connect &amp; Direct Gateways</h2>
                            </div>
                            <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-indigo-950 text-indigo-300 border border-indigo-700/50">
                                Direct Deposit Mode
                            </span>
                        </div>

                        <p class="text-xs text-slate-400">
                            Configure your Stripe merchant API keys so replenishment orders and hosted checkout payments deposit directly into your company's merchant bank account. If left blank, the platform uses frictionless local simulation.
                        </p>

                        <div class="space-y-4 text-xs">
                            <div>
                                <label class="block text-slate-400 mb-1.5 font-semibold flex items-center justify-between">
                                    <span>Stripe Publishable Key</span>
                                    <span class="text-[10px] text-slate-500 font-normal">Begins with pk_live_ or pk_test_</span>
                                </label>
                                <input type="text" id="setting-stripe-pub-key" placeholder="pk_live_51M..." class="w-full bg-slate-950 border border-slate-700 rounded-xl p-2.5 text-slate-100 font-mono focus:outline-none focus:border-indigo-500 text-xs">
                            </div>

                            <div>
                                <label class="block text-slate-400 mb-1.5 font-semibold flex items-center justify-between">
                                    <span>Stripe Secret Key</span>
                                    <span class="text-[10px] text-slate-500 font-normal">Encrypted at rest • Begins with sk_live_ or sk_test_</span>
                                </label>
                                <div class="relative">
                                    <input type="password" id="setting-stripe-sec-key" placeholder="••••••••••••••••••••••••••••" class="w-full bg-slate-950 border border-slate-700 rounded-xl p-2.5 text-slate-100 font-mono focus:outline-none focus:border-indigo-500 text-xs pr-10">
                                    <button type="button" onclick="toggleStripeSecretVisibility()" class="absolute right-3 top-2.5 text-slate-400 hover:text-slate-200 cursor-pointer">
                                        <i class="fa-solid fa-eye" id="icon-toggle-secret"></i>
                                    </button>
                                </div>
                            </div>

                            <div>
                                <label class="block text-slate-400 mb-1.5 font-semibold flex items-center justify-between">
                                    <span>Stripe Webhook Signing Secret</span>
                                    <span class="text-[10px] text-slate-500 font-normal">Begins with whsec_</span>
                                </label>
                                <input type="password" id="setting-stripe-webhook-sec" placeholder="whsec_..." class="w-full bg-slate-950 border border-slate-700 rounded-xl p-2.5 text-slate-100 font-mono focus:outline-none focus:border-indigo-500 text-xs">
                            </div>

                            <div class="p-3 bg-slate-950 rounded-xl border border-slate-800 space-y-2">
                                <div class="flex items-center justify-between">
                                    <span class="text-slate-400 font-semibold text-[11px]"><i class="fa-solid fa-network-wired text-indigo-400 mr-1"></i> Your Stripe Webhook Endpoint URL:</span>
                                    <button onclick="copyWebhookEndpointUrl()" class="text-indigo-400 hover:text-indigo-300 text-[11px] font-semibold flex items-center gap-1 cursor-pointer">
                                        <i class="fa-solid fa-copy"></i> Copy URL
                                    </button>
                                </div>
                                <div class="font-mono text-[11px] text-slate-300 bg-slate-900 p-2 rounded-lg border border-slate-800/80 break-all select-all" id="text-webhook-url-display">
                                    https://therealbonz.com/JsProject/api/v1/payments/stripe/webhook
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Multi-Channel Notification Gateways (Twilio SMS & SendGrid Email) -->
                    <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 space-y-5 shadow-xl">
                        <div class="flex items-center justify-between pb-3 border-b border-slate-800">
                            <div class="flex items-center gap-2">
                                <div class="h-6 w-6 rounded bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-xs">
                                    <i class="fa-solid fa-paper-plane"></i>
                                </div>
                                <h2 class="font-bold text-sm text-slate-200">Live Notification Gateways (Twilio &amp; SendGrid)</h2>
                            </div>
                            <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-950 text-emerald-300 border border-emerald-700/50 flex items-center gap-1">
                                <i class="fa-solid fa-tower-broadcast text-emerald-400"></i> Multi-Channel Engine
                            </span>
                        </div>

                        <p class="text-xs text-slate-400">
                            Configure your enterprise Twilio and SendGrid credentials to dispatch real-time SMS and branded transactional emails upon replenishment restocks, invoice payments, and delivery checkpoint scans. If left blank, notifications operate in local simulation mode.
                        </p>

                        <!-- Two Sub-Sections: Twilio SMS and SendGrid Email -->
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-5 pt-1">
                            <!-- Twilio SMS Box -->
                            <div class="p-4 bg-slate-950 rounded-xl border border-slate-800 space-y-3.5">
                                <div class="flex items-center justify-between pb-2 border-b border-slate-800">
                                    <span class="font-bold text-xs text-slate-200 flex items-center gap-1.5">
                                        <i class="fa-solid fa-comment-sms text-cyan-400"></i> Twilio SMS Gateway
                                    </span>
                                    <span id="badge-twilio-status" class="text-[10px] font-mono text-slate-400">Simulation</span>
                                </div>

                                <div class="space-y-3 text-xs">
                                    <div>
                                        <label class="block text-slate-400 mb-1 font-semibold">Account SID</label>
                                        <input type="text" id="setting-twilio-sid" placeholder="ACxxxxxxxxxxxxxxxxxxxxxxxx" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-100 font-mono text-xs focus:outline-none focus:border-cyan-500">
                                    </div>
                                    <div>
                                        <label class="block text-slate-400 mb-1 font-semibold">Auth Token</label>
                                        <input type="password" id="setting-twilio-token" placeholder="••••••••••••••••" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-100 font-mono text-xs focus:outline-none focus:border-cyan-500">
                                    </div>
                                    <div>
                                        <label class="block text-slate-400 mb-1 font-semibold">Twilio Phone Number</label>
                                        <input type="text" id="setting-twilio-phone" placeholder="+15551234567" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-100 font-mono text-xs focus:outline-none focus:border-cyan-500">
                                    </div>
                                    <div class="pt-1">
                                        <button type="button" onclick="promptSendTestSms()" class="w-full py-2 bg-slate-800 hover:bg-slate-700 text-cyan-300 font-semibold rounded-lg text-xs border border-slate-700 transition flex items-center justify-center gap-1.5 cursor-pointer">
                                            <i class="fa-solid fa-mobile-screen"></i> Send Test SMS
                                        </button>
                                    </div>
                                </div>
                            </div>

                            <!-- SendGrid Email Box -->
                            <div class="p-4 bg-slate-950 rounded-xl border border-slate-800 space-y-3.5">
                                <div class="flex items-center justify-between pb-2 border-b border-slate-800">
                                    <span class="font-bold text-xs text-slate-200 flex items-center gap-1.5">
                                        <i class="fa-solid fa-envelope text-purple-400"></i> SendGrid / Postmark Email
                                    </span>
                                    <span id="badge-sendgrid-status" class="text-[10px] font-mono text-slate-400">Simulation</span>
                                </div>

                                <div class="space-y-3 text-xs">
                                    <div>
                                        <label class="block text-slate-400 mb-1 font-semibold">API Key</label>
                                        <input type="password" id="setting-sendgrid-key" placeholder="SG.xxxxxxxxxxxxxxxx" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-100 font-mono text-xs focus:outline-none focus:border-purple-500">
                                    </div>
                                    <div>
                                        <label class="block text-slate-400 mb-1 font-semibold">Sender Email Address</label>
                                        <input type="email" id="setting-email-from" placeholder="orders@yourcompany.com" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-100 text-xs focus:outline-none focus:border-purple-500">
                                    </div>
                                    <div>
                                        <label class="block text-slate-400 mb-1 font-semibold">Sender Display Name</label>
                                        <input type="text" id="setting-email-name" placeholder="Acme Logistics Dispatch" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-100 text-xs focus:outline-none focus:border-purple-500">
                                    </div>
                                    <div class="pt-1">
                                        <button type="button" onclick="promptSendTestEmail()" class="w-full py-2 bg-slate-800 hover:bg-slate-700 text-purple-300 font-semibold rounded-lg text-xs border border-slate-700 transition flex items-center justify-center gap-1.5 cursor-pointer">
                                            <i class="fa-solid fa-paper-plane"></i> Send Test Branded Email
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Recent Notifications Dispatch Table Strip -->
                        <div class="pt-2 border-t border-slate-800">
                            <div class="flex items-center justify-between mb-2">
                                <span class="font-bold text-xs text-slate-300 flex items-center gap-1.5">
                                    <i class="fa-solid fa-clock-rotate-left text-indigo-400"></i> Recent Multi-Channel Dispatches
                                </span>
                                <button type="button" onclick="fetchNotificationHistory()" class="text-indigo-400 hover:text-indigo-300 text-[11px] font-semibold cursor-pointer">
                                    <i class="fa-solid fa-rotate-right"></i> Refresh Log
                                </button>
                            </div>
                            <div id="settings-notifications-log" class="space-y-1.5 max-h-36 overflow-y-auto pr-1 text-xs">
                                <div class="text-center py-2 text-slate-500 text-[11px] italic">Loading recent notifications...</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Right Col: Interactive Live Customer Experience Preview -->
                <div class="space-y-6">
                    <div class="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 space-y-4 shadow-xl sticky top-20">
                        <div class="flex items-center justify-between pb-2 border-b border-slate-800">
                            <h3 class="font-bold text-xs uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                                <i class="fa-solid fa-desktop text-cyan-400"></i> Live Customer Experience Preview
                            </h3>
                            <span class="px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-800/60 font-semibold">
                                Live Interactive
                            </span>
                        </div>

                        <!-- Mini Customer Tracking Portal Card -->
                        <div class="bg-slate-950 rounded-xl p-4 border border-slate-800 space-y-3 shadow-inner">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center gap-2">
                                    <div id="preview-logo-box" class="h-8 w-8 rounded-lg bg-indigo-600/20 border border-indigo-500/40 text-indigo-400 flex items-center justify-center font-bold text-xs overflow-hidden shrink-0">
                                        <i class="fa-solid fa-truck-ramp-box" id="preview-default-icon"></i>
                                    </div>
                                    <div>
                                        <div class="font-bold text-xs text-white" id="preview-brand-name">Acme Supply Co.</div>
                                        <div class="text-[10px] text-slate-400">Delivery Tracking #SO-SAMPLE</div>
                                    </div>
                                </div>
                                <span id="preview-status-pill" class="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-950 text-indigo-300 border border-indigo-700/50">
                                    In Transit (60%)
                                </span>
                            </div>

                            <div id="preview-notice-box" class="hidden p-2 rounded-lg bg-indigo-950/40 border border-indigo-800/50 text-[10px] text-indigo-200">
                                Notice will appear here
                            </div>

                            <!-- Mini Stepper Bar -->
                            <div class="space-y-1 pt-1">
                                <div class="flex justify-between text-[10px] text-slate-400">
                                    <span>Carrier: FedEx Freight</span>
                                    <span class="font-mono text-emerald-400">On Schedule</span>
                                </div>
                                <div class="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                                    <div id="preview-progress-bar" class="h-full bg-indigo-500 rounded-full" style="width: 60%;"></div>
                                </div>
                            </div>
                        </div>

                        <!-- Mini Hosted Stripe Checkout Card -->
                        <div class="bg-slate-950 rounded-xl p-4 border border-slate-800 space-y-3 shadow-inner">
                            <div class="flex items-center justify-between text-xs">
                                <span class="text-slate-400">Sample Restock Order:</span>
                                <span class="font-bold font-mono text-emerald-400">$1,485.00</span>
                            </div>
                            <button id="preview-btn-pay" class="w-full py-2.5 bg-indigo-600 hover:opacity-90 text-white font-bold rounded-xl text-xs shadow-lg flex items-center justify-center gap-2 cursor-pointer transition">
                                <i class="fa-solid fa-lock text-[11px]"></i> <span>Pay with <span id="preview-btn-brand-name">Acme Supply Co.</span></span>
                            </button>
                            <div class="text-center text-[10px] text-slate-500">
                                Support: <span id="preview-support-email" class="text-indigo-400">support@acmesupply.com</span>
                            </div>
                        </div>

                        <div class="pt-2">
                            <button onclick="saveOrganizationSettings()" class="w-full py-3 bg-gradient-to-r from-purple-600 via-indigo-600 to-purple-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-bold rounded-xl shadow-xl shadow-purple-600/30 transition flex items-center justify-center gap-2 cursor-pointer">
                                <i class="fa-solid fa-check-double"></i> Save Brand &amp; Gateway Settings
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Executive Closer Briefing Modal -->
        <div id="modal-closer-briefing" class="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm hidden flex items-center justify-center p-4">
            <div class="bg-slate-900 border border-slate-700 rounded-2xl max-w-xl w-full p-6 space-y-4 shadow-2xl">
                <div class="flex justify-between items-center pb-2 border-b border-slate-800">
                    <h3 class="font-bold text-base text-slate-100 flex items-center gap-2">
                        <i class="fa-solid fa-file-signature text-emerald-400"></i> Executive Closer Briefing Dossier
                    </h3>
                    <button onclick="closeBriefingModal()" class="text-slate-400 hover:text-slate-200 cursor-pointer"><i class="fa-solid fa-xmark text-lg"></i></button>
                </div>
                <div id="briefing-modal-content" class="space-y-3 text-xs text-slate-300 max-h-[70vh] overflow-y-auto pr-1">
                    <!-- Populated via JS -->
                </div>
                <div class="flex justify-end pt-2 border-t border-slate-800">
                    <button onclick="closeBriefingModal()" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-semibold cursor-pointer">Close</button>
                </div>
            </div>
        </div>

        <script>
            const BASE_PREFIX = window.location.pathname.startsWith("/JsProject") ? "/JsProject" : "";
            const API_BASE = BASE_PREFIX + "/api/v1";

            let authToken = "";
            let currentOrgId = "";
            let selectedLead = null;
            let currentConvId = null;
            let currentCrmMode = "prospects";
            let selectedClient = null;
            let allClients = [];

            async function seedAndLogin() {
                try {
                    // Try login first
                    let res = await fetch(API_BASE + "/auth/login", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ email: "admin@acme.com", password: "Password123!" })
                    });
                    if (!res.ok) {
                        // Register if not exists
                        res = await fetch(API_BASE + "/auth/register", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({
                                email: "admin@acme.com",
                                password: "Password123!",
                                full_name: "Sarah Jenkins",
                                organization_name: "Acme Supply Corp"
                            })
                        });
                    }
                    const data = await res.json();
                    authToken = data.access_token;
                    currentOrgId = data.organization_id;
                    document.getElementById("tenant-name").innerText = "Acme Supply Corp";
                    document.getElementById("user-email").innerText = data.email;
                    
                    fetchLeads();
                    fetchAppointments();
                    fetchHitlRequests();
                    fetchAuditLogs();
                    fetchClientStats();
                    fetchClients();
                    fetchDueReplenishments();
                    fetchProcurementStats();
                    fetchSuppliers();
                    fetchPurchaseOrders();
                    fetchOrganizationSettings();
                } catch(e) {
                    alert("Error authenticating: " + e.message);
                }
            }

            function setCallTimeNow(id) {
                const now = new Date();
                now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
                const elem = document.getElementById(id);
                if (elem) elem.value = now.toISOString().slice(0, 16);
            }

            function toggleCallInputs() {
                const chk = document.getElementById("chk-log-call");
                const fields = document.getElementById("call-tracking-fields");
                if (chk && fields) {
                    fields.classList.toggle("hidden", !chk.checked);
                    if (chk.checked && !document.getElementById("in-call-time").value) {
                        setCallTimeNow("in-call-time");
                    }
                }
            }

            function toggleLogCallForm() {
                const form = document.getElementById("new-call-form");
                if (form) {
                    form.classList.toggle("hidden");
                    if (!form.classList.contains("hidden")) {
                        setCallTimeNow("modal-call-time");
                        document.getElementById("modal-call-notes").focus();
                    }
                }
            }

            function escapeHtml(text) {
                if (!text) return "";
                return String(text)
                    .replace(/&/g, "&amp;")
                    .replace(/</g, "&lt;")
                    .replace(/>/g, "&gt;")
                    .replace(/"/g, "&quot;")
                    .replace(/'/g, "&#039;");
            }

            function showToast(title, message, icon = "fa-circle-check", type = "success") {
                const container = document.getElementById("toast-container");
                if (!container) return;
                const toast = document.createElement("div");
                const bgClass = type === "success" ? "bg-emerald-950/95 border-emerald-500 text-emerald-100" : "bg-indigo-950/95 border-indigo-500 text-indigo-100";
                toast.className = `p-4 rounded-xl border ${bgClass} shadow-2xl backdrop-blur-md flex items-start gap-3 pointer-events-auto transform transition-all duration-300 translate-y-2 opacity-0`;
                toast.innerHTML = `
                    <div class="text-xl ${type === 'success' ? 'text-emerald-400' : 'text-indigo-400'} pt-0.5">
                        <i class="fa-solid ${icon}"></i>
                    </div>
                    <div class="flex-1">
                        <div class="font-bold text-xs text-white">${escapeHtml(title)}</div>
                        <div class="text-[11px] opacity-90 mt-0.5 leading-relaxed">${escapeHtml(message)}</div>
                    </div>
                    <button onclick="this.parentElement.remove()" class="text-slate-400 hover:text-white text-xs cursor-pointer"><i class="fa-solid fa-xmark"></i></button>
                `;
                container.appendChild(toast);
                requestAnimationFrame(() => {
                    toast.classList.remove("translate-y-2", "opacity-0");
                });
                setTimeout(() => {
                    toast.classList.add("opacity-0", "translate-y-2");
                    setTimeout(() => toast.remove(), 400);
                }, 6000);
            }

            async function autoSeedDemoLead() {
                try {
                    const payload = {
                        company_name: "Titan Logistics & Distribution",
                        industry: "Warehousing & Logistics",
                        company_domain: "titanlogistics.com",
                        contact_first_name: "Marcus",
                        contact_last_name: "Vance",
                        contact_email: "mvance@titanlogistics.com",
                        contact_title: "VP of Supply Chain",
                        notes: "Spoke with Marcus regarding 3 regional fulfillment centers. Confirmed budget $120k for commercial supplies. Ready for client onboarding and initial supply order.",
                        last_call_at: new Date().toISOString(),
                        last_call_outcome: "scheduled_demo",
                        last_call_notes: "Marcus confirmed pricing approval from executive board. Requested contract to be finalized today.",
                        call_duration_minutes: 15
                    };
                    const createRes = await fetch(API_BASE + "/crm/leads", {
                        method: "POST",
                        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId },
                        body: JSON.stringify(payload)
                    });
                    if (createRes.ok) {
                        const res = await fetch(API_BASE + "/crm/leads", {
                            headers: { "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId }
                        });
                        if (res.ok) return await res.json();
                    }
                } catch(e) {
                    console.error("Error auto-seeding demo lead:", e);
                }
                return [];
            }

            async function fetchLeads() {
                if (!authToken) return;
                try {
                    const res = await fetch(API_BASE + "/crm/leads", {
                        headers: { "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId }
                    });
                    let leads = await res.json();
                    const container = document.getElementById("leads-list");
                    container.innerHTML = "";

                    if (!leads || !leads.length) {
                        leads = await autoSeedDemoLead();
                    }

                    if (!leads || !leads.length) {
                        container.innerHTML = "<p class='text-xs text-slate-500 italic'>No leads yet. Create one above!</p>";
                        return;
                    }
                    leads.forEach(l => {
                        const div = document.createElement("div");
                        const isSelected = selectedLead && selectedLead.id === l.id;
                        div.className = `p-2.5 rounded-lg bg-slate-900/80 border ${isSelected ? 'border-amber-500/80 bg-slate-900' : 'border-slate-700/60 hover:border-indigo-500/60'} cursor-pointer transition space-y-1`;
                        div.onclick = () => selectLead(l);

                        let callBadgeHtml = "";
                        if (l.last_call_at) {
                            const callDate = new Date(l.last_call_at).toLocaleString([], {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'});
                            const outcomeLabel = (l.last_call_outcome || 'connected').replace(/_/g, ' ');
                            callBadgeHtml = `
                                <div class="mt-1.5 p-1.5 rounded bg-slate-950/80 border border-slate-800 text-[10px]">
                                    <div class="flex justify-between items-center text-emerald-400 font-mono">
                                        <span><i class="fa-solid fa-phone text-[9px] mr-1"></i>Last call: ${callDate}</span>
                                        <span class="text-[9px] text-indigo-300 font-sans uppercase">${escapeHtml(outcomeLabel)}</span>
                                    </div>
                                    ${l.last_call_notes ? `<div class="text-slate-400 italic truncate mt-0.5 font-sans">"${escapeHtml(l.last_call_notes)}"</div>` : ''}
                                </div>
                            `;
                        } else {
                            callBadgeHtml = `<div class="mt-1 text-[10px] text-slate-500 italic"><i class="fa-solid fa-phone-slash mr-1"></i>No calls logged</div>`;
                        }

                        div.innerHTML = `
                            <div class="flex justify-between items-center">
                                <div>
                                    <div class="font-semibold text-slate-200 text-xs">${escapeHtml(l.company ? l.company.name : 'Account')}</div>
                                    <div class="text-[11px] text-slate-400">${escapeHtml(l.contact ? l.contact.first_name + ' ' + l.contact.last_name : '')} • <span class="text-indigo-400 font-mono">${escapeHtml(l.pipeline_stage)}</span></div>
                                </div>
                                <span class="text-xs font-bold px-2 py-0.5 rounded bg-slate-800 text-indigo-300 border border-slate-700">${l.lead_score} pts</span>
                            </div>
                            ${l.notes ? `<div class="text-[10px] text-amber-300/90 truncate flex items-center gap-1"><i class="fa-regular fa-note-sticky text-amber-400"></i> ${escapeHtml(l.notes)}</div>` : ''}
                            ${callBadgeHtml}
                        `;
                        container.appendChild(div);
                    });

                    // Auto-select lead so selectedLead is never null on load
                    if (!selectedLead || !leads.some(l => l.id === selectedLead.id)) {
                        selectLead(leads[0]);
                    } else {
                        const refreshed = leads.find(l => l.id === selectedLead.id);
                        selectLead(refreshed || leads[0]);
                    }
                } catch(e) {
                    console.error("Failed to fetch leads:", e);
                }
            }

            async function selectLead(lead) {
                selectedLead = lead;
                const companyName = lead.company ? lead.company.name : 'Lead';
                document.getElementById("selected-lead-name").innerText = companyName + " (" + lead.pipeline_stage + ")";
                document.getElementById("account-lead-pill").innerText = companyName + " • " + lead.pipeline_stage.toUpperCase();
                document.getElementById("log-call-target-name").innerText = companyName;
                const barLeadName = document.getElementById("action-bar-lead-name");
                if (barLeadName) barLeadName.innerText = companyName + " (" + lead.pipeline_stage.toUpperCase() + ")";

                // Buttons activation
                document.getElementById("btn-research").disabled = false;
                document.getElementById("btn-research").className = "py-2 px-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-xs font-semibold transition flex items-center justify-center gap-1.5 cursor-pointer";
                document.getElementById("btn-draft").disabled = false;
                document.getElementById("btn-draft").className = "py-2 px-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-semibold transition flex items-center justify-center gap-1.5 cursor-pointer";
                const btnBi = document.getElementById("btn-gather-bi");
                if (btnBi) {
                    btnBi.disabled = false;
                    btnBi.className = "py-2 px-3 bg-indigo-700 hover:bg-indigo-600 text-white rounded text-xs font-semibold transition flex items-center justify-center gap-1.5 cursor-pointer";
                }
                const btnApt = document.getElementById("btn-book-appointment");
                if (btnApt) {
                    btnApt.disabled = false;
                    btnApt.className = "py-2 px-3 bg-emerald-700 hover:bg-emerald-600 text-white rounded text-xs font-semibold transition flex items-center justify-center gap-1.5 cursor-pointer";
                }
                const btnExec = document.getElementById("btn-executive-sales");
                if (btnExec) {
                    btnExec.disabled = false;
                    btnExec.className = "col-span-2 py-2.5 px-3 bg-gradient-to-r from-blue-700 via-indigo-600 to-violet-700 hover:from-blue-600 hover:to-violet-600 text-white rounded-lg text-xs font-bold transition flex items-center justify-center gap-2 shadow border border-blue-400/40 cursor-pointer";
                }
                document.getElementById("btn-simulate").disabled = false;
                document.getElementById("btn-save-notes").disabled = false;
                document.getElementById("btn-toggle-log-call").disabled = false;
                const btnConvert = document.getElementById("btn-convert");
                if (btnConvert) {
                    btnConvert.disabled = false;
                    btnConvert.className = "col-span-2 py-2 px-3 bg-gradient-to-r from-amber-600 via-amber-500 to-emerald-600 hover:from-amber-500 hover:to-emerald-500 text-white rounded-lg text-xs font-bold transition flex items-center justify-center gap-2 shadow-md cursor-pointer border border-amber-400/40";
                }

                // Populate Account Notes
                document.getElementById("hub-notes").value = lead.notes || (lead.company && lead.company.notes ? lead.company.notes : "");

                // Render Last Call Summary
                const badge = document.getElementById("last-call-badge");
                const whatSaid = document.getElementById("last-call-what-said");
                if (lead.last_call_at) {
                    const callDate = new Date(lead.last_call_at).toLocaleString([], {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'});
                    const outcome = (lead.last_call_outcome || 'connected').toUpperCase().replace(/_/g, ' ');
                    badge.innerText = callDate + " • " + outcome;
                    badge.className = "px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-700/60 font-mono";
                    whatSaid.innerText = lead.last_call_notes || "Call logged without notes.";
                    whatSaid.className = "text-slate-200 text-xs italic bg-slate-900/80 p-2 rounded border border-slate-700/60 whitespace-pre-wrap font-sans";
                } else {
                    badge.innerText = "No calls logged";
                    badge.className = "px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400 border border-slate-700 font-mono";
                    whatSaid.innerText = "No calls recorded yet for this account. Click '+ Log Follow-up Call' above to record discussion notes.";
                    whatSaid.className = "text-slate-500 text-xs italic bg-slate-900/40 p-2 rounded border border-slate-800 whitespace-pre-wrap";
                }

                // Fetch call logs and conversation
                fetchCallsForLead(lead.id);
                fetchConversation(lead.id);
            }

            async function fetchCallsForLead(leadId) {
                try {
                    const res = await fetch(API_BASE + "/crm/leads/" + leadId + "/calls", {
                        headers: { "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId }
                    });
                    if (!res.ok) return;
                    const calls = await res.json();
                    const countLabel = document.getElementById("call-count-label");
                    if (countLabel) countLabel.innerText = calls.length + " Call" + (calls.length === 1 ? "" : "s") + " Recorded";
                    const container = document.getElementById("call-history-timeline");
                    container.innerHTML = "";
                    if (!calls.length) {
                        container.innerHTML = "<p class='text-slate-500 italic text-[11px]'>No call history recorded yet.</p>";
                        return;
                    }
                    calls.forEach(c => {
                        const callDate = new Date(c.called_at).toLocaleString([], {month:'short', day:'numeric', year:'numeric', hour:'2-digit', minute:'2-digit'});
                        const outcomeClass = (c.outcome === 'connected' || c.outcome === 'scheduled_demo') ? 'bg-emerald-950 text-emerald-300 border-emerald-700/60' : 'bg-slate-800 text-slate-300 border-slate-700';
                        const div = document.createElement("div");
                        div.className = "p-2.5 rounded-lg bg-slate-900/90 border border-slate-800 text-xs space-y-1.5 shadow-sm";
                        div.innerHTML = `
                            <div class="flex justify-between items-center text-[11px]">
                                <span class="font-semibold text-slate-200 flex items-center gap-1.5">
                                    <i class="fa-solid fa-phone-volume text-emerald-400"></i> ${escapeHtml(c.caller_name || 'Sales Rep')}
                                </span>
                                <span class="text-[10px] text-slate-400 font-mono">${callDate}</span>
                            </div>
                            <div class="flex items-center gap-2">
                                <span class="px-1.5 py-0.5 rounded text-[10px] border ${outcomeClass}">${escapeHtml(c.outcome.replace(/_/g, ' '))}</span>
                                ${c.duration_minutes ? `<span class="text-[10px] text-slate-400 font-mono">${c.duration_minutes} min duration</span>` : ''}
                            </div>
                            <div class="text-slate-300 text-[11px] whitespace-pre-wrap bg-slate-950/70 p-2 rounded border border-slate-800/80 font-sans">
                                ${escapeHtml(c.notes)}
                            </div>
                            ${c.next_steps ? `<div class="text-[10px] text-indigo-300"><i class="fa-solid fa-arrow-right mr-1"></i>Next: ${escapeHtml(c.next_steps)}</div>` : ''}
                        `;
                        container.appendChild(div);
                    });
                } catch(e) {
                    console.error("Failed to fetch calls:", e);
                }
            }

            async function saveLeadNotes() {
                if (!selectedLead) return;
                const notesVal = document.getElementById("hub-notes").value;
                const btn = document.getElementById("btn-save-notes");
                try {
                    const res = await fetch(API_BASE + "/crm/leads/" + selectedLead.id, {
                        method: "PATCH",
                        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId },
                        body: JSON.stringify({ notes: notesVal })
                    });
                    if (res.ok) {
                        selectedLead.notes = notesVal;
                        fetchLeads();
                        fetchAuditLogs();
                        const origHtml = btn.innerHTML;
                        btn.innerHTML = `<i class="fa-solid fa-check text-emerald-400"></i> Saved!`;
                        setTimeout(() => { btn.innerHTML = origHtml; }, 1800);
                    }
                } catch(e) {
                    alert("Error saving notes: " + e.message);
                }
            }

            async function handleLogNewCall(e) {
                e.preventDefault();
                if (!selectedLead) return;
                const callTimeVal = document.getElementById("modal-call-time").value;
                const outcome = document.getElementById("modal-call-outcome").value;
                const notes = document.getElementById("modal-call-notes").value;
                const duration = parseInt(document.getElementById("modal-call-duration").value) || 0;

                const payload = {
                    called_at: callTimeVal ? new Date(callTimeVal).toISOString() : new Date().toISOString(),
                    outcome: outcome,
                    notes: notes,
                    duration_minutes: duration
                };

                try {
                    const res = await fetch(API_BASE + "/crm/leads/" + selectedLead.id + "/calls", {
                        method: "POST",
                        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId },
                        body: JSON.stringify(payload)
                    });
                    if (res.ok) {
                        const callLog = await res.json();
                        selectedLead.last_call_at = callLog.called_at;
                        selectedLead.last_call_notes = callLog.notes;
                        selectedLead.last_call_outcome = callLog.outcome;

                        // Update Last Call card
                        const callDate = new Date(callLog.called_at).toLocaleString([], {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'});
                        document.getElementById("last-call-badge").innerText = callDate + " • " + callLog.outcome.toUpperCase();
                        document.getElementById("last-call-badge").className = "px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-700/60 font-mono";
                        const whatSaid = document.getElementById("last-call-what-said");
                        whatSaid.innerText = callLog.notes;
                        whatSaid.className = "text-slate-200 text-xs italic bg-slate-900/80 p-2 rounded border border-slate-700/60 whitespace-pre-wrap font-sans";

                        // Reset modal form
                        document.getElementById("modal-call-notes").value = "";
                        document.getElementById("new-call-form").classList.add("hidden");

                        fetchCallsForLead(selectedLead.id);
                        fetchLeads();
                        fetchAuditLogs();
                    } else {
                        const err = await res.json();
                        alert("Error saving call: " + (err.detail || res.statusText));
                    }
                } catch(e) {
                    alert("Error saving call log: " + e.message);
                }
            }

            async function handleCreateLead(e) {
                e.preventDefault();
                if (!authToken) { alert("Please connect default tenant first!"); return; }

                const logCallChecked = document.getElementById("chk-log-call").checked;
                const callTimeVal = document.getElementById("in-call-time").value;

                const payload = {
                    company_name: document.getElementById("in-company").value,
                    industry: document.getElementById("in-industry").value,
                    company_domain: document.getElementById("in-domain").value,
                    contact_first_name: document.getElementById("in-fname").value,
                    contact_last_name: document.getElementById("in-lname").value,
                    contact_email: document.getElementById("in-email").value,
                    contact_title: document.getElementById("in-title") ? document.getElementById("in-title").value : "VP of Procurement",
                    notes: document.getElementById("in-notes").value
                };

                if (logCallChecked) {
                    payload.last_call_at = callTimeVal ? new Date(callTimeVal).toISOString() : new Date().toISOString();
                    payload.last_call_outcome = document.getElementById("in-call-outcome").value;
                    payload.last_call_notes = document.getElementById("in-call-notes").value;
                    payload.call_duration_minutes = parseInt(document.getElementById("in-call-duration").value) || 0;
                }

                const res = await fetch(API_BASE + "/crm/leads", {
                    method: "POST",
                    headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId },
                    body: JSON.stringify(payload)
                });
                if (res.ok) {
                    const newLead = await res.json();
                    fetchLeads();
                    selectLead(newLead);
                    fetchAuditLogs();
                } else {
                    const err = await res.json();
                    alert("Failed to create lead: " + (err.detail || res.statusText));
                }
            }

            async function triggerResearch() {
                if (!selectedLead) return;
                document.getElementById("ai-output").innerText = "Analyzing prospect via Google Gemini AI...";
                const res = await fetch(API_BASE + "/agent/leads/" + selectedLead.id + "/research", {
                    method: "POST",
                    headers: { "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId }
                });
                const data = await res.json();
                document.getElementById("ai-output").innerText = 
                    "LEAD SCORE: " + data.lead_score + "/100 (Confidence: " + Math.round(data.confidence_score * 100) + "%)\\n\\n" +
                    "RECOMMENDED ANGLE:\\n" + data.suggested_angle + "\\n\\n" +
                    "OVERVIEW:\\n" + data.company_overview + "\\n\\n" +
                    "PAIN POINTS:\\n" + data.pain_points.map(p => "• " + p).join("\\n");
                fetchLeads();
                fetchAuditLogs();
            }

            async function triggerDraftOutreach() {
                if (!selectedLead) return;
                document.getElementById("ai-output").innerText = "Drafting grounded cold email via Google Gemini...";
                const res = await fetch(API_BASE + "/agent/leads/" + selectedLead.id + "/draft-outreach", {
                    method: "POST",
                    headers: { "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId }
                });
                const data = await res.json();
                document.getElementById("ai-output").innerText = 
                    "SUBJECT: " + data.subject + "\\n\\n" +
                    data.body_text + "\\n\\n" +
                    "[Grounded Call to Action: " + data.call_to_action + "]";
                
                const thread = document.getElementById("conversation-thread");
                thread.innerHTML = `
                    <div class="p-2.5 rounded bg-indigo-950/70 border border-indigo-700/50">
                        <div class="font-bold text-[11px] text-indigo-300 mb-1">Outbound AI Email Draft (Sent)</div>
                        <div class="text-xs text-slate-200">${data.body_text.replace(/\\n/g, '<br>')}</div>
                    </div>
                `;
                fetchAuditLogs();
            }

            async function triggerGatherIntelligence() {
                if (!selectedLead) return;
                document.getElementById("ai-output").innerText = "Uncovering corporate ownership & key decision-makers via Google Gemini BI...";
                try {
                    const res = await fetch(API_BASE + "/agent/leads/" + selectedLead.id + "/gather-intelligence", {
                        method: "POST",
                        headers: { "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId }
                    });
                    if (!res.ok) {
                        const err = await res.json();
                        throw new Error(err.detail || res.statusText);
                    }
                    const data = await res.json();
                    let dmText = (data.key_decision_makers || []).map(d => `  • ${d.first_name} ${d.last_name} — ${d.job_title} [Role: ${d.decision_maker_role.toUpperCase()}]\n    Email: ${d.email || 'N/A'} | Phone: ${d.phone || 'N/A'} (Confidence: ${Math.round(d.confidence_score * 100)}%)`).join("\n");
                    
                    document.getElementById("ai-output").innerText =
                        "=== BUSINESS INTELLIGENCE & DECISION MAKERS ===\n\n" +
                        "COMPANY: " + data.company_name + " (" + (data.estimated_employee_count || 'Regional Business') + ")\n" +
                        "OWNERSHIP: " + data.ownership_structure + "\n\n" +
                        "IDENTIFIED DECISION-MAKERS (Auto-Created in CRM Contacts):\n" + dmText + "\n\n" +
                        "PROCUREMENT SIGNALS:\n" + (data.procurement_signals || []).map(s => "  • " + s).join("\n") + "\n\n" +
                        "SUGGESTED ANGLE:\n" + data.suggested_angle;
                    
                    fetchLeads();
                    fetchAuditLogs();
                } catch(e) {
                    document.getElementById("ai-output").innerText = "Error gathering intelligence: " + e.message;
                }
            }

            async function triggerBookAppointment() {
                if (!selectedLead) return;
                document.getElementById("ai-output").innerText = "Scheduling calendar consultation & generating executive closer briefing dossier...";
                try {
                    const res = await fetch(API_BASE + "/agent/leads/" + selectedLead.id + "/book-appointment", {
                        method: "POST",
                        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId },
                        body: JSON.stringify({})
                    });
                    if (!res.ok) {
                        const err = await res.json();
                        throw new Error(err.detail || res.statusText);
                    }
                    const data = await res.json();
                    const briefing = data.executive_briefing || {};
                    
                    document.getElementById("ai-output").innerText =
                        "=== APPOINTMENT BOOKED & CLOSER HANDOFF DOSSIER ===\n\n" +
                        "STATUS: " + data.status.toUpperCase() + " | TIME: " + new Date(data.scheduled_at).toLocaleString() + "\n" +
                        "ASSIGNED CLOSER: " + data.closer_name + "\n" +
                        "MEETING URL: " + data.meeting_url + "\n\n" +
                        "--- EXECUTIVE CLOSER BRIEFING DOSSIER ---\n" +
                        "SUMMARY: " + (briefing.company_summary || 'Ready for closing call') + "\n\n" +
                        "PROSPECT INFLUENCE: " + (briefing.target_prospect ? briefing.target_prospect.influence : 'Key Decision Maker') + "\n\n" +
                        "KEY PAIN POINTS:\n" + (briefing.key_pain_points || []).map(p => "  • " + p).join("\n") + "\n\n" +
                        "RECOMMENDED CLOSING STRATEGY:\n" + (briefing.recommended_closing_strategy || 'Present volume catalog pricing with net-30 terms.') + "\n\n" +
                        "DEAL POTENTIAL: " + (briefing.estimated_deal_potential || '$10k - $25k ACV');

                    fetchAppointments();
                    fetchLeads();
                    fetchConversation(selectedLead.id);
                    fetchAuditLogs();
                } catch(e) {
                    document.getElementById("ai-output").innerText = "Error booking appointment: " + e.message;
                }
            }

            async function triggerExecutiveSalesProgram() {
                if (!selectedLead) {
                    await fetchLeads();
                }
                if (!selectedLead) {
                    alert("Please select or create an account from the leads list first!");
                    return;
                }
                const companyName = selectedLead.company ? selectedLead.company.name : "Target Account";
                document.getElementById("ai-output").innerText = "Formulating C-Suite Executive Sales Program & Commercial Pitch for " + companyName + " via Google Gemini AI...";
                try {
                    const res = await fetch(API_BASE + "/agent/leads/" + selectedLead.id + "/executive-sales-program", {
                        method: "POST",
                        headers: { "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId }
                    });
                    if (!res.ok) {
                        const err = await res.json();
                        throw new Error(err.detail || res.statusText);
                    }
                    const data = await res.json();

                    let objectionsText = (data.executive_objection_matrix || []).map(o =>
                        `  • Executive Pushback: "${o.objection}"\n    Tactical Rebuttal: ${o.rebuttal}`
                    ).join("\n\n");

                    let roadmapText = (data.implementation_roadmap || []).map((step, idx) =>
                        `  ${idx + 1}. ${step}`
                    ).join("\n");

                    document.getElementById("ai-output").innerText =
                        `=== EXECUTIVE SALES PROGRAM ===\n` +
                        `PROGRAM: ${data.program_title.toUpperCase()}\n` +
                        `TARGET ACCOUNT: ${data.company_name}\n` +
                        `EXECUTIVE SPONSOR: ${data.executive_sponsor || 'C-Suite Decision Maker'}\n` +
                        `CONFIDENCE: ${Math.round((data.confidence_score || 0.95) * 100)}%\n\n` +
                        `--- C-SUITE VALUE PROPOSITION & ROI ---\n` +
                        `${data.c_suite_value_proposition}\n\n` +
                        `ANNUAL FINANCIAL IMPACT:\n${data.annual_financial_impact}\n\n` +
                        `--- STRATEGIC COMMERCIAL PRICING & TERMS ---\n` +
                        `${data.pricing_proposal}\n\n` +
                        `--- EXECUTIVE CLOSER TALKING SCRIPT ---\n` +
                        `${data.executive_pitch_script}\n\n` +
                        `--- EXECUTIVE OBJECTION HANDLING MATRIX ---\n` +
                        `${objectionsText}\n\n` +
                        `--- ONBOARDING & IMPLEMENTATION ROADMAP ---\n` +
                        `${roadmapText}\n\n` +
                        `RECOMMENDED CLOSING ACTION:\n${data.recommended_closing_action}`;

                    showToast(
                        "Executive Sales Program Formulated!",
                        `Formulated C-suite commercial proposal and closer pitch for "${data.company_name}". Pipeline moved to Proposal.`,
                        "fa-briefcase",
                        "success"
                    );

                    fetchLeads();
                    fetchConversation(selectedLead.id);
                    fetchAuditLogs();
                } catch(e) {
                    document.getElementById("ai-output").innerText = "Error formulating executive sales program: " + e.message;
                }
            }

            async function fetchAppointments() {
                if (!authToken) return;
                try {
                    const res = await fetch(API_BASE + "/crm/appointments", {
                        headers: { "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId }
                    });
                    if (!res.ok) return;
                    const appointments = await res.json();
                    const badge = document.getElementById("appointments-count");
                    if (badge) badge.innerText = appointments.length + " Booked";
                    const container = document.getElementById("appointments-list");
                    if (!container) return;
                    container.innerHTML = "";
                    if (!appointments.length) {
                        container.innerHTML = "<p class='text-xs text-slate-500 italic'>No appointments scheduled yet. The AI SDR books qualified meetings here.</p>";
                        return;
                    }
                    window._appointmentsCache = appointments;
                    appointments.forEach(apt => {
                        const dt = new Date(apt.scheduled_at).toLocaleString([], {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'});
                        const compName = apt.company ? apt.company.name : 'Account';
                        const contactName = apt.contact ? (apt.contact.first_name + ' ' + apt.contact.last_name) : 'Executive Lead';
                        const statusColor = apt.status === 'completed' ? 'bg-emerald-950 text-emerald-300 border-emerald-700/60' : 'bg-indigo-950 text-indigo-300 border-indigo-700/60';
                        const div = document.createElement("div");
                        div.className = "p-2.5 rounded-lg bg-slate-900 border border-slate-700/80 text-xs space-y-1.5 shadow";
                        div.innerHTML = `
                            <div class="flex justify-between items-start">
                                <div>
                                    <div class="font-bold text-slate-100">${escapeHtml(compName)}</div>
                                    <div class="text-[11px] text-slate-400"><i class="fa-solid fa-user-tie mr-1 text-slate-500"></i>${escapeHtml(contactName)} • <span class="text-indigo-400 font-mono">${escapeHtml(apt.closer_name)}</span></div>
                                </div>
                                <span class="px-1.5 py-0.5 rounded text-[10px] font-mono border ${statusColor}">${apt.status.toUpperCase()}</span>
                            </div>
                            <div class="flex items-center justify-between text-[11px] text-emerald-400 font-mono pt-1 border-t border-slate-800">
                                <span><i class="fa-regular fa-clock mr-1"></i>${dt} (${apt.duration_minutes}m)</span>
                                <a href="${apt.meeting_url}" target="_blank" class="text-indigo-300 hover:text-indigo-200 underline flex items-center gap-1"><i class="fa-solid fa-video text-[10px]"></i> Join Call</a>
                            </div>
                            <div class="flex gap-1.5 pt-1">
                                <button onclick="viewBriefingDossier('${apt.id}')" class="flex-1 py-1 bg-slate-800 hover:bg-slate-700 text-indigo-300 rounded text-[10px] font-semibold flex items-center justify-center gap-1 border border-slate-700 cursor-pointer">
                                    <i class="fa-solid fa-file-invoice"></i> Closer Dossier
                                </button>
                                ${apt.status !== 'completed' ? `
                                <button onclick="completeAppointment('${apt.id}')" class="px-2 py-1 bg-emerald-900/60 hover:bg-emerald-800 text-emerald-200 rounded text-[10px] font-semibold border border-emerald-700/60 cursor-pointer">
                                    <i class="fa-solid fa-check"></i> Done
                                </button>` : ''}
                            </div>
                        `;
                        container.appendChild(div);
                    });
                } catch(e) {
                    console.error("Failed to fetch appointments:", e);
                }
            }

            function viewBriefingDossier(aptId) {
                const apt = (window._appointmentsCache || []).find(a => a.id === aptId);
                if (!apt) return;
                const modal = document.getElementById("modal-closer-briefing");
                const content = document.getElementById("briefing-modal-content");
                const b = apt.executive_briefing || {};

                content.innerHTML = `
                    <div class="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-1">
                        <div class="text-[11px] text-slate-400 uppercase font-bold tracking-wider">Account & Closer Assignment</div>
                        <div class="text-sm font-bold text-white">${escapeHtml(apt.company ? apt.company.name : 'Account')}</div>
                        <div class="text-xs text-indigo-300">Scheduled: ${new Date(apt.scheduled_at).toLocaleString()} • Closer: ${escapeHtml(apt.closer_name)}</div>
                        <div class="text-xs text-emerald-400">Meeting Link: <a href="${apt.meeting_url}" target="_blank" class="underline">${apt.meeting_url}</a></div>
                    </div>

                    <div class="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-1">
                        <div class="text-[11px] text-amber-400 font-bold uppercase tracking-wider">Executive Summary</div>
                        <div class="text-xs text-slate-300">${escapeHtml(b.company_summary || 'No summary')}</div>
                    </div>

                    <div class="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-1">
                        <div class="text-[11px] text-red-400 font-bold uppercase tracking-wider">Key Pain Points Uncovered by AI</div>
                        <ul class="list-disc list-inside text-xs text-slate-300 space-y-0.5">
                            ${(b.key_pain_points || []).map(p => `<li>${escapeHtml(p)}</li>`).join('')}
                        </ul>
                    </div>

                    <div class="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-1">
                        <div class="text-[11px] text-emerald-400 font-bold uppercase tracking-wider">Recommended Closer Strategy</div>
                        <div class="text-xs text-slate-200 bg-emerald-950/40 p-2 rounded border border-emerald-700/40 font-semibold">${escapeHtml(b.recommended_closing_strategy || 'Proceed with standard consultation')}</div>
                    </div>

                    <div class="grid grid-cols-2 gap-2">
                        <div class="bg-slate-950 p-2.5 rounded-lg border border-slate-800 text-[11px]">
                            <span class="text-slate-400 font-bold">Deal Potential:</span>
                            <div class="font-mono text-emerald-400 font-bold text-xs mt-0.5">${escapeHtml(b.estimated_deal_potential || '$10,000+')}</div>
                        </div>
                        <div class="bg-slate-950 p-2.5 rounded-lg border border-slate-800 text-[11px]">
                            <span class="text-slate-400 font-bold">Target Products:</span>
                            <div class="text-slate-300 truncate mt-0.5">${escapeHtml((b.target_products || []).join(', ') || 'Wholesale Supplies')}</div>
                        </div>
                    </div>
                `;
                modal.classList.remove("hidden");
            }

            function closeBriefingModal() {
                document.getElementById("modal-closer-briefing").classList.add("hidden");
            }

            async function completeAppointment(aptId) {
                try {
                    const res = await fetch(API_BASE + "/crm/appointments/" + aptId, {
                        method: "PATCH",
                        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId },
                        body: JSON.stringify({ status: "completed" })
                    });
                    if (res.ok) {
                        fetchAppointments();
                        fetchAuditLogs();
                    }
                } catch(e) {
                    alert("Error updating appointment: " + e.message);
                }
            }

            async function simulateInbound() {
                if (!selectedLead) return;
                const text = document.getElementById("in-reply-text").value;
                const thread = document.getElementById("conversation-thread");
                thread.innerHTML += `
                    <div class="p-2.5 rounded bg-slate-900 border border-slate-700">
                        <div class="font-bold text-[11px] text-purple-300 mb-1">Inbound Customer Reply</div>
                        <div class="text-xs text-slate-200">${text}</div>
                    </div>
                `;

                const res = await fetch(API_BASE + "/agent/conversations/" + selectedLead.id + "/inbound-simulate?incoming_text=" + encodeURIComponent(text), {
                    method: "POST",
                    headers: { "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId }
                });
                const analysis = await res.json();

                if (analysis.requires_hitl) {
                    thread.innerHTML += `
                        <div class="p-2.5 rounded bg-amber-950/70 border border-amber-600/70">
                            <div class="font-bold text-[11px] text-amber-300 flex items-center gap-1">
                                <i class="fa-solid fa-hand"></i> AI Execution Halted — Escalated to Human Manager
                            </div>
                            <div class="text-xs text-amber-200 mt-1">${analysis.hitl_reason}</div>
                        </div>
                    `;
                } else if (analysis.suggested_reply) {
                    thread.innerHTML += `
                        <div class="p-2.5 rounded bg-emerald-950/70 border border-emerald-600/70">
                            <div class="font-bold text-[11px] text-emerald-300 mb-1">Autonomous AI Response (Grounded)</div>
                            <div class="text-xs text-slate-200">${analysis.suggested_reply}</div>
                        </div>
                    `;
                }

                fetchHitlRequests();
                fetchAuditLogs();
            }

            async function fetchHitlRequests() {
                if (!authToken) return;
                const res = await fetch(API_BASE + "/hitl/requests?status_filter=pending", {
                    headers: { "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId }
                });
                const requests = await res.json();
                document.getElementById("hitl-count").innerText = requests.length + " Pending";
                const container = document.getElementById("hitl-list");
                container.innerHTML = "";

                if (!requests.length) {
                    container.innerHTML = "<p class='text-xs text-slate-500 italic'>No pending human approval requests. System operating autonomously.</p>";
                    return;
                }

                requests.forEach(r => {
                    const card = document.createElement("div");
                    card.className = "p-3 rounded-lg bg-amber-950/40 border border-amber-600/60 space-y-2 text-xs";
                    card.innerHTML = `
                        <div class="flex justify-between font-bold text-amber-300">
                            <span><i class="fa-solid fa-shield-halved"></i> ${r.trigger_reason}</span>
                            <span class="text-[10px] text-slate-400">${new Date(r.created_at).toLocaleTimeString()}</span>
                        </div>
                        <div class="text-slate-200">${r.situation_summary}</div>
                        <div class="text-[11px] text-slate-400 bg-slate-900/80 p-2 rounded border border-slate-800">
                            <strong>AI Recommendation:</strong> ${r.ai_recommendation || 'Request human manager direction'}
                        </div>
                        <div class="grid grid-cols-3 gap-1.5 pt-1">
                            <button onclick="resolveHitl('${r.id}', 'approve')" class="py-1 px-2 bg-emerald-700 hover:bg-emerald-600 rounded text-[11px] font-semibold text-white">
                                <i class="fa-solid fa-check"></i> Approve
                            </button>
                            <button onclick="resolveHitl('${r.id}', 'reject')" class="py-1 px-2 bg-rose-700 hover:bg-rose-600 rounded text-[11px] font-semibold text-white">
                                <i class="fa-solid fa-xmark"></i> Reject
                            </button>
                            <button onclick="resolveHitl('${r.id}', 'take_over')" class="py-1 px-2 bg-indigo-700 hover:bg-indigo-600 rounded text-[11px] font-semibold text-white">
                                <i class="fa-solid fa-user"></i> Take Over
                            </button>
                        </div>
                    `;
                    container.appendChild(card);
                });
            }

            async function resolveHitl(requestId, action) {
                const res = await fetch(API_BASE + "/hitl/requests/" + requestId + "/action", {
                    method: "POST",
                    headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId },
                    body: JSON.stringify({ action: action, instructions: "Action triggered from web console" })
                });
                if (res.ok) {
                    fetchHitlRequests();
                    fetchAuditLogs();
                }
            }

            async function fetchAuditLogs() {
                if (!authToken) return;
                const res = await fetch(API_BASE + "/hitl/audit-logs?limit=15", {
                    headers: { "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId }
                });
                const logs = await res.json();
                const container = document.getElementById("audit-list");
                container.innerHTML = "";
                logs.forEach(log => {
                    const div = document.createElement("div");
                    div.className = "py-1 px-2 rounded bg-slate-900/90 border border-slate-800 text-[11px] text-slate-300";
                    div.innerHTML = `<span class="text-indigo-400 font-bold">${log.action}</span> by <span class="text-slate-400">${log.actor_type}</span> <span class="text-[10px] text-slate-500 float-right">${new Date(log.created_at).toLocaleTimeString()}</span>`;
                    container.appendChild(div);
                });
            }

            // ==============================================================================
            // CRM 2: Client Accounts, Sales Ledger & Lead Conversion Handlers
            // ==============================================================================

            function switchCrmMode(mode) {
                currentCrmMode = mode;
                const viewProspects = document.getElementById("view-prospects");
                const viewClients = document.getElementById("view-clients");
                const viewFulfillment = document.getElementById("view-fulfillment");
                const viewSettings = document.getElementById("view-settings");
                const tabProspects = document.getElementById("tab-prospects");
                const tabClients = document.getElementById("tab-clients");
                const tabFulfillment = document.getElementById("tab-fulfillment");
                const tabSettings = document.getElementById("tab-settings");

                // Reset all tabs to inactive state
                tabProspects.className = "px-4 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800/60";
                tabClients.className = "px-4 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800/60";
                if (tabFulfillment) tabFulfillment.className = "px-4 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800/60";
                if (tabSettings) tabSettings.className = "px-4 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800/60";

                viewProspects.classList.add("hidden");
                viewClients.classList.add("hidden");
                if (viewFulfillment) viewFulfillment.classList.add("hidden");
                if (viewSettings) viewSettings.classList.add("hidden");

                if (mode === 'prospects') {
                    viewProspects.classList.remove("hidden");
                    tabProspects.className = "px-4 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-2 bg-indigo-600 text-white shadow-md";
                } else if (mode === 'clients') {
                    viewClients.classList.remove("hidden");
                    tabClients.className = "px-4 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-2 bg-emerald-600 text-white shadow-md";
                    fetchClientStats();
                    fetchClients();
                    fetchDueReplenishments();
                } else if (mode === 'fulfillment') {
                    if (viewFulfillment) viewFulfillment.classList.remove("hidden");
                    if (tabFulfillment) tabFulfillment.className = "px-4 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-2 bg-amber-500 text-slate-950 font-bold shadow-md";
                    fetchProcurementStats();
                    fetchSuppliers();
                    fetchPurchaseOrders();
                    fetchAllSalesForFulfillmentSelector();
                } else if (mode === 'settings') {
                    if (viewSettings) viewSettings.classList.remove("hidden");
                    if (tabSettings) tabSettings.className = "px-4 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-2 bg-purple-600 text-white shadow-md";
                    fetchOrganizationSettings();
                }
            }

            async function fetchClientStats() {
                if (!authToken) return;
                try {
                    const res = await fetch(API_BASE + "/crm/clients/stats/overview", {
                        headers: { "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId }
                    });
                    if (!res.ok) return;
                    const stats = await res.json();
                    const formattedRev = "$" + (stats.total_revenue || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                    const formattedAov = "$" + (stats.average_order_value || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});

                    // Update Nav strip KPIs
                    document.getElementById("kpi-nav-rev").innerText = formattedRev;
                    document.getElementById("kpi-nav-clients").innerText = stats.active_clients_count || 0;
                    document.getElementById("kpi-nav-orders").innerText = stats.total_orders_count || 0;
                    document.getElementById("kpi-nav-aov").innerText = formattedAov;
                    document.getElementById("nav-badge-clients").innerText = stats.active_clients_count || 0;

                    // Update Client CRM 2 Highlight Cards
                    const statRev = document.getElementById("client-stat-rev");
                    if (statRev) statRev.innerText = formattedRev;
                    const statCount = document.getElementById("client-stat-count");
                    if (statCount) statCount.innerText = stats.active_clients_count || 0;
                    const statOrders = document.getElementById("client-stat-orders");
                    if (statOrders) statOrders.innerText = stats.total_orders_count || 0;
                    const statAov = document.getElementById("client-stat-aov");
                    if (statAov) statAov.innerText = formattedAov;
                } catch(e) {
                    console.error("Error fetching client stats:", e);
                }
            }

            async function fetchClients() {
                if (!authToken) return;
                try {
                    const res = await fetch(API_BASE + "/crm/clients", {
                        headers: { "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId }
                    });
                    if (!res.ok) return;
                    allClients = await res.json();
                    const container = document.getElementById("clients-list");
                    container.innerHTML = "";

                    if (!allClients.length) {
                        container.innerHTML = "<p class='text-xs text-slate-500 italic'>No client accounts yet. Add an account above or convert a won lead!</p>";
                        return;
                    }

                    allClients.forEach(c => {
                        const div = document.createElement("div");
                        const isSelected = selectedClient && selectedClient.id === c.id;
                        div.className = `p-3 rounded-lg bg-slate-900/90 border ${isSelected ? 'border-emerald-500 bg-slate-900' : 'border-slate-700/60 hover:border-emerald-500/60'} cursor-pointer transition space-y-1.5`;
                        div.onclick = () => selectClient(c);

                        let tierBadgeClass = "bg-slate-800 text-slate-300 border-slate-700";
                        if (c.account_tier === 'vip') tierBadgeClass = "bg-amber-950/80 text-amber-300 border-amber-600/70";
                        else if (c.account_tier === 'enterprise') tierBadgeClass = "bg-purple-950/80 text-purple-300 border-purple-600/70";
                        else if (c.account_tier === 'premium') tierBadgeClass = "bg-blue-950/80 text-blue-300 border-blue-600/70";

                        let restockBadge = "";
                        if (c.next_reorder_date) {
                            const diffDays = Math.ceil((new Date(c.next_reorder_date) - new Date()) / (1000 * 60 * 60 * 24));
                            if (diffDays <= 0) {
                                restockBadge = `<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-rose-950 text-rose-300 border border-rose-700/60 flex items-center gap-1"><i class="fa-solid fa-clock-rotate-left"></i> Due</span>`;
                            } else if (diffDays <= 7) {
                                restockBadge = `<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-950 text-amber-300 border border-amber-700/60 flex items-center gap-1"><i class="fa-solid fa-hourglass-half"></i> ${diffDays}d</span>`;
                            } else {
                                restockBadge = `<span class="px-1.5 py-0.5 rounded text-[9px] font-medium bg-slate-800 text-slate-400 border border-slate-700">${diffDays}d</span>`;
                            }
                        }

                        let cardBadge = "";
                        if (c.has_payment_method_on_file) {
                            const brand = (c.card_brand || "CARD").toUpperCase();
                            const isAuto = Boolean(c.auto_charge_enabled);
                            cardBadge = `<span class="px-1.5 py-0.5 rounded text-[9px] font-mono font-bold ${isAuto ? 'bg-emerald-950/90 text-emerald-300 border border-emerald-700/60' : 'bg-indigo-950/90 text-indigo-300 border border-indigo-700/60'}" title="${isAuto ? 'Auto-Charge Active' : 'Card on File'}"><i class="fa-solid fa-credit-card text-[8px] mr-1"></i>${brand} ${c.card_last4 || '••••'}</span>`;
                        }

                        const revFormatted = "$" + (c.total_revenue || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                        const contactName = c.primary_contact ? (c.primary_contact.first_name + " " + c.primary_contact.last_name) : (c.company ? c.company.name : "Contact");

                        div.innerHTML = `
                            <div class="flex justify-between items-start">
                                <div>
                                    <div class="font-bold text-slate-200 text-xs">${escapeHtml(c.account_name)}</div>
                                    <div class="text-[11px] text-slate-400">${escapeHtml(contactName)} • <span class="text-slate-500">${escapeHtml(c.company ? c.company.industry || '' : '')}</span></div>
                                </div>
                                <div class="flex items-center gap-1 flex-wrap justify-end">
                                    <span class="px-1.5 py-0.5 rounded text-[10px] font-semibold border ${tierBadgeClass} uppercase">${escapeHtml(c.account_tier)}</span>
                                    ${cardBadge}
                                    ${restockBadge}
                                </div>
                            </div>
                            <div class="flex justify-between items-center pt-1 border-t border-slate-800/80 text-[11px]">
                                <span class="font-bold font-mono text-emerald-400">${revFormatted}</span>
                                <span class="text-slate-400">${c.order_count || 0} Orders</span>
                            </div>
                            ${c.notes ? `<div class="text-[10px] text-slate-400 truncate italic"><i class="fa-regular fa-note-sticky text-amber-400 mr-1"></i>${escapeHtml(c.notes)}</div>` : ''}
                        `;
                        container.appendChild(div);
                    });

                    // Auto-select first client if none selected
                    if (!selectedClient && allClients.length > 0) {
                        selectClient(allClients[0]);
                    } else if (selectedClient) {
                        const current = allClients.find(c => c.id === selectedClient.id);
                        if (current) selectClient(current);
                    }
                } catch(e) {
                    console.error("Error fetching clients:", e);
                }
            }

            async function selectClient(client) {
                selectedClient = client;

                document.getElementById("detail-client-name").innerText = client.account_name;
                const tierPill = document.getElementById("detail-client-tier");
                tierPill.innerText = client.account_tier;
                tierPill.classList.remove("hidden");
                let tierBadgeClass = "bg-slate-800 text-slate-300 border border-slate-700";
                if (client.account_tier === 'vip') tierBadgeClass = "bg-amber-950 text-amber-300 border border-amber-600/70";
                else if (client.account_tier === 'enterprise') tierBadgeClass = "bg-purple-950 text-purple-300 border border-purple-600/70";
                else if (client.account_tier === 'premium') tierBadgeClass = "bg-blue-950 text-blue-300 border border-blue-600/70";
                tierPill.className = "px-2 py-0.5 rounded text-[11px] font-semibold uppercase " + tierBadgeClass;

                const statusPill = document.getElementById("detail-client-status");
                statusPill.innerText = client.status;
                statusPill.classList.remove("hidden");
                statusPill.className = "px-2 py-0.5 rounded text-[11px] font-mono " + (client.status === 'active' ? 'bg-emerald-950 text-emerald-300 border border-emerald-700/60' : 'bg-slate-800 text-slate-400 border border-slate-700');

                const contactStr = client.primary_contact ? `${client.primary_contact.first_name} ${client.primary_contact.last_name} (${client.primary_contact.email || 'No email'}) • Account Rep: ${client.account_manager || 'Sales Director'}` : `Account Rep: ${client.account_manager || 'Sales Director'}`;
                document.getElementById("detail-client-contact").innerText = contactStr;

                // Summary Metrics
                const revFormatted = "$" + (client.total_revenue || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                document.getElementById("detail-client-rev").innerText = revFormatted;
                document.getElementById("detail-client-orders").innerText = client.order_count || 0;
                document.getElementById("detail-client-cadence").innerText = (client.reorder_cadence_days || 30) + " Days";
                
                if (client.next_reorder_date) {
                    const nextDate = new Date(client.next_reorder_date).toLocaleDateString([], {month: 'short', day: 'numeric', year: 'numeric'});
                    document.getElementById("detail-client-next-reorder").innerText = nextDate;
                } else {
                    document.getElementById("detail-client-next-reorder").innerText = "—";
                }

                // Stored Card on File & Auto-Charge status
                const badgeCard = document.getElementById("detail-card-status-badge");
                const descCard = document.getElementById("detail-card-description");
                const btnAttach = document.getElementById("btn-attach-card");
                const btnAttachText = document.getElementById("btn-attach-card-text");
                const btnToggleAuto = document.getElementById("btn-toggle-auto-charge");
                const btnDetach = document.getElementById("btn-detach-card");

                if (btnAttach) btnAttach.disabled = false;

                if (client.has_payment_method_on_file) {
                    const brand = (client.card_brand || "card").toUpperCase();
                    const last4 = client.card_last4 || "••••";
                    const isAuto = Boolean(client.auto_charge_enabled);
                    const limitStr = client.auto_charge_limit ? ` (Max: $${Number(client.auto_charge_limit).toLocaleString()})` : " (Unlimited)";
                    
                    if (badgeCard) {
                        badgeCard.className = `px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${isAuto ? 'bg-emerald-950 text-emerald-300 border-emerald-600/60' : 'bg-amber-950 text-amber-300 border-amber-600/60'}`;
                        badgeCard.innerHTML = `<i class="fa-solid fa-credit-card mr-1"></i>${brand} •••• ${last4} &bull; ${isAuto ? 'AUTO-CHARGE ACTIVE' : 'AUTO-CHARGE PAUSED'}`;
                    }
                    if (descCard) {
                        descCard.innerHTML = `<span class="text-slate-300 font-semibold">${brand} ending in ${last4}</span> on file.${limitStr} ${isAuto ? '<span class="text-emerald-400">Autonomous replenishment charges execute without human intervention.</span>' : '<span class="text-amber-400">Card stored; auto-charge paused.</span>'}`;
                    }
                    if (btnAttachText) btnAttachText.innerText = "Update Card";
                    if (btnDetach) {
                        btnDetach.disabled = false;
                        btnDetach.classList.remove("hidden");
                    }
                    if (btnToggleAuto) {
                        btnToggleAuto.disabled = false;
                        btnToggleAuto.innerHTML = isAuto
                            ? `<i class="fa-solid fa-pause text-amber-400"></i> Pause Auto-Charge`
                            : `<i class="fa-solid fa-play text-emerald-400"></i> Enable Auto-Charge`;
                        btnToggleAuto.className = isAuto
                            ? `px-2.5 py-1.5 bg-amber-950/60 hover:bg-amber-900 text-amber-300 border border-amber-800/60 rounded text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer`
                            : `px-2.5 py-1.5 bg-emerald-950/60 hover:bg-emerald-900 text-emerald-300 border border-emerald-800/60 rounded text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer`;
                    }
                } else {
                    if (badgeCard) {
                        badgeCard.className = "px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-800 text-slate-400 border border-slate-700";
                        badgeCard.innerText = "No Card on File";
                    }
                    if (descCard) {
                        descCard.innerText = "Attach a corporate card to enable hands-free autonomous replenishment billing.";
                    }
                    if (btnAttachText) btnAttachText.innerText = "Store Card";
                    if (btnDetach) {
                        btnDetach.disabled = true;
                        btnDetach.classList.add("hidden");
                    }
                    if (btnToggleAuto) {
                        btnToggleAuto.disabled = true;
                        btnToggleAuto.innerHTML = `<i class="fa-solid fa-bolt text-slate-500"></i> Auto-Charge`;
                        btnToggleAuto.className = `px-2.5 py-1.5 bg-slate-800 text-slate-500 border border-slate-700 rounded text-xs font-semibold flex items-center gap-1.5 cursor-not-allowed`;
                    }
                }

                // Notes
                document.getElementById("detail-client-notes").value = client.notes || "";

                // Buttons
                document.getElementById("btn-toggle-sale").disabled = false;
                const btnReplenish = document.getElementById("btn-trigger-replenishment");
                if (btnReplenish) btnReplenish.disabled = false;
                const btnPortal = document.getElementById("btn-portal-link");
                if (btnPortal) btnPortal.disabled = false;
                document.getElementById("btn-save-client-notes").disabled = false;

                // Fetch sales for this client
                fetchSalesForClient(client.id);
            }

            async function fetchSalesForClient(clientId) {
                try {
                    const res = await fetch(API_BASE + "/crm/clients/" + clientId + "/sales", {
                        headers: { "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId }
                    });
                    if (!res.ok) return;
                    const sales = await res.json();
                    document.getElementById("sales-count-badge").innerText = sales.length + " Transaction" + (sales.length === 1 ? "" : "s");
                    const tbody = document.getElementById("sales-ledger-body");
                    tbody.innerHTML = "";

                    if (!sales.length) {
                        tbody.innerHTML = `<tr><td colspan="8" class="p-4 text-center text-slate-500 italic">No sales recorded yet for this client account. Click '+ Log New Sale / Order' to record the first transaction.</td></tr>`;
                        return;
                    }

                    sales.forEach(s => {
                        const tr = document.createElement("tr");
                        tr.className = "hover:bg-slate-900/60 transition";
                        const saleDate = new Date(s.sale_date).toLocaleDateString([], {month:'short', day:'numeric', year:'numeric'});
                        let statusBadge = "bg-emerald-950 text-emerald-300 border-emerald-700/60";
                        if (s.status === 'invoiced') statusBadge = "bg-amber-950 text-amber-300 border-amber-600/60";
                        else if (s.status === 'pending') statusBadge = "bg-blue-950 text-blue-300 border-blue-600/60";
                        else if (s.status === 'cancelled') statusBadge = "bg-rose-950 text-rose-300 border-rose-600/60";

                        const amtFormatted = "$" + (s.amount || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});

                        let fulfillmentHtml = "";
                        if (s.po_number) {
                            const isDropship = s.destination_type === 'customer_dropship';
                            const isDeliv = s.shipping_status === 'delivered';
                            fulfillmentHtml = `
                                <div class="space-y-1">
                                    <div class="flex items-center gap-1.5 flex-wrap">
                                        <span class="px-1.5 py-0.5 rounded text-[10px] font-mono bg-amber-950/80 text-amber-300 border border-amber-700/50 font-bold">${escapeHtml(s.po_number)}</span>
                                        <span class="px-1.5 py-0.5 rounded text-[9px] uppercase font-semibold ${isDropship ? 'bg-purple-950 text-purple-300 border border-purple-700/40' : 'bg-slate-800 text-slate-300 border border-slate-700'}">${isDropship ? 'Drop Ship' : 'Warehouse'}</span>
                                    </div>
                                    ${s.tracking_number ? `
                                        <div class="flex items-center gap-1 text-[10px]">
                                            <span class="font-bold text-cyan-400">${escapeHtml(s.carrier || 'UPS')}:</span>
                                            <a href="${escapeHtml(s.tracking_url || '#')}" target="_blank" class="font-mono text-cyan-300 hover:underline">${escapeHtml(s.tracking_number)}</a>
                                            <span class="px-1 py-0.2 rounded text-[9px] ${isDeliv ? 'bg-emerald-950 text-emerald-300 border border-emerald-700/40' : 'bg-indigo-950 text-indigo-300 border border-indigo-700/40'}">${escapeHtml(s.shipping_status || 'in_transit')}</span>
                                        </div>
                                    ` : `<span class="text-[10px] text-slate-400">Order Placed</span>`}
                                </div>
                            `;
                        } else {
                            fulfillmentHtml = `
                                <button onclick="triggerFulfillSaleFromLedger('${s.id}', '${escapeHtml(s.order_number)}', '${escapeHtml(s.items_summary)}', '${escapeHtml(selectedClient ? selectedClient.account_name : '')}')" class="px-2 py-1 bg-gradient-to-r from-amber-500 to-emerald-600 hover:from-amber-400 hover:to-emerald-500 text-slate-950 font-bold rounded text-[10px] flex items-center gap-1 shadow cursor-pointer transition">
                                    <i class="fa-solid fa-robot"></i> Auto-Fulfill (Drop Ship)
                                </button>
                            `;
                        }

                        const isPaid = s.payment_status === 'paid';
                        const paymentBadge = isPaid
                            ? `<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-950 text-emerald-300 border border-emerald-700/50">✓ PAID</span>`
                            : `<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-950 text-amber-300 border border-amber-700/50">UNPAID</span>`;

                        const publicTrackUrl = SUB_PATH + "/track/" + encodeURIComponent(s.order_number);
                        const customerPortalLink = `
                            <a href="${publicTrackUrl}" target="_blank" class="text-[10px] text-cyan-400 hover:text-cyan-300 flex items-center gap-1 font-semibold mt-0.5" title="Open Customer Delivery Portal">
                                <i class="fa-solid fa-arrow-up-right-from-square text-[8px]"></i> Tracking Portal
                            </a>
                        `;

                        let stripeActionsHtml = "";
                        if (!isPaid) {
                            let autoChargeBtn = "";
                            if (selectedClient && selectedClient.has_payment_method_on_file) {
                                autoChargeBtn = `
                                    <button onclick="chargeClientSaleWithStoredCard('${selectedClient.id}', '${s.id}', '${escapeHtml(s.order_number)}')" class="px-1.5 py-0.5 bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-white border border-emerald-400/40 rounded text-[9px] font-semibold flex items-center gap-1 cursor-pointer shadow-sm" title="Charge client's stored card-on-file">
                                        <i class="fa-solid fa-bolt text-amber-300"></i> Auto-Charge Card
                                    </button>
                                `;
                            }
                            stripeActionsHtml = `
                                <div class="flex items-center gap-1 mt-1 flex-wrap">
                                    ${autoChargeBtn}
                                    <button onclick="createStripeCheckout('${s.id}', '${escapeHtml(s.order_number)}')" class="px-1.5 py-0.5 bg-indigo-900/60 hover:bg-indigo-800 text-indigo-200 border border-indigo-700/40 rounded text-[9px] font-semibold flex items-center gap-1 cursor-pointer" title="Create / Open Stripe Checkout">
                                        <i class="fa-brands fa-stripe"></i> Pay Link
                                    </button>
                                    <button onclick="simulateCustomerPayment('${s.id}')" class="px-1.5 py-0.5 bg-emerald-900/60 hover:bg-emerald-800 text-emerald-200 border border-emerald-700/40 rounded text-[9px] font-semibold flex items-center gap-1 cursor-pointer" title="Simulate online payment & trigger bot dropshipping">
                                        <i class="fa-solid fa-bolt text-amber-400"></i> Pay &amp; Fulfill
                                    </button>
                                </div>
                            `;
                        }

                        tr.innerHTML = `
                            <td class="p-2.5 text-slate-400 font-mono text-[11px] whitespace-nowrap">${saleDate}</td>
                            <td class="p-2.5 whitespace-nowrap">
                                <span class="font-mono text-indigo-300 font-bold">${escapeHtml(s.order_number)}</span>
                                <div class="flex items-center gap-2 mt-1">
                                    ${customerPortalLink}
                                    <span class="text-slate-600">&bull;</span>
                                    <a href="${SUB_PATH}/api/v1/documents/invoice/${s.id}?print=true" target="_blank" class="text-[10px] text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-semibold" title="Print Commercial B2B Invoice">
                                        <i class="fa-solid fa-file-invoice text-[9px]"></i> Invoice
                                    </a>
                                    <span class="text-slate-600">&bull;</span>
                                    <a href="${SUB_PATH}/api/v1/documents/packing-slip/${s.id}?print=true" target="_blank" class="text-[10px] text-amber-400 hover:text-amber-300 flex items-center gap-1 font-semibold" title="Print Warehouse Packing Slip">
                                        <i class="fa-solid fa-box-open text-[9px]"></i> Slip
                                    </a>
                                </div>
                            </td>
                            <td class="p-2.5 text-slate-200">
                                <div class="font-medium">${escapeHtml(s.items_summary)}</div>
                                ${s.notes ? `<div class="text-[10px] text-slate-500 italic">${escapeHtml(s.notes)}</div>` : ''}
                            </td>
                            <td class="p-2.5 text-slate-400 whitespace-nowrap uppercase text-[10px] font-mono">
                                <div>${escapeHtml(s.payment_method ? s.payment_method.replace(/_/g, ' ') : '')}</div>
                                <div class="mt-0.5">${paymentBadge}</div>
                                ${stripeActionsHtml}
                            </td>
                            <td class="p-2.5 text-slate-300 whitespace-nowrap text-[11px]">${escapeHtml(s.sales_rep_name || 'Sales Rep')}</td>
                            <td class="p-2.5">${fulfillmentHtml}</td>
                            <td class="p-2.5 whitespace-nowrap">
                                <span class="px-2 py-0.5 rounded text-[10px] border ${statusBadge} uppercase font-semibold">${escapeHtml(s.status)}</span>
                            </td>
                            <td class="p-2.5 text-right font-mono font-bold text-emerald-400 text-xs whitespace-nowrap">${amtFormatted}</td>
                        `;
                        tbody.appendChild(tr);
                    });
                } catch(e) {
                    console.error("Error fetching sales:", e);
                }
            }

            async function createStripeCheckout(saleId, orderNum) {
                try {
                    const res = await fetch(API_BASE + "/crm/sales/" + saleId + "/create-checkout", {
                        method: "POST",
                        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId },
                        body: JSON.stringify({})
                    });
                    if (res.ok) {
                        const data = await res.json();
                        const fullUrl = data.checkout_url.startsWith("http") ? data.checkout_url : (SUB_PATH + data.checkout_url);
                        showToast("Stripe Checkout Ready", `Payment link created for Order #${orderNum}`, "fa-stripe", "info");
                        window.open(fullUrl, "_blank");
                        if (selectedClient) fetchSalesForClient(selectedClient.id);
                    } else {
                        const err = await res.json();
                        alert("Error generating checkout link: " + (err.detail || res.statusText));
                    }
                } catch(e) {
                    alert("Error: " + e.message);
                }
            }

            async function simulateCustomerPayment(saleId) {
                try {
                    const res = await fetch(API_BASE + "/crm/sales/" + saleId + "/simulate-payment", {
                        method: "POST",
                        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId }
                    });
                    if (res.ok) {
                        const data = await res.json();
                        showToast("Payment Received!", `Order #${data.order_number} paid online! Autonomous dropshipping triggered.`, "fa-bolt", "success");
                        if (selectedClient) fetchSalesForClient(selectedClient.id);
                        await fetchPurchaseOrders();
                        await fetchProcurementStats();
                    } else {
                        const err = await res.json();
                        alert("Error simulating payment: " + (err.detail || res.statusText));
                    }
                } catch(e) {
                    alert("Error: " + e.message);
                }
            }

            function openAttachCardModal() {
                if (!selectedClient) {
                    alert("Please select a client account first.");
                    return;
                }
                if (selectedClient.has_payment_method_on_file) {
                    if (selectedClient.card_brand) document.getElementById("in-card-brand").value = selectedClient.card_brand.toLowerCase();
                    if (selectedClient.card_last4) document.getElementById("in-card-last4").value = selectedClient.card_last4;
                    document.getElementById("in-auto-charge-enabled").checked = Boolean(selectedClient.auto_charge_enabled);
                    document.getElementById("in-auto-charge-limit").value = selectedClient.auto_charge_limit || "";
                }
                document.getElementById("modal-attach-card").classList.remove("hidden");
            }

            function closeAttachCardModal() {
                document.getElementById("modal-attach-card").classList.add("hidden");
            }

            async function handleAttachPaymentMethod(e) {
                e.preventDefault();
                if (!selectedClient) return;

                const brand = document.getElementById("in-card-brand").value;
                const last4 = document.getElementById("in-card-last4").value;
                const enableAuto = document.getElementById("in-auto-charge-enabled").checked;
                const limitVal = document.getElementById("in-auto-charge-limit").value;
                const limit = limitVal ? parseFloat(limitVal) : null;

                try {
                    const res = await fetch(API_BASE + `/crm/clients/${selectedClient.id}/payment-method/attach`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId },
                        body: JSON.stringify({
                            card_brand: brand,
                            card_last4: last4,
                            payment_method_type: "card",
                            enable_auto_charge: enableAuto,
                            auto_charge_limit: limit
                        })
                    });

                    if (res.ok) {
                        const updated = await res.json();
                        closeAttachCardModal();
                        showToast("Card Stored on File!", `${brand.toUpperCase()} ending in ${last4} authorized for auto-billing.`, "fa-credit-card", "success");
                        await fetchClients();
                        selectClient(updated);
                    } else {
                        const err = await res.json();
                        alert("Error attaching payment method: " + (err.detail || res.statusText));
                    }
                } catch(err) {
                    alert("Error: " + err.message);
                }
            }

            async function toggleAutoCharge() {
                if (!selectedClient || !selectedClient.has_payment_method_on_file) return;
                const currentStatus = Boolean(selectedClient.auto_charge_enabled);
                const nextStatus = !currentStatus;

                try {
                    const res = await fetch(API_BASE + `/crm/clients/${selectedClient.id}/payment-method/auto-charge`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId },
                        body: JSON.stringify({
                            enabled: nextStatus,
                            limit: selectedClient.auto_charge_limit
                        })
                    });

                    if (res.ok) {
                        const updated = await res.json();
                        showToast(nextStatus ? "Auto-Charge Enabled" : "Auto-Charge Paused", `Recurring restock charges will ${nextStatus ? 'process autonomously' : 'pause for review'}.`, "fa-bolt", "info");
                        await fetchClients();
                        selectClient(updated);
                    } else {
                        const err = await res.json();
                        alert("Error toggling auto-charge: " + (err.detail || res.statusText));
                    }
                } catch(e) {
                    alert("Error: " + e.message);
                }
            }

            async function detachPaymentMethod() {
                if (!selectedClient || !selectedClient.has_payment_method_on_file) return;
                if (!confirm(`Are you sure you want to remove the stored card for ${selectedClient.account_name}? Automatic replenishment billing will be disabled.`)) return;

                try {
                    const res = await fetch(API_BASE + `/crm/clients/${selectedClient.id}/payment-method`, {
                        method: "DELETE",
                        headers: { "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId }
                    });

                    if (res.ok) {
                        const updated = await res.json();
                        showToast("Card Removed", "Payment method detached from client account.", "fa-trash-can", "info");
                        await fetchClients();
                        selectClient(updated);
                    } else {
                        const err = await res.json();
                        alert("Error detaching payment method: " + (err.detail || res.statusText));
                    }
                } catch(e) {
                    alert("Error: " + e.message);
                }
            }

            async function chargeClientSaleWithStoredCard(clientId, saleId, orderNum) {
                if (!confirm(`Charge client's stored card for Order #${orderNum}?`)) return;
                try {
                    const res = await fetch(API_BASE + `/crm/clients/${clientId}/charge-sale/${saleId}`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId }
                    });
                    if (res.ok) {
                        const data = await res.json();
                        showToast("Auto-Charge Successful!", `Card charged for Order #${orderNum}. Autonomous fulfillment triggered.`, "fa-bolt", "success");
                        await fetchClients();
                        if (selectedClient) fetchSalesForClient(selectedClient.id);
                        await fetchPurchaseOrders();
                        await fetchProcurementStats();
                        await fetchDueReplenishments();
                    } else {
                        const err = await res.json();
                        alert("Auto-charge failed: " + (err.detail || res.statusText));
                    }
                } catch(e) {
                    alert("Error: " + e.message);
                }
            }

            async function fetchDueReplenishments() {
                if (!authToken) return;
                try {
                    const res = await fetch(API_BASE + "/crm/replenishments/due?threshold_days=7", {
                        headers: { "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId }
                    });
                    if (res.ok) {
                        const data = await res.json();
                        const countBadge = document.getElementById("badge-replenishment-count");
                        if (countBadge) {
                            countBadge.innerText = `${data.count} Due`;
                            countBadge.className = data.count > 0
                                ? "px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-950 text-rose-300 border border-rose-700/60 animate-pulse"
                                : "px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-950 text-emerald-300 border border-emerald-700/50";
                        }
                    }
                } catch(e) {
                    console.error("Error fetching due replenishments:", e);
                }
            }

            async function processDueReplenishments() {
                if (!authToken) return;
                try {
                    const res = await fetch(API_BASE + "/crm/replenishments/process-due?threshold_days=7", {
                        method: "POST",
                        headers: { "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId }
                    });
                    if (res.ok) {
                        const data = await res.json();
                        showToast("Replenishments Processed!", `Generated ${data.generated_count} new restock order proposal(s) with Stripe checkout links.`, "fa-bolt", "success");
                        await fetchClients();
                        await fetchDueReplenishments();
                        if (selectedClient) fetchSalesForClient(selectedClient.id);
                    } else {
                        const err = await res.json();
                        alert("Error processing replenishments: " + (err.detail || res.statusText));
                    }
                } catch(e) {
                    alert("Error: " + e.message);
                }
            }

            async function triggerClientReplenishmentProposal() {
                if (!selectedClient) return;
                const btn = document.getElementById("btn-trigger-replenishment");
                if (btn) btn.disabled = true;
                try {
                    const res = await fetch(API_BASE + "/crm/clients/" + selectedClient.id + "/generate-replenishment", {
                        method: "POST",
                        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId },
                        body: JSON.stringify({})
                    });
                    if (res.ok) {
                        const data = await res.json();
                        const fullUrl = data.checkout_url.startsWith("http") ? data.checkout_url : (SUB_PATH + data.checkout_url);
                        showToast("Restock Proposal Ready", `Order #${data.order_number} ($${data.amount.toFixed(2)}) generated with Stripe Checkout!`, "fa-stripe", "success");
                        window.open(fullUrl, "_blank");
                        await fetchClients();
                        await fetchSalesForClient(selectedClient.id);
                        await fetchDueReplenishments();
                    } else {
                        const err = await res.json();
                        alert("Error creating restock proposal: " + (err.detail || res.statusText));
                    }
                } catch(e) {
                    alert("Error: " + e.message);
                } finally {
                    if (btn) btn.disabled = false;
                }
            }

            async function openClientPortalLink() {
                if (!selectedClient) return;
                try {
                    const res = await fetch(API_BASE + "/crm/clients/" + selectedClient.id + "/portal-link", {
                        method: "POST",
                        headers: { "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId }
                    });
                    if (res.ok) {
                        const data = await res.json();
                        const fullUrl = data.portal_path.startsWith("http") ? data.portal_path : (SUB_PATH + data.portal_path);
                        showToast("Customer Portal Ready", `Opening self-service portal for ${selectedClient.account_name}`, "fa-arrow-up-right-from-square", "info");
                        window.open(fullUrl, "_blank");
                    } else {
                        const err = await res.json();
                        alert("Error retrieving portal link: " + (err.detail || res.statusText));
                    }
                } catch(e) {
                    alert("Error: " + e.message);
                }
            }

            async function saveClientNotes() {
                if (!selectedClient) return;
                const notesVal = document.getElementById("detail-client-notes").value;
                const btn = document.getElementById("btn-save-client-notes");
                try {
                    const res = await fetch(API_BASE + "/crm/clients/" + selectedClient.id, {
                        method: "PATCH",
                        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId },
                        body: JSON.stringify({ notes: notesVal })
                    });
                    if (res.ok) {
                        selectedClient.notes = notesVal;
                        fetchClients();
                        fetchAuditLogs();
                        const orig = btn.innerHTML;
                        btn.innerHTML = `<i class="fa-solid fa-check text-emerald-400"></i> Saved!`;
                        setTimeout(() => { btn.innerHTML = orig; }, 1800);
                    }
                } catch(e) {
                    alert("Error saving client notes: " + e.message);
                }
            }

            function toggleLogSaleForm() {
                const panel = document.getElementById("log-sale-panel");
                if (panel) {
                    panel.classList.toggle("hidden");
                    if (!panel.classList.contains("hidden")) {
                        setCallTimeNow("in-sale-date");
                        document.getElementById("in-sale-amount").focus();
                    }
                }
            }

            async function handleCreateClient(e) {
                e.preventDefault();
                if (!authToken) { alert("Please connect default tenant first!"); return; }

                const payload = {
                    account_name: document.getElementById("in-client-name").value,
                    industry: document.getElementById("in-client-industry").value,
                    company_domain: document.getElementById("in-client-domain").value,
                    contact_first_name: document.getElementById("in-client-fname").value,
                    contact_last_name: document.getElementById("in-client-lname").value,
                    contact_email: document.getElementById("in-client-email").value,
                    contact_phone: document.getElementById("in-client-phone").value,
                    account_tier: document.getElementById("in-client-tier").value,
                    reorder_cadence_days: parseInt(document.getElementById("in-client-cadence").value) || 30,
                    notes: document.getElementById("in-client-notes").value
                };

                try {
                    const res = await fetch(API_BASE + "/crm/clients", {
                        method: "POST",
                        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId },
                        body: JSON.stringify(payload)
                    });
                    if (res.ok) {
                        const newClient = await res.json();
                        await fetchClientStats();
                        await fetchClients();
                        selectClient(newClient);
                        fetchAuditLogs();
                    } else {
                        const err = await res.json();
                        alert("Error creating client: " + (err.detail || res.statusText));
                    }
                } catch(e) {
                    alert("Error creating client: " + e.message);
                }
            }

            async function handleLogSale(e) {
                e.preventDefault();
                if (!selectedClient) { alert("Please select a client account first!"); return; }

                const dateVal = document.getElementById("in-sale-date").value;
                const payload = {
                    amount: parseFloat(document.getElementById("in-sale-amount").value),
                    order_number: document.getElementById("in-sale-ordernum").value || undefined,
                    sale_date: dateVal ? new Date(dateVal).toISOString() : new Date().toISOString(),
                    status: document.getElementById("in-sale-status").value,
                    payment_method: document.getElementById("in-sale-payment").value,
                    sales_rep_name: document.getElementById("in-sale-rep").value,
                    items_summary: document.getElementById("in-sale-items").value,
                    notes: document.getElementById("in-sale-notes").value
                };

                try {
                    const res = await fetch(API_BASE + "/crm/clients/" + selectedClient.id + "/sales", {
                        method: "POST",
                        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId },
                        body: JSON.stringify(payload)
                    });
                    if (res.ok) {
                        document.getElementById("log-sale-panel").classList.add("hidden");
                        // Refresh client detail
                        const updatedRes = await fetch(API_BASE + "/crm/clients/" + selectedClient.id, {
                            headers: { "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId }
                        });
                        if (updatedRes.ok) {
                            const refreshed = await updatedRes.json();
                            selectClient(refreshed);
                        }
                        fetchSalesForClient(selectedClient.id);
                        fetchClients();
                        fetchClientStats();
                        fetchAuditLogs();
                    } else {
                        const err = await res.json();
                        alert("Error recording sale: " + (err.detail || res.statusText));
                    }
                } catch(e) {
                    alert("Error recording sale: " + e.message);
                }
            }

            async function openConvertModal() {
                if (!selectedLead) {
                    await fetchLeads();
                }
                if (!selectedLead) {
                    alert("Please create or select an active prospect first!");
                    return;
                }
                const company = selectedLead.company ? selectedLead.company.name : "Company";
                const contact = selectedLead.contact ? (selectedLead.contact.first_name + " " + selectedLead.contact.last_name + " (" + selectedLead.contact.email + ")") : "Contact";
                document.getElementById("modal-convert-lead-name").innerText = company;
                document.getElementById("modal-convert-lead-contact").innerText = "Primary Contact: " + contact;
                document.getElementById("modal-convert-notes").value = selectedLead.notes || "Converted from Prospect Pipeline";
                document.getElementById("convert-modal").classList.remove("hidden");
            }

            function closeConvertModal() {
                document.getElementById("convert-modal").classList.add("hidden");
            }

            async function executeFastConversion() {
                if (!selectedLead) {
                    await fetchLeads();
                }
                if (!selectedLead) {
                    alert("Please select or create an account in the prospect pipeline to convert!");
                    return;
                }

                const btn = document.getElementById("btn-action-fast-convert");
                const origHtml = btn ? btn.innerHTML : "";
                if (btn) {
                    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Transferring Data to Client CRM...`;
                    btn.disabled = true;
                }

                const companyName = selectedLead.company ? selectedLead.company.name : "Prospect";
                const payload = {
                    account_tier: "enterprise",
                    reorder_cadence_days: 30,
                    initial_order_amount: 7500.00,
                    initial_order_items: "Initial Commercial B2B Supply Agreement (Tier 1)",
                    notes: (selectedLead.notes ? selectedLead.notes + " — " : "") + "Won and transferred from Prospect Pipeline."
                };

                try {
                    const res = await fetch(API_BASE + "/crm/leads/" + selectedLead.id + "/convert-to-client", {
                        method: "POST",
                        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId },
                        body: JSON.stringify(payload)
                    });
                    if (res.ok) {
                        const convertedClient = await res.json();
                        // Automatically switch to the Client CRM view!
                        switchCrmMode('clients');
                        await fetchClients();
                        await fetchClientStats();
                        selectClient(convertedClient);
                        fetchAuditLogs();
                        fetchLeads();

                        showToast(
                            "Lead Transferred to Client CRM!",
                            `Successfully transferred "${companyName}" to Client CRM (CRM 2) with initial $7,500.00 order recorded.`,
                            "fa-trophy",
                            "success"
                        );
                    } else {
                        const err = await res.json();
                        alert("Error converting lead: " + (err.detail || res.statusText));
                    }
                } catch(e) {
                    alert("Error during lead conversion: " + e.message);
                } finally {
                    if (btn) {
                        btn.innerHTML = origHtml;
                        btn.disabled = false;
                    }
                }
            }

            async function handleConvertLead(e) {
                e.preventDefault();
                if (!selectedLead) {
                    await fetchLeads();
                    if (!selectedLead) return;
                }

                const initialAmount = parseFloat(document.getElementById("modal-convert-sale-amount").value) || 0;
                const itemsSummary = document.getElementById("modal-convert-sale-items").value || "Initial Supply Agreement";
                const payload = {
                    account_tier: document.getElementById("modal-convert-tier").value,
                    reorder_cadence_days: parseInt(document.getElementById("modal-convert-cadence").value) || 30,
                    initial_order_amount: initialAmount,
                    initial_order_items: itemsSummary,
                    notes: document.getElementById("modal-convert-notes").value
                };

                const companyName = selectedLead.company ? selectedLead.company.name : "Prospect";

                try {
                    const res = await fetch(API_BASE + "/crm/leads/" + selectedLead.id + "/convert-to-client", {
                        method: "POST",
                        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId },
                        body: JSON.stringify(payload)
                    });
                    if (res.ok) {
                        const convertedClient = await res.json();
                        closeConvertModal();
                        // Switch to CRM 2
                        switchCrmMode('clients');
                        await fetchClients();
                        await fetchClientStats();
                        selectClient(convertedClient);
                        fetchAuditLogs();
                        fetchLeads();

                        showToast(
                            "Lead Transferred to Client CRM!",
                            `Successfully transferred "${companyName}" to Client CRM (CRM 2) with initial $${initialAmount.toLocaleString(undefined, {minimumFractionDigits: 2})} order recorded.`,
                            "fa-trophy",
                            "success"
                        );
                    } else {
                        const err = await res.json();
                        alert("Error converting lead: " + (err.detail || res.statusText));
                    }
                } catch(e) {
                    alert("Error converting lead: " + e.message);
                }
            }

            // ==============================================================================
            // CRM 3: AI Order Filler & Supply Chain Logistics Handlers
            // ==============================================================================

            let allSuppliers = [];
            let allPurchaseOrders = [];

            let allClientSalesList = [];

            async function fetchProcurementStats() {
                if (!authToken) return;
                try {
                    const res = await fetch(API_BASE + "/fulfillment/stats", {
                        headers: { "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId }
                    });
                    if (!res.ok) return;
                    const stats = await res.json();
                    
                    const spendVal = stats.total_procurement_spend || 0;
                    document.getElementById("proc-kpi-spend").innerText = "$" + spendVal.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                    
                    const salesVal = stats.total_sales_revenue || 0;
                    const salesEl = document.getElementById("bot-stat-sales-rev");
                    if (salesEl) salesEl.innerText = "$" + salesVal.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});

                    const marginVal = stats.net_profit_margin || 0;
                    const marginPct = stats.profit_margin_pct || 0;
                    const marginEl = document.getElementById("bot-stat-margin");
                    if (marginEl) marginEl.innerText = (marginVal >= 0 ? "+$" : "-$") + Math.abs(marginVal).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                    const marginPctEl = document.getElementById("bot-stat-margin-pct");
                    if (marginPctEl) marginPctEl.innerText = marginPct.toFixed(1) + "%";

                    const successRate = stats.shipping_success_rate !== undefined ? stats.shipping_success_rate : 100.0;
                    const successRateEl = document.getElementById("bot-stat-success-rate");
                    if (successRateEl) successRateEl.innerText = successRate.toFixed(1) + "%";
                    const delivEl = document.getElementById("bot-stat-delivered-count");
                    if (delivEl) delivEl.innerText = stats.delivered_orders_count || 0;

                    const splitEl = document.getElementById("bot-stat-dropship-split");
                    if (splitEl) splitEl.innerHTML = `${stats.dropship_orders_count || 0} Drop Ships<br><span class="text-slate-400 font-normal">${stats.warehouse_orders_count || 0} Warehouse</span>`;

                    const transitVal = stats.in_transit_shipments_count || 0;
                    document.getElementById("proc-kpi-transit").innerText = transitVal;
                    const transitEl = document.getElementById("bot-stat-active-transit");
                    if (transitEl) transitEl.innerText = transitVal;

                    const navSuccessEl = document.getElementById("kpi-nav-bot-success");
                    if (navSuccessEl) navSuccessEl.innerText = successRate.toFixed(1) + "%";
                    const badge = document.getElementById("nav-badge-shipments");
                    if (badge) badge.innerText = transitVal;

                    const supEl = document.getElementById("proc-kpi-suppliers");
                    if (supEl) supEl.innerText = stats.connected_suppliers_count || 0;
                    const unitEl = document.getElementById("proc-kpi-units");
                    if (unitEl) unitEl.innerText = (stats.units_in_transit || 0) + " Units";
                } catch(e) {
                    console.error("Error fetching procurement stats:", e);
                }
            }

            async function fetchAllSalesForFulfillmentSelector() {
                if (!authToken) return;
                try {
                    const res = await fetch(API_BASE + "/crm/sales", {
                        headers: { "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId }
                    });
                    if (!res.ok) return;
                    allClientSalesList = await res.json();
                    const sel = document.getElementById("in-autofill-client-sale");
                    if (!sel) return;
                    const currVal = sel.value;
                    sel.innerHTML = `<option value="">⚡ Direct Autonomous Procurement (No Client Sale)</option>`;
                    allClientSalesList.forEach(s => {
                        const opt = document.createElement("option");
                        opt.value = s.id;
                        const isFulfilled = !!s.po_number;
                        opt.innerText = `${s.order_number} • $${s.amount.toFixed(2)} (${s.items_summary.substring(0, 32)}...) ${isFulfilled ? '✓ Fulfilled' : '⚡ Needs Drop Ship'}`;
                        sel.appendChild(opt);
                    });
                    if (currVal) sel.value = currVal;
                } catch(e) {
                    console.error("Error loading sales for fulfillment selector:", e);
                }
            }

            function handleClientSaleSelection(saleId) {
                if (!saleId) {
                    const destType = document.getElementById("in-autofill-dest-type");
                    if (destType) destType.value = "warehouse";
                    return;
                }
                const sale = allClientSalesList.find(s => s.id === saleId);
                if (!sale) return;

                const destType = document.getElementById("in-autofill-dest-type");
                if (destType) destType.value = "customer_dropship";

                const promptEl = document.getElementById("in-autofill-prompt");
                if (promptEl) {
                    promptEl.value = `Order ${sale.items_summary} for customer fulfillment (${sale.order_number})`;
                }

                const budgetEl = document.getElementById("in-autofill-budget");
                if (budgetEl && sale.amount) {
                    budgetEl.value = Math.max(500, Math.round(sale.amount * 0.8));
                }

                const destEl = document.getElementById("in-autofill-destination");
                if (destEl) {
                    destEl.value = `Customer Destination Facility (${sale.order_number}), 500 Logistics Way`;
                }
            }

            function toggleFulfillmentMode(mode) {
                const destEl = document.getElementById("in-autofill-destination");
                if (!destEl) return;
                if (mode === "customer_dropship") {
                    if (destEl.value.includes("Main Logistics Warehouse")) {
                        destEl.value = "Customer Destination Facility (Direct Drop Ship)";
                    }
                } else {
                    destEl.value = "Main Logistics Warehouse (Bay 4), 100 Supply Chain Blvd";
                }
            }

            function triggerFulfillSaleFromLedger(saleId, orderNum, itemsSummary, clientName) {
                switchCrmMode('fulfillment');
                setTimeout(() => {
                    const sel = document.getElementById("in-autofill-client-sale");
                    if (sel) {
                        sel.value = saleId;
                    }
                    const destType = document.getElementById("in-autofill-dest-type");
                    if (destType) destType.value = "customer_dropship";

                    const promptEl = document.getElementById("in-autofill-prompt");
                    if (promptEl) {
                        promptEl.value = `Order ${itemsSummary} for customer fulfillment (${orderNum})`;
                    }

                    const destEl = document.getElementById("in-autofill-destination");
                    if (destEl) {
                        destEl.value = `${clientName ? clientName + ' Receiving Dock' : 'Customer Facility'}, Commercial Delivery Bay`;
                    }

                    promptEl?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    promptEl?.focus();
                }, 200);
            }

            async function fetchSuppliers() {
                if (!authToken) return;
                try {
                    const res = await fetch(API_BASE + "/fulfillment/suppliers", {
                        headers: { "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId }
                    });
                    if (!res.ok) return;
                    allSuppliers = await res.json();
                    
                    // Render into suppliers list
                    const container = document.getElementById("suppliers-list");
                    if (container) {
                        container.innerHTML = "";
                        allSuppliers.forEach(s => {
                            const isApi = s.adapter_type === 'api';
                            const badgeColor = isApi ? 'bg-indigo-950 text-indigo-300 border-indigo-700/50' : 'bg-emerald-950 text-emerald-300 border-emerald-700/50';
                            const card = document.createElement("div");
                            card.className = "p-3 rounded-lg bg-slate-900/90 border border-slate-800 flex items-center justify-between text-xs";
                            card.innerHTML = `
                                <div>
                                    <div class="flex items-center gap-2">
                                        <span class="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
                                        <span class="font-bold text-slate-100">${escapeHtml(s.name)}</span>
                                        <span class="px-1.5 py-0.5 rounded text-[10px] border ${badgeColor} font-mono">${escapeHtml(s.adapter_type.toUpperCase())}</span>
                                    </div>
                                    <div class="text-[11px] text-slate-400 mt-1 flex items-center gap-2">
                                        <span><i class="fa-solid fa-tag text-amber-400 mr-1"></i>${escapeHtml(s.category)}</span>
                                        <span>•</span>
                                        <span class="text-slate-500">${s.lead_days_estimate}d lead time</span>
                                    </div>
                                </div>
                                <a href="${escapeHtml(s.website_url)}" target="_blank" class="px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded text-[11px] text-slate-300 transition flex items-center gap-1">
                                    <i class="fa-solid fa-arrow-up-right-from-square"></i> Visit
                                </a>
                            `;
                            container.appendChild(card);
                        });
                    }

                    // Update target supplier dropdown options
                    const select = document.getElementById("in-autofill-supplier");
                    if (select) {
                        select.innerHTML = '<option value="auto">⚡ AI Auto-Route (Best Price/Stock)</option>';
                        allSuppliers.forEach(s => {
                            const opt = document.createElement("option");
                            opt.value = s.code;
                            opt.innerText = `${s.name} (${s.category})`;
                            select.appendChild(opt);
                        });
                    }
                } catch(e) {
                    console.error("Error fetching suppliers:", e);
                }
            }

            function openAddSupplierModal() {
                document.getElementById("modal-add-supplier").classList.remove("hidden");
                document.getElementById("in-sup-name").focus();
            }

            function closeAddSupplierModal() {
                document.getElementById("modal-add-supplier").classList.add("hidden");
            }

            async function handleCreateSupplier(e) {
                e.preventDefault();
                const name = document.getElementById("in-sup-name").value;
                const url = document.getElementById("in-sup-url").value;
                const adapter = document.getElementById("in-sup-adapter").value;
                const category = document.getElementById("in-sup-category").value;
                const notes = document.getElementById("in-sup-notes").value;
                const code = name.toLowerCase().replace(/[^a-z0-9]/g, '_');

                try {
                    const res = await fetch(API_BASE + "/fulfillment/suppliers", {
                        method: "POST",
                        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId },
                        body: JSON.stringify({
                            name: name,
                            code: code,
                            website_url: url,
                            adapter_type: adapter,
                            category: category,
                            lead_days_estimate: 2,
                            notes: notes
                        })
                    });
                    if (res.ok) {
                        closeAddSupplierModal();
                        document.getElementById("form-new-supplier").reset();
                        await fetchSuppliers();
                        await fetchProcurementStats();
                        showToast("Supplier Connected", `Registered "${name}" portal for AI automated purchasing.`, "fa-plug", "success");
                    } else {
                        const err = await res.json();
                        alert("Error adding supplier: " + (err.detail || res.statusText));
                    }
                } catch(err) {
                    alert("Error adding supplier: " + err.message);
                }
            }

            async function handleAutoFillOrder(e) {
                e.preventDefault();
                const prompt = document.getElementById("in-autofill-prompt").value;
                const supplierCode = document.getElementById("in-autofill-supplier").value;
                const budgetLimit = parseFloat(document.getElementById("in-autofill-budget").value) || 500.0;
                const destination = document.getElementById("in-autofill-destination").value;
                const clientSaleId = document.getElementById("in-autofill-client-sale") ? document.getElementById("in-autofill-client-sale").value : null;
                const destType = document.getElementById("in-autofill-dest-type") ? document.getElementById("in-autofill-dest-type").value : "warehouse";

                const btn = document.getElementById("btn-run-autofill");
                const logBox = document.getElementById("autofill-agent-log");
                btn.disabled = true;
                btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> AI Bot Analyzing Catalogs &amp; Purchasing...`;
                logBox.classList.remove("hidden");
                logBox.innerHTML = `
                    <div class="text-amber-400 font-bold"><i class="fa-solid fa-microchip mr-1"></i> Initializing Gemini Order Filler Agent...</div>
                    <div class="text-slate-400">Parsing prompt: "${escapeHtml(prompt)}"...</div>
                    <div class="text-slate-400">Querying supplier catalogs &amp; checking live stock...</div>
                `;

                try {
                    const res = await fetch(API_BASE + "/fulfillment/autofill", {
                        method: "POST",
                        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId },
                        body: JSON.stringify({
                            requirement_prompt: prompt,
                            preferred_supplier_code: supplierCode,
                            destination_address: destination,
                            destination_type: destType,
                            client_sale_id: clientSaleId || null,
                            max_budget_limit: budgetLimit
                        })
                    });
                    if (!res.ok) {
                        const err = await res.json();
                        throw new Error(err.detail || res.statusText);
                    }
                    const data = await res.json();
                    
                    let logHtml = `<div class="text-emerald-400 font-bold"><i class="fa-solid fa-check-double mr-1"></i> Order Processing Complete:</div>`;
                    (data.logs || []).forEach(l => {
                        logHtml += `<div class="text-slate-300">• ${escapeHtml(l)}</div>`;
                    });
                    if (data.requires_approval) {
                        logHtml += `<div class="text-amber-300 font-bold mt-1">⚠️ Safety Threshold: Placed in HITL queue for manager sign-off ($${data.total_cost.toFixed(2)} &gt; $${budgetLimit.toFixed(2)}).</div>`;
                    } else {
                        logHtml += `<div class="text-cyan-300 font-bold mt-1">✓ Order Confirmed: PO ${data.po_number} | Tracking: ${data.carrier} ${data.tracking_number}</div>`;
                    }
                    logBox.innerHTML = logHtml;

                    await fetchPurchaseOrders();
                    await fetchProcurementStats();
                    fetchAllSalesForFulfillmentSelector();
                    fetchClients();
                    fetchAuditLogs();

                    showToast(
                        data.requires_approval ? "Order Placed (Approval Required)" : "Order Purchased & Dispatched!",
                        `PO ${data.po_number} with ${data.supplier} ($${data.total_cost.toFixed(2)}) processed.`,
                        data.requires_approval ? "fa-shield-halved" : "fa-truck-fast",
                        data.requires_approval ? "info" : "success"
                    );
                } catch(err) {
                    logBox.innerHTML = `<div class="text-rose-400 font-bold">Error: ${escapeHtml(err.message)}</div>`;
                    alert("Error executing order autofill: " + err.message);
                } finally {
                    btn.disabled = false;
                    btn.innerHTML = `<i class="fa-solid fa-cart-shopping"></i> Run AI Auto-Fill &amp; Purchase`;
                }
            }

            function renderOrdersMatrix(orders) {
                const matrixBody = document.getElementById("orders-matrix-body");
                const matrixCount = document.getElementById("bot-matrix-count");
                if (matrixCount) {
                    const count = (orders && orders.length) || 0;
                    matrixCount.innerText = `${count} Order${count === 1 ? '' : 's'}`;
                }
                if (!matrixBody) return;

                if (!orders || orders.length === 0) {
                    matrixBody.innerHTML = `
                        <tr>
                            <td colspan="8" class="p-6 text-center text-slate-500 italic">
                                No purchase orders executed yet. Run the AI Order Filler below to process orders.
                            </td>
                        </tr>
                    `;
                    return;
                }

                matrixBody.innerHTML = orders.map(po => {
                    const isPending = po.status === 'pending_approval';
                    const isDelivered = po.status === 'delivered';
                    const totalUnits = (po.items_json || []).reduce((acc, it) => acc + (it.qty || 1), 0);
                    const sh = (po.shipments && po.shipments.length > 0) ? po.shipments[0] : null;

                    // 1. Customer Sale
                    let saleCell = `<span class="text-slate-500 italic text-[11px]">Direct Restock</span>`;
                    if (po.client_sale_order_number) {
                        const trackUrl = SUB_PATH + "/track/" + encodeURIComponent(po.client_sale_order_number);
                        saleCell = `
                            <div>
                                <div class="font-mono font-bold text-slate-200 text-xs">${escapeHtml(po.client_sale_order_number)}</div>
                                <div class="flex items-center gap-1.5 mt-0.5">
                                    <a href="${trackUrl}" target="_blank" class="text-[10px] text-cyan-400 hover:text-cyan-300 flex items-center gap-1 font-semibold" title="View Customer Tracking Portal">
                                        <i class="fa-solid fa-arrow-up-right-from-square text-[8px]"></i> Tracking
                                    </a>
                                    <span class="text-slate-600">&bull;</span>
                                    <a href="${SUB_PATH}/api/v1/documents/invoice/${encodeURIComponent(po.client_sale_order_number)}?print=true" target="_blank" class="text-[10px] text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-semibold" title="Print B2B Commercial Invoice">
                                        <i class="fa-solid fa-file-invoice text-[8px]"></i> Invoice
                                    </a>
                                    <span class="text-slate-600">&bull;</span>
                                    <a href="${SUB_PATH}/api/v1/documents/packing-slip/${encodeURIComponent(po.client_sale_order_number)}?print=true" target="_blank" class="text-[10px] text-amber-400 hover:text-amber-300 flex items-center gap-1 font-semibold" title="Print Warehouse Packing Slip">
                                        <i class="fa-solid fa-box-open text-[8px]"></i> Slip
                                    </a>
                                </div>
                                <div class="text-[11px] text-slate-400 font-medium">${escapeHtml(po.client_name || 'Client')}</div>
                                <div class="text-[11px] font-mono font-bold text-emerald-400">$${(po.client_sale_amount || 0).toFixed(2)}</div>
                            </div>
                        `;
                    }

                    // 2. Bot Purchasing (PO)
                    const poCell = `
                        <div>
                            <div class="font-mono font-bold text-amber-300 text-xs">${escapeHtml(po.po_number)}</div>
                            <div class="text-[10px] text-slate-400">${new Date(po.placed_at).toLocaleDateString([], {month:'short', day:'numeric'})}</div>
                            <div class="text-[10px] text-slate-400 font-mono">${totalUnits} Unit${totalUnits === 1 ? '' : 's'}</div>
                        </div>
                    `;

                    // 3. Supplier & Cost
                    const supplierCell = `
                        <div>
                            <div class="font-semibold text-slate-200 text-xs">${escapeHtml(po.supplier_name || 'Vendor')}</div>
                            <div class="font-mono font-bold text-slate-100 text-xs">$${po.total_cost.toFixed(2)}</div>
                        </div>
                    `;

                    // 4. Margin & ROI
                    let marginCell = `<span class="text-slate-500 text-[11px]">N/A</span>`;
                    if (po.profit_margin_dollars !== null && po.profit_margin_dollars !== undefined) {
                        const isPositive = po.profit_margin_dollars >= 0;
                        marginCell = `
                            <div>
                                <div class="font-mono font-bold ${isPositive ? 'text-emerald-400' : 'text-rose-400'} text-xs">
                                    ${isPositive ? '+' : ''}$${po.profit_margin_dollars.toFixed(2)}
                                </div>
                                <div class="text-[10px] font-mono ${isPositive ? 'text-emerald-300' : 'text-rose-300'} font-semibold">
                                    ${po.profit_margin_pct}% ROI
                                </div>
                            </div>
                        `;
                    }

                    // 5. Drop Shipping Mode
                    const isDropShip = po.destination_type === 'customer_dropship';
                    const dropShipCell = isDropShip ? `
                        <div>
                            <span class="px-2 py-0.5 rounded-full text-[10px] bg-amber-950/90 text-amber-300 border border-amber-600/60 font-semibold flex items-center gap-1 w-max">
                                <i class="fa-solid fa-truck-arrow-right text-amber-400"></i> Drop Ship
                            </span>
                            <div class="text-[10px] text-slate-400 truncate max-w-[140px] mt-1" title="${escapeHtml(po.destination_address || '')}">
                                ${escapeHtml(po.destination_address || 'Customer Address')}
                            </div>
                        </div>
                    ` : `
                        <div>
                            <span class="px-2 py-0.5 rounded-full text-[10px] bg-slate-800 text-slate-300 border border-slate-700 font-semibold flex items-center gap-1 w-max">
                                <i class="fa-solid fa-warehouse text-slate-400"></i> Warehouse
                            </span>
                            <div class="text-[10px] text-slate-500 mt-1">Central Facility</div>
                        </div>
                    `;

                    // 6. Carrier Tracking
                    let trackingCell = `<span class="text-slate-500 text-[11px]">Awaiting Dispatch</span>`;
                    if (sh) {
                        trackingCell = `
                            <div>
                                <div class="font-semibold text-slate-300 text-[11px] flex items-center gap-1">
                                    <i class="fa-solid fa-truck text-indigo-400 text-[10px]"></i> ${escapeHtml(sh.carrier || 'Carrier')}
                                </div>
                                <a href="${escapeHtml(sh.tracking_url || '#')}" target="_blank" class="font-mono text-cyan-400 hover:text-cyan-300 font-bold text-[11px] flex items-center gap-1 mt-0.5">
                                    ${escapeHtml(sh.tracking_number || '')} <i class="fa-solid fa-arrow-up-right-from-square text-[8px]"></i>
                                </a>
                            </div>
                        `;
                    }

                    // 7. Shipping Success Status
                    const stagePct = po.shipping_stage_pct !== null && po.shipping_stage_pct !== undefined ? po.shipping_stage_pct : (isDelivered ? 100 : (sh ? 40 : 0));
                    const successStatus = po.shipping_success_status || (isDelivered ? 'Complete Success' : (isPending ? 'Pending Approval' : 'In Transit'));
                    const statusColor = isDelivered ? 'text-emerald-400' : (isPending ? 'text-amber-400' : 'text-indigo-300');
                    const barColor = isDelivered ? 'bg-emerald-500' : 'bg-gradient-to-r from-amber-500 to-indigo-500';

                    const statusCell = `
                        <div class="space-y-1">
                            <div class="flex items-center justify-between gap-2 text-[10px] font-bold">
                                <span class="${statusColor} flex items-center gap-1">
                                    <i class="fa-solid ${isDelivered ? 'fa-circle-check text-emerald-400' : (isPending ? 'fa-clock text-amber-400' : 'fa-truck-fast text-indigo-400')}"></i>
                                    ${escapeHtml(successStatus)}
                                </span>
                                <span class="font-mono text-slate-400">${stagePct}%</span>
                            </div>
                            <div class="w-28 bg-slate-800 rounded-full h-1.5 overflow-hidden">
                                <div class="h-1.5 rounded-full ${barColor} transition-all duration-500" style="width: ${stagePct}%"></div>
                            </div>
                        </div>
                    `;

                    // 8. Actions
                    let actionsCell = "";
                    if (isPending) {
                        actionsCell = `
                            <button onclick="approvePurchaseOrder('${po.id}')" class="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded text-[10px] shadow transition flex items-center gap-1 ml-auto cursor-pointer">
                                <i class="fa-solid fa-check"></i> Approve
                            </button>
                        `;
                    } else if (sh && !isDelivered) {
                        actionsCell = `
                            <button onclick="advanceShipmentMilestone('${sh.id}')" class="px-2.5 py-1 bg-amber-600 hover:bg-amber-500 text-slate-950 font-bold rounded text-[10px] shadow transition flex items-center gap-1 ml-auto cursor-pointer">
                                <i class="fa-solid fa-forward-step"></i> Advance Scan
                            </button>
                        `;
                    } else if (isDelivered) {
                        actionsCell = `
                            <span class="text-emerald-400 font-bold text-[10px] flex items-center justify-end gap-1">
                                <i class="fa-solid fa-check-double"></i> Delivered
                            </span>
                        `;
                    } else {
                        actionsCell = `<span class="text-slate-600 text-[10px]">-</span>`;
                    }

                    return `
                        <tr class="hover:bg-slate-900/60 transition border-b border-slate-800/60">
                            <td class="p-2.5 align-top">${saleCell}</td>
                            <td class="p-2.5 align-top">${poCell}</td>
                            <td class="p-2.5 align-top">${supplierCell}</td>
                            <td class="p-2.5 align-top">${marginCell}</td>
                            <td class="p-2.5 align-top">${dropShipCell}</td>
                            <td class="p-2.5 align-top">${trackingCell}</td>
                            <td class="p-2.5 align-top">${statusCell}</td>
                            <td class="p-2.5 align-top text-right">${actionsCell}</td>
                        </tr>
                    `;
                }).join("");
            }

            async function fetchPurchaseOrders() {
                if (!authToken) return;
                try {
                    const res = await fetch(API_BASE + "/fulfillment/orders", {
                        headers: { "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId }
                    });
                    if (!res.ok) return;
                    allPurchaseOrders = await res.json();

                    // Render Order Bot Success Matrix Table
                    renderOrdersMatrix(allPurchaseOrders);

                    const container = document.getElementById("orders-feed-container");
                    if (!container) return;
                    container.innerHTML = "";

                    if (!allPurchaseOrders.length) {
                        container.innerHTML = `
                            <div class="p-8 text-center text-slate-500 italic bg-slate-900/50 rounded-xl border border-slate-800">
                                <i class="fa-solid fa-cart-plus text-3xl mb-2 block text-slate-600"></i>
                                No purchase orders placed yet. Use the AI Order Filler panel on the left to purchase inventory.
                            </div>
                        `;
                        return;
                    }

                    allPurchaseOrders.forEach(po => {
                        const isPending = po.status === 'pending_approval';
                        const isDelivered = po.status === 'delivered';
                        const statusColors = {
                            'pending_approval': 'bg-amber-950 text-amber-300 border-amber-600/50',
                            'ordered': 'bg-blue-950 text-blue-300 border-blue-600/50',
                            'in_transit': 'bg-indigo-950 text-indigo-300 border-indigo-600/50',
                            'shipped': 'bg-indigo-950 text-indigo-300 border-indigo-600/50',
                            'delivered': 'bg-emerald-950 text-emerald-300 border-emerald-600/50'
                        };
                        const badgeClass = statusColors[po.status] || 'bg-slate-800 text-slate-300 border-slate-700';

                        // Calculate total item count
                        const totalUnits = (po.items_json || []).reduce((acc, it) => acc + (it.qty || 1), 0);
                        const itemsSummary = (po.items_json || []).map(it => `${it.qty}x ${it.name}`).join(", ");

                        // Shipment Card Section
                        let shipmentHtml = "";
                        if (po.shipments && po.shipments.length > 0) {
                            const sh = po.shipments[0];
                            const stages = [
                                { id: 'label_created', label: 'Label Created' },
                                { id: 'picked_up', label: 'Picked Up' },
                                { id: 'in_transit', label: 'In Transit' },
                                { id: 'out_for_delivery', label: 'Out for Delivery' },
                                { id: 'delivered', label: 'Delivered' }
                            ];
                            const stageIds = stages.map(s => s.id);
                            const currentIdx = stageIds.indexOf(sh.current_status);

                            // Stepper HTML
                            let stepsHtml = "";
                            stages.forEach((s, idx) => {
                                const isDone = idx <= currentIdx;
                                const isCurrent = idx === currentIdx;
                                const dotBg = isDone ? 'bg-emerald-500 text-slate-950' : 'bg-slate-800 text-slate-500 border border-slate-700';
                                const lineBg = idx < currentIdx ? 'bg-emerald-500' : 'bg-slate-800';
                                
                                stepsHtml += `
                                    <div class="flex-1 flex flex-col items-center relative">
                                        ${idx > 0 ? `<div class="absolute top-3 right-1/2 w-full h-0.5 ${lineBg} -z-0"></div>` : ''}
                                        <div class="h-6 w-6 rounded-full flex items-center justify-center text-[10px] font-bold z-10 ${dotBg} ${isCurrent && !isDelivered ? 'ring-2 ring-emerald-400 ring-offset-2 ring-offset-slate-900 animate-pulse' : ''}">
                                            ${isDone ? '<i class="fa-solid fa-check"></i>' : (idx + 1)}
                                        </div>
                                        <span class="text-[10px] mt-1 text-center font-medium ${isDone ? 'text-emerald-300 font-bold' : 'text-slate-500'}">${s.label}</span>
                                    </div>
                                `;
                            });

                            // Events log list
                            let eventsHtml = "";
                            (sh.history_events || []).forEach(ev => {
                                eventsHtml += `
                                    <div class="text-[10px] text-slate-400 flex items-start gap-2 border-l border-slate-700 pl-2 py-0.5">
                                        <span class="text-slate-500 font-mono">${new Date(ev.timestamp).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}</span>
                                        <span class="font-semibold text-slate-300">${escapeHtml(ev.location)}:</span>
                                        <span class="text-slate-400">${escapeHtml(ev.description)}</span>
                                    </div>
                                `;
                            });

                            shipmentHtml = `
                                <div class="mt-3 p-3 rounded-xl bg-slate-950/80 border border-slate-700/60 space-y-3">
                                    <div class="flex flex-wrap items-center justify-between gap-2 text-xs">
                                        <div class="flex items-center gap-2">
                                            <span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-indigo-900/60 text-indigo-300 border border-indigo-700/50 flex items-center gap-1">
                                                <i class="fa-solid fa-truck"></i> ${escapeHtml(sh.carrier)}
                                            </span>
                                            <a href="${escapeHtml(sh.tracking_url || '#')}" target="_blank" class="font-mono text-cyan-400 hover:text-cyan-300 flex items-center gap-1 font-bold">
                                                ${escapeHtml(sh.tracking_number)} <i class="fa-solid fa-arrow-up-right-from-square text-[9px]"></i>
                                            </a>
                                        </div>
                                        <div class="flex items-center gap-2">
                                            ${!isDelivered ? `
                                                <button onclick="advanceShipmentMilestone('${sh.id}')" class="px-2.5 py-1 bg-amber-600 hover:bg-amber-500 text-slate-950 font-bold rounded text-[11px] transition flex items-center gap-1 cursor-pointer">
                                                    <i class="fa-solid fa-forward-step"></i> Advance Transit Scan
                                                </button>
                                            ` : `
                                                <span class="px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-700/50 flex items-center gap-1">
                                                    <i class="fa-solid fa-box-archive"></i> In Stock (Warehouse Bay 4)
                                                </span>
                                            `}
                                            <button onclick="openDispatchModal('${po.id}', '${po.po_number}', '${escapeHtml(itemsSummary)}')" class="px-2.5 py-1 bg-emerald-700 hover:bg-emerald-600 text-white font-semibold rounded text-[11px] transition flex items-center gap-1 cursor-pointer">
                                                <i class="fa-solid fa-paper-plane"></i> Dispatch to Client
                                            </button>
                                        </div>
                                    </div>

                                    <!-- Stepper Progress Bar -->
                                    <div class="flex items-center justify-between pt-1 pb-1">
                                        ${stepsHtml}
                                    </div>

                                    <!-- Recent Milestones Accordion -->
                                    <div class="space-y-1 pt-1">
                                        <span class="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Carrier Activity Log:</span>
                                        ${eventsHtml}
                                    </div>
                                </div>
                            `;
                        }

                        const card = document.createElement("div");
                        card.className = "p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3 shadow-lg hover:border-slate-700 transition";
                        card.innerHTML = `
                            <div class="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-slate-800">
                                <div class="flex items-center gap-2.5">
                                    <div class="h-8 w-8 rounded-lg bg-amber-500/20 text-amber-400 flex items-center justify-center font-mono font-bold text-xs">
                                        <i class="fa-solid fa-receipt"></i>
                                    </div>
                                    <div>
                                        <div class="flex items-center gap-2">
                                            <span class="font-mono font-bold text-sm text-slate-100">${escapeHtml(po.po_number)}</span>
                                            <span class="px-2 py-0.5 rounded-full text-[10px] border ${badgeClass} font-semibold uppercase tracking-wider">${escapeHtml(po.status.replace(/_/g, ' '))}</span>
                                        </div>
                                        <p class="text-[11px] text-slate-400 mt-0.5">
                                            Supplier: <strong class="text-slate-200">${escapeHtml(po.supplier_name || 'Vendor')}</strong> • 
                                            Placed: <span class="text-slate-400">${new Date(po.placed_at).toLocaleDateString([], {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'})}</span>
                                        </p>
                                    </div>
                                </div>
                                <div class="text-right">
                                    <div class="font-mono font-bold text-base text-emerald-400">$${po.total_cost.toFixed(2)}</div>
                                    <div class="text-[10px] text-slate-400">${totalUnits} Total Units</div>
                                </div>
                            </div>

                            ${po.client_sale_order_number ? `
                                <div class="p-2.5 rounded-lg bg-emerald-950/40 border border-emerald-500/30 flex flex-wrap items-center justify-between gap-2 text-xs">
                                    <div class="flex items-center gap-2">
                                        <span class="px-1.5 py-0.5 rounded bg-emerald-900/60 text-emerald-300 font-mono font-bold text-[10px] border border-emerald-600/40">
                                            <i class="fa-solid fa-tag"></i> Linked Sale: ${escapeHtml(po.client_sale_order_number)}
                                        </span>
                                        <span class="text-slate-200 font-semibold">${escapeHtml(po.client_name || 'Client')}</span>
                                        <span class="text-slate-400 font-mono">($${(po.client_sale_amount || 0).toFixed(2)})</span>
                                        <a href="${SUB_PATH}/api/v1/documents/invoice/${encodeURIComponent(po.client_sale_order_number)}?print=true" target="_blank" class="px-1.5 py-0.5 bg-slate-800 hover:bg-slate-700 text-indigo-300 border border-slate-700 rounded text-[9px] font-semibold flex items-center gap-1 ml-1" title="Print Invoice">
                                            <i class="fa-solid fa-file-invoice"></i> Invoice
                                        </a>
                                        <a href="${SUB_PATH}/api/v1/documents/packing-slip/${encodeURIComponent(po.client_sale_order_number)}?print=true" target="_blank" class="px-1.5 py-0.5 bg-slate-800 hover:bg-slate-700 text-amber-300 border border-slate-700 rounded text-[9px] font-semibold flex items-center gap-1" title="Print Warehouse Packing Slip">
                                            <i class="fa-solid fa-box-open"></i> Slip
                                        </a>
                                    </div>
                                    <div class="flex items-center gap-2.5">
                                        <span class="text-[11px] ${po.destination_type === 'customer_dropship' ? 'text-amber-300 font-semibold' : 'text-slate-400'}">
                                            <i class="fa-solid ${po.destination_type === 'customer_dropship' ? 'fa-truck-arrow-right text-amber-400' : 'fa-warehouse text-slate-400'}"></i>
                                            ${po.destination_type === 'customer_dropship' ? 'Direct Drop Ship' : 'Warehouse Restock'}
                                        </span>
                                        ${po.profit_margin_dollars !== null && po.profit_margin_dollars !== undefined ? `
                                            <span class="font-mono font-bold text-emerald-400 bg-emerald-950/80 px-2 py-0.5 rounded border border-emerald-700/50 text-[11px]">
                                                Margin: +$${po.profit_margin_dollars.toFixed(2)} (${po.profit_margin_pct}%)
                                            </span>
                                        ` : ''}
                                    </div>
                                </div>
                            ` : ''}

                            ${isPending ? `
                                <div class="p-3 rounded-lg bg-amber-950/60 border border-amber-600/70 flex flex-col md:flex-row items-start md:items-center justify-between gap-3 text-xs">
                                    <div>
                                        <div class="font-bold text-amber-300 flex items-center gap-1.5">
                                            <i class="fa-solid fa-shield-halved"></i> High-Spend Protection Hold
                                        </div>
                                        <p class="text-slate-300 text-[11px] mt-0.5">${escapeHtml(po.approval_reason || 'Order exceeds auto-purchase budget cap.')}</p>
                                    </div>
                                    <button onclick="approvePurchaseOrder('${po.id}')" class="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-lg text-xs shadow-md transition flex items-center gap-1.5 cursor-pointer shrink-0">
                                        <i class="fa-solid fa-check"></i> Approve &amp; Execute Order
                                    </button>
                                </div>
                            ` : ''}

                            <!-- Itemized Breakdown -->
                            <div class="overflow-x-auto">
                                <table class="w-full text-left text-xs text-slate-300 border border-slate-800 rounded">
                                    <thead class="bg-slate-950 text-slate-400 text-[10px] uppercase font-mono">
                                        <tr>
                                            <th class="p-2">SKU</th>
                                            <th class="p-2">Item Description</th>
                                            <th class="p-2 text-center">Qty</th>
                                            <th class="p-2 text-right">Unit Price</th>
                                            <th class="p-2 text-right">Total</th>
                                        </tr>
                                    </thead>
                                    <tbody class="divide-y divide-slate-800/60 font-sans">
                                        ${(po.items_json || []).map(it => `
                                            <tr>
                                                <td class="p-2 font-mono text-[11px] text-indigo-300">${escapeHtml(it.sku)}</td>
                                                <td class="p-2 font-medium text-slate-200">${escapeHtml(it.name)}</td>
                                                <td class="p-2 text-center font-mono">${it.qty}</td>
                                                <td class="p-2 text-right font-mono">$${(it.unit_cost || 0).toFixed(2)}</td>
                                                <td class="p-2 text-right font-mono font-bold text-slate-100">$${(it.total || 0).toFixed(2)}</td>
                                            </tr>
                                        `).join('')}
                                    </tbody>
                                </table>
                            </div>

                            ${shipmentHtml}
                        `;
                        container.appendChild(card);
                    });
                } catch(e) {
                    console.error("Error fetching purchase orders:", e);
                }
            }

            async function approvePurchaseOrder(poId) {
                try {
                    const res = await fetch(API_BASE + "/fulfillment/orders/" + poId + "/approve", {
                        method: "POST",
                        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId }
                    });
                    if (res.ok) {
                        const data = await res.json();
                        await fetchPurchaseOrders();
                        await fetchProcurementStats();
                        fetchAllSalesForFulfillmentSelector();
                        if (typeof selectedClient !== 'undefined' && selectedClient && selectedClient.id) {
                            fetchSalesForClient(selectedClient.id);
                        }
                        showToast("Purchase Order Approved!", `Order dispatched. Tracking: ${data.carrier} ${data.tracking_number}`, "fa-check", "success");
                    } else {
                        const err = await res.json();
                        alert("Error approving order: " + (err.detail || res.statusText));
                    }
                } catch(e) {
                    alert("Error approving order: " + e.message);
                }
            }

            async function advanceShipmentMilestone(trackingId) {
                try {
                    const res = await fetch(API_BASE + "/fulfillment/shipments/" + trackingId + "/advance", {
                        method: "POST",
                        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId },
                        body: JSON.stringify({})
                    });
                    if (res.ok) {
                        const data = await res.json();
                        await fetchPurchaseOrders();
                        await fetchProcurementStats();
                        fetchAllSalesForFulfillmentSelector();
                        if (typeof selectedClient !== 'undefined' && selectedClient && selectedClient.id) {
                            fetchSalesForClient(selectedClient.id);
                        }
                        showToast("Carrier Scan Updated", `Milestone reached: ${data.current_status.toUpperCase().replace(/_/g, ' ')} (${data.carrier} ${data.tracking_number})`, "fa-truck-fast", "success");
                    } else {
                        const err = await res.json();
                        alert("Error advancing tracking: " + (err.detail || res.statusText));
                    }
                } catch(e) {
                    alert("Error advancing tracking: " + e.message);
                }
            }

            function openDispatchModal(poId, poNumber, itemsSummary) {
                document.getElementById("dispatch-po-id").value = poId;
                document.getElementById("dispatch-po-label").innerText = poNumber;
                document.getElementById("dispatch-items-label").innerText = itemsSummary;

                // Populate client select
                const sel = document.getElementById("dispatch-client-select");
                sel.innerHTML = '<option value="">Select Client Account (Autofills Destination)...</option>';
                allClients.forEach(c => {
                    const opt = document.createElement("option");
                    opt.value = c.id;
                    opt.innerText = `${c.account_name} (${c.account_tier.toUpperCase()})`;
                    sel.appendChild(opt);
                });

                document.getElementById("modal-dispatch").classList.remove("hidden");
            }

            function closeDispatchModal() {
                document.getElementById("modal-dispatch").classList.add("hidden");
            }

            function populateClientAddress(clientId) {
                if (!clientId) return;
                const client = allClients.find(c => c.id === clientId);
                if (client && client.company && client.company.address) {
                    document.getElementById("dispatch-address").value = client.company.address;
                } else if (client) {
                    document.getElementById("dispatch-address").value = `${client.account_name} Receiving Facility, Dock 2`;
                }
            }

            async function handleDispatchShipment(e) {
                e.preventDefault();
                const poId = document.getElementById("dispatch-po-id").value;
                const carrier = document.getElementById("dispatch-carrier").value;
                const dest = document.getElementById("dispatch-address").value;

                try {
                    const res = await fetch(API_BASE + "/fulfillment/shipments/dispatch", {
                        method: "POST",
                        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId },
                        body: JSON.stringify({
                            purchase_order_id: poId,
                            carrier: carrier,
                            destination: dest
                        })
                    });
                    if (res.ok) {
                        const data = await res.json();
                        closeDispatchModal();
                        await fetchPurchaseOrders();
                        await fetchProcurementStats();
                        showToast("Outbound Shipment Dispatched!", `Carrier ${data.carrier} manifest generated with tracking ${data.tracking_number}.`, "fa-paper-plane", "success");
                    } else {
                        const err = await res.json();
                        alert("Error dispatching shipment: " + (err.detail || res.statusText));
                    }
                } catch(err) {
                    alert("Error dispatching shipment: " + err.message);
                }
            }

            // ==============================================================================
            // CRM 4: Multi-Tenant White-Labeling & Stripe Connect Handlers
            // ==============================================================================

            let cachedOrgSettings = null;

            async function fetchOrganizationSettings() {
                if (!authToken) return;
                const icon = document.getElementById("btn-settings-refresh-icon");
                if (icon) icon.classList.add("fa-spin");

                try {
                    const res = await fetch(API_BASE + "/orgs/settings", {
                        headers: { "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId }
                    });
                    if (!res.ok) return;
                    const data = await res.json();
                    cachedOrgSettings = data;

                    // Populate form fields
                    const orgInput = document.getElementById("setting-org-name");
                    if (orgInput) orgInput.value = data.name || "";
                    const brandInput = document.getElementById("setting-brand-name");
                    if (brandInput) brandInput.value = data.brand_name || "";
                    const logoInput = document.getElementById("setting-brand-logo-url");
                    if (logoInput) logoInput.value = data.brand_logo_url || "";
                    
                    const accentColor = data.brand_accent_color || "#4f46e5";
                    const picker = document.getElementById("setting-accent-picker");
                    if (picker) picker.value = accentColor;
                    const hexInput = document.getElementById("setting-accent-hex");
                    if (hexInput) hexInput.value = accentColor;
                    
                    const emailInput = document.getElementById("setting-support-email");
                    if (emailInput) emailInput.value = data.support_email || "";
                    const phoneInput = document.getElementById("setting-support-phone");
                    if (phoneInput) phoneInput.value = data.support_phone || "";
                    const noticeInput = document.getElementById("setting-tracking-notice");
                    if (noticeInput) noticeInput.value = data.tracking_portal_notice || "";
                    const footerInput = document.getElementById("setting-custom-footer");
                    if (footerInput) footerInput.value = data.custom_footer_text || "";

                    const pubKeyInput = document.getElementById("setting-stripe-pub-key");
                    if (pubKeyInput) pubKeyInput.value = data.stripe_publishable_key || "";
                    const secInput = document.getElementById("setting-stripe-sec-key");
                    if (secInput) {
                        if (data.has_stripe_secret && data.masked_stripe_secret) {
                            secInput.value = data.masked_stripe_secret;
                        } else {
                            secInput.value = "";
                        }
                    }

                    const webhookInput = document.getElementById("setting-stripe-webhook-sec");
                    if (webhookInput) {
                        if (data.has_stripe_webhook_secret) {
                            webhookInput.value = "whsec_••••••••••••••••";
                        } else {
                            webhookInput.value = "";
                        }
                    }

                    // Multi-Channel Notification Gateways
                    const twilioSid = document.getElementById("setting-twilio-sid");
                    if (twilioSid) twilioSid.value = data.twilio_account_sid || "";
                    const twilioToken = document.getElementById("setting-twilio-token");
                    if (twilioToken) {
                        if (data.has_twilio_token && data.masked_twilio_token) {
                            twilioToken.value = data.masked_twilio_token;
                        } else {
                            twilioToken.value = "";
                        }
                    }
                    const twilioPhone = document.getElementById("setting-twilio-phone");
                    if (twilioPhone) twilioPhone.value = data.twilio_from_number || "";

                    const twilioBadge = document.getElementById("badge-twilio-status");
                    if (twilioBadge) {
                        if (data.is_sms_configured) {
                            twilioBadge.innerHTML = `<i class="fa-solid fa-circle-check text-cyan-400"></i> Twilio Live`;
                            twilioBadge.className = "text-[10px] font-mono text-cyan-400 font-semibold";
                        } else {
                            twilioBadge.innerHTML = `<i class="fa-solid fa-bolt text-slate-400"></i> Simulation Ready`;
                            twilioBadge.className = "text-[10px] font-mono text-slate-400";
                        }
                    }

                    const sendgridKey = document.getElementById("setting-sendgrid-key");
                    if (sendgridKey) {
                        if (data.has_sendgrid_key && data.masked_sendgrid_key) {
                            sendgridKey.value = data.masked_sendgrid_key;
                        } else {
                            sendgridKey.value = "";
                        }
                    }
                    const emailFrom = document.getElementById("setting-email-from");
                    if (emailFrom) emailFrom.value = data.email_from_address || "";
                    const emailName = document.getElementById("setting-email-name");
                    if (emailName) emailName.value = data.email_from_name || "";

                    const sendgridBadge = document.getElementById("badge-sendgrid-status");
                    if (sendgridBadge) {
                        if (data.is_email_configured) {
                            sendgridBadge.innerHTML = `<i class="fa-solid fa-circle-check text-purple-400"></i> SendGrid Live`;
                            sendgridBadge.className = "text-[10px] font-mono text-purple-400 font-semibold";
                        } else {
                            sendgridBadge.innerHTML = `<i class="fa-solid fa-bolt text-slate-400"></i> Simulation Ready`;
                            sendgridBadge.className = "text-[10px] font-mono text-slate-400";
                        }
                    }

                    // Status ribbons
                    const labelOrg = document.getElementById("label-settings-org-id");
                    if (labelOrg) labelOrg.innerText = data.brand_name || data.name || data.slug || "Active";
                    const modeLabel = document.getElementById("label-settings-payment-mode");
                    const navBadge = document.getElementById("nav-badge-payment-status");
                    if (data.is_payment_configured) {
                        if (modeLabel) {
                            modeLabel.innerHTML = `<i class="fa-solid fa-circle-check text-emerald-400"></i> Direct Stripe Live`;
                            modeLabel.className = "font-semibold text-emerald-400 flex items-center gap-1";
                        }
                        if (navBadge) {
                            navBadge.innerText = "Stripe Live";
                            navBadge.className = "px-2 py-0.5 rounded-full text-[10px] bg-emerald-950/80 text-emerald-300 font-mono border border-emerald-700/50";
                        }
                    } else {
                        if (modeLabel) {
                            modeLabel.innerHTML = `<i class="fa-solid fa-bolt text-indigo-400"></i> Simulation Ready`;
                            modeLabel.className = "font-semibold text-indigo-300 flex items-center gap-1";
                        }
                        if (navBadge) {
                            navBadge.innerText = "Sim Ready";
                            navBadge.className = "px-2 py-0.5 rounded-full text-[10px] bg-purple-950/80 text-purple-300 font-mono border border-purple-700/50";
                        }
                    }

                    updateLiveBrandPreview();
                    fetchNotificationHistory();
                } catch(e) {
                    console.error("Error fetching organization settings:", e);
                } finally {
                    if (icon) icon.classList.remove("fa-spin");
                }
            }

            function syncAccentColorFromPicker(val) {
                const hexInput = document.getElementById("setting-accent-hex");
                if (hexInput) hexInput.value = val;
                updateLiveBrandPreview();
            }

            function syncAccentColorFromText(val) {
                if (val && !val.startsWith("#")) val = "#" + val;
                if (val.length === 7) {
                    const picker = document.getElementById("setting-accent-picker");
                    if (picker) picker.value = val;
                }
                updateLiveBrandPreview();
            }

            function updateLiveBrandPreview() {
                const brandName = (document.getElementById("setting-brand-name")?.value) || (document.getElementById("setting-org-name")?.value) || "Acme Supply Co.";
                const logoUrl = document.getElementById("setting-brand-logo-url")?.value || "";
                const accentColor = document.getElementById("setting-accent-hex")?.value || "#4f46e5";
                const supportEmail = document.getElementById("setting-support-email")?.value || "support@acmesupply.com";
                const trackingNotice = document.getElementById("setting-tracking-notice")?.value || "";

                // Live Preview Updates
                const previewBrand = document.getElementById("preview-brand-name");
                if (previewBrand) previewBrand.innerText = brandName;
                const previewBtnBrand = document.getElementById("preview-btn-brand-name");
                if (previewBtnBrand) previewBtnBrand.innerText = brandName;
                const previewEmail = document.getElementById("preview-support-email");
                if (previewEmail) previewEmail.innerText = supportEmail;

                // Swatch ribbons
                const swatchSmall = document.getElementById("swatch-accent-small");
                if (swatchSmall) swatchSmall.style.backgroundColor = accentColor;
                const textAccent = document.getElementById("text-accent-hex-val");
                if (textAccent) textAccent.innerText = accentColor;

                // Notice Box
                const noticeBox = document.getElementById("preview-notice-box");
                if (noticeBox) {
                    if (trackingNotice.trim()) {
                        noticeBox.classList.remove("hidden");
                        noticeBox.innerText = trackingNotice;
                    } else {
                        noticeBox.classList.add("hidden");
                    }
                }

                // Logo box
                const logoBox = document.getElementById("preview-logo-box");
                if (logoBox) {
                    if (logoUrl.trim()) {
                        logoBox.innerHTML = `<img src="${logoUrl}" alt="Logo" class="h-full w-full object-contain p-0.5">`;
                    } else {
                        logoBox.innerHTML = `<i class="fa-solid fa-truck-ramp-box text-indigo-400"></i>`;
                    }
                }

                // Button and bar theme
                const btnPay = document.getElementById("preview-btn-pay");
                if (btnPay) btnPay.style.backgroundColor = accentColor;
                const progBar = document.getElementById("preview-progress-bar");
                if (progBar) progBar.style.backgroundColor = accentColor;
            }

            function toggleStripeSecretVisibility() {
                const input = document.getElementById("setting-stripe-sec-key");
                const icon = document.getElementById("icon-toggle-secret");
                if (!input || !icon) return;
                if (input.type === "password") {
                    input.type = "text";
                    icon.classList.remove("fa-eye");
                    icon.classList.add("fa-eye-slash");
                } else {
                    input.type = "password";
                    icon.classList.remove("fa-eye-slash");
                    icon.classList.add("fa-eye");
                }
            }

            function copyWebhookEndpointUrl() {
                const urlEl = document.getElementById("text-webhook-url-display");
                const url = urlEl ? urlEl.innerText.trim() : "https://therealbonz.com/JsProject/api/v1/payments/stripe/webhook";
                navigator.clipboard.writeText(url).then(() => {
                    showToast("Webhook URL Copied!", "Copied Stripe webhook listener endpoint to clipboard.", "fa-copy", "info");
                }).catch(() => {
                    prompt("Copy your Stripe Webhook URL:", url);
                });
            }

            async function saveOrganizationSettings() {
                if (!authToken) return;

                const payload = {
                    name: document.getElementById("setting-org-name")?.value.trim() || undefined,
                    brand_name: document.getElementById("setting-brand-name")?.value.trim() || undefined,
                    brand_logo_url: document.getElementById("setting-brand-logo-url")?.value.trim() || undefined,
                    brand_accent_color: document.getElementById("setting-accent-hex")?.value.trim() || undefined,
                    support_email: document.getElementById("setting-support-email")?.value.trim() || undefined,
                    support_phone: document.getElementById("setting-support-phone")?.value.trim() || undefined,
                    tracking_portal_notice: document.getElementById("setting-tracking-notice")?.value.trim() || undefined,
                    custom_footer_text: document.getElementById("setting-custom-footer")?.value.trim() || undefined,
                    stripe_publishable_key: document.getElementById("setting-stripe-pub-key")?.value.trim() || undefined,
                    stripe_secret_key: document.getElementById("setting-stripe-sec-key")?.value.trim() || undefined,
                    stripe_webhook_secret: document.getElementById("setting-stripe-webhook-sec")?.value.trim() || undefined,
                    twilio_account_sid: document.getElementById("setting-twilio-sid")?.value.trim() || undefined,
                    twilio_auth_token: document.getElementById("setting-twilio-token")?.value.trim() || undefined,
                    twilio_from_number: document.getElementById("setting-twilio-phone")?.value.trim() || undefined,
                    sendgrid_api_key: document.getElementById("setting-sendgrid-key")?.value.trim() || undefined,
                    email_from_address: document.getElementById("setting-email-from")?.value.trim() || undefined,
                    email_from_name: document.getElementById("setting-email-name")?.value.trim() || undefined,
                };

                try {
                    const res = await fetch(API_BASE + "/orgs/settings", {
                        method: "PUT",
                        headers: {
                            "Content-Type": "application/json",
                            "Authorization": "Bearer " + authToken,
                            "X-Organization-Id": currentOrgId
                        },
                        body: JSON.stringify(payload)
                    });

                    if (res.ok) {
                        const updated = await res.json();
                        cachedOrgSettings = updated;
                        showToast("Settings Saved!", "White-Label branding and payment configuration updated.", "fa-check", "success");
                        fetchOrganizationSettings();
                    } else {
                        const err = await res.json();
                        alert("Failed to save settings: " + (err.detail || res.statusText));
                    }
                } catch(err) {
                    alert("Error saving settings: " + err.message);
                }
            }

            async function promptSendTestSms() {
                if (!authToken) return;
                const recipient = prompt("Enter recipient mobile phone number for test SMS (E.164 format):", "+15551234567");
                if (!recipient || !recipient.trim()) return;

                try {
                    showToast("Sending Test SMS...", "Dispatching test message via Twilio gateway...", "fa-paper-plane", "info");
                    const res = await fetch(API_BASE + "/orgs/notifications/test-sms", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "Authorization": "Bearer " + authToken,
                            "X-Organization-Id": currentOrgId
                        },
                        body: JSON.stringify({ recipient: recipient.trim(), channel: "sms" })
                    });
                    const data = await res.json();
                    if (res.ok && data.success) {
                        const modeText = data.mode === "live_twilio" ? "Live Twilio API" : "Local Simulation Mode";
                        showToast("SMS Dispatched!", `Delivered via ${modeText}. SID: ${data.sid}`, "fa-check-circle", "success");
                        fetchNotificationHistory();
                    } else {
                        alert("SMS Dispatch Failed: " + (data.error || JSON.stringify(data)));
                    }
                } catch(e) {
                    alert("Error sending test SMS: " + e.message);
                }
            }

            async function promptSendTestEmail() {
                if (!authToken) return;
                const recipient = prompt("Enter recipient email address for test branded notification:", "test@example.com");
                if (!recipient || !recipient.trim()) return;

                try {
                    showToast("Sending Test Email...", "Generating branded HTML template & sending via SendGrid...", "fa-paper-plane", "info");
                    const res = await fetch(API_BASE + "/orgs/notifications/test-email", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "Authorization": "Bearer " + authToken,
                            "X-Organization-Id": currentOrgId
                        },
                        body: JSON.stringify({ recipient: recipient.trim(), channel: "email" })
                    });
                    const data = await res.json();
                    if (res.ok && data.success) {
                        const modeText = data.mode === "live_sendgrid" ? "Live SendGrid API" : "Local Simulation Mode";
                        showToast("Email Dispatched!", `Delivered via ${modeText}.`, "fa-check-circle", "success");
                        fetchNotificationHistory();
                    } else {
                        alert("Email Dispatch Failed: " + (data.error || JSON.stringify(data)));
                    }
                } catch(e) {
                    alert("Error sending test email: " + e.message);
                }
            }

            async function fetchNotificationHistory() {
                if (!authToken) return;
                const container = document.getElementById("settings-notifications-log");
                if (!container) return;

                try {
                    const res = await fetch(API_BASE + "/orgs/notifications/history?limit=15", {
                        headers: {
                            "Authorization": "Bearer " + authToken,
                            "X-Organization-Id": currentOrgId
                        }
                    });
                    if (!res.ok) return;
                    const items = await res.json();
                    if (!items || items.length === 0) {
                        container.innerHTML = `<div class="text-center py-2 text-slate-500 text-[11px] italic">No notifications logged yet. Trigger replenishment or test dispatch above.</div>`;
                        return;
                    }

                    container.innerHTML = items.map(n => {
                        const isSms = n.channel === 'sms';
                        const icon = isSms ? 'fa-comment-sms text-cyan-400' : 'fa-envelope text-purple-400';
                        const badgeColor = n.status === 'sent' ? 'bg-emerald-950 text-emerald-400 border-emerald-800' : 'bg-rose-950 text-rose-400 border-rose-800';
                        const timeStr = n.sent_at ? new Date(n.sent_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : 'Pending';
                        return `
                            <div class="p-2 bg-slate-900/90 rounded border border-slate-800 flex items-center justify-between text-[11px]">
                                <div class="flex items-center gap-2 overflow-hidden">
                                    <i class="fa-solid ${icon} text-xs shrink-0"></i>
                                    <div class="truncate">
                                        <span class="font-semibold text-slate-200">${n.title || 'Notification'}</span>
                                        <span class="text-slate-400 ml-1">&rarr; ${n.recipient}</span>
                                    </div>
                                </div>
                                <div class="flex items-center gap-2 shrink-0 ml-2">
                                    <span class="text-slate-500 font-mono text-[10px]">${timeStr}</span>
                                    <span class="px-1.5 py-0.5 rounded text-[10px] font-mono border ${badgeColor} uppercase font-bold">${n.status}</span>
                                </div>
                            </div>
                        `;
                    }).join('');
                } catch(e) {
                    console.error("Error fetching notification history:", e);
                }
            }

            // Auto-login default tenant on load
            window.onload = () => {
                setCallTimeNow("in-call-time");
                seedAndLogin();
            };
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
