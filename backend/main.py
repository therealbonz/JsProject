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
                    <span class="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
                    Gemini AI Ready
                </span>
                <a href="/docs" target="_blank" class="text-xs text-indigo-400 hover:text-indigo-300 transition flex items-center gap-1">
                    <i class="fa-solid fa-code"></i> OpenAPI Docs
                </a>
            </div>
        </nav>

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
                        <i class="fa-solid fa-user-plus text-indigo-400"></i> Quick Add B2B Lead
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
                        <div>
                            <label class="block text-slate-400 mb-1">Contact Email</label>
                            <input id="in-email" type="email" required value="mvance@titanlogistics.com" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-slate-100 focus:outline-none focus:border-indigo-500">
                        </div>
                        <button type="submit" class="w-full py-2 bg-emerald-600 hover:bg-emerald-500 rounded text-xs font-semibold transition">
                            <i class="fa-solid fa-plus"></i> Add Lead to Pipeline
                        </button>
                    </form>
                </div>

                <!-- Pipeline Leads List -->
                <div class="bg-slate-800/80 border border-slate-700/60 rounded-xl p-5 shadow-xl">
                    <div class="flex justify-between items-center mb-3">
                        <h2 class="font-semibold text-sm uppercase tracking-wider text-slate-400 flex items-center gap-2">
                            <i class="fa-solid fa-users text-indigo-400"></i> Active Leads
                        </h2>
                        <button onclick="fetchLeads()" class="text-xs text-slate-400 hover:text-white"><i class="fa-solid fa-rotate"></i></button>
                    </div>
                    <div id="leads-list" class="space-y-2 max-h-72 overflow-y-auto pr-1">
                        <p class="text-xs text-slate-500 italic">Click "Connect Default Tenant" to load leads.</p>
                    </div>
                </div>
            </div>

            <!-- Middle Column: AI Sales Agent Interaction Console -->
            <div class="space-y-6">
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

        <script>
            const BASE_PREFIX = window.location.pathname.startsWith("/JsProject") ? "/JsProject" : "";
            const API_BASE = BASE_PREFIX + "/api/v1";

            let authToken = "";
            let currentOrgId = "";
            let selectedLead = null;
            let currentConvId = null;

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
                } catch(e) {
                    alert("Error authenticating: " + e.message);
                }
            }

            async function fetchLeads() {
                if (!authToken) return;
                const res = await fetch(API_BASE + "/crm/leads", {
                    headers: { "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId }
                });
                const leads = await res.json();
                const container = document.getElementById("leads-list");
                container.innerHTML = "";
                if (!leads.length) {
                    container.innerHTML = "<p class='text-xs text-slate-500 italic'>No leads yet. Create one above!</p>";
                    return;
                }
                leads.forEach(l => {
                    const div = document.createElement("div");
                    div.className = "p-2.5 rounded-lg bg-slate-900/80 border border-slate-700/60 hover:border-indigo-500/60 cursor-pointer transition flex justify-between items-center";
                    div.onclick = () => selectLead(l);
                    div.innerHTML = `
                        <div>
                            <div class="font-semibold text-slate-200 text-xs">${l.company ? l.company.name : 'Lead'}</div>
                            <div class="text-[11px] text-slate-400">${l.contact ? l.contact.first_name + ' ' + l.contact.last_name : ''} • <span class="text-indigo-400 font-mono">${l.pipeline_stage}</span></div>
                        </div>
                        <span class="text-xs font-bold px-2 py-0.5 rounded bg-slate-800 text-indigo-300 border border-slate-700">${l.lead_score} pts</span>
                    `;
                    container.appendChild(div);
                });
            }

            function selectLead(lead) {
                selectedLead = lead;
                document.getElementById("selected-lead-name").innerText = lead.company.name + " (" + lead.pipeline_stage + ")";
                document.getElementById("btn-research").disabled = false;
                document.getElementById("btn-research").className = "py-2 px-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-xs font-semibold transition flex items-center justify-center gap-2";
                document.getElementById("btn-draft").disabled = false;
                document.getElementById("btn-draft").className = "py-2 px-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-semibold transition flex items-center justify-center gap-2";
                document.getElementById("btn-simulate").disabled = false;

                // Load conversation ID if exists
                fetchConversation(lead.id);
            }

            async function fetchConversation(leadId) {
                const res = await fetch(API_BASE + "/crm/leads/" + leadId, {
                    headers: { "Authorization": "Bearer " + authToken, "X-Organization-Id": currentOrgId }
                });
                const leadData = await res.json();
                currentConvId = leadId;
                document.getElementById("ai-output").innerText = leadData.research_summary || "Lead ready. Click 'AI Lead Research' or 'Draft Cold Outreach'.";
            }

            async function handleCreateLead(e) {
                e.preventDefault();
                if (!authToken) { alert("Please connect default tenant first!"); return; }
                const payload = {
                    company_name: document.getElementById("in-company").value,
                    industry: document.getElementById("in-industry").value,
                    company_domain: document.getElementById("in-domain").value,
                    contact_first_name: document.getElementById("in-fname").value,
                    contact_last_name: document.getElementById("in-lname").value,
                    contact_email: document.getElementById("in-email").value,
                };
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

            // Auto-login default tenant on load
            window.onload = () => seedAndLogin();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
