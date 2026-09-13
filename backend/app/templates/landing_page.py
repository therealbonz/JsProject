"""
SaaS Marketing Landing Page Template
Renders a modern, responsive, high-converting product showcase
emphasizing the 5 Specialized Types of AI Agents and Visual Pipeline Orchestration.
"""

def render_landing_page(api_prefix: str = "") -> str:
    # Ensure api_prefix doesn't have trailing slash for clean concatenation
    prefix = api_prefix.rstrip("/")
    console_url = f"{prefix}/console" if prefix else "/console"
    lead_api_url = f"{prefix}/api/v1/crm/leads" if prefix else "/api/v1/crm/leads"

    return f"""<!DOCTYPE html>
<html lang="en" class="scroll-smooth">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NexFlow AI • Autonomous Multi-Agent CRM &amp; Supply Chain Engine</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {{
            theme: {{
                extend: {{
                    fontFamily: {{
                        sans: ['Inter', 'sans-serif'],
                        mono: ['JetBrains Mono', 'monospace'],
                    }},
                    colors: {{
                        brand: {{
                            50: '#eef2ff',
                            100: '#e0e7ff',
                            400: '#818cf8',
                            500: '#6366f1',
                            600: '#4f46e5',
                            700: '#4338ca',
                            900: '#312e81',
                            950: '#1e1b4b',
                        }}
                    }}
                }}
            }}
        }}
    </script>
    <style>
        .glass-panel {{
            background: rgba(15, 23, 42, 0.75);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.08);
        }}
        .glow-indigo {{
            box-shadow: 0 0 50px -10px rgba(99, 102, 241, 0.35);
        }}
        .glow-emerald {{
            box-shadow: 0 0 50px -10px rgba(16, 185, 129, 0.35);
        }}
        .gradient-text {{
            background: linear-gradient(135deg, #a5b4fc 0%, #ffffff 50%, #c084fc 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .grid-bg {{
            background-size: 40px 40px;
            background-image: 
                linear-gradient(to right, rgba(255, 255, 255, 0.03) 1px, transparent 1px),
                linear-gradient(to bottom, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
        }}
    </style>
</head>
<body class="bg-slate-950 text-slate-100 font-sans selection:bg-indigo-500 selection:text-white relative overflow-x-hidden min-h-screen">

    <!-- Ambient Top Lighting -->
    <div class="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[450px] bg-gradient-to-b from-indigo-600/20 via-purple-600/10 to-transparent blur-3xl pointer-events-none -z-10"></div>
    <div class="absolute top-[600px] right-0 w-[500px] h-[500px] bg-emerald-600/10 blur-3xl pointer-events-none -z-10"></div>

    <!-- Navigation Bar -->
    <header class="sticky top-0 z-50 glass-panel border-b border-slate-800/80">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-20 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <div class="h-11 w-11 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-500 flex items-center justify-center text-white text-xl shadow-lg shadow-indigo-500/30">
                    <i class="fa-solid fa-brain"></i>
                </div>
                <div>
                    <div class="flex items-center gap-2">
                        <span class="font-extrabold text-xl tracking-tight text-white">NexFlow<span class="text-indigo-400">.ai</span></span>
                        <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-indigo-950 text-indigo-300 border border-indigo-700/50">5 AI AGENTS</span>
                    </div>
                    <span class="text-[11px] text-slate-400">Autonomous CRM &amp; Supply Chain Pipeline Workforce</span>
                </div>
            </div>

            <!-- Desktop Nav Links -->
            <nav class="hidden md:flex items-center gap-8 text-sm font-medium text-slate-300">
                <a href="#agents" class="hover:text-indigo-400 transition flex items-center gap-1.5">
                    <i class="fa-solid fa-users-gear text-indigo-400 text-xs"></i> 5 AI Agents
                </a>
                <a href="#workflows" class="hover:text-indigo-400 transition flex items-center gap-1.5">
                    <i class="fa-solid fa-diagram-project text-purple-400 text-xs"></i> DAG Canvas
                </a>
                <a href="#portals" class="hover:text-indigo-400 transition flex items-center gap-1.5">
                    <i class="fa-solid fa-headset text-pink-400 text-xs"></i> 24/7 Copilot
                </a>
                <a href="#pricing" class="hover:text-indigo-400 transition flex items-center gap-1.5">
                    <i class="fa-solid fa-tag text-emerald-400 text-xs"></i> Pricing &amp; Metering
                </a>
                <a href="#dossier-demo" class="hover:text-indigo-400 transition flex items-center gap-1.5">
                    <i class="fa-solid fa-wand-magic-sparkles text-amber-400 text-xs"></i> Live Demo
                </a>
            </nav>

            <!-- Actions -->
            <div class="flex items-center gap-3">
                <a href="{console_url}" class="hidden sm:inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold text-slate-300 hover:text-white bg-slate-900/80 hover:bg-slate-800 border border-slate-700/80 transition">
                    <i class="fa-solid fa-shield-halved text-slate-400"></i> Management Console
                </a>
                <a href="#dossier-demo" class="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 shadow-lg shadow-indigo-600/30 transition transform hover:-translate-y-0.5">
                    <span>Deploy Workforce</span>
                    <i class="fa-solid fa-arrow-right"></i>
                </a>
            </div>
        </div>
    </header>

    <!-- HERO SECTION -->
    <section class="relative pt-16 pb-24 md:pt-24 md:pb-32 grid-bg">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center space-y-8">
            <!-- Feature Tag -->
            <div class="inline-flex items-center gap-2 px-4 py-2 rounded-full glass-panel border border-indigo-500/30 text-xs font-semibold text-indigo-300 shadow-xl">
                <span class="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>Next-Gen Multi-Agent Autonomous CRM Platform • 5 Specialized Agents</span>
                <i class="fa-solid fa-chevron-right text-[10px] text-indigo-400"></i>
            </div>

            <!-- Main Heading -->
            <h1 class="text-4xl sm:text-6xl lg:text-7xl font-black tracking-tight max-w-5xl mx-auto leading-[1.1]">
                Deploy an Autonomous <br>
                <span class="gradient-text">5-Agent AI Workforce</span> <br>
                for Enterprise Sales &amp; Supply Chains
            </h1>

            <!-- Subtitle -->
            <p class="text-base sm:text-xl text-slate-300 max-w-3xl mx-auto leading-relaxed font-normal">
                Stop juggling fragmented tools. NexFlow deploys <strong class="text-white font-semibold">5 specialized AI agents</strong> that collaborate across visual DAG pipelines to qualify inbound prospects, forecast inventory replenishment, resolve post-sale customer tickets 24/7, and protect enterprise deals.
            </p>

            <!-- CTA Cluster -->
            <div class="flex flex-wrap items-center justify-center gap-4 pt-4">
                <a href="#dossier-demo" class="px-8 py-4 rounded-2xl text-sm font-bold text-white bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 hover:from-indigo-500 hover:to-pink-500 shadow-2xl shadow-indigo-600/40 transition transform hover:-translate-y-0.5 flex items-center gap-3">
                    <i class="fa-solid fa-bolt text-amber-300 text-base"></i>
                    <span>Test Instant AI Dossier Demo</span>
                </a>
                <a href="{console_url}" class="px-7 py-4 rounded-2xl text-sm font-bold text-slate-200 bg-slate-900/90 hover:bg-slate-800/90 border border-slate-700/80 shadow-xl transition flex items-center gap-2.5">
                    <i class="fa-solid fa-desktop text-indigo-400"></i>
                    <span>Launch Live Console</span>
                </a>
                <a href="#agents" class="px-6 py-4 rounded-2xl text-sm font-semibold text-slate-400 hover:text-white transition flex items-center gap-2">
                    <i class="fa-solid fa-play text-xs text-indigo-400"></i>
                    <span>See How 5 Agents Work</span>
                </a>
            </div>

            <!-- Live Telemetry Ticker Bar -->
            <div class="pt-12 max-w-4xl mx-auto">
                <div class="glass-panel rounded-2xl p-6 border border-slate-800 grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
                    <div class="space-y-1">
                        <div class="text-2xl sm:text-3xl font-black font-mono text-emerald-400" id="stat-dossiers">14,892+</div>
                        <div class="text-xs text-slate-400 uppercase tracking-wider font-semibold">AI Dossiers Generated</div>
                    </div>
                    <div class="space-y-1">
                        <div class="text-2xl sm:text-3xl font-black font-mono text-indigo-400" id="stat-stockouts">3,410</div>
                        <div class="text-xs text-slate-400 uppercase tracking-wider font-semibold">Stockouts Averted</div>
                    </div>
                    <div class="space-y-1">
                        <div class="text-2xl sm:text-3xl font-black font-mono text-purple-400">99.4%</div>
                        <div class="text-xs text-slate-400 uppercase tracking-wider font-semibold">Autonomous Resolution</div>
                    </div>
                    <div class="space-y-1">
                        <div class="text-2xl sm:text-3xl font-black font-mono text-pink-400">28ms</div>
                        <div class="text-xs text-slate-400 uppercase tracking-wider font-semibold">Avg DAG Step Latency</div>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- 5 SPECIALIZED AI AGENTS SHOWCASE -->
    <section id="agents" class="py-24 relative border-t border-slate-900 bg-slate-950/60">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-16">
            <div class="text-center space-y-4 max-w-3xl mx-auto">
                <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-purple-950/60 text-purple-300 border border-purple-800/50 text-xs font-semibold">
                    <i class="fa-solid fa-network-wired"></i>
                    <span>Autonomous Collaborative Workforce</span>
                </div>
                <h2 class="text-3xl sm:text-5xl font-black tracking-tight text-white">
                    The 5 Specialized AI Agents <br>
                    <span class="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400">Powering Your Pipeline</span>
                </h2>
                <p class="text-slate-400 text-sm sm:text-base">
                    Each agent specializes in a critical stage of the commercial lifecycle. Together, they form an uninterrupted autonomous pipeline from initial inbound touch to recurring replenishment.
                </p>
            </div>

            <!-- Agent Selector Tabs -->
            <div class="flex flex-wrap items-center justify-center gap-2 bg-slate-900/80 p-2 rounded-2xl border border-slate-800 max-w-5xl mx-auto">
                <button onclick="switchAgentTab('sales')" id="tab-btn-sales" class="px-4 py-2.5 rounded-xl text-xs font-bold transition flex items-center gap-2 bg-indigo-600 text-white shadow-lg">
                    <i class="fa-solid fa-magnifying-glass-chart"></i>
                    <span>1. Sales Intelligence Agent</span>
                </button>
                <button onclick="switchAgentTab('demand')" id="tab-btn-demand" class="px-4 py-2.5 rounded-xl text-xs font-bold transition flex items-center gap-2 text-slate-400 hover:text-white hover:bg-slate-800">
                    <i class="fa-solid fa-boxes-packing"></i>
                    <span>2. Demand &amp; Replenishment Agent</span>
                </button>
                <button onclick="switchAgentTab('support')" id="tab-btn-support" class="px-4 py-2.5 rounded-xl text-xs font-bold transition flex items-center gap-2 text-slate-400 hover:text-white hover:bg-slate-800">
                    <i class="fa-solid fa-headset"></i>
                    <span>3. Support Copilot Agent</span>
                </button>
                <button onclick="switchAgentTab('orchestrator')" id="tab-btn-orchestrator" class="px-4 py-2.5 rounded-xl text-xs font-bold transition flex items-center gap-2 text-slate-400 hover:text-white hover:bg-slate-800">
                    <i class="fa-solid fa-diagram-project"></i>
                    <span>4. Visual DAG Orchestrator</span>
                </button>
                <button onclick="switchAgentTab('hitl')" id="tab-btn-hitl" class="px-4 py-2.5 rounded-xl text-xs font-bold transition flex items-center gap-2 text-slate-400 hover:text-white hover:bg-slate-800">
                    <i class="fa-solid fa-user-shield"></i>
                    <span>5. HITL Remediation Agent</span>
                </button>
            </div>

            <!-- Agent Dynamic Detail Card Container -->
            <div id="agent-detail-container" class="glass-panel rounded-3xl p-6 sm:p-10 border border-slate-800 max-w-5xl mx-auto glow-indigo">
                <!-- Dynamically populated via JS -->
            </div>

            <!-- 5 Agent Cards Grid Summary -->
            <div class="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4 pt-8">
                <div class="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-3 hover:border-indigo-500/50 transition">
                    <div class="h-10 w-10 rounded-xl bg-indigo-600/20 text-indigo-400 flex items-center justify-center text-lg">
                        <i class="fa-solid fa-magnifying-glass-chart"></i>
                    </div>
                    <div class="font-bold text-sm text-white">1. Sales Intelligence</div>
                    <p class="text-xs text-slate-400">Analyzes prospect buyer intent, scores readiness, and creates tailored closing dossiers.</p>
                    <div class="text-[11px] font-mono text-emerald-400 font-semibold">+34% Close Velocity</div>
                </div>
                <div class="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-3 hover:border-emerald-500/50 transition">
                    <div class="h-10 w-10 rounded-xl bg-emerald-600/20 text-emerald-400 flex items-center justify-center text-lg">
                        <i class="fa-solid fa-boxes-packing"></i>
                    </div>
                    <div class="font-bold text-sm text-white">2. Demand &amp; Restock</div>
                    <p class="text-xs text-slate-400">Models consumption velocity, predicts depletion dates, and auto-dispatches supplier RFQs.</p>
                    <div class="text-[11px] font-mono text-emerald-400 font-semibold">Zero Stockout Incidents</div>
                </div>
                <div class="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-3 hover:border-pink-500/50 transition">
                    <div class="h-10 w-10 rounded-xl bg-pink-600/20 text-pink-400 flex items-center justify-center text-lg">
                        <i class="fa-solid fa-headset"></i>
                    </div>
                    <div class="font-bold text-sm text-white">3. Support Copilot</div>
                    <p class="text-xs text-slate-400">24/7 portal assistant with 7 tools for tracking, cadence shifts, and card-on-file lookup.</p>
                    <div class="text-[11px] font-mono text-emerald-400 font-semibold">82% Autonomous Resolution</div>
                </div>
                <div class="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-3 hover:border-purple-500/50 transition">
                    <div class="h-10 w-10 rounded-xl bg-purple-600/20 text-purple-400 flex items-center justify-center text-lg">
                        <i class="fa-solid fa-diagram-project"></i>
                    </div>
                    <div class="font-bold text-sm text-white">4. Visual DAG Engine</div>
                    <p class="text-xs text-slate-400">Executes condition branches, webhooks, and multi-agent coordination with full telemetry.</p>
                    <div class="text-[11px] font-mono text-emerald-400 font-semibold">&lt; 30ms Step Latency</div>
                </div>
                <div class="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-3 hover:border-amber-500/50 transition">
                    <div class="h-10 w-10 rounded-xl bg-amber-600/20 text-amber-400 flex items-center justify-center text-lg">
                        <i class="fa-solid fa-user-shield"></i>
                    </div>
                    <div class="font-bold text-sm text-white">5. HITL Remediation</div>
                    <p class="text-xs text-slate-400">Intercepts customer hostility, prepares concessions, and stages 1-click human rep takeover.</p>
                    <div class="text-[11px] font-mono text-emerald-400 font-semibold">100% Churn Containment</div>
                </div>
            </div>
        </div>
    </section>

    <!-- VISUAL WORKFLOW DAG CANVAS SHOWCASE -->
    <section id="workflows" class="py-24 relative border-t border-slate-900">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-16">
            <div class="text-center space-y-4 max-w-3xl mx-auto">
                <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-950/60 text-indigo-300 border border-indigo-800/50 text-xs font-semibold">
                    <i class="fa-solid fa-wand-magic-sparkles"></i>
                    <span>Step 15 Visual Automation Studio</span>
                </div>
                <h2 class="text-3xl sm:text-5xl font-black tracking-tight text-white">
                    Design Multi-Agent Pipelines on a <br>
                    <span class="gradient-text">Drag-and-Drop Visual DAG Canvas</span>
                </h2>
                <p class="text-slate-400 text-sm sm:text-base">
                    Compose complex multi-agent workflows without code. Connect triggers, logical conditions, domain actions, and AI reasoning nodes with full real-time telemetry and dry-run simulations.
                </p>
            </div>

            <!-- Visual Workflow Canvas Interactive Teaser Mockup -->
            <div class="glass-panel rounded-3xl border border-slate-800 p-6 shadow-2xl relative overflow-hidden">
                <!-- Canvas Header Bar -->
                <div class="flex items-center justify-between border-b border-slate-800 pb-4 mb-6">
                    <div class="flex items-center gap-3">
                        <div class="h-3 w-3 rounded-full bg-rose-500"></div>
                        <div class="h-3 w-3 rounded-full bg-amber-500"></div>
                        <div class="h-3 w-3 rounded-full bg-emerald-500"></div>
                        <span class="text-xs font-mono font-bold text-slate-300 ml-2">Recipe: VIP High-Value Lead Fast-Track &amp; AI Dossier (Active DAG)</span>
                    </div>
                    <div class="flex items-center gap-2">
                        <span class="px-2.5 py-1 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-800 text-[10px] font-mono font-bold flex items-center gap-1.5">
                            <span class="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"></span> DAG Online • 0 Failures
                        </span>
                        <a href="{console_url}" class="px-3 py-1 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-xs font-bold text-white transition">
                            Open in Studio
                        </a>
                    </div>
                </div>

                <!-- Canvas Grid Layout (Simulated SVG Pipeline) -->
                <div class="relative bg-slate-950/80 rounded-2xl p-8 min-h-[380px] grid-bg border border-slate-800/60 overflow-x-auto">
                    <!-- SVG Edge Connectors -->
                    <svg class="absolute inset-0 w-full h-full pointer-events-none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M 230 140 L 320 140" stroke="#6366f1" stroke-width="2" stroke-dasharray="4 4" fill="none" class="animate-pulse" />
                        <path d="M 520 140 L 610 140" stroke="#6366f1" stroke-width="2" fill="none" />
                        <path d="M 810 140 L 900 100" stroke="#10b981" stroke-width="2" fill="none" />
                        <path d="M 810 140 L 900 190" stroke="#8b5cf6" stroke-width="2" fill="none" />
                    </svg>

                    <!-- Interactive Mock Nodes -->
                    <div class="flex items-center gap-12 min-w-[950px] relative z-10 py-6">
                        <!-- Node 1: Trigger -->
                        <div class="w-48 bg-slate-900 border-2 border-emerald-500/80 rounded-2xl p-4 shadow-xl space-y-2 transform hover:scale-105 transition">
                            <div class="flex items-center justify-between">
                                <span class="px-2 py-0.5 rounded text-[9px] font-bold font-mono bg-emerald-950 text-emerald-300 uppercase">Trigger</span>
                                <i class="fa-solid fa-bolt text-emerald-400 text-xs"></i>
                            </div>
                            <div class="font-bold text-xs text-white">Inbound Lead Created</div>
                            <div class="text-[10px] font-mono text-slate-400">event: lead_created</div>
                        </div>

                        <!-- Node 2: Condition -->
                        <div class="w-48 bg-slate-900 border-2 border-amber-500/80 rounded-2xl p-4 shadow-xl space-y-2 transform hover:scale-105 transition">
                            <div class="flex items-center justify-between">
                                <span class="px-2 py-0.5 rounded text-[9px] font-bold font-mono bg-amber-950 text-amber-300 uppercase">Condition</span>
                                <i class="fa-solid fa-code-branch text-amber-400 text-xs"></i>
                            </div>
                            <div class="font-bold text-xs text-white">Deal Value &gt;= $10,000</div>
                            <div class="text-[10px] font-mono text-slate-400">estimated_value &gt;= 10k</div>
                        </div>

                        <!-- Node 3: AI Agent -->
                        <div class="w-48 bg-slate-900 border-2 border-indigo-500 rounded-2xl p-4 shadow-xl space-y-2 glow-indigo transform hover:scale-105 transition">
                            <div class="flex items-center justify-between">
                                <span class="px-2 py-0.5 rounded text-[9px] font-bold font-mono bg-indigo-950 text-indigo-300 uppercase">AI Agent 1</span>
                                <i class="fa-solid fa-robot text-indigo-400 text-xs"></i>
                            </div>
                            <div class="font-bold text-xs text-white">Sales Dossier Agent</div>
                            <div class="text-[10px] font-mono text-slate-400">Synthesizes Strategy</div>
                        </div>

                        <!-- Split Branches (Actions) -->
                        <div class="flex flex-col gap-4">
                            <div class="w-48 bg-slate-900 border-2 border-emerald-500/80 rounded-2xl p-3.5 shadow-xl space-y-1 transform hover:scale-105 transition">
                                <div class="flex items-center justify-between">
                                    <span class="px-2 py-0.5 rounded text-[9px] font-bold font-mono bg-emerald-950 text-emerald-300 uppercase">Action</span>
                                    <i class="fa-solid fa-user-check text-emerald-400 text-xs"></i>
                                </div>
                                <div class="font-bold text-xs text-white">Assign Senior Closer</div>
                                <div class="text-[10px] text-slate-400">Locks rep &amp; routing</div>
                            </div>

                            <div class="w-48 bg-slate-900 border-2 border-purple-500/80 rounded-2xl p-3.5 shadow-xl space-y-1 transform hover:scale-105 transition">
                                <div class="flex items-center justify-between">
                                    <span class="px-2 py-0.5 rounded text-[9px] font-bold font-mono bg-purple-950 text-purple-300 uppercase">Notification</span>
                                    <i class="fa-solid fa-bell text-purple-400 text-xs"></i>
                                </div>
                                <div class="font-bold text-xs text-white">Dispatch VIP Alerts</div>
                                <div class="text-[10px] text-slate-400">Omnichannel Email/Slack</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Simulation Footer -->
                <div class="mt-4 flex flex-wrap items-center justify-between gap-4 text-xs text-slate-400 pt-3 border-t border-slate-800/80">
                    <div class="flex items-center gap-2">
                        <i class="fa-solid fa-circle-check text-emerald-400"></i>
                        <span>Includes 4 pre-built enterprise templates with zero setup needed.</span>
                    </div>
                    <div class="font-mono text-indigo-400">
                        Total Execution Latency: <strong>32.4ms</strong>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- CUSTOMER SELF-SERVICE PORTAL & 24/7 COPILOT -->
    <section id="portals" class="py-24 relative border-t border-slate-900 bg-slate-950/80">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
                <div class="space-y-6">
                    <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-pink-950/60 text-pink-300 border border-pink-800/50 text-xs font-semibold">
                        <i class="fa-solid fa-comments"></i>
                        <span>Customer Experience &amp; Retention</span>
                    </div>
                    <h2 class="text-3xl sm:text-5xl font-black tracking-tight text-white leading-tight">
                        Branded Portals with <br>
                        <span class="text-transparent bg-clip-text bg-gradient-to-r from-pink-400 to-indigo-400">24/7 AI Support Copilot</span>
                    </h2>
                    <p class="text-slate-300 text-sm sm:text-base leading-relaxed">
                        Empower your B2B buyers with self-service transparency. Customers access secure portals via cryptographically signed tokens (`/portal/{{token}}`) with zero login friction.
                    </p>
                    <ul class="space-y-3 text-sm text-slate-300">
                        <li class="flex items-start gap-3">
                            <div class="h-6 w-6 rounded-lg bg-pink-600/20 text-pink-400 flex items-center justify-center shrink-0 mt-0.5 text-xs">
                                <i class="fa-solid fa-cube"></i>
                            </div>
                            <span><strong>7 Autonomous Live Tools:</strong> Lookup shipments, inspect recent orders, review card on file, check SaaS licenses, and reschedule replenishment.</span>
                        </li>
                        <li class="flex items-start gap-3">
                            <div class="h-6 w-6 rounded-lg bg-indigo-600/20 text-indigo-400 flex items-center justify-center shrink-0 mt-0.5 text-xs">
                                <i class="fa-solid fa-clock-rotate-left"></i>
                            </div>
                            <span><strong>Dynamic Restock Cadence:</strong> Customers can snooze restock schedules by 14 days or accelerate emergency deliveries in 1 click.</span>
                        </li>
                        <li class="flex items-start gap-3">
                            <div class="h-6 w-6 rounded-lg bg-emerald-600/20 text-emerald-400 flex items-center justify-center shrink-0 mt-0.5 text-xs">
                                <i class="fa-solid fa-user-tie"></i>
                            </div>
                            <span><strong>Instant Human Rep Takeover:</strong> Frustrated tone detection immediately flags the CRM 11 queue for dedicated sales rep intervention.</span>
                        </li>
                    </ul>
                </div>

                <!-- Portal Copilot Live Simulation Mockup -->
                <div class="glass-panel rounded-3xl border border-slate-800 p-6 shadow-2xl space-y-4">
                    <div class="flex items-center justify-between pb-3 border-b border-slate-800">
                        <div class="flex items-center gap-3">
                            <div class="h-9 w-9 rounded-xl bg-pink-600/20 text-pink-400 flex items-center justify-center text-sm font-bold">
                                <i class="fa-solid fa-headset"></i>
                            </div>
                            <div>
                                <div class="font-bold text-sm text-white">Pacific Lumber Co. Account Portal</div>
                                <div class="text-[10px] text-emerald-400 font-mono flex items-center gap-1">
                                    <span class="h-1.5 w-1.5 rounded-full bg-emerald-400"></span> Agent 3 (Copilot) Online
                                </div>
                            </div>
                        </div>
                        <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-800 text-slate-300">SECURE ACCESS</span>
                    </div>

                    <!-- Simulated Chat Stream -->
                    <div class="bg-slate-950/70 rounded-2xl p-4 space-y-3.5 text-xs border border-slate-900">
                        <div class="flex items-start gap-2.5">
                            <div class="h-6 w-6 rounded-full bg-slate-800 text-slate-300 flex items-center justify-center text-[10px] shrink-0 mt-0.5">
                                <i class="fa-solid fa-user"></i>
                            </div>
                            <div class="bg-slate-900 border border-slate-800 rounded-xl p-3 text-slate-200">
                                Can you check on my order ORD-7788 and snooze my next restock by 14 days?
                            </div>
                        </div>

                        <div class="flex items-start gap-2.5">
                            <div class="h-6 w-6 rounded-full bg-pink-600/20 text-pink-400 flex items-center justify-center text-[10px] shrink-0 mt-0.5">
                                <i class="fa-solid fa-robot"></i>
                            </div>
                            <div class="bg-indigo-950/40 border border-indigo-700/50 rounded-xl p-3 text-indigo-100 space-y-2">
                                <p>Certainly! I verified <strong>ORD-7788</strong> is currently <strong>SHIPPED</strong> via Freight Express (Tracking: <code class="font-mono text-emerald-400">FX-992144</code>). Estimated delivery is tomorrow by 3:00 PM.</p>
                                <p>I have also snoozed your scheduled replenishment: your next delivery has been shifted from Oct 1 to <strong>Oct 15</strong>.</p>
                                <div class="p-2 rounded-lg bg-slate-900/80 border border-slate-800 text-[11px] flex items-center justify-between text-slate-300 font-mono">
                                    <span>Executed: snooze_restock_schedule (+14d)</span>
                                    <span class="text-emerald-400 font-bold">SUCCESS</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="pt-2 flex items-center justify-between text-xs text-slate-400">
                        <span>Card on file: <strong>Visa ending in 4242</strong></span>
                        <span class="text-pink-400 font-semibold">Self-Service Enabled</span>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- LIVE INTERACTIVE LEAD DOSSIER DEMO / LEAD FUNNEL -->
    <section id="dossier-demo" class="py-24 relative border-t border-slate-900 grid-bg">
        <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 space-y-12">
            <div class="text-center space-y-4 max-w-3xl mx-auto">
                <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-950/60 text-amber-300 border border-amber-800/50 text-xs font-semibold">
                    <i class="fa-solid fa-bolt text-amber-400"></i>
                    <span>Live Interactive Agent Demo</span>
                </div>
                <h2 class="text-3xl sm:text-5xl font-black tracking-tight text-white">
                    Test Agent 1 in Real-Time: <br>
                    <span class="gradient-text">Instant AI Lead Dossier Generator</span>
                </h2>
                <p class="text-slate-400 text-sm sm:text-base">
                    Enter your organization details below. Watch Agent 1 synthesize a strategic deal closing dossier and trigger the Step 15 automated enrichment pipeline live!
                </p>
            </div>

            <!-- Interactive Dossier Generator Form Card -->
            <div class="glass-panel rounded-3xl p-6 sm:p-10 border border-slate-800 shadow-2xl space-y-8">
                <form id="dossier-form" onsubmit="generateLiveDossier(event)" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    <div class="space-y-1.5">
                        <label class="text-xs font-bold uppercase text-slate-300 tracking-wider">Company Name</label>
                        <input id="demo-company" type="text" required value="Apex Aerospace Solutions" placeholder="e.g. Acme Logistics" class="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-xs text-white focus:border-indigo-500 outline-none">
                    </div>
                    <div class="space-y-1.5">
                        <label class="text-xs font-bold uppercase text-slate-300 tracking-wider">Industry</label>
                        <select id="demo-industry" class="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-xs text-white focus:border-indigo-500 outline-none">
                            <option value="Defense &amp; Aerospace">Defense &amp; Aerospace</option>
                            <option value="Industrial Supply &amp; Manufacturing">Industrial Supply &amp; Manufacturing</option>
                            <option value="Wholesale Logistics &amp; 3PL">Wholesale Logistics &amp; 3PL</option>
                            <option value="Enterprise SaaS &amp; Cloud">Enterprise SaaS &amp; Cloud</option>
                        </select>
                    </div>
                    <div class="space-y-1.5">
                        <label class="text-xs font-bold uppercase text-slate-300 tracking-wider">Target Deal Size</label>
                        <select id="demo-value" class="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-xs text-white focus:border-indigo-500 outline-none">
                            <option value="75000">$75,000 / yr</option>
                            <option value="150000" selected>$150,000 / yr</option>
                            <option value="500000">$500,000 / yr</option>
                            <option value="1200000">$1,200,000 / yr</option>
                        </select>
                    </div>
                    <div class="space-y-1.5 flex flex-col justify-end">
                        <button type="submit" id="btn-demo-submit" class="w-full py-2.5 px-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-bold rounded-xl text-xs shadow-lg shadow-indigo-600/30 transition flex items-center justify-center gap-2">
                            <i class="fa-solid fa-wand-magic-sparkles"></i>
                            <span>Generate AI Dossier</span>
                        </button>
                    </div>
                </form>

                <!-- Loading State -->
                <div id="dossier-loading" class="hidden text-center py-8 space-y-3">
                    <div class="h-10 w-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
                    <div class="text-xs font-mono text-indigo-300">Agent 1 Synthesizing Firmographics &amp; Strategic Closing Angles...</div>
                </div>

                <!-- Resulting Output Dossier Card -->
                <div id="dossier-output" class="bg-slate-950/80 rounded-2xl p-6 border border-slate-800 space-y-4 font-sans text-xs">
                    <div class="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
                        <div class="flex items-center gap-2.5">
                            <span class="h-2.5 w-2.5 rounded-full bg-emerald-400"></span>
                            <span class="font-bold text-white text-sm" id="out-company">Apex Aerospace Solutions</span>
                            <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-indigo-950 text-indigo-300 border border-indigo-800" id="out-tier">ENTERPRISE VIP TIER</span>
                        </div>
                        <div class="flex items-center gap-3 font-mono text-[11px]">
                            <span class="text-slate-400">Readiness Score: <strong class="text-emerald-400 font-bold" id="out-score">96/100</strong></span>
                            <span class="text-slate-400">Target Value: <strong class="text-white font-bold" id="out-deal">$150,000</strong></span>
                        </div>
                    </div>

                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div class="space-y-2">
                            <div class="font-bold text-slate-300 uppercase tracking-wider text-[10px] flex items-center gap-1.5">
                                <i class="fa-solid fa-bullseye text-indigo-400"></i> Executive Buyer Profile
                            </div>
                            <p class="text-slate-300 text-xs leading-relaxed" id="out-buyer-profile">
                                High-intent industrial avionics manufacturer facing severe component replenishment lead times. Primary vulnerability is tier-1 supplier stockout risk impacting Q4 avionics delivery deadlines.
                            </p>
                        </div>
                        <div class="space-y-2">
                            <div class="font-bold text-slate-300 uppercase tracking-wider text-[10px] flex items-center gap-1.5">
                                <i class="fa-solid fa-chess-knight text-purple-400"></i> Recommended Closing Strategy
                            </div>
                            <p class="text-slate-300 text-xs leading-relaxed" id="out-closing-strategy">
                                Pitch autonomous demand replenishment and multi-tier SaaS provisioning with SLA-backed restock buffers. Offer 90-day custom EDI integration to displace legacy ERP manual purchase ordering.
                            </p>
                        </div>
                    </div>

                    <div class="p-3 bg-slate-900 rounded-xl border border-slate-800 flex items-center justify-between text-slate-400 text-[11px] font-mono">
                        <span>Automated Next Action: <strong class="text-emerald-400">Assign Senior Closer &amp; Dispatch VIP Welcome Hook</strong></span>
                        <span>Confidence: <strong>98.2%</strong></span>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- PRICING & METERED BILLING SECTION -->
    <section id="pricing" class="py-24 relative border-t border-slate-900 bg-slate-950/60">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-16">
            <div class="text-center space-y-4 max-w-3xl mx-auto">
                <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-950/60 text-emerald-300 border border-emerald-800/50 text-xs font-semibold">
                    <i class="fa-solid fa-credit-card"></i>
                    <span>Predictable Tiering + Flexible Usage</span>
                </div>
                <h2 class="text-3xl sm:text-5xl font-black tracking-tight text-white">
                    Transparent SaaS Pricing &amp; <br>
                    <span class="gradient-text">Automated Metered Billing</span>
                </h2>
                <p class="text-slate-400 text-sm sm:text-base">
                    Scale from single-rep teams to global supply chains. Generous baseline quotas with seamless automated overage billing powered by Stripe.
                </p>
            </div>

            <!-- Pricing Tier Cards -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <!-- Starter Tier -->
                <div class="glass-panel rounded-3xl p-6 border border-slate-800 flex flex-col justify-between space-y-6 hover:border-slate-700 transition">
                    <div class="space-y-4">
                        <div class="space-y-1">
                            <span class="text-xs font-mono font-bold text-slate-400 uppercase">Starter</span>
                            <div class="flex items-baseline gap-1">
                                <span class="text-4xl font-black text-white">$199</span>
                                <span class="text-xs text-slate-400">/ month</span>
                            </div>
                        </div>
                        <p class="text-xs text-slate-400">Perfect for agile sales teams launching autonomous lead enrichment.</p>
                        <div class="border-t border-slate-800 pt-4 space-y-2.5 text-xs text-slate-300">
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> 1,000 AI Agent Turns/mo</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> 5,000 API Requests/mo</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> 3 Active DAG Workflows</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> 2 Seats Included</div>
                            <div class="flex items-center gap-2 text-slate-500"><i class="fa-solid fa-xmark text-slate-600 text-[10px]"></i> Custom Domain &amp; White-Label</div>
                        </div>
                    </div>
                    <a href="{console_url}" class="w-full py-2.5 px-4 rounded-xl text-xs font-bold text-slate-200 bg-slate-900 hover:bg-slate-800 border border-slate-700 transition text-center block">
                        Get Started
                    </a>
                </div>

                <!-- Growth Tier -->
                <div class="glass-panel rounded-3xl p-6 border border-slate-800 flex flex-col justify-between space-y-6 hover:border-indigo-500/60 transition">
                    <div class="space-y-4">
                        <div class="space-y-1">
                            <span class="text-xs font-mono font-bold text-indigo-400 uppercase">Growth</span>
                            <div class="flex items-baseline gap-1">
                                <span class="text-4xl font-black text-white">$499</span>
                                <span class="text-xs text-slate-400">/ month</span>
                            </div>
                        </div>
                        <p class="text-xs text-slate-400">Scaling distributors needing demand forecasting and restock automation.</p>
                        <div class="border-t border-slate-800 pt-4 space-y-2.5 text-xs text-slate-300">
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> 5,000 AI Agent Turns/mo</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> 25,000 API Requests/mo</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> 15 Active DAG Workflows</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> 5 Seats Included</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> 24/7 AI Support Copilot</div>
                        </div>
                    </div>
                    <a href="{console_url}" class="w-full py-2.5 px-4 rounded-xl text-xs font-bold text-slate-200 bg-slate-900 hover:bg-slate-800 border border-slate-700 transition text-center block">
                        Start Free Trial
                    </a>
                </div>

                <!-- Enterprise Tier (Highlighted) -->
                <div class="glass-panel rounded-3xl p-6 border-2 border-indigo-500 flex flex-col justify-between space-y-6 glow-indigo relative">
                    <div class="absolute -top-3.5 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-bold text-[10px] tracking-wider uppercase shadow-lg">
                        Most Popular
                    </div>
                    <div class="space-y-4 pt-1">
                        <div class="space-y-1">
                            <span class="text-xs font-mono font-bold text-indigo-300 uppercase">Enterprise</span>
                            <div class="flex items-baseline gap-1">
                                <span class="text-4xl font-black text-white">$1,499</span>
                                <span class="text-xs text-slate-400">/ month</span>
                            </div>
                        </div>
                        <p class="text-xs text-slate-300">Full 5-agent autonomous workforce for high-volume enterprise operations.</p>
                        <div class="border-t border-slate-800 pt-4 space-y-2.5 text-xs text-slate-200">
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> 25,000 AI Agent Turns/mo</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> 100,000 API Requests/mo</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> Unlimited DAG Workflows</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> 20 Seats Included</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> Custom Domain &amp; White-Label</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> Dedicated HITL Remediation Queue</div>
                        </div>
                    </div>
                    <a href="{console_url}" class="w-full py-2.5 px-4 rounded-xl text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-500 shadow-lg shadow-indigo-600/40 transition text-center block">
                        Deploy Enterprise
                    </a>
                </div>

                <!-- Custom Scale Tier -->
                <div class="glass-panel rounded-3xl p-6 border border-slate-800 flex flex-col justify-between space-y-6 hover:border-purple-500/60 transition">
                    <div class="space-y-4">
                        <div class="space-y-1">
                            <span class="text-xs font-mono font-bold text-purple-400 uppercase">Scale &amp; Custom</span>
                            <div class="flex items-baseline gap-1">
                                <span class="text-3xl font-black text-white">Custom</span>
                            </div>
                        </div>
                        <p class="text-xs text-slate-400">Bespoke SLA, private tenant cloud instances, and high-throughput EDI.</p>
                        <div class="border-t border-slate-800 pt-4 space-y-2.5 text-xs text-slate-300">
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-purple-400 text-[10px]"></i> Custom AI Models &amp; Quotas</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-purple-400 text-[10px]"></i> Unlimited Multi-Tenant Seats</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-purple-400 text-[10px]"></i> Dedicated PostgreSQL DB Cluster</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-purple-400 text-[10px]"></i> 99.99% Guaranteed SLA</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-purple-400 text-[10px]"></i> Custom EDI X12 Drop-Ship Mappings</div>
                        </div>
                    </div>
                    <a href="{console_url}" class="w-full py-2.5 px-4 rounded-xl text-xs font-bold text-purple-200 bg-purple-950/60 hover:bg-purple-900 border border-purple-800 transition text-center block">
                        Contact Enterprise Team
                    </a>
                </div>
            </div>

            <!-- Transparent Metered Billing Explainer Box -->
            <div class="glass-panel rounded-2xl p-6 border border-slate-800 max-w-4xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-6">
                <div class="flex items-center gap-4">
                    <div class="h-12 w-12 rounded-xl bg-emerald-600/20 text-emerald-400 flex items-center justify-center text-xl shrink-0">
                        <i class="fa-solid fa-gauge-high"></i>
                    </div>
                    <div>
                        <div class="font-bold text-sm text-white">Automated Metered Overage Protection</div>
                        <p class="text-xs text-slate-400">Never experience sudden pipeline cutoffs. Transparent rates apply automatically only when baseline quotas are exceeded:</p>
                    </div>
                </div>
                <div class="flex items-center gap-4 text-xs font-mono shrink-0">
                    <div class="px-3 py-1.5 bg-slate-900 rounded-lg border border-slate-800 text-center">
                        <div class="font-bold text-emerald-400">$0.005</div>
                        <div class="text-[10px] text-slate-400">per AI Turn</div>
                    </div>
                    <div class="px-3 py-1.5 bg-slate-900 rounded-lg border border-slate-800 text-center">
                        <div class="font-bold text-indigo-400">$0.001</div>
                        <div class="text-[10px] text-slate-400">per API Call</div>
                    </div>
                </div>
            </div>

            <!-- Interactive ROI Calculator Widget -->
            <div class="glass-panel rounded-3xl p-6 sm:p-8 border border-slate-800 max-w-3xl mx-auto space-y-6">
                <div class="flex items-center justify-between">
                    <div>
                        <h3 class="font-bold text-base text-white">Estimate Your Autonomous Workforce ROI</h3>
                        <p class="text-xs text-slate-400">Drag to adjust your monthly sales &amp; replenishment volume</p>
                    </div>
                    <div class="text-right">
                        <span class="text-xs text-slate-400">Monthly Time Saved</span>
                        <div class="text-xl font-bold font-mono text-emerald-400" id="roi-hours-saved">160 Hours</div>
                    </div>
                </div>
                <div class="space-y-2">
                    <div class="flex justify-between text-xs text-slate-300">
                        <span>Monthly Deals &amp; Orders Handled: <strong id="roi-volume-label" class="text-white font-mono">500</strong></span>
                    </div>
                    <input type="range" min="100" max="5000" step="100" value="500" id="roi-slider" oninput="calculateRoi(this.value)" class="w-full accent-indigo-500 cursor-pointer">
                </div>
                <div class="grid grid-cols-2 gap-4 pt-2 border-t border-slate-800 text-center text-xs">
                    <div class="p-3 bg-slate-900 rounded-xl border border-slate-800">
                        <div class="text-slate-400 text-[10px] uppercase">Labor Cost Saved</div>
                        <div class="text-base font-bold font-mono text-white" id="roi-cost-saved">$9,600 / mo</div>
                    </div>
                    <div class="p-3 bg-slate-900 rounded-xl border border-slate-800">
                        <div class="text-slate-400 text-[10px] uppercase">Stockout Revenue Protected</div>
                        <div class="text-base font-bold font-mono text-emerald-400" id="roi-revenue-protected">$48,000 / mo</div>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- FOOTER -->
    <footer class="border-t border-slate-900 bg-slate-950 py-12 text-slate-400 text-xs">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
            <div class="flex flex-wrap items-center justify-between gap-6 pb-8 border-b border-slate-900">
                <div class="flex items-center gap-3">
                    <div class="h-8 w-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white text-sm">
                        <i class="fa-solid fa-brain"></i>
                    </div>
                    <span class="font-extrabold text-base text-white">NexFlow<span class="text-indigo-400">.ai</span></span>
                    <span class="text-slate-500">| Enterprise Multi-Agent Automation</span>
                </div>
                <div class="flex items-center gap-6 text-xs">
                    <a href="{console_url}" class="hover:text-white transition">Launch Console</a>
                    <a href="#agents" class="hover:text-white transition">5 AI Agents</a>
                    <a href="#workflows" class="hover:text-white transition">DAG Studio</a>
                    <a href="#pricing" class="hover:text-white transition">Pricing</a>
                    <a href="{prefix}/docs" target="_blank" class="hover:text-white transition flex items-center gap-1">
                        <i class="fa-solid fa-code"></i> OpenAPI Docs
                    </a>
                </div>
            </div>
            <div class="flex flex-wrap items-center justify-between gap-4 text-slate-500 text-[11px]">
                <p>&copy; 2026 NexFlow AI Technologies Inc. All rights reserved. Powered by Google Gemini &amp; Multi-Tenant PostgreSQL.</p>
                <div class="flex items-center gap-4">
                    <span class="flex items-center gap-1.5"><i class="fa-solid fa-shield-halved text-emerald-400"></i> SOC-2 Ready Isolation</span>
                    <span class="flex items-center gap-1.5"><i class="fa-solid fa-lock text-indigo-400"></i> Cryptographic Tokens</span>
                    <span class="flex items-center gap-1.5"><i class="fa-solid fa-credit-card text-purple-400"></i> Stripe Verified</span>
                </div>
            </div>
        </div>
    </footer>

    <!-- INTERACTIVE SCRIPT LOGIC -->
    <script>
        const API_PREFIX = "{prefix}";
        const LEAD_API_URL = "{lead_api_url}";

        // The 5 AI Agent Specifications Matrix
        const AGENT_DATA = {{
            sales: {{
                name: "1. Sales Intelligence & Lead Dossier Agent",
                icon: "fa-magnifying-glass-chart",
                color: "indigo",
                role: "Inbound Prospect Qualification & Executive Closing Playbook Synthesis",
                description: "Interprets incoming web forms, LinkedIn signals, and buyer inquiries. Performs real-time firmographic enrichment, calculates deal readiness scores, and synthesizes tailored closing dossiers.",
                capabilities: [
                    "Firmographic & revenue profiling",
                    "Buyer intent & readiness classification",
                    "Closing objection preparation",
                    "Automated senior closer account assignment"
                ],
                sampleInput: `{{"company": "Titanium Aerospace", "deal_value": 85000, "intent": "Avionics Replenishment"}}`,
                sampleOutput: `{{"buyer_readiness": "96%", "recommended_offer": "SLA-Backed Annual Restock Tier", "confidence": 0.98}}`,
                impactMetric: "+34% Sales Velocity"
            }},
            demand: {{
                name: "2. Predictive Demand & Inventory Replenishment Agent",
                icon: "fa-boxes-packing",
                color: "emerald",
                role: "Burn Rate Analytics, Stockout Risk Mitigation & PO Dispatch",
                description: "Continuously monitors customer burn rate velocity, safety stock buffers, and reorder cadence. Predicts stockouts weeks before they occur and autonomously generates purchase orders and RFQs.",
                capabilities: [
                    "Dynamic consumption burn rate modeling",
                    "Lead time variability calculations",
                    "Autonomous purchase order drafting",
                    "Emergency supplier negotiation RFQ dispatch"
                ],
                sampleInput: `{{"sku": "PUMP-3000PSI", "burn_rate": 2.4, "current_stock": 5, "reorder_point": 12}}`,
                sampleOutput: `{{"stockout_risk_score": 94, "action": "draft_po", "urgency": "critical", "po_number": "PO-AUTO-91823"}}`,
                impactMetric: "Zero Stockout Revenue Loss"
            }},
            support: {{
                name: "3. 24/7 Support Copilot & Customer Success Agent",
                icon: "fa-headset",
                color: "pink",
                role: "Autonomous Post-Sale Portal Resolution with 7 Live Account Tools",
                description: "Embedded directly in customer self-service portals (/portal/{{token}}). Resolves delivery tracking, order history, billing checks, and restock cadence shifts with zero wait times.",
                capabilities: [
                    "7 Live Account & Carrier Tools",
                    "1-Click restock cadence snoozing & acceleration",
                    "Card-on-file & invoice payment verification",
                    "Hostile tone detection & immediate manager page"
                ],
                sampleInput: `{{"customer_message": "Where is ORD-7788 and can you snooze next delivery 2 weeks?"}}`,
                sampleOutput: `{{"tool_executed": "snooze_restock_schedule", "shifted_to": "2026-10-15", "tracking_url": "FX-992144"}}`,
                impactMetric: "82% Autonomous Support Resolution"
            }},
            orchestrator: {{
                name: "4. Visual DAG Workflow Orchestrator Agent",
                icon: "fa-diagram-project",
                color: "purple",
                role: "Event-Driven Multi-Step Pipeline Coordination & Webhook Relays",
                description: "The pipeline brain. Evaluates multi-step DAG canvas logic, executes conditional branches (==, !=, >, <, in, contains), coordinates agent handoffs, and syncs external webhooks.",
                capabilities: [
                    "Visual SVG node-based canvas builder",
                    "Live dry-run simulation mode",
                    "Omnichannel alert dispatches (Slack, Email, SMS)",
                    "Sub-30ms step execution latency telemetry"
                ],
                sampleInput: `{{"event": "lead_created", "workflow_id": "wf_vip_fasttrack", "dry_run": true}}`,
                sampleOutput: `{{"steps_executed": 4, "overall_status": "completed", "execution_time_ms": 28.4}}`,
                impactMetric: "&lt; 30ms Execution Latency"
            }},
            hitl: {{
                name: "5. Human-in-the-Loop (HITL) Remediation Agent",
                icon: "fa-user-shield",
                color: "amber",
                role: "Grievance Safeguards, Concession Packages & Human Takeover",
                description: "Intercepts high-risk edge cases, frustrated sentiments, and contractual disputes. Formulates instant concession packages and stages high-confidence recommendations for 1-click human takeover.",
                capabilities: [
                    "Continuous sentiment & hostility parsing",
                    "Automatic priority HITL ticket generation",
                    "AI remediation proposal synthesis",
                    "1-Click human sales rep console takeover"
                ],
                sampleInput: `{{"sentiment": "hostile", "complaint": "Delayed critical shipment impacting factory floor"}}`,
                sampleOutput: `{{"remediation": "Offer expedited freight credit + senior manager outreach", "hitl_id": "hitl-90a1"}}`,
                impactMetric: "100% Churn Prevention"
            }}
        }};

        function switchAgentTab(key) {{
            const agent = AGENT_DATA[key];
            if (!agent) return;

            // Update tab button styles
            const tabs = ['sales', 'demand', 'support', 'orchestrator', 'hitl'];
            tabs.forEach(t => {{
                const btn = document.getElementById(`tab-btn-${{t}}`);
                if (btn) {{
                    if (t === key) {{
                        btn.className = "px-4 py-2.5 rounded-xl text-xs font-bold transition flex items-center gap-2 bg-indigo-600 text-white shadow-lg";
                    }} else {{
                        btn.className = "px-4 py-2.5 rounded-xl text-xs font-bold transition flex items-center gap-2 text-slate-400 hover:text-white hover:bg-slate-800";
                    }}
                }}
            }});

            // Render detail card
            const container = document.getElementById("agent-detail-container");
            container.innerHTML = `
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-8 items-center">
                    <div class="space-y-5">
                        <div class="flex items-center gap-3">
                            <div class="h-12 w-12 rounded-2xl bg-${{agent.color}}-600/20 text-${{agent.color}}-400 flex items-center justify-center text-xl shadow-lg">
                                <i class="fa-solid ${{agent.icon}}"></i>
                            </div>
                            <div>
                                <h3 class="font-extrabold text-xl text-white">${{agent.name}}</h3>
                                <span class="text-xs font-mono font-semibold text-${{agent.color}}-400">${{agent.role}}</span>
                            </div>
                        </div>

                        <p class="text-sm text-slate-300 leading-relaxed">${{agent.description}}</p>

                        <div class="space-y-2">
                            <span class="text-xs font-bold uppercase tracking-wider text-slate-400">Autonomous Capabilities:</span>
                            <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-slate-200">
                                ${{agent.capabilities.map(c => `
                                    <div class="flex items-center gap-2">
                                        <i class="fa-solid fa-circle-check text-emerald-400 text-xs"></i>
                                        <span>${{c}}</span>
                                    </div>
                                `).join('')}}
                            </div>
                        </div>

                        <div class="pt-2 flex items-center gap-4">
                            <span class="px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs font-mono text-emerald-400 font-bold">
                                ROI: ${{agent.impactMetric}}
                            </span>
                            <a href="${{API_PREFIX}}/console" class="text-xs text-indigo-400 hover:text-indigo-300 font-semibold flex items-center gap-1">
                                Test in Management Console <i class="fa-solid fa-arrow-right text-[10px]"></i>
                            </a>
                        </div>
                    </div>

                    <!-- Live Simulated Telemetry Trace Card -->
                    <div class="bg-slate-950/90 rounded-2xl p-5 border border-slate-800/80 font-mono text-xs space-y-3 shadow-xl">
                        <div class="flex items-center justify-between pb-2 border-b border-slate-800">
                            <span class="text-[11px] text-slate-400 uppercase tracking-wider">Live Agent Telemetry Feed</span>
                            <span class="text-emerald-400 text-[10px] font-bold flex items-center gap-1">
                                <span class="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"></span> EXECUTING
                            </span>
                        </div>

                        <div class="space-y-1">
                            <span class="text-[10px] text-slate-500 uppercase">Input Payload:</span>
                            <pre class="bg-slate-900 p-2.5 rounded-lg text-slate-300 overflow-x-auto text-[11px]">${{agent.sampleInput}}</pre>
                        </div>

                        <div class="space-y-1">
                            <span class="text-[10px] text-slate-500 uppercase">Structured Decision Output:</span>
                            <pre class="bg-indigo-950/40 border border-indigo-800/50 p-2.5 rounded-lg text-indigo-200 overflow-x-auto text-[11px]">${{agent.sampleOutput}}</pre>
                        </div>
                    </div>
                </div>
            `;
        }}

        // Live Interactive Lead Dossier Generator
        async function generateLiveDossier(e) {{
            e.preventDefault();
            const comp = document.getElementById("demo-company").value;
            const ind = document.getElementById("demo-industry").value;
            const val = document.getElementById("demo-value").value;

            document.getElementById("btn-demo-submit").disabled = true;
            document.getElementById("dossier-output").classList.add("hidden");
            document.getElementById("dossier-loading").classList.remove("hidden");

            // Format synthetic payload
            const payload = {{
                company: comp,
                estimated_value: parseFloat(val),
                industry: ind,
                notes: `Generated via public landing page interactive dossier generator for ${{comp}}.`
            }};

            // Optional real backend call to CRM leads (falls back gracefully)
            try {{
                await fetch(LEAD_API_URL, {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{
                        name: `Contact at ${{comp}}`,
                        email: `info@${{comp.toLowerCase().replace(/[^a-z0-9]/g, '')}}.example`,
                        company: comp,
                        deal_size: parseFloat(val),
                        notes: `Inbound request from ${{ind}} sector.`
                    }})
                }});
            }} catch (err) {{
                // Silent fallback for public unauthenticated visitors
            }}

            setTimeout(() => {{
                document.getElementById("dossier-loading").classList.add("hidden");
                document.getElementById("dossier-output").classList.remove("hidden");
                document.getElementById("btn-demo-submit").disabled = false;

                document.getElementById("out-company").innerText = comp;
                document.getElementById("out-deal").innerText = "$" + Number(val).toLocaleString();
                document.getElementById("out-tier").innerText = parseFloat(val) >= 250000 ? "STRATEGIC ENTERPRISE VIP" : "HIGH-VALUE ENTERPRISE";
                document.getElementById("out-score").innerText = (93 + Math.floor(Math.random() * 6)) + "/100";
                
                document.getElementById("out-buyer-profile").innerText = 
                    `High-intent enterprise organization operating in the ${{ind}} sector. Verified high buyer readiness. Critical operational priority is eliminating procurement bottlenecks and deploying autonomous replenishment pipelines.`;

                document.getElementById("out-closing-strategy").innerText = 
                    `Engage senior leadership with SLA-backed autonomous replenishment guarantees. Emphasize multi-agent DAG orchestration to integrate existing enterprise ERP and eliminate stockout vulnerability.`;
            }}, 750);
        }}

        // ROI Calculator Logic
        function calculateRoi(val) {{
            document.getElementById("roi-volume-label").innerText = val;
            const hours = Math.round(val * 0.32);
            const cost = Math.round(hours * 60);
            const revenue = Math.round(val * 96);

            document.getElementById("roi-hours-saved").innerText = hours.toLocaleString() + " Hours";
            document.getElementById("roi-cost-saved").innerText = "$" + cost.toLocaleString() + " / mo";
            document.getElementById("roi-revenue-protected").innerText = "$" + revenue.toLocaleString() + " / mo";
        }}

        // Initialize Default Agent Tab
        document.addEventListener("DOMContentLoaded", () => {{
            switchAgentTab("sales");
        }});
    </script>
</body>
</html>
"""
