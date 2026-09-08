import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from app.core.config import settings
from app.core.database import engine, Base
from app.api.v1 import auth, crm, agent, hitl, conversations
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
                <!-- Dual Switcher Tabs -->
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
                    <div class="flex items-center gap-2.5 w-full md:w-auto shrink-0">
                        <button id="btn-action-fast-convert" onclick="executeFastConversion()" class="flex-1 md:flex-none px-5 py-2.5 bg-gradient-to-r from-amber-500 via-emerald-500 to-emerald-600 hover:from-amber-400 hover:to-emerald-500 text-slate-950 font-extrabold rounded-xl text-xs shadow-lg transition flex items-center justify-center gap-2 cursor-pointer transform hover:scale-[1.02] border border-amber-300/40">
                            <i class="fa-solid fa-bolt text-slate-950"></i> 1-Click Transfer to Client CRM
                        </button>
                        <button onclick="openConvertModal()" class="px-3.5 py-2.5 bg-slate-800/90 hover:bg-slate-700 border border-amber-500/40 text-amber-300 rounded-xl text-xs font-semibold transition flex items-center justify-center gap-1.5 cursor-pointer">
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
                            <button id="btn-research" onclick="triggerResearch()" disabled class="py-2 px-3 bg-slate-700 text-slate-400 rounded text-xs font-semibold transition flex items-center justify-center gap-2">
                                <i class="fa-solid fa-magnifying-glass"></i> AI Lead Research
                            </button>
                            <button id="btn-draft" onclick="triggerDraftOutreach()" disabled class="py-2 px-3 bg-slate-700 text-slate-400 rounded text-xs font-semibold transition flex items-center justify-center gap-2">
                                <i class="fa-solid fa-envelope-open-text"></i> Draft Cold Outreach
                            </button>
                            <button id="btn-convert" onclick="executeFastConversion()" class="col-span-2 py-2.5 px-3 bg-gradient-to-r from-amber-600 via-amber-500 to-emerald-600 hover:from-amber-500 hover:to-emerald-500 text-white rounded-lg text-xs font-bold transition flex items-center justify-center gap-2 shadow-md cursor-pointer border border-amber-400/40">
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

            <!-- Right Column: Human-in-the-Loop (HITL) Queue & Audit Logs -->
            <div class="space-y-6">
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
                                        <th class="p-2.5">Status</th>
                                        <th class="p-2.5 text-right">Amount</th>
                                    </tr>
                                </thead>
                                <tbody id="sales-ledger-body" class="divide-y divide-slate-800 font-sans">
                                    <tr>
                                        <td colspan="7" class="p-4 text-center text-slate-500 italic">Select a client account to inspect sales history.</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
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
                    fetchHitlRequests();
                    fetchAuditLogs();
                    fetchClientStats();
                    fetchClients();
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
                document.getElementById("btn-research").className = "py-2 px-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-xs font-semibold transition flex items-center justify-center gap-2 cursor-pointer";
                document.getElementById("btn-draft").disabled = false;
                document.getElementById("btn-draft").className = "py-2 px-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-semibold transition flex items-center justify-center gap-2 cursor-pointer";
                document.getElementById("btn-simulate").disabled = false;
                document.getElementById("btn-save-notes").disabled = false;
                document.getElementById("btn-toggle-log-call").disabled = false;
                const btnConvert = document.getElementById("btn-convert");
                if (btnConvert) {
                    btnConvert.disabled = false;
                    btnConvert.className = "col-span-2 py-2.5 px-3 bg-gradient-to-r from-amber-600 via-amber-500 to-emerald-600 hover:from-amber-500 hover:to-emerald-500 text-white rounded-lg text-xs font-bold transition flex items-center justify-center gap-2 shadow-md cursor-pointer border border-amber-400/40";
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
                const tabProspects = document.getElementById("tab-prospects");
                const tabClients = document.getElementById("tab-clients");

                if (mode === 'prospects') {
                    viewProspects.classList.remove("hidden");
                    viewClients.classList.add("hidden");
                    tabProspects.className = "px-4 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-2 bg-indigo-600 text-white shadow-md";
                    tabClients.className = "px-4 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800/60";
                } else {
                    viewProspects.classList.add("hidden");
                    viewClients.classList.remove("hidden");
                    tabClients.className = "px-4 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-2 bg-emerald-600 text-white shadow-md";
                    tabProspects.className = "px-4 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800/60";
                    fetchClientStats();
                    fetchClients();
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

                        const revFormatted = "$" + (c.total_revenue || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                        const contactName = c.primary_contact ? (c.primary_contact.first_name + " " + c.primary_contact.last_name) : (c.company ? c.company.name : "Contact");

                        div.innerHTML = `
                            <div class="flex justify-between items-start">
                                <div>
                                    <div class="font-bold text-slate-200 text-xs">${escapeHtml(c.account_name)}</div>
                                    <div class="text-[11px] text-slate-400">${escapeHtml(contactName)} • <span class="text-slate-500">${escapeHtml(c.company ? c.company.industry || '' : '')}</span></div>
                                </div>
                                <span class="px-1.5 py-0.5 rounded text-[10px] font-semibold border ${tierBadgeClass} uppercase">${escapeHtml(c.account_tier)}</span>
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

                // Notes
                document.getElementById("detail-client-notes").value = client.notes || "";

                // Buttons
                document.getElementById("btn-toggle-sale").disabled = false;
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
                        tbody.innerHTML = `<tr><td colspan="7" class="p-4 text-center text-slate-500 italic">No sales recorded yet for this client account. Click '+ Log New Sale / Order' to record the first transaction.</td></tr>`;
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

                        tr.innerHTML = `
                            <td class="p-2.5 text-slate-400 font-mono text-[11px] whitespace-nowrap">${saleDate}</td>
                            <td class="p-2.5 font-mono text-indigo-300 font-bold whitespace-nowrap">${escapeHtml(s.order_number)}</td>
                            <td class="p-2.5 text-slate-200">
                                <div class="font-medium">${escapeHtml(s.items_summary)}</div>
                                ${s.notes ? `<div class="text-[10px] text-slate-500 italic">${escapeHtml(s.notes)}</div>` : ''}
                            </td>
                            <td class="p-2.5 text-slate-400 whitespace-nowrap uppercase text-[10px] font-mono">${escapeHtml(s.payment_method ? s.payment_method.replace(/_/g, ' ') : '')}</td>
                            <td class="p-2.5 text-slate-300 whitespace-nowrap text-[11px]">${escapeHtml(s.sales_rep_name || 'Sales Rep')}</td>
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
