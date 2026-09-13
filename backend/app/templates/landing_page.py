"""
SaaS Marketing Landing Page Template
Renders a modern, responsive, high-converting product showcase
spotlighting the 6 Specialized Types of AI Sales Agents available for SaaS clients:
1. The Lead Developer Agent
2. The Decision-Maker Pathfinder & Literature Bot
3. The Appointment Setter Agent
4. The Cold Outreach SDR Agent
5. The Executive Sales Bot
6. The Objection Handler & Account Expansion Bot
"""

def render_landing_page(api_prefix: str = "") -> str:
    prefix = api_prefix.rstrip("/")
    console_url = f"{prefix}/console" if prefix else "/console"
    signup_url = f"{prefix}/signup" if prefix else "/signup"
    lead_api_url = f"{prefix}/api/v1/crm/leads" if prefix else "/api/v1/crm/leads"

    return f"""<!DOCTYPE html>
<html lang="en" class="scroll-smooth">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NexFlow AI • Autonomous AI Sales Bots Workforce for SaaS</title>
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
            background: rgba(15, 23, 42, 0.78);
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
    <div class="absolute top-0 left-1/2 -translate-x-1/2 w-[1100px] h-[480px] bg-gradient-to-b from-indigo-600/20 via-purple-600/10 to-transparent blur-3xl pointer-events-none -z-10"></div>
    <div class="absolute top-[650px] right-0 w-[550px] h-[550px] bg-emerald-600/10 blur-3xl pointer-events-none -z-10"></div>

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
                        <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-indigo-950 text-indigo-300 border border-indigo-700/50">6 SALES AI BOTS</span>
                    </div>
                    <span class="text-[11px] text-slate-400">Autonomous Sales Pipeline Workforce for SaaS</span>
                </div>
            </div>

            <!-- Desktop Nav Links -->
            <nav class="hidden md:flex items-center gap-8 text-sm font-medium text-slate-300">
                <a href="#agents" class="hover:text-indigo-400 transition flex items-center gap-1.5">
                    <i class="fa-solid fa-users-gear text-indigo-400 text-xs"></i> 6 Sales Bots
                </a>
                <a href="#pipeline" class="hover:text-indigo-400 transition flex items-center gap-1.5">
                    <i class="fa-solid fa-diagram-project text-purple-400 text-xs"></i> Pipeline Architecture
                </a>
                <a href="#interactive-tester" class="hover:text-indigo-400 transition flex items-center gap-1.5">
                    <i class="fa-solid fa-wand-magic-sparkles text-amber-400 text-xs"></i> Live Agent Demo
                </a>
                <a href="#inbound-demo" class="hover:text-cyan-400 transition flex items-center gap-1.5">
                    <i class="fa-solid fa-file-arrow-down text-cyan-400 text-xs"></i> Whitepaper &amp; Demo
                </a>
                <a href="#stack-configurator" class="hover:text-indigo-400 transition flex items-center gap-1.5">
                    <i class="fa-solid fa-calculator text-emerald-400 text-xs"></i> Stack Calculator
                </a>
                <a href="#pricing" class="hover:text-indigo-400 transition flex items-center gap-1.5">
                    <i class="fa-solid fa-tag text-pink-400 text-xs"></i> Pricing Plans
                </a>
            </nav>

            <!-- Actions -->
            <div class="flex items-center gap-3">
                <a href="{console_url}" class="hidden sm:inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold text-slate-300 hover:text-white bg-slate-900/80 hover:bg-slate-800 border border-slate-700/80 transition">
                    <i class="fa-solid fa-shield-halved text-slate-400"></i> Management Console
                </a>
                <a href="{signup_url}" class="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 shadow-lg shadow-indigo-600/30 transition transform hover:-translate-y-0.5">
                    <span>Deploy Sales Bots</span>
                    <i class="fa-solid fa-arrow-right"></i>
                </a>
            </div>
        </div>
    </header>

    <!-- HERO SECTION -->
    <section class="relative pt-16 pb-24 md:pt-24 md:pb-32 grid-bg">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center space-y-8">
            <!-- Feature Badge -->
            <div class="inline-flex items-center gap-2 px-4 py-2 rounded-full glass-panel border border-indigo-500/30 text-xs font-semibold text-indigo-300 shadow-xl">
                <span class="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>The Complete Autonomous AI Sales Workforce for SaaS Clients</span>
                <i class="fa-solid fa-chevron-right text-[10px] text-indigo-400"></i>
            </div>

            <!-- Main Heading -->
            <h1 class="text-4xl sm:text-6xl lg:text-7xl font-black tracking-tight max-w-5xl mx-auto leading-[1.1]">
                Hire an Autonomous AI Sales Team: <br>
                <span class="gradient-text">The 6 Specialized Sales Bots</span> <br>
                Built to Scale SaaS Revenue
            </h1>

            <!-- Subtitle -->
            <p class="text-base sm:text-xl text-slate-300 max-w-3xl mx-auto leading-relaxed font-normal">
                Replace fragmented sales software with a dedicated team of <strong class="text-white font-semibold">6 specialized AI sales bots</strong>. From automated <strong class="text-indigo-400">Lead Development</strong> and phone/email <strong class="text-cyan-400">Decision-Maker Discovery &amp; Literature Dispatch</strong> to <strong class="text-pink-400">Appointment Setting</strong> and high-touch <strong class="text-purple-400">Executive Sales Closers</strong>, your SaaS sales pipeline runs 24/7 without burning out reps.
            </p>

            <!-- Primary CTAs -->
            <div class="flex flex-wrap items-center justify-center gap-4 pt-4">
                <a href="#interactive-tester" class="px-8 py-4 rounded-2xl text-sm font-bold text-white bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 hover:from-indigo-500 hover:to-pink-500 shadow-2xl shadow-indigo-600/40 transition transform hover:-translate-y-0.5 flex items-center gap-3">
                    <i class="fa-solid fa-robot text-amber-300 text-base"></i>
                    <span>Test Drive The Sales Bots</span>
                </a>
                <a href="#stack-configurator" class="px-7 py-4 rounded-2xl text-sm font-bold text-slate-200 bg-slate-900/90 hover:bg-slate-800/90 border border-slate-700/80 shadow-xl transition flex items-center gap-2.5">
                    <i class="fa-solid fa-sliders text-indigo-400"></i>
                    <span>Configure Your 6-Bot Stack</span>
                </a>
                <a href="{console_url}" class="px-6 py-4 rounded-2xl text-sm font-semibold text-slate-400 hover:text-white transition flex items-center gap-2">
                    <i class="fa-solid fa-desktop text-xs text-indigo-400"></i>
                    <span>Open CRM Console</span>
                </a>
            </div>

            <!-- Key Performance Proof Ticker -->
            <div class="pt-12 max-w-6xl mx-auto">
                <div class="glass-panel rounded-2xl p-6 border border-slate-800 grid grid-cols-2 md:grid-cols-5 gap-4 text-center">
                    <div class="space-y-1">
                        <div class="text-2xl sm:text-3xl font-black font-mono text-emerald-400">48+ Demos</div>
                        <div class="text-xs text-slate-400 uppercase tracking-wider font-semibold">Booked / Mo per Client</div>
                    </div>
                    <div class="space-y-1">
                        <div class="text-2xl sm:text-3xl font-black font-mono text-cyan-400">74% DM Opt-In</div>
                        <div class="text-xs text-slate-400 uppercase tracking-wider font-semibold">Switchboard to DM Lit</div>
                    </div>
                    <div class="space-y-1">
                        <div class="text-2xl sm:text-3xl font-black font-mono text-indigo-400">&lt; 3 Minutes</div>
                        <div class="text-xs text-slate-400 uppercase tracking-wider font-semibold">Inbound Lead Response</div>
                    </div>
                    <div class="space-y-1">
                        <div class="text-2xl sm:text-3xl font-black font-mono text-purple-400">+38%</div>
                        <div class="text-xs text-slate-400 uppercase tracking-wider font-semibold">Close Rate with Exec Bot</div>
                    </div>
                    <div class="space-y-1">
                        <div class="text-2xl sm:text-3xl font-black font-mono text-pink-400">68% Lower</div>
                        <div class="text-xs text-slate-400 uppercase tracking-wider font-semibold">Customer Acquisition Cost</div>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- THE 6 SPECIALIZED SALES AI BOTS OPTIONS -->
    <section id="agents" class="py-24 relative border-t border-slate-900 bg-slate-950/70">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-16">
            <div class="text-center space-y-4 max-w-3xl mx-auto">
                <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-950/60 text-indigo-300 border border-indigo-800/50 text-xs font-semibold">
                    <i class="fa-solid fa-users-gear text-indigo-400"></i>
                    <span>SaaS Client Sales Agent Portfolio</span>
                </div>
                <h2 class="text-3xl sm:text-5xl font-black tracking-tight text-white">
                    The 6 Types of AI Sales Bots <br>
                    <span class="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400">Available For Your SaaS Pipeline</span>
                </h2>
                <p class="text-slate-400 text-sm sm:text-base">
                    Choose individual bots or deploy all six together. Each bot is pre-trained on high-converting B2B SaaS sales playbooks, objection frameworks, phone switchboard discovery, and appointment booking cadences.
                </p>
            </div>

            <!-- Agent Selector Tabs -->
            <div class="flex flex-wrap items-center justify-center gap-2 bg-slate-900/80 p-2 rounded-2xl border border-slate-800 max-w-6xl mx-auto">
                <button onclick="switchAgentTab('lead_dev')" id="tab-btn-lead_dev" class="px-4 py-2.5 rounded-xl text-xs font-bold transition flex items-center gap-2 bg-indigo-600 text-white shadow-lg">
                    <i class="fa-solid fa-database text-indigo-200"></i>
                    <span>1. The Lead Developer</span>
                </button>
                <button onclick="switchAgentTab('discovery')" id="tab-btn-discovery" class="px-4 py-2.5 rounded-xl text-xs font-bold transition flex items-center gap-2 text-slate-400 hover:text-white hover:bg-slate-800">
                    <i class="fa-solid fa-phone-volume text-cyan-400"></i>
                    <span>2. Decision-Maker &amp; Literature Bot</span>
                </button>
                <button onclick="switchAgentTab('setter')" id="tab-btn-setter" class="px-4 py-2.5 rounded-xl text-xs font-bold transition flex items-center gap-2 text-slate-400 hover:text-white hover:bg-slate-800">
                    <i class="fa-solid fa-calendar-check text-pink-400"></i>
                    <span>3. The Appointment Setter</span>
                </button>
                <button onclick="switchAgentTab('sdr')" id="tab-btn-sdr" class="px-4 py-2.5 rounded-xl text-xs font-bold transition flex items-center gap-2 text-slate-400 hover:text-white hover:bg-slate-800">
                    <i class="fa-solid fa-paper-plane text-emerald-400"></i>
                    <span>4. The Cold Outreach SDR</span>
                </button>
                <button onclick="switchAgentTab('exec_bot')" id="tab-btn-exec_bot" class="px-4 py-2.5 rounded-xl text-xs font-bold transition flex items-center gap-2 text-slate-400 hover:text-white hover:bg-slate-800">
                    <i class="fa-solid fa-chess-king text-purple-400"></i>
                    <span>5. The Executive Sales Bot</span>
                </button>
                <button onclick="switchAgentTab('closer')" id="tab-btn-closer" class="px-4 py-2.5 rounded-xl text-xs font-bold transition flex items-center gap-2 text-slate-400 hover:text-white hover:bg-slate-800">
                    <i class="fa-solid fa-handshake-angle text-amber-400"></i>
                    <span>6. The Objection Closer</span>
                </button>
            </div>

            <!-- Dynamic Agent Focus Viewport -->
            <div id="agent-detail-container" class="glass-panel rounded-3xl p-6 sm:p-10 border border-slate-800 max-w-5xl mx-auto glow-indigo">
                <!-- Dynamically rendered via JS -->
            </div>

            <!-- Comprehensive Agent Cards Matrix -->
            <div class="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4 pt-6">
                <!-- Card 1 -->
                <div onclick="switchAgentTab('lead_dev')" class="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 space-y-2.5 hover:border-indigo-500/50 transition cursor-pointer group">
                    <div class="h-9 w-9 rounded-xl bg-indigo-600/20 text-indigo-400 flex items-center justify-center text-base group-hover:scale-110 transition">
                        <i class="fa-solid fa-database"></i>
                    </div>
                    <div class="font-bold text-xs text-white">1. The Lead Developer</div>
                    <p class="text-[11px] text-slate-400 leading-relaxed">Scrapes &amp; enriches ideal B2B accounts with verified emails and intent signals.</p>
                    <div class="text-[10px] font-mono text-indigo-400 font-semibold">1k+ Accounts/Day</div>
                </div>

                <!-- Card 2 (NEW: Decision-Maker Pathfinder & Literature Bot) -->
                <div onclick="switchAgentTab('discovery')" class="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 space-y-2.5 hover:border-cyan-500/50 transition cursor-pointer group">
                    <div class="h-9 w-9 rounded-xl bg-cyan-600/20 text-cyan-400 flex items-center justify-center text-base group-hover:scale-110 transition">
                        <i class="fa-solid fa-phone-volume"></i>
                    </div>
                    <div class="font-bold text-xs text-white">2. DM &amp; Literature Bot</div>
                    <p class="text-[11px] text-slate-400 leading-relaxed">Contacts via phone &amp; email to find decision-makers and dispatches marketing collateral.</p>
                    <div class="text-[10px] font-mono text-cyan-400 font-semibold">74% DM Opt-in Rate</div>
                </div>

                <!-- Card 3 -->
                <div onclick="switchAgentTab('setter')" class="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 space-y-2.5 hover:border-pink-500/50 transition cursor-pointer group">
                    <div class="h-9 w-9 rounded-xl bg-pink-600/20 text-pink-400 flex items-center justify-center text-base group-hover:scale-110 transition">
                        <i class="fa-solid fa-calendar-check"></i>
                    </div>
                    <div class="font-bold text-xs text-white">3. Appointment Setter</div>
                    <p class="text-[11px] text-slate-400 leading-relaxed">Conversational 2-way booking onto rep Google &amp; Outlook calendars.</p>
                    <div class="text-[10px] font-mono text-pink-400 font-semibold">48 Demos Booked / Mo</div>
                </div>

                <!-- Card 4 -->
                <div onclick="switchAgentTab('sdr')" class="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 space-y-2.5 hover:border-emerald-500/50 transition cursor-pointer group">
                    <div class="h-9 w-9 rounded-xl bg-emerald-600/20 text-emerald-400 flex items-center justify-center text-base group-hover:scale-110 transition">
                        <i class="fa-solid fa-paper-plane"></i>
                    </div>
                    <div class="font-bold text-xs text-white">4. Cold Outreach SDR</div>
                    <p class="text-[11px] text-slate-400 leading-relaxed">Delivers hyper-personalized 1-to-1 multi-channel cold sequences.</p>
                    <div class="text-[10px] font-mono text-emerald-400 font-semibold">28% Cold Reply Rate</div>
                </div>

                <!-- Card 5 -->
                <div onclick="switchAgentTab('exec_bot')" class="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 space-y-2.5 hover:border-purple-500/50 transition cursor-pointer group">
                    <div class="h-9 w-9 rounded-xl bg-purple-600/20 text-purple-400 flex items-center justify-center text-lg group-hover:scale-110 transition">
                        <i class="fa-solid fa-chess-king"></i>
                    </div>
                    <div class="font-bold text-xs text-white">5. Executive Sales Bot</div>
                    <p class="text-[11px] text-slate-400 leading-relaxed">Synthesizes deal closing dossiers, proposals, and ROI business cases.</p>
                    <div class="text-[10px] font-mono text-purple-400 font-semibold">Wins 5 &amp; 6-Figure Deals</div>
                </div>

                <!-- Card 6 -->
                <div onclick="switchAgentTab('closer')" class="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 space-y-2.5 hover:border-amber-500/50 transition cursor-pointer group">
                    <div class="h-9 w-9 rounded-xl bg-amber-600/20 text-amber-400 flex items-center justify-center text-base group-hover:scale-110 transition">
                        <i class="fa-solid fa-handshake-angle"></i>
                    </div>
                    <div class="font-bold text-xs text-white">6. The Objection Closer</div>
                    <p class="text-[11px] text-slate-400 leading-relaxed">Overcomes pricing friction, stalls, and recovers stuck negotiations.</p>
                    <div class="text-[10px] font-mono text-amber-400 font-semibold">Recovers 35% Stalls</div>
                </div>
            </div>
        </div>
    </section>

    <!-- PIPELINE ARCHITECTURE & COLLABORATION -->
    <section id="pipeline" class="py-24 relative border-t border-slate-900">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-16">
            <div class="text-center space-y-4 max-w-3xl mx-auto">
                <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-purple-950/60 text-purple-300 border border-purple-800/50 text-xs font-semibold">
                    <i class="fa-solid fa-diagram-project text-purple-400"></i>
                    <span>Autonomous Handoff Architecture</span>
                </div>
                <h2 class="text-3xl sm:text-5xl font-black tracking-tight text-white">
                    How The 6 Autonomous Sales Bots <br>
                    <span class="gradient-text">Build Your Complete Pipeline</span>
                </h2>
                <p class="text-slate-400 text-sm sm:text-base">
                    No leads slip through the cracks. Each agent executes its specialty and smoothly passes the prospect downstream in the sales funnel.
                </p>
            </div>

            <!-- Pipeline Visual Stepper (6-Stage Autonomous Flow) -->
            <div class="glass-panel rounded-3xl p-8 border border-slate-800 relative overflow-hidden">
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-3 relative z-10">
                    <!-- Stage 1 -->
                    <div class="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 space-y-2.5 relative">
                        <div class="h-7 w-7 rounded-lg bg-indigo-600/20 text-indigo-400 font-mono font-bold flex items-center justify-center text-xs">01</div>
                        <div class="font-bold text-[10px] text-white uppercase tracking-wider text-indigo-400">Lead Research</div>
                        <h4 class="font-bold text-xs text-slate-200">The Lead Developer</h4>
                        <p class="text-[11px] text-slate-400">Scrapes verified emails and intent signals.</p>
                        <div class="text-[9px] font-mono text-emerald-400 bg-emerald-950/40 p-1.5 rounded border border-emerald-800/40">✓ Enriched ICP Account</div>
                    </div>

                    <!-- Stage 2: NEW Decision-Maker Discovery & Literature Dispatch -->
                    <div class="bg-slate-900/90 border border-cyan-500/50 rounded-2xl p-4 space-y-2.5 relative">
                        <div class="h-7 w-7 rounded-lg bg-cyan-600/20 text-cyan-400 font-mono font-bold flex items-center justify-center text-xs">02</div>
                        <div class="font-bold text-[10px] text-white uppercase tracking-wider text-cyan-400">DM Discovery &amp; Literature</div>
                        <h4 class="font-bold text-xs text-slate-200">DM &amp; Literature Bot</h4>
                        <p class="text-[11px] text-slate-400">Calls/emails switchboard, connects with DM, and emails/mails literature.</p>
                        <div class="text-[9px] font-mono text-cyan-400 bg-cyan-950/40 p-1.5 rounded border border-cyan-800/40">✓ Literature Sent &amp; Warmed</div>
                    </div>

                    <!-- Stage 3 -->
                    <div class="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 space-y-2.5 relative">
                        <div class="h-7 w-7 rounded-lg bg-emerald-600/20 text-emerald-400 font-mono font-bold flex items-center justify-center text-xs">03</div>
                        <div class="font-bold text-[10px] text-white uppercase tracking-wider text-emerald-400">Outreach Cadence</div>
                        <h4 class="font-bold text-xs text-slate-200">Cold Outreach SDR</h4>
                        <p class="text-[11px] text-slate-400">Delivers tailored 1-to-1 multi-channel sequences.</p>
                        <div class="text-[9px] font-mono text-emerald-400 bg-emerald-950/40 p-1.5 rounded border border-emerald-800/40">✓ Positive Reply Detected</div>
                    </div>

                    <!-- Stage 4 -->
                    <div class="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 space-y-2.5 relative">
                        <div class="h-7 w-7 rounded-lg bg-pink-600/20 text-pink-400 font-mono font-bold flex items-center justify-center text-xs">04</div>
                        <div class="font-bold text-[10px] text-white uppercase tracking-wider text-pink-400">Demo Scheduling</div>
                        <h4 class="font-bold text-xs text-slate-200">Appointment Setter</h4>
                        <p class="text-[11px] text-slate-400">Locks confirmed demo into rep calendars.</p>
                        <div class="text-[9px] font-mono text-pink-400 bg-pink-950/40 p-1.5 rounded border border-pink-800/40">✓ Calendar Invite Confirmed</div>
                    </div>

                    <!-- Stage 5 -->
                    <div class="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 space-y-2.5 relative">
                        <div class="h-7 w-7 rounded-lg bg-purple-600/20 text-purple-400 font-mono font-bold flex items-center justify-center text-xs">05</div>
                        <div class="font-bold text-[10px] text-white uppercase tracking-wider text-purple-400">Executive Closing</div>
                        <h4 class="font-bold text-xs text-slate-200">Executive Sales Bot</h4>
                        <p class="text-[11px] text-slate-400">Assembles deal dossiers &amp; bespoke proposals.</p>
                        <div class="text-[9px] font-mono text-purple-400 bg-purple-950/40 p-1.5 rounded border border-purple-800/40">✓ Custom Proposal Sent</div>
                    </div>

                    <!-- Stage 6 -->
                    <div class="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 space-y-2.5 relative">
                        <div class="h-7 w-7 rounded-lg bg-amber-600/20 text-amber-400 font-mono font-bold flex items-center justify-center text-xs">06</div>
                        <div class="font-bold text-[10px] text-white uppercase tracking-wider text-amber-400">Contract &amp; Stalls</div>
                        <h4 class="font-bold text-xs text-slate-200">The Objection Closer</h4>
                        <p class="text-[11px] text-slate-400">Neutralizes pricing friction &amp; contract stalls.</p>
                        <div class="text-[9px] font-mono text-amber-400 bg-amber-950/40 p-1.5 rounded border border-amber-800/40">✓ Deal Signed &amp; Renewed</div>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- LIVE INTERACTIVE AGENT TESTER -->
    <section id="interactive-tester" class="py-24 relative border-t border-slate-900 grid-bg">
        <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 space-y-12">
            <div class="text-center space-y-4 max-w-3xl mx-auto">
                <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-950/60 text-amber-300 border border-amber-800/50 text-xs font-semibold">
                    <i class="fa-solid fa-wand-magic-sparkles text-amber-400"></i>
                    <span>Interactive Real-Time Simulation</span>
                </div>
                <h2 class="text-3xl sm:text-5xl font-black tracking-tight text-white">
                    Test Drive Your AI Sales Workforce: <br>
                    <span class="gradient-text">See The Decision-Maker &amp; Executive Bots in Action</span>
                </h2>
                <p class="text-slate-400 text-sm sm:text-base">
                    Enter your SaaS prospect details below. Test drive the Decision-Maker Pathfinder &amp; Literature Bot, the Executive Sales Bot, the Appointment Setter, or the Lead Developer.
                </p>
            </div>

            <!-- Interactive Tester Card -->
            <div class="glass-panel rounded-3xl p-6 sm:p-10 border border-slate-800 shadow-2xl space-y-8">
                <!-- Agent Selector for Tester -->
                <div class="flex flex-wrap items-center gap-2 pb-2 border-b border-slate-800">
                    <span class="text-xs font-bold uppercase text-slate-400 tracking-wider mr-2">Select Bot to Test:</span>
                    <button type="button" onclick="selectTesterAgent('discovery')" id="btn-test-discovery" class="px-3 py-1.5 rounded-lg text-xs font-bold bg-cyan-600 text-white flex items-center gap-1.5 shadow-lg shadow-cyan-600/30">
                        <i class="fa-solid fa-phone-volume text-white"></i> Phone/Email DM &amp; Literature Bot
                    </button>
                    <button type="button" onclick="selectTesterAgent('exec_bot')" id="btn-test-exec" class="px-3 py-1.5 rounded-lg text-xs font-bold bg-slate-900 text-slate-400 hover:text-white flex items-center gap-1.5">
                        <i class="fa-solid fa-chess-king text-purple-400"></i> Executive Sales Bot
                    </button>
                    <button type="button" onclick="selectTesterAgent('lead_dev')" id="btn-test-dev" class="px-3 py-1.5 rounded-lg text-xs font-bold bg-slate-900 text-slate-400 hover:text-white flex items-center gap-1.5">
                        <i class="fa-solid fa-database text-indigo-400"></i> Lead Developer
                    </button>
                    <button type="button" onclick="selectTesterAgent('sdr')" id="btn-test-sdr" class="px-3 py-1.5 rounded-lg text-xs font-bold bg-slate-900 text-slate-400 hover:text-white flex items-center gap-1.5">
                        <i class="fa-solid fa-paper-plane text-emerald-400"></i> Cold Outreach SDR
                    </button>
                    <button type="button" onclick="selectTesterAgent('setter')" id="btn-test-setter" class="px-3 py-1.5 rounded-lg text-xs font-bold bg-slate-900 text-slate-400 hover:text-white flex items-center gap-1.5">
                        <i class="fa-solid fa-calendar-check text-pink-400"></i> Appointment Setter
                    </button>
                    <button type="button" onclick="selectTesterAgent('closer')" id="btn-test-closer" class="px-3 py-1.5 rounded-lg text-xs font-bold bg-slate-900 text-slate-400 hover:text-white flex items-center gap-1.5">
                        <i class="fa-solid fa-handshake-angle text-amber-400"></i> Objection Closer
                    </button>
                </div>

                <!-- Input Form -->
                <form id="tester-form" onsubmit="runInteractiveAgentDemo(event)" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    <div class="space-y-1.5">
                        <label class="text-xs font-bold uppercase text-slate-300 tracking-wider">Prospect Company</label>
                        <input id="demo-company" type="text" required value="Titanium Cloud Systems" placeholder="e.g. Acme Corp" class="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-xs text-white focus:border-indigo-500 outline-none">
                    </div>
                    <div class="space-y-1.5">
                        <label class="text-xs font-bold uppercase text-slate-300 tracking-wider">Prospect Industry</label>
                        <select id="demo-industry" class="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-xs text-white focus:border-indigo-500 outline-none">
                            <option value="Enterprise SaaS &amp; Cloud" selected>Enterprise SaaS &amp; Cloud</option>
                            <option value="Logistics &amp; Supply Chain">Logistics &amp; Supply Chain</option>
                            <option value="Industrial Manufacturing">Industrial Manufacturing</option>
                            <option value="Fintech &amp; Payments">Fintech &amp; Payments</option>
                        </select>
                    </div>
                    <div class="space-y-1.5">
                        <label class="text-xs font-bold uppercase text-slate-300 tracking-wider">Target Deal Value</label>
                        <select id="demo-value" class="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-xs text-white focus:border-indigo-500 outline-none">
                            <option value="45000">$45,000 / yr</option>
                            <option value="120000" selected>$120,000 / yr</option>
                            <option value="350000">$350,000 / yr</option>
                            <option value="1000000">$1,000,000 / yr</option>
                        </select>
                    </div>
                    <div class="space-y-1.5 flex flex-col justify-end">
                        <button type="submit" id="btn-tester-submit" class="w-full py-2.5 px-4 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-bold rounded-xl text-xs shadow-lg shadow-purple-600/30 transition flex items-center justify-center gap-2 cursor-pointer">
                            <i class="fa-solid fa-play"></i>
                            <span>Execute Agent Task</span>
                        </button>
                    </div>
                </form>

                <!-- Processing Spinner -->
                <div id="tester-loading" class="hidden text-center py-8 space-y-3">
                    <div class="h-10 w-10 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
                    <div class="text-xs font-mono text-purple-300" id="tester-loading-text">The Executive Sales Bot is analyzing buyer intent &amp; synthesizing closing dossier...</div>
                </div>

                <!-- Structured Agent Response Display -->
                <div id="tester-output" class="bg-slate-950/80 rounded-2xl p-6 border border-slate-800 space-y-4 font-sans text-xs">
                    <div class="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
                        <div class="flex items-center gap-2.5">
                            <span class="h-2.5 w-2.5 rounded-full bg-emerald-400"></span>
                            <span class="font-bold text-white text-sm" id="out-target-name">Titanium Cloud Systems</span>
                            <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-purple-950 text-purple-300 border border-purple-800" id="out-agent-badge">AGENT 4: EXECUTIVE SALES BOT</span>
                        </div>
                        <div class="flex items-center gap-3 font-mono text-[11px]">
                            <span class="text-slate-400">Buyer Intent: <strong class="text-emerald-400 font-bold" id="out-intent-score">96% HIGH INTENT</strong></span>
                            <span class="text-slate-400">Annual Contract Value: <strong class="text-white font-bold" id="out-acv">$120,000</strong></span>
                        </div>
                    </div>

                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div class="space-y-2">
                            <div class="font-bold text-slate-300 uppercase tracking-wider text-[10px] flex items-center gap-1.5">
                                <i class="fa-solid fa-bullseye text-indigo-400"></i> <span id="out-box-title-1">Executive Buyer Assessment</span>
                            </div>
                            <p class="text-slate-300 text-xs leading-relaxed" id="out-box-desc-1">
                                High-priority enterprise SaaS prospect experiencing rapid headcount growth. Current friction is manual rep prospecting and lack of automated calendar booking, leading to a 4-week sales cycle lag.
                            </p>
                        </div>
                        <div class="space-y-2">
                            <div class="font-bold text-slate-300 uppercase tracking-wider text-[10px] flex items-center gap-1.5">
                                <i class="fa-solid fa-chess-knight text-purple-400"></i> <span id="out-box-title-2">Recommended Closing Proposal</span>
                            </div>
                            <p class="text-slate-300 text-xs leading-relaxed" id="out-box-desc-2">
                                Propose Full 5-Agent Workforce tier with 20 included seats and SLA-guaranteed calendar appointment velocity. Package a 90-day pilot with dedicated integration engineering to displace legacy manual SDR tools.
                            </p>
                        </div>
                    </div>

                    <div class="p-3 bg-slate-900 rounded-xl border border-slate-800 flex items-center justify-between text-slate-400 text-[11px] font-mono">
                        <span>Autonomous Next Step: <strong class="text-emerald-400" id="out-next-step">Dispatch Calendar Setter &amp; Prepare Custom Contract Proposal</strong></span>
                        <span>Confidence: <strong>98.6%</strong></span>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- INBOUND PIPELINE NURTURE & WHITEPAPER DISPATCH -->
    <section id="inbound-demo" class="py-24 relative border-t border-slate-900 bg-slate-950/80">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-16">
            <div class="text-center space-y-4 max-w-3xl mx-auto">
                <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-950/60 text-cyan-300 border border-cyan-800/50 text-xs font-semibold">
                    <i class="fa-solid fa-bolt text-cyan-400"></i>
                    <span>Autonomous Inbound Lead Nurturing Sequence</span>
                </div>
                <h2 class="text-3xl sm:text-5xl font-black tracking-tight text-white">
                    Request an Architecture Briefing <br>
                    <span class="gradient-text">&amp; Download The 16-Page ROI Dossier</span>
                </h2>
                <p class="text-slate-400 text-sm sm:text-base">
                    Experience the autonomous pipeline first-hand. Ingest your organization into our 5-step cadence: receive an instant Welcome &amp; Whitepaper email, automated SMS routing confirmation, and personalized SDR benchmarks.
                </p>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start max-w-6xl mx-auto">
                <!-- Left: Form Card -->
                <div class="lg:col-span-6 glass-panel rounded-3xl p-6 sm:p-8 border border-slate-800 shadow-2xl space-y-6">
                    <div class="flex items-center gap-3 pb-4 border-b border-slate-800">
                        <div class="h-10 w-10 rounded-xl bg-cyan-600/20 text-cyan-400 flex items-center justify-center text-lg">
                            <i class="fa-solid fa-file-arrow-down"></i>
                        </div>
                        <div>
                            <h3 class="font-bold text-sm text-white">Inbound Lead Capture</h3>
                            <p class="text-xs text-slate-400">Instant auto-enrollment into 5-touchpoint cadence</p>
                        </div>
                    </div>

                    <form id="inbound-demo-form" onsubmit="submitInboundDemoCapture(event)" class="space-y-4">
                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div class="space-y-1.5">
                                <label class="text-xs font-bold uppercase text-slate-300 tracking-wider">Your Full Name *</label>
                                <input id="inbound-name" type="text" required placeholder="e.g. Marcus Vance" class="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-xs text-white focus:border-cyan-500 outline-none">
                            </div>
                            <div class="space-y-1.5">
                                <label class="text-xs font-bold uppercase text-slate-300 tracking-wider">Work Email *</label>
                                <input id="inbound-email" type="email" required placeholder="m.vance@company.com" class="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-xs text-white focus:border-cyan-500 outline-none">
                            </div>
                        </div>

                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div class="space-y-1.5">
                                <label class="text-xs font-bold uppercase text-slate-300 tracking-wider">Company Name *</label>
                                <input id="inbound-company" type="text" required placeholder="Acme Systems" class="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-xs text-white focus:border-cyan-500 outline-none">
                            </div>
                            <div class="space-y-1.5">
                                <label class="text-xs font-bold uppercase text-slate-300 tracking-wider">Direct Phone (for SMS / Voice)</label>
                                <input id="inbound-phone" type="tel" placeholder="+1 (555) 019-9832" class="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-xs text-white focus:border-cyan-500 outline-none">
                            </div>
                        </div>

                        <div class="space-y-1.5">
                            <label class="text-xs font-bold uppercase text-slate-300 tracking-wider">Industry Sector</label>
                            <select id="inbound-industry" class="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-xs text-white focus:border-cyan-500 outline-none">
                                <option value="Enterprise SaaS & Cloud" selected>Enterprise SaaS &amp; Cloud</option>
                                <option value="Supply Chain & Logistics">Supply Chain &amp; Logistics</option>
                                <option value="Industrial & Warehousing">Industrial &amp; Warehousing</option>
                                <option value="Fintech & Banking">Fintech &amp; Banking</option>
                                <option value="Healthcare & Bio">Healthcare &amp; Bio</option>
                            </select>
                        </div>

                        <button type="submit" id="btn-inbound-submit" class="w-full py-3 px-4 bg-gradient-to-r from-cyan-600 via-indigo-600 to-purple-600 hover:from-cyan-500 hover:to-purple-500 text-white font-bold rounded-xl text-xs shadow-lg shadow-cyan-600/30 transition flex items-center justify-center gap-2 cursor-pointer">
                            <i class="fa-solid fa-paper-plane"></i>
                            <span>Download Whitepaper &amp; Enroll in Cadence</span>
                        </button>
                    </form>

                    <!-- Realtime Result Box -->
                    <div id="inbound-result-box" class="hidden"></div>
                </div>

                <!-- Right: 5-Step Visual Cadence Timeline -->
                <div class="lg:col-span-6 space-y-4">
                    <div class="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                        <i class="fa-solid fa-clock-rotate-left text-cyan-400"></i>
                        <span>Autonomous 5-Step Inbound Cadence Roadmap</span>
                    </div>

                    <div class="space-y-3 font-sans">
                        <!-- Step 1 -->
                        <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 flex items-start gap-3.5 hover:border-cyan-500/40 transition">
                            <div class="h-8 w-8 rounded-lg bg-indigo-600/20 text-indigo-400 font-mono font-bold flex items-center justify-center text-xs shrink-0">1</div>
                            <div class="space-y-1">
                                <div class="flex items-center justify-between">
                                    <h4 class="font-bold text-xs text-white">Instant Welcome &amp; 16-Page ROI Whitepaper</h4>
                                    <span class="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800/40">Minute 0 • Email</span>
                                </div>
                                <p class="text-[11px] text-slate-400 leading-relaxed">
                                    Dispatches branded executive briefing PDF and dynamic ROI analysis via SendGrid immediately upon ingestion.
                                </p>
                            </div>
                        </div>

                        <!-- Step 2 -->
                        <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 flex items-start gap-3.5 hover:border-cyan-500/40 transition">
                            <div class="h-8 w-8 rounded-lg bg-cyan-600/20 text-cyan-400 font-mono font-bold flex items-center justify-center text-xs shrink-0">2</div>
                            <div class="space-y-1">
                                <div class="flex items-center justify-between">
                                    <h4 class="font-bold text-xs text-white">Postal Routing &amp; SMS Confirmation</h4>
                                    <span class="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800/40">Hour 2 • Twilio SMS</span>
                                </div>
                                <p class="text-[11px] text-slate-400 leading-relaxed">
                                    Mobile notification confirming physical literature dispatch and personalized calendar demo link.
                                </p>
                            </div>
                        </div>

                        <!-- Step 3 -->
                        <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 flex items-start gap-3.5 hover:border-cyan-500/40 transition">
                            <div class="h-8 w-8 rounded-lg bg-emerald-600/20 text-emerald-400 font-mono font-bold flex items-center justify-center text-xs shrink-0">3</div>
                            <div class="space-y-1">
                                <div class="flex items-center justify-between">
                                    <h4 class="font-bold text-xs text-white">SDR Tailored Industry Insights</h4>
                                    <span class="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800/40">Day 1 • 1-to-1 Email</span>
                                </div>
                                <p class="text-[11px] text-slate-400 leading-relaxed">
                                    1-to-1 SDR custom analysis with sector efficiency benchmarks and appointment booking prompt.
                                </p>
                            </div>
                        </div>

                        <!-- Step 4 -->
                        <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 flex items-start gap-3.5 hover:border-cyan-500/40 transition">
                            <div class="h-8 w-8 rounded-lg bg-purple-600/20 text-purple-400 font-mono font-bold flex items-center justify-center text-xs shrink-0">4</div>
                            <div class="space-y-1">
                                <div class="flex items-center justify-between">
                                    <h4 class="font-bold text-xs text-white">Decision-Maker Voice AI / Lob Postcard</h4>
                                    <span class="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-950 text-purple-300 border border-purple-800/40">Day 3 • Voice &amp; Postal</span>
                                </div>
                                <p class="text-[11px] text-slate-400 leading-relaxed">
                                    Autonomous switchboard Voice AI consultation or priority USPS 22-digit IMb tracked glossy postcard.
                                </p>
                            </div>
                        </div>

                        <!-- Step 5 -->
                        <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 flex items-start gap-3.5 hover:border-cyan-500/40 transition">
                            <div class="h-8 w-8 rounded-lg bg-pink-600/20 text-pink-400 font-mono font-bold flex items-center justify-center text-xs shrink-0">5</div>
                            <div class="space-y-1">
                                <div class="flex items-center justify-between">
                                    <h4 class="font-bold text-xs text-white">Senior Executive Sales Bot Consultation</h4>
                                    <span class="text-[10px] font-mono px-2 py-0.5 rounded bg-pink-950 text-pink-300 border border-pink-800/40">Day 6 • Executive Close</span>
                                </div>
                                <p class="text-[11px] text-slate-400 leading-relaxed">
                                    Custom commercial proposal, enterprise tier reservation, and direct CTO office meeting invitation.
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- INTERACTIVE 6-BOT STACK CONFIGURATOR -->
    <section id="stack-configurator" class="py-24 relative border-t border-slate-900 bg-slate-950/60">
        <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 space-y-12">
            <div class="text-center space-y-4 max-w-3xl mx-auto">
                <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-950/60 text-emerald-300 border border-emerald-800/50 text-xs font-semibold">
                    <i class="fa-solid fa-sliders text-emerald-400"></i>
                    <span>Interactive Stack Builder</span>
                </div>
                <h2 class="text-3xl sm:text-5xl font-black tracking-tight text-white">
                    Build Your Custom AI Sales Stack <br>
                    <span class="gradient-text">&amp; Project Monthly Revenue Added</span>
                </h2>
                <p class="text-slate-400 text-sm sm:text-base">
                    Select which of the 6 AI Sales Bots you want on your team. Watch your pipeline projections update live.
                </p>
            </div>

            <div class="glass-panel rounded-3xl p-8 border border-slate-800 shadow-2xl space-y-8">
                <!-- Agent Checklist -->
                <div class="space-y-3">
                    <label class="flex items-center justify-between p-4 bg-slate-900/80 hover:bg-slate-900 rounded-2xl border border-slate-800 cursor-pointer transition">
                        <div class="flex items-center gap-3">
                            <input type="checkbox" id="chk-dev" checked onchange="recalculateStack()" class="w-4 h-4 accent-indigo-500 rounded">
                            <div>
                                <div class="font-bold text-sm text-white flex items-center gap-2">
                                    <span>1. The Lead Developer</span>
                                    <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-indigo-950 text-indigo-300">DATA ENRICHMENT</span>
                                </div>
                                <div class="text-xs text-slate-400">Scrapes, verifies, and enriches 1,000+ target ICP accounts monthly</div>
                            </div>
                        </div>
                        <span class="text-xs font-mono font-bold text-emerald-400">+1,000 Accounts</span>
                    </label>

                    <label class="flex items-center justify-between p-4 bg-slate-900/80 hover:bg-slate-900 rounded-2xl border border-slate-800 cursor-pointer transition">
                        <div class="flex items-center gap-3">
                            <input type="checkbox" id="chk-discovery" checked onchange="recalculateStack()" class="w-4 h-4 accent-cyan-500 rounded">
                            <div>
                                <div class="font-bold text-sm text-white flex items-center gap-2">
                                    <span>2. Decision-Maker &amp; Literature Bot</span>
                                    <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-cyan-950 text-cyan-300">DM DISCOVERY &amp; LITERATURE</span>
                                </div>
                                <div class="text-xs text-slate-400">Calls &amp; emails switchboard to uncover DM, pitch value, and email/mail marketing collateral</div>
                            </div>
                        </div>
                        <span class="text-xs font-mono font-bold text-cyan-400">+74% DM Opt-in</span>
                    </label>

                    <label class="flex items-center justify-between p-4 bg-slate-900/80 hover:bg-slate-900 rounded-2xl border border-slate-800 cursor-pointer transition">
                        <div class="flex items-center gap-3">
                            <input type="checkbox" id="chk-sdr" checked onchange="recalculateStack()" class="w-4 h-4 accent-emerald-500 rounded">
                            <div>
                                <div class="font-bold text-sm text-white flex items-center gap-2">
                                    <span>3. The Cold Outreach SDR</span>
                                    <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-950 text-emerald-300">OUTBOUND CADENCE</span>
                                </div>
                                <div class="text-xs text-slate-400">Delivers personalized multi-channel cold sequences across Email &amp; LinkedIn</div>
                            </div>
                        </div>
                        <span class="text-xs font-mono font-bold text-emerald-400">+28% Reply Rate</span>
                    </label>

                    <label class="flex items-center justify-between p-4 bg-slate-900/80 hover:bg-slate-900 rounded-2xl border border-slate-800 cursor-pointer transition">
                        <div class="flex items-center gap-3">
                            <input type="checkbox" id="chk-setter" checked onchange="recalculateStack()" class="w-4 h-4 accent-pink-500 rounded">
                            <div>
                                <div class="font-bold text-sm text-white flex items-center gap-2">
                                    <span>4. The Appointment Setter</span>
                                    <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-pink-950 text-pink-300">MEETING BOOKER</span>
                                </div>
                                <div class="text-xs text-slate-400">Conversational 2-way booking directly onto rep Google/Outlook calendars</div>
                            </div>
                        </div>
                        <span class="text-xs font-mono font-bold text-pink-400">+35 Confirmed Demos</span>
                    </label>

                    <label class="flex items-center justify-between p-4 bg-slate-900/80 hover:bg-slate-900 rounded-2xl border border-slate-800 cursor-pointer transition">
                        <div class="flex items-center gap-3">
                            <input type="checkbox" id="chk-exec" checked onchange="recalculateStack()" class="w-4 h-4 accent-purple-500 rounded">
                            <div>
                                <div class="font-bold text-sm text-white flex items-center gap-2">
                                    <span>5. The Executive Sales Bot</span>
                                    <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-purple-950 text-purple-300">DEAL STRATEGIST</span>
                                </div>
                                <div class="text-xs text-slate-400">Synthesizes executive dossiers, custom proposals, and enterprise closing angles</div>
                            </div>
                        </div>
                        <span class="text-xs font-mono font-bold text-purple-400">+8 Enterprise Wins</span>
                    </label>

                    <label class="flex items-center justify-between p-4 bg-slate-900/80 hover:bg-slate-900 rounded-2xl border border-slate-800 cursor-pointer transition">
                        <div class="flex items-center gap-3">
                            <input type="checkbox" id="chk-closer" checked onchange="recalculateStack()" class="w-4 h-4 accent-amber-500 rounded">
                            <div>
                                <div class="font-bold text-sm text-white flex items-center gap-2">
                                    <span>6. The Objection Closer &amp; Expansion Bot</span>
                                    <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-amber-950 text-amber-300">OBJECTION HANDLING</span>
                                </div>
                                <div class="text-xs text-slate-400">Recovers stalled contract negotiations and drives renewal expansion</div>
                            </div>
                        </div>
                        <span class="text-xs font-mono font-bold text-amber-400">+35% Stalled Deals Won</span>
                    </label>
                </div>

                <!-- Live Calculated Totals -->
                <div class="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t border-slate-800 text-center">
                    <div class="p-4 bg-slate-900/90 rounded-2xl border border-slate-800">
                        <div class="text-slate-400 text-[10px] uppercase font-bold">Active Agents</div>
                        <div class="text-2xl font-black font-mono text-indigo-400" id="stack-count">6 Agents</div>
                    </div>
                    <div class="p-4 bg-slate-900/90 rounded-2xl border border-slate-800">
                        <div class="text-slate-400 text-[10px] uppercase font-bold">Monthly Demos</div>
                        <div class="text-2xl font-black font-mono text-pink-400" id="stack-demos">60 Demos</div>
                    </div>
                    <div class="p-4 bg-slate-900/90 rounded-2xl border border-slate-800">
                        <div class="text-slate-400 text-[10px] uppercase font-bold">Deals Closed</div>
                        <div class="text-2xl font-black font-mono text-purple-400" id="stack-deals">22 Closed</div>
                    </div>
                    <div class="p-4 bg-slate-900/90 rounded-2xl border border-slate-800">
                        <div class="text-slate-400 text-[10px] uppercase font-bold">Projected Pipeline</div>
                        <div class="text-2xl font-black font-mono text-emerald-400" id="stack-pipeline">$264,000 / mo</div>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- PRICING TIERS SECTION FOR SAAS CLIENTS -->
    <section id="pricing" class="py-24 relative border-t border-slate-900 bg-slate-950/70">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-16">
            <div class="text-center space-y-4 max-w-3xl mx-auto">
                <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-pink-950/60 text-pink-300 border border-pink-800/50 text-xs font-semibold">
                    <i class="fa-solid fa-credit-card text-pink-400"></i>
                    <span>SaaS Client Deployment Plans</span>
                </div>
                <h2 class="text-3xl sm:text-5xl font-black tracking-tight text-white">
                    Transparent Plans to Deploy <br>
                    <span class="gradient-text">Your AI Sales Workforce</span>
                </h2>
                <p class="text-slate-400 text-sm sm:text-base">
                    From single-bot appointment setting to an entire 6-agent autonomous enterprise workforce.
                </p>
            </div>

            <!-- Pricing Grid -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <!-- Starter SDR Tier -->
                <div class="glass-panel rounded-3xl p-6 border border-slate-800 flex flex-col justify-between space-y-6 hover:border-slate-700 transition">
                    <div class="space-y-4">
                        <div class="space-y-1">
                            <span class="text-xs font-mono font-bold text-slate-400 uppercase">Starter SDR</span>
                            <div class="flex items-baseline gap-1">
                                <span class="text-4xl font-black text-white">$199</span>
                                <span class="text-xs text-slate-400">/ month</span>
                            </div>
                        </div>
                        <p class="text-xs text-slate-400">Deploy 1 AI Sales Agent (e.g. Appointment Setter or Lead Developer).</p>
                        <div class="border-t border-slate-800 pt-4 space-y-2.5 text-xs text-slate-300">
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> 1 AI Sales Agent Deployed</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> 1,000 Pipeline Touches/mo</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> Google &amp; Outlook Calendar Sync</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> 2 Seats Included</div>
                            <div class="flex items-center gap-2 text-slate-500"><i class="fa-solid fa-xmark text-slate-600 text-[10px]"></i> Executive Sales Bot &amp; Closer</div>
                        </div>
                    </div>
                    <a href="{signup_url}?plan=starter" class="w-full py-2.5 px-4 rounded-xl text-xs font-bold text-slate-200 bg-slate-900 hover:bg-slate-800 border border-slate-700 transition text-center block">
                        Get Started
                    </a>
                </div>

                <!-- Growth Sales Team Tier -->
                <div class="glass-panel rounded-3xl p-6 border border-slate-800 flex flex-col justify-between space-y-6 hover:border-indigo-500/60 transition">
                    <div class="space-y-4">
                        <div class="space-y-1">
                            <span class="text-xs font-mono font-bold text-indigo-400 uppercase">Growth Team</span>
                            <div class="flex items-baseline gap-1">
                                <span class="text-4xl font-black text-white">$499</span>
                                <span class="text-xs text-slate-400">/ month</span>
                            </div>
                        </div>
                        <p class="text-xs text-slate-400">Deploy 3 AI Sales Agents (e.g. Lead Developer + Decision-Maker Bot + Appointment Setter).</p>
                        <div class="border-t border-slate-800 pt-4 space-y-2.5 text-xs text-slate-300">
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> 3 AI Sales Agents Deployed</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> 5,000 Pipeline Touches/mo</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> Multi-Channel Voice, Email &amp; LinkedIn</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> 5 Seats Included</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> Automated Follow-Up Sequences</div>
                        </div>
                    </div>
                    <a href="{signup_url}?plan=growth" class="w-full py-2.5 px-4 rounded-xl text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-500 shadow-md shadow-indigo-600/30 transition text-center block">
                        Start Free Trial
                    </a>
                </div>

                <!-- Full Executive Workforce Tier (Highlighted) -->
                <div class="glass-panel rounded-3xl p-6 border-2 border-indigo-500 flex flex-col justify-between space-y-6 glow-indigo relative">
                    <div class="absolute -top-3.5 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-bold text-[10px] tracking-wider uppercase shadow-lg">
                        Full 6-Agent Suite
                    </div>
                    <div class="space-y-4 pt-1">
                        <div class="space-y-1">
                            <span class="text-xs font-mono font-bold text-indigo-300 uppercase">Executive Workforce</span>
                            <div class="flex items-baseline gap-1">
                                <span class="text-4xl font-black text-white">$1,499</span>
                                <span class="text-xs text-slate-400">/ month</span>
                            </div>
                        </div>
                        <p class="text-xs text-slate-300">All 6 AI Sales Bots deployed with decision-maker phone/email discovery, executive proposal generation, and objection closing.</p>
                        <div class="border-t border-slate-800 pt-4 space-y-2.5 text-xs text-slate-200">
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> All 6 AI Sales Bots Included</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> 25,000 Pipeline Touches/mo</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> Decision-Maker &amp; Literature Dispatch Included</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> The Executive Sales Bot Included</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> 20 Seats + Custom Domain</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400 text-[10px]"></i> Dedicated HITL Takeover Queue</div>
                        </div>
                    </div>
                    <a href="{signup_url}?plan=executive" class="w-full py-2.5 px-4 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 hover:from-indigo-500 hover:to-pink-500 shadow-lg shadow-indigo-600/40 transition text-center block">
                        Deploy All 6 Agents
                    </a>
                </div>

                <!-- Custom Scale Tier -->
                <div class="glass-panel rounded-3xl p-6 border border-slate-800 flex flex-col justify-between space-y-6 hover:border-purple-500/60 transition">
                    <div class="space-y-4">
                        <div class="space-y-1">
                            <span class="text-xs font-mono font-bold text-purple-400 uppercase">Custom &amp; Scale</span>
                            <div class="flex items-baseline gap-1">
                                <span class="text-3xl font-black text-white">Custom</span>
                            </div>
                        </div>
                        <p class="text-xs text-slate-400">Unlimited custom agents fine-tuned on your sales recordings &amp; enterprise playbooks.</p>
                        <div class="border-t border-slate-800 pt-4 space-y-2.5 text-xs text-slate-300">
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-purple-400 text-[10px]"></i> Custom Fine-Tuned LLMs</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-purple-400 text-[10px]"></i> Unlimited Seats &amp; Pipelines</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-purple-400 text-[10px]"></i> Bespoke CRM/ERP Bi-Directional Sync</div>
                            <div class="flex items-center gap-2"><i class="fa-solid fa-check text-purple-400 text-[10px]"></i> Dedicated Sales Engineer &amp; SLA</div>
                        </div>
                    </div>
                    <a href="{signup_url}?plan=executive" class="w-full py-2.5 px-4 rounded-xl text-xs font-bold text-purple-200 bg-purple-950/60 hover:bg-purple-900 border border-purple-800 transition text-center block">
                        Talk to Enterprise Sales
                    </a>
                </div>
            </div>

            <!-- Metered Overage Rates Explainer -->
            <div class="glass-panel rounded-2xl p-6 border border-slate-800 max-w-4xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-6">
                <div class="flex items-center gap-4">
                    <div class="h-12 w-12 rounded-xl bg-emerald-600/20 text-emerald-400 flex items-center justify-center text-xl shrink-0">
                        <i class="fa-solid fa-gauge-high"></i>
                    </div>
                    <div>
                        <div class="font-bold text-sm text-white">Automated Metered Overage Protection</div>
                        <p class="text-xs text-slate-400">Scale without artificial limits. Transparent rates apply automatically when your monthly baseline quota is exceeded:</p>
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
                    <span class="text-slate-500">| Autonomous AI Sales Agents for SaaS</span>
                </div>
                <div class="flex items-center gap-6 text-xs">
                    <a href="{console_url}" class="hover:text-white transition">Launch Console</a>
                    <a href="#agents" class="hover:text-white transition">6 Sales Bots</a>
                    <a href="#pipeline" class="hover:text-white transition">Pipeline Funnel</a>
                    <a href="#pricing" class="hover:text-white transition">Pricing Plans</a>
                    <a href="{prefix}/docs" target="_blank" class="hover:text-white transition flex items-center gap-1">
                        <i class="fa-solid fa-code"></i> OpenAPI Docs
                    </a>
                </div>
            </div>
            <div class="flex flex-wrap items-center justify-between gap-4 text-slate-500 text-[11px]">
                <p>&copy; 2026 NexFlow AI Technologies Inc. All rights reserved. The Autonomous Sales Workforce for SaaS.</p>
                <div class="flex items-center gap-4">
                    <span class="flex items-center gap-1.5"><i class="fa-solid fa-shield-halved text-emerald-400"></i> Multi-Tenant Isolated</span>
                    <span class="flex items-center gap-1.5"><i class="fa-solid fa-lock text-indigo-400"></i> SOC-2 Compliant Stack</span>
                    <span class="flex items-center gap-1.5"><i class="fa-solid fa-credit-card text-purple-400"></i> Stripe Verified Billing</span>
                </div>
            </div>
        </div>
    </footer>

    <!-- INTERACTIVE SCRIPTS -->
    <script>
        const API_PREFIX = "{prefix}";
        const LEAD_API_URL = "{lead_api_url}";

        // The 6 AI Sales Bots Data Matrix
        const SALES_AGENTS = {{
            lead_dev: {{
                id: "lead_dev",
                number: "1",
                name: "The Lead Developer Agent",
                subtitle: "Inbound Prospector & Account Enrichment Engine",
                icon: "fa-database",
                color: "indigo",
                description: "Scours incoming web visitors, LinkedIn company profiles, job board signals, and firmographic databases. Validates contact email addresses, checks software tech stack fit, and scores buyer intent before handing off to the outreach team.",
                skills: [
                    "B2B Firmographic & Technographic Enrichment",
                    "Real-Time Buyer Intent Signal Detection",
                    "Automated Email & Phone Verification",
                    "Custom Ideal Customer Profile (ICP) Scoring"
                ],
                sampleInput: `{{"target_domain": "titaniumcloud.example", "ideal_titles": ["VP Sales", "CRO"], "signal": "Hiring 5 Account Execs"}}`,
                sampleOutput: `{{"status": "enriched", "verified_leads": 3, "primary_contact": "Marcus Vance (CRO)", "intent_score": 96}}`,
                impactMetric: "1,000+ Verified Accounts/Day",
                badge: "LEAD DEVELOPMENT"
            }},
            discovery: {{
                id: "discovery",
                number: "2",
                name: "The Decision-Maker Pathfinder & Literature Bot",
                subtitle: "Phone & Email Switchboard Navigator & Collateral Dispatcher",
                icon: "fa-phone-volume",
                color: "cyan",
                description: "Autonomously contacts target companies via conversational voice AI phone calls and exploratory emails to navigate past switchboards and gatekeepers to discover the true decision-maker. Once connected, speaks with them directly, introduces high-impact SaaS value, and secures opt-in consent to email digital whitepapers or postal mail executive briefing literature to warm up and set up the sale for downstream closers.",
                skills: [
                    "Voice AI Switchboard & Gatekeeper Phone Navigation",
                    "Exploratory Front-Desk Email Discovery Sequences",
                    "Direct Decision-Maker Voice & Email Connection",
                    "Digital Whitepaper & Physical Postal Collateral Dispatch",
                    "Warm Pipeline Staging for Downstream Closers"
                ],
                sampleInput: `{{"target_company": "Titanium Cloud Systems", "switchboard_phone": "+1-800-555-0199", "inquiry_target": "Discover VP Procurement & Head of Architecture"}}`,
                sampleOutput: `{{"status": "decision_maker_connected", "decision_maker": "Sarah Jenkins (VP Cloud Architecture)", "contact_channels": "Voice Switchboard AI + Direct Email", "literature_dispatched": ["Architecture Benchmark Whitepaper (Email PDF)", "Executive Briefing Packet (Postal Mail)"], "sale_readiness": "warm_staged"}}`,
                impactMetric: "74% Switchboard to DM Conversion",
                badge: "DM & LITERATURE BOT"
            }},
            setter: {{
                id: "setter",
                number: "3",
                name: "The Appointment Setter Agent",
                subtitle: "2-Way Conversational Calendar Booking Engine",
                icon: "fa-calendar-check",
                color: "pink",
                description: "Converses via Email, LinkedIn, and SMS with qualified prospects to secure demos directly on your sales reps' Google or Outlook calendars. Handles time zones, qualification questions, and automated reminder sequences to slash no-shows.",
                skills: [
                    "2-Way Conversational Meeting Scheduling",
                    "Timezone Normalization & Rescheduling",
                    "Qualification Criteria Gating",
                    "No-Show Reduction & Warm-Up Sequences"
                ],
                sampleInput: `{{"prospect_reply": "I'm interested, but travelling until Thursday afternoon. What's open?"}}`,
                sampleOutput: `{{"action": "propose_slots", "suggested": ["Friday 10:00 AM EDT", "Friday 2:00 PM EDT"], "calendar_link": "sent"}}`,
                impactMetric: "48 Qualified Demos Booked / Mo Avg",
                badge: "APPOINTMENT SETTER"
            }},
            sdr: {{
                id: "sdr",
                number: "4",
                name: "The Cold Outreach SDR Agent",
                subtitle: "Hyper-Personalized Multi-Channel Outbound Generator",
                icon: "fa-paper-plane",
                color: "emerald",
                description: "Researches each prospect company individually to craft 1-to-1 personalized cold email and LinkedIn sequences. Never sends generic templates. Dynamically references company news, mutual connections, and verified pain points.",
                skills: [
                    "1-to-1 Dynamic Personalization Engine",
                    "Multi-Channel Cadence (Email + LinkedIn + SMS)",
                    "A/B Testing Subject Lines & CTAs",
                    "Sentiment Reply Categorization & Routing"
                ],
                sampleInput: `{{"prospect_name": "Sarah Jenkins", "company": "Apex Supply", "event": "Raised Series B $25M"}}`,
                sampleOutput: `{{"subject": "Scaling Apex's sales reps post-Series B", "touch_1_personalized": "true", "sent_status": "delivered"}}`,
                impactMetric: "28% Verified Cold Reply Rate",
                badge: "COLD OUTREACH SDR"
            }},
            exec_bot: {{
                id: "exec_bot",
                number: "5",
                name: "The Executive Sales Bot",
                subtitle: "Senior Deal Strategist & Executive Closing Architect",
                icon: "fa-chess-king",
                color: "purple",
                description: "Your autonomous VP of Enterprise Sales. Synthesizes comprehensive executive deal closing dossiers, drafts bespoke commercial proposals, maps multi-stakeholder buyer committees, and formulates ROI business cases to win 5-figure and 6-figure SaaS deals.",
                skills: [
                    "Executive Closing Dossier Synthesis",
                    "Bespoke Commercial Proposal Drafting",
                    "Multi-Stakeholder Champion Mapping",
                    "ROI Business Case Financial Modeling"
                ],
                sampleInput: `{{"client": "Pacific Lumber Co.", "budget": "$120,000", "stakeholders": ["CFO", "VP Supply Chain"]}}`,
                sampleOutput: `{{"dossier_status": "synthesized", "recommended_tier": "Executive Workforce", "closing_strategy": "SLA-backed restock pilot"}}`,
                impactMetric: "+38% Enterprise Win Rate",
                badge: "EXECUTIVE SALES BOT"
            }},
            closer: {{
                id: "closer",
                number: "6",
                name: "The Objection Closer & Expansion Bot",
                subtitle: "Negotiation Safeguards & Customer Expansion Engine",
                icon: "fa-handshake-angle",
                color: "amber",
                description: "Safeguards stalled deals during contract review and drives account expansion post-sale. Counters pricing, security, and timing hesitations with pre-approved concession packages, and uncovers high-margin upsell opportunities.",
                skills: [
                    "Contextual Pricing Objection Reframing",
                    "Contract Review & Concession Packaging",
                    "Automated License Expansion Triggers",
                    "Human Rep Escalation for High-Stakes Terms"
                ],
                sampleInput: `{{"objection": "Your quote is 20% higher than competitor X", "margin_floor": "15%"}}`,
                sampleOutput: `{{"rebuttal_strategy": "Highlight automated replenishment SLA + offer quarterly billing concession", "status": "counter_sent"}}`,
                impactMetric: "35% Stalled Deals Won",
                badge: "OBJECTION CLOSER"
            }}
        }};

        function switchAgentTab(key) {{
            const agent = SALES_AGENTS[key];
            if (!agent) return;

            // Highlight Tab Buttons
            const tabs = ['lead_dev', 'discovery', 'setter', 'sdr', 'exec_bot', 'closer'];
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

            // Render Focused Agent Viewport
            const container = document.getElementById("agent-detail-container");
            container.innerHTML = `
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-8 items-center">
                    <div class="space-y-5">
                        <div class="flex items-center gap-3">
                            <div class="h-12 w-12 rounded-2xl bg-${{agent.color}}-600/20 text-${{agent.color}}-400 flex items-center justify-center text-xl shadow-lg">
                                <i class="fa-solid ${{agent.icon}}"></i>
                            </div>
                            <div>
                                <div class="flex items-center gap-2">
                                    <h3 class="font-extrabold text-xl text-white">${{agent.name}}</h3>
                                    <span class="px-2 py-0.5 rounded text-[9px] font-mono font-bold bg-${{agent.color}}-950 text-${{agent.color}}-300 border border-${{agent.color}}-800/60">${{agent.badge}}</span>
                                </div>
                                <span class="text-xs font-mono font-semibold text-${{agent.color}}-400">${{agent.subtitle}}</span>
                            </div>
                        </div>

                        <p class="text-sm text-slate-300 leading-relaxed">${{agent.description}}</p>

                        <div class="space-y-2">
                            <span class="text-xs font-bold uppercase tracking-wider text-slate-400">Autonomous Sales Skills:</span>
                            <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-slate-200">
                                ${{agent.skills.map(s => `
                                    <div class="flex items-center gap-2">
                                        <i class="fa-solid fa-circle-check text-emerald-400 text-xs"></i>
                                        <span>${{s}}</span>
                                    </div>
                                `).join('')}}
                            </div>
                        </div>

                        <div class="pt-2 flex items-center gap-4">
                            <span class="px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs font-mono text-emerald-400 font-bold">
                                Performance: ${{agent.impactMetric}}
                            </span>
                            <a href="#interactive-tester" onclick="selectTesterAgent('${{agent.id}}')" class="text-xs text-indigo-400 hover:text-indigo-300 font-semibold flex items-center gap-1">
                                Test Drive in Live Demo <i class="fa-solid fa-arrow-right text-[10px]"></i>
                            </a>
                        </div>
                    </div>

                    <!-- Live Telemetry Simulation View -->
                    <div class="bg-slate-950/90 rounded-2xl p-5 border border-slate-800 font-mono text-xs space-y-3 shadow-xl">
                        <div class="flex items-center justify-between pb-2 border-b border-slate-800">
                            <span class="text-[11px] text-slate-400 uppercase tracking-wider">Live Agent Telemetry Feed</span>
                            <span class="text-emerald-400 text-[10px] font-bold flex items-center gap-1">
                                <span class="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"></span> ACTIVE SESSION
                            </span>
                        </div>

                        <div class="space-y-1">
                            <span class="text-[10px] text-slate-500 uppercase">Input Payload / Trigger:</span>
                            <pre class="bg-slate-900 p-2.5 rounded-lg text-slate-300 overflow-x-auto text-[11px]">${{agent.sampleInput}}</pre>
                        </div>

                        <div class="space-y-1">
                            <span class="text-[10px] text-slate-500 uppercase">Agent Autonomous Execution:</span>
                            <pre class="bg-${{agent.color}}-950/40 border border-${{agent.color}}-800/50 p-2.5 rounded-lg text-${{agent.color}}-200 overflow-x-auto text-[11px]">${{agent.sampleOutput}}</pre>
                        </div>
                    </div>
                </div>
            `;
        }}

        // Tester Agent Selector
        let currentTesterAgent = "discovery";
        function selectTesterAgent(agentId) {{
            currentTesterAgent = agentId;
            const btns = {{
                discovery: document.getElementById("btn-test-discovery"),
                exec_bot: document.getElementById("btn-test-exec"),
                lead_dev: document.getElementById("btn-test-dev"),
                sdr: document.getElementById("btn-test-sdr"),
                setter: document.getElementById("btn-test-setter"),
                closer: document.getElementById("btn-test-closer")
            }};
            const activeColors = {{
                discovery: "bg-cyan-600 shadow-cyan-600/30",
                exec_bot: "bg-purple-600 shadow-purple-600/30",
                lead_dev: "bg-indigo-600 shadow-indigo-600/30",
                sdr: "bg-emerald-600 shadow-emerald-600/30",
                setter: "bg-pink-600 shadow-pink-600/30",
                closer: "bg-amber-600 shadow-amber-600/30"
            }};
            Object.keys(btns).forEach(k => {{
                if (btns[k]) {{
                    if (k === agentId) {{
                        btns[k].className = `px-3 py-1.5 rounded-lg text-xs font-bold text-white flex items-center gap-1.5 shadow-lg ${{activeColors[k] || 'bg-indigo-600'}}`;
                    }} else {{
                        btns[k].className = "px-3 py-1.5 rounded-lg text-xs font-bold bg-slate-900 text-slate-400 hover:text-white flex items-center gap-1.5";
                    }}
                }}
            }});

            const descText = {{
                discovery: "The Decision-Maker Pathfinder & Literature Bot is calling/emailing switchboard & dispatching collateral...",
                exec_bot: "The Executive Sales Bot is analyzing buyer intent & synthesizing closing dossier...",
                lead_dev: "The Lead Developer is scraping domain firmographics and scoring buyer readiness...",
                sdr: "The Cold Outreach SDR is generating hyper-personalized 1-to-1 multi-channel cadences...",
                setter: "The Appointment Setter is negotiating calendar slots and formatting demo invite...",
                closer: "The Objection Closer is analyzing pricing friction and packaging contract concessions..."
            }};
            document.getElementById("tester-loading-text").innerText = descText[agentId] || descText.discovery;
        }}

        // Run Interactive Agent Demo
        async function runInteractiveAgentDemo(e) {{
            e.preventDefault();
            const comp = document.getElementById("demo-company").value;
            const ind = document.getElementById("demo-industry").value;
            const val = document.getElementById("demo-value").value;

            document.getElementById("btn-tester-submit").disabled = true;
            document.getElementById("tester-output").classList.add("hidden");
            document.getElementById("tester-loading").classList.remove("hidden");

            // Background submission to CRM Leads if available
            try {{
                await fetch(LEAD_API_URL, {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{
                        name: `Exec Lead for ${{comp}}`,
                        email: `contact@${{comp.toLowerCase().replace(/[^a-z0-9]/g, '')}}.example`,
                        company: comp,
                        deal_size: parseFloat(val),
                        notes: `Inbound prospect via interactive landing page tester for ${{ind}} sector.`
                    }})
                }});
            }} catch (err) {{
                // Silent fallback for unauthenticated public visitors
            }}

            // Auto-enroll in Inbound Lead Nurturing Sequence
            try {{
                await fetch(API_PREFIX + "/api/v1/nurture/inbound-capture", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{
                        name: `Exec Lead for ${{comp}}`,
                        email: `contact@${{comp.toLowerCase().replace(/[^a-z0-9]/g, '')}}.example.com`,
                        company_name: comp,
                        source: "interactive_agent_tester",
                        industry: ind,
                        custom_notes: `Tested ${{currentTesterAgent}} agent with target deal value $${{val}}.`
                    }})
                }});
            }} catch (err) {{
                // Non-blocking
            }}

            setTimeout(() => {{
                document.getElementById("tester-loading").classList.add("hidden");
                document.getElementById("tester-output").classList.remove("hidden");
                document.getElementById("btn-tester-submit").disabled = false;

                document.getElementById("out-target-name").innerText = comp;
                document.getElementById("out-acv").innerText = "$" + Number(val).toLocaleString();

                if (currentTesterAgent === "discovery") {{
                    document.getElementById("out-agent-badge").innerText = "AGENT 2: DECISION-MAKER & LITERATURE BOT";
                    document.getElementById("out-box-title-1").innerText = "Phone & Email Switchboard Discovery";
                    document.getElementById("out-box-desc-1").innerText = 
                        `Autonomous Voice AI phoned ${{comp}} switchboard & sent discovery inquiry to front office. Navigated past gatekeeper and connected directly with Sarah Jenkins (VP Cloud Architecture).`;
                    document.getElementById("out-box-title-2").innerText = "Marketing Literature Dispatched";
                    document.getElementById("out-box-desc-2").innerText = 
                        `Secured permission during phone call. Dispatched digital architecture blueprint via tracked email and scheduled physical executive briefing folder via courier to warm up and set up the sale for later.`;
                    document.getElementById("out-next-step").innerText = "Track Content Engagement & Route to Appointment Setter for Meeting Booking";
                }} else if (currentTesterAgent === "lead_dev") {{
                    document.getElementById("out-agent-badge").innerText = "AGENT 1: THE LEAD DEVELOPER";
                    document.getElementById("out-box-title-1").innerText = "Enriched Account Intelligence";
                    document.getElementById("out-box-desc-1").innerText = 
                        `Verified ${{comp}} is a high-growth player in ${{ind}}. Identified 4 decision-makers across Revenue & Operations with verified work emails.`;
                    document.getElementById("out-box-title-2").innerText = "Intent Signal Analysis";
                    document.getElementById("out-box-desc-2").innerText = 
                        `Detected active hiring for 8 sales and operational roles. Ingested into CRM with buyer intent readiness rated at 94/100.`;
                    document.getElementById("out-next-step").innerText = "Route to Decision-Maker & Literature Bot for Phone/Email Outreach";
                }} else if (currentTesterAgent === "sdr") {{
                    document.getElementById("out-agent-badge").innerText = "AGENT 3: THE COLD OUTREACH SDR";
                    document.getElementById("out-box-title-1").innerText = "1-to-1 Tailored Outbound Cadence";
                    document.getElementById("out-box-desc-1").innerText = 
                        `Crafted bespoke sequence referencing ${{comp}}'s recent expansion into ${{ind}}. Dynamically tailored value props to VP of Engineering pain points.`;
                    document.getElementById("out-box-title-2").innerText = "Multi-Channel Touchpoints";
                    document.getElementById("out-box-desc-2").innerText = 
                        `Scheduled 4 personalized touchpoints across Email and LinkedIn InMail with verified delivery and reply sentiment tracking.`;
                    document.getElementById("out-next-step").innerText = "Monitor Open & Reply Signals for Automatic Appointment Setter Handshake";
                }} else if (currentTesterAgent === "setter") {{
                    document.getElementById("out-agent-badge").innerText = "AGENT 4: THE APPOINTMENT SETTER";
                    document.getElementById("out-box-title-1").innerText = "Calendar Negotiation Status";
                    document.getElementById("out-box-desc-1").innerText = 
                        `Prospect indicated availability for product walk-through. Setter normalized timezone to Eastern Time and offered 2 optimal 30-minute slots on team calendar.`;
                    document.getElementById("out-box-title-2").innerText = "Confirmed Meeting Details";
                    document.getElementById("out-box-desc-2").innerText = 
                        `Demo locked for Friday at 11:00 AM EDT with VP of Engineering at ${{comp}}. Automated calendar invitations sent with attached product deck.`;
                    document.getElementById("out-next-step").innerText = "Sync Google/Outlook Calendar & Dispatch 24h Reminder Sequence";
                }} else if (currentTesterAgent === "closer") {{
                    document.getElementById("out-agent-badge").innerText = "AGENT 6: THE OBJECTION CLOSER";
                    document.getElementById("out-box-title-1").innerText = "Contract Friction Analysis";
                    document.getElementById("out-box-desc-1").innerText = 
                        `Analyzed procurement pushback regarding upfront annual billing. Formulated concession package maintaining 82% margin while offering quarterly billing schedule.`;
                    document.getElementById("out-box-title-2").innerText = "Rebuttal Strategy & Concessions";
                    document.getElementById("out-box-desc-2").innerText = 
                        `Drafted executive concession response with SLA renewal guarantees to neutralize hesitation and accelerate contract signing.`;
                    document.getElementById("out-next-step").innerText = "Issue Revised Master Services Agreement & Lock Closing Signature";
                }} else {{
                    // Default Executive Sales Bot
                    document.getElementById("out-agent-badge").innerText = "AGENT 5: THE EXECUTIVE SALES BOT";
                    document.getElementById("out-box-title-1").innerText = "Executive Buyer Assessment";
                    document.getElementById("out-box-desc-1").innerText = 
                        `High-intent enterprise organization operating in ${{ind}}. Primary operational bottleneck is fragmented sales tools and pipeline latency.`;
                    document.getElementById("out-box-title-2").innerText = "Recommended Closing Strategy";
                    document.getElementById("out-box-desc-2").innerText = 
                        `Package Full 6-Agent Workforce with SLA-guaranteed demo velocity. Position multi-agent DAG orchestration to integrate existing enterprise stack.`;
                    document.getElementById("out-next-step").innerText = "Prepare Custom Proposal & Staged Commercial Pilot Contract";
                }}
            }}, 650);
        }}

        // Stack Configurator Recalculation Logic
        function recalculateStack() {{
            const dev = document.getElementById("chk-dev").checked;
            const discovery = document.getElementById("chk-discovery") ? document.getElementById("chk-discovery").checked : true;
            const sdr = document.getElementById("chk-sdr").checked;
            const setter = document.getElementById("chk-setter").checked;
            const exec = document.getElementById("chk-exec").checked;
            const closer = document.getElementById("chk-closer").checked;

            let count = (dev ? 1 : 0) + (discovery ? 1 : 0) + (sdr ? 1 : 0) + (setter ? 1 : 0) + (exec ? 1 : 0) + (closer ? 1 : 0);
            let demos = (dev ? 10 : 0) + (discovery ? 12 : 0) + (sdr ? 16 : 0) + (setter ? 22 : 0);
            let deals = Math.round(demos * 0.22) + (exec ? 5 : 0) + (closer ? 4 : 0);
            let pipeline = deals * 12000;

            document.getElementById("stack-count").innerText = `${{count}} Agents`;
            document.getElementById("stack-demos").innerText = `${{demos}} Demos`;
            document.getElementById("stack-deals").innerText = `${{deals}} Closed`;
            document.getElementById("stack-pipeline").innerText = `$${{pipeline.toLocaleString()}} / mo`;
        }}

        function escapeHtml(str) {{
            if (!str) return '';
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;');
        }}

        // Inbound Demo & Whitepaper Submission
        async function submitInboundDemoCapture(e) {{
            e.preventDefault();
            const btn = document.getElementById("btn-inbound-submit");
            const resBox = document.getElementById("inbound-result-box");
            const name = document.getElementById("inbound-name").value;
            const email = document.getElementById("inbound-email").value;
            const company = document.getElementById("inbound-company").value;
            const phone = document.getElementById("inbound-phone").value;
            const industry = document.getElementById("inbound-industry").value;

            btn.disabled = true;
            btn.innerHTML = `<i class="fa-solid fa-spinner animate-spin"></i> <span>Enrolling in Cadence...</span>`;

            try {{
                const response = await fetch(`${{API_PREFIX}}/api/v1/nurture/inbound-capture`, {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{
                        name: name,
                        email: email,
                        company_name: company,
                        phone: phone,
                        industry: industry,
                        source: "landing_page_whitepaper_form"
                    }})
                }});

                const data = await response.json();
                if (response.ok && data.lead_id) {{
                    resBox.classList.remove("hidden");
                    resBox.innerHTML = `
                        <div class="p-4 rounded-xl bg-emerald-950/80 border border-emerald-500/50 text-emerald-300 space-y-2">
                            <div class="flex items-center gap-2 font-bold text-sm">
                                <i class="fa-solid fa-circle-check text-emerald-400 text-base"></i>
                                <span>Cadence Enrolled! ROI Dossier &amp; Whitepaper Dispatched</span>
                            </div>
                            <p class="text-xs text-slate-300 leading-relaxed">
                                Welcome email with the 16-page Autonomous Workforce Whitepaper has been dispatched to <strong>${{escapeHtml(email)}}</strong>.
                                Your lead ID is <span class="font-mono text-cyan-300">${{data.lead_id.substring(0, 8)}}...</span> and Step 1 of your 5-touchpoint nurture sequence is live!
                            </p>
                        </div>
                    `;
                    document.getElementById("inbound-demo-form").reset();
                }} else {{
                    resBox.classList.remove("hidden");
                    resBox.innerHTML = `
                        <div class="p-3 rounded-xl bg-amber-950/80 border border-amber-500/50 text-amber-300 text-xs">
                            <i class="fa-solid fa-triangle-exclamation mr-1"></i> ${{escapeHtml(data.detail || "Unable to enroll at this time. Please try again.")}}
                        </div>
                    `;
                }}
            }} catch (err) {{
                resBox.classList.remove("hidden");
                resBox.innerHTML = `
                    <div class="p-3 rounded-xl bg-red-950/80 border border-red-500/50 text-red-300 text-xs">
                        <i class="fa-solid fa-circle-xmark mr-1"></i> Network error connecting to nurture pipeline.
                    </div>
                `;
            }} finally {{
                btn.disabled = false;
                btn.innerHTML = `<i class="fa-solid fa-paper-plane"></i> <span>Download Whitepaper &amp; Enroll in Cadence</span>`;
            }}
        }}

        // Initialize First Tab on Load
        document.addEventListener("DOMContentLoaded", () => {{
            switchAgentTab("lead_dev");
            selectTesterAgent("discovery");
            recalculateStack();
        }});
    </script>
</body>
</html>
"""
