"""
SaaS Self-Serve Signup & Subscription Checkout Template
Renders a modern, responsive, high-converting onboarding interface
for prospective SaaS clients selecting an AI Sales Workforce tier:
- Starter SDR ($199/mo)
- Growth Team ($499/mo)
- Executive Workforce ($1,499/mo)
"""

def render_signup_page(api_prefix: str = "", default_plan: str = "growth") -> str:
    prefix = api_prefix.rstrip("/")
    landing_url = f"{prefix}/" if prefix else "/"
    console_url = f"{prefix}/console" if prefix else "/console"
    checkout_api_url = f"{prefix}/api/v1/billing/saas-checkout-session" if prefix else "/api/v1/billing/saas-checkout-session"

    return f"""<!DOCTYPE html>
<html lang="en" class="scroll-smooth">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Get Started • Deploy Your AI Sales Workforce | NexFlow.ai</title>
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
            background: rgba(15, 23, 42, 0.82);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.08);
        }}
        .glow-indigo {{
            box-shadow: 0 0 50px -10px rgba(99, 102, 241, 0.35);
        }}
        .glow-purple {{
            box-shadow: 0 0 50px -10px rgba(168, 85, 247, 0.35);
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
<body class="bg-slate-950 text-slate-100 font-sans selection:bg-indigo-500 selection:text-white relative overflow-x-hidden min-h-screen grid-bg">

    <!-- Ambient Top Lighting -->
    <div class="absolute top-0 left-1/2 -translate-x-1/2 w-[1100px] h-[450px] bg-gradient-to-b from-indigo-600/20 via-purple-600/10 to-transparent blur-3xl pointer-events-none -z-10"></div>

    <!-- Navigation Bar -->
    <header class="sticky top-0 z-50 glass-panel border-b border-slate-800/80">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-20 flex items-center justify-between">
            <a href="{landing_url}" class="flex items-center gap-3 group">
                <div class="h-11 w-11 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-500 flex items-center justify-center text-white text-xl shadow-lg shadow-indigo-500/30 group-hover:scale-105 transition">
                    <i class="fa-solid fa-brain"></i>
                </div>
                <div>
                    <div class="flex items-center gap-2">
                        <span class="font-extrabold text-xl tracking-tight text-white">NexFlow<span class="text-indigo-400">.ai</span></span>
                        <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-indigo-950 text-indigo-300 border border-indigo-700/50">CHECKOUT</span>
                    </div>
                    <span class="text-[11px] text-slate-400">Self-Serve SaaS Onboarding</span>
                </div>
            </a>

            <div class="flex items-center gap-4 text-xs font-semibold">
                <a href="{landing_url}" class="text-slate-400 hover:text-white transition flex items-center gap-1.5">
                    <i class="fa-solid fa-arrow-left"></i>
                    <span>Back to 6 Bots Overview</span>
                </a>
                <a href="{console_url}" class="px-4 py-2 rounded-xl text-slate-300 hover:text-white bg-slate-900 border border-slate-700/80 transition flex items-center gap-1.5">
                    <i class="fa-solid fa-right-to-bracket text-indigo-400"></i>
                    <span>Sign In</span>
                </a>
            </div>
        </div>
    </header>

    <!-- MAIN ONBOARDING & CHECKOUT SECTION -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 md:py-16">
        
        <!-- Header Banner -->
        <div class="text-center space-y-3 max-w-3xl mx-auto pb-10">
            <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-950/80 text-indigo-300 border border-indigo-800/60 text-xs font-semibold">
                <i class="fa-solid fa-bolt text-amber-400"></i>
                <span>Instant Autonomous Bot Provisioning</span>
            </div>
            <h1 class="text-3xl sm:text-5xl font-black tracking-tight text-white">
                Deploy Your <span class="gradient-text">Autonomous AI Sales Workforce</span>
            </h1>
            <p class="text-slate-400 text-sm sm:text-base">
                Select your tier and activate your specialized sales bots in under 2 minutes. Multi-tenant isolated workspace included.
            </p>
        </div>

        <!-- 2-Column Split: Plan Selection (Left) & Account Form (Right) -->
        <div class="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            
            <!-- LEFT COLUMN: Plan Tier Selection Cards -->
            <div class="lg:col-span-7 space-y-5">
                <div class="flex items-center justify-between pb-1">
                    <span class="text-xs font-mono uppercase tracking-wider text-slate-400 font-bold">Step 1: Choose Subscription Tier</span>
                    <span class="text-xs text-emerald-400 font-semibold flex items-center gap-1">
                        <i class="fa-solid fa-shield-check"></i> 14-Day Risk-Free Guarantee
                    </span>
                </div>

                <!-- Plan 1: Starter SDR ($199) -->
                <div id="card-plan-starter" onclick="selectPlan('starter')" class="glass-panel rounded-2xl p-5 border-2 border-slate-800 hover:border-indigo-500/60 transition cursor-pointer relative group">
                    <div class="flex items-start justify-between gap-4">
                        <div class="flex items-center gap-3">
                            <div class="h-6 w-6 rounded-full border-2 border-slate-600 flex items-center justify-center plan-radio-outer" id="radio-starter">
                                <div class="h-3 w-3 rounded-full bg-transparent plan-radio-inner" id="dot-starter"></div>
                            </div>
                            <div>
                                <div class="flex items-center gap-2">
                                    <h3 class="font-bold text-white text-base">Starter SDR</h3>
                                    <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-900 text-slate-300 border border-slate-700">1 AI BOT</span>
                                </div>
                                <p class="text-xs text-slate-400 pt-0.5">Ideal for single-agent appointment setting or lead enrichment.</p>
                            </div>
                        </div>
                        <div class="text-right shrink-0">
                            <div class="text-2xl font-black text-white font-mono">$199</div>
                            <div class="text-[10px] text-slate-400 font-semibold uppercase">per month</div>
                        </div>
                    </div>
                    <div class="mt-4 pt-3 border-t border-slate-800/80 flex flex-wrap gap-y-1.5 gap-x-4 text-xs text-slate-300">
                        <span class="flex items-center gap-1.5"><i class="fa-solid fa-check text-emerald-400 text-[11px]"></i> 1 Active AI Bot (Lead Dev or Setter)</span>
                        <span class="flex items-center gap-1.5"><i class="fa-solid fa-check text-emerald-400 text-[11px]"></i> 1,000 Pipeline Touches/mo</span>
                        <span class="flex items-center gap-1.5"><i class="fa-solid fa-check text-emerald-400 text-[11px]"></i> 2 Seats Included</span>
                    </div>
                </div>

                <!-- Plan 2: Growth Team ($499) - Default & Highlighted -->
                <div id="card-plan-growth" onclick="selectPlan('growth')" class="glass-panel rounded-2xl p-5 border-2 border-indigo-500 transition cursor-pointer relative glow-indigo group">
                    <div class="absolute -top-3 right-6 px-3 py-0.5 rounded-full bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-bold text-[10px] tracking-wider uppercase shadow-md flex items-center gap-1">
                        <i class="fa-solid fa-fire text-amber-300 text-[9px]"></i> Most Popular
                    </div>
                    <div class="flex items-start justify-between gap-4">
                        <div class="flex items-center gap-3">
                            <div class="h-6 w-6 rounded-full border-2 border-indigo-500 flex items-center justify-center plan-radio-outer" id="radio-growth">
                                <div class="h-3 w-3 rounded-full bg-indigo-500 plan-radio-inner" id="dot-growth"></div>
                            </div>
                            <div>
                                <div class="flex items-center gap-2">
                                    <h3 class="font-bold text-white text-base">Growth Team</h3>
                                    <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-indigo-950 text-indigo-300 border border-indigo-800">3 AI BOTS</span>
                                </div>
                                <p class="text-xs text-slate-300 pt-0.5">End-to-end phone &amp; email decision-maker discovery + appointment booking.</p>
                            </div>
                        </div>
                        <div class="text-right shrink-0">
                            <div class="text-2xl font-black text-white font-mono">$499</div>
                            <div class="text-[10px] text-slate-400 font-semibold uppercase">per month</div>
                        </div>
                    </div>
                    <div class="mt-4 pt-3 border-t border-slate-800/80 grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-slate-200">
                        <span class="flex items-center gap-1.5"><i class="fa-solid fa-check text-emerald-400 text-[11px]"></i> 3 Specialized Sales Bots Deployed</span>
                        <span class="flex items-center gap-1.5"><i class="fa-solid fa-check text-emerald-400 text-[11px]"></i> 5,000 Pipeline Touches/mo</span>
                        <span class="flex items-center gap-1.5"><i class="fa-solid fa-check text-emerald-400 text-[11px]"></i> Decision-Maker &amp; Literature Dispatch</span>
                        <span class="flex items-center gap-1.5"><i class="fa-solid fa-check text-emerald-400 text-[11px]"></i> 5 Seats + Voice AI Switchboard</span>
                    </div>
                </div>

                <!-- Plan 3: Executive Workforce ($1,499) -->
                <div id="card-plan-executive" onclick="selectPlan('executive')" class="glass-panel rounded-2xl p-5 border-2 border-slate-800 hover:border-purple-500/60 transition cursor-pointer relative group">
                    <div class="flex items-start justify-between gap-4">
                        <div class="flex items-center gap-3">
                            <div class="h-6 w-6 rounded-full border-2 border-slate-600 flex items-center justify-center plan-radio-outer" id="radio-executive">
                                <div class="h-3 w-3 rounded-full bg-transparent plan-radio-inner" id="dot-executive"></div>
                            </div>
                            <div>
                                <div class="flex items-center gap-2">
                                    <h3 class="font-bold text-white text-base">Executive Workforce</h3>
                                    <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-purple-950 text-purple-300 border border-purple-800">ALL 7 BOTS</span>
                                </div>
                                <p class="text-xs text-slate-400 pt-0.5">Autonomous VP of Sales &amp; enterprise closers handling multi-stakeholder deals.</p>
                            </div>
                        </div>
                        <div class="text-right shrink-0">
                            <div class="text-2xl font-black text-white font-mono">$1,499</div>
                            <div class="text-[10px] text-slate-400 font-semibold uppercase">per month</div>
                        </div>
                    </div>
                    <div class="mt-4 pt-3 border-t border-slate-800/80 grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-slate-300">
                        <span class="flex items-center gap-1.5"><i class="fa-solid fa-check text-emerald-400 text-[11px]"></i> Complete 7-Bot Workforce Deployed</span>
                        <span class="flex items-center gap-1.5"><i class="fa-solid fa-check text-emerald-400 text-[11px]"></i> 25,000 Pipeline Touches/mo</span>
                        <span class="flex items-center gap-1.5"><i class="fa-solid fa-check text-emerald-400 text-[11px]"></i> Executive Sales Bot &amp; Objection Closer</span>
                        <span class="flex items-center gap-1.5"><i class="fa-solid fa-check text-emerald-400 text-[11px]"></i> 20 Seats + Dedicated HITL Queue</span>
                    </div>
                </div>

                <!-- Included Bot Roster Breakdown Widget -->
                <div class="glass-panel rounded-2xl p-4 border border-slate-800 space-y-2">
                    <span class="text-[11px] font-mono text-slate-400 uppercase font-bold flex items-center gap-1.5">
                        <i class="fa-solid fa-users-gear text-indigo-400"></i>
                        <span>Bots Included In Selected Plan:</span>
                    </span>
                    <div id="roster-chips" class="flex flex-wrap gap-2 pt-1">
                        <!-- Rendered via JS -->
                    </div>
                </div>
            </div>

            <!-- RIGHT COLUMN: Account Details & Instant Checkout -->
            <div class="lg:col-span-5">
                <div class="glass-panel rounded-3xl p-6 sm:p-8 border border-slate-800 space-y-6 shadow-2xl">
                    <div class="space-y-1">
                        <span class="text-xs font-mono uppercase tracking-wider text-slate-400 font-bold">Step 2: Create Account</span>
                        <h2 class="text-xl font-black text-white">Setup Your Workspace</h2>
                        <p class="text-xs text-slate-400">Your credentials will grant immediate administrative access to your CRM console.</p>
                    </div>

                    <!-- Error Alert -->
                    <div id="form-error" class="hidden p-3 rounded-xl bg-red-950/80 border border-red-800/80 text-xs text-red-200 flex items-start gap-2.5">
                        <i class="fa-solid fa-circle-exclamation text-red-400 text-sm shrink-0 mt-0.5"></i>
                        <span id="form-error-text">An error occurred while creating your account.</span>
                    </div>

                    <form id="signup-form" onsubmit="handleSignupSubmit(event)" class="space-y-4">
                        <div class="space-y-1.5">
                            <label class="block text-xs font-bold text-slate-300 uppercase tracking-wider">Company / Organization Name</label>
                            <div class="relative">
                                <i class="fa-solid fa-building absolute left-3.5 top-3 text-slate-500 text-xs"></i>
                                <input type="text" id="org_name" required placeholder="e.g. Acme SaaS Technologies" class="w-full pl-9 pr-3 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition">
                            </div>
                        </div>

                        <div class="space-y-1.5">
                            <label class="block text-xs font-bold text-slate-300 uppercase tracking-wider">Your Full Name</label>
                            <div class="relative">
                                <i class="fa-solid fa-user absolute left-3.5 top-3 text-slate-500 text-xs"></i>
                                <input type="text" id="full_name" required placeholder="e.g. Marcus Vance" class="w-full pl-9 pr-3 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition">
                            </div>
                        </div>

                        <div class="space-y-1.5">
                            <label class="block text-xs font-bold text-slate-300 uppercase tracking-wider">Work Email Address</label>
                            <div class="relative">
                                <i class="fa-solid fa-envelope absolute left-3.5 top-3 text-slate-500 text-xs"></i>
                                <input type="email" id="email" required placeholder="marcus@company.example" class="w-full pl-9 pr-3 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition">
                            </div>
                        </div>

                        <div class="space-y-1.5">
                            <label class="block text-xs font-bold text-slate-300 uppercase tracking-wider">Password</label>
                            <div class="relative">
                                <i class="fa-solid fa-lock absolute left-3.5 top-3 text-slate-500 text-xs"></i>
                                <input type="password" id="password" required minlength="6" placeholder="At least 6 characters" class="w-full pl-9 pr-3 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition">
                            </div>
                        </div>

                        <!-- Order Summary Box -->
                        <div class="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2.5">
                            <div class="flex items-center justify-between text-xs text-slate-400">
                                <span>Selected Tier:</span>
                                <span class="font-bold text-white" id="summary-tier-name">Growth Team</span>
                            </div>
                            <div class="flex items-center justify-between text-xs text-slate-400">
                                <span>Monthly Investment:</span>
                                <span class="font-black text-indigo-400 text-sm" id="summary-tier-price">$499 / mo</span>
                            </div>
                            <div class="flex items-center justify-between text-[11px] text-slate-500 pt-1 border-t border-slate-800/80">
                                <span>Billing Interval:</span>
                                <span>Monthly (Cancel Anytime)</span>
                            </div>
                            <div class="flex items-center justify-between text-[11px] text-emerald-400">
                                <span>Setup Fee:</span>
                                <span class="font-bold">$0 (Waived Today)</span>
                            </div>
                        </div>

                        <!-- Submit Button -->
                        <button type="submit" id="btn-submit" class="w-full py-4 px-6 rounded-xl text-sm font-extrabold text-white bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 hover:from-indigo-500 hover:to-pink-500 shadow-xl shadow-indigo-600/30 transition transform hover:-translate-y-0.5 flex items-center justify-center gap-2">
                            <span id="btn-text">Proceed to Checkout &amp; Deploy Bots</span>
                            <i class="fa-solid fa-arrow-right text-xs" id="btn-icon"></i>
                        </button>
                    </form>

                    <!-- Trust & Compliance Badges -->
                    <div class="pt-2 border-t border-slate-800/80 grid grid-cols-2 gap-3 text-[11px] text-slate-400">
                        <div class="flex items-center gap-2">
                            <i class="fa-solid fa-shield-halved text-emerald-400"></i>
                            <span>Isolated Tenant Schema</span>
                        </div>
                        <div class="flex items-center gap-2">
                            <i class="fa-solid fa-credit-card text-purple-400"></i>
                            <span>Stripe Verified Billing</span>
                        </div>
                        <div class="flex items-center gap-2">
                            <i class="fa-solid fa-lock text-indigo-400"></i>
                            <span>256-Bit SSL Encryption</span>
                        </div>
                        <div class="flex items-center gap-2">
                            <i class="fa-solid fa-rotate-left text-amber-400"></i>
                            <span>14-Day Money Back</span>
                        </div>
                    </div>
                </div>
            </div>

        </div>
    </main>

    <!-- FOOTER -->
    <footer class="border-t border-slate-900 bg-slate-950 py-8 text-slate-500 text-xs text-center">
        <div class="max-w-7xl mx-auto px-4">
            <p>&copy; 2026 NexFlow AI Technologies Inc. All rights reserved. The Autonomous Sales Workforce for SaaS.</p>
        </div>
    </footer>

    <!-- INTERACTIVE LOGIC -->
    <script>
        const API_PREFIX = "{prefix}";
        const CHECKOUT_API_URL = "{checkout_api_url}";
        const DEFAULT_PLAN = "{default_plan}";

        const PLAN_DATA = {{
            starter: {{
                name: "Starter SDR",
                price: "$199 / mo",
                rawPrice: 199,
                bots: [
                    {{ name: "1. The Lead Developer", icon: "fa-database", color: "indigo" }}
                ]
            }},
            growth: {{
                name: "Growth Team",
                price: "$499 / mo",
                rawPrice: 499,
                bots: [
                    {{ name: "1. The Lead Developer", icon: "fa-database", color: "indigo" }},
                    {{ name: "2. Decision-Maker & Literature Bot", icon: "fa-phone-volume", color: "cyan" }},
                    {{ name: "3. The Appointment Setter", icon: "fa-calendar-check", color: "pink" }}
                ]
            }},
            executive: {{
                name: "Executive Workforce",
                price: "$1,499 / mo",
                rawPrice: 1499,
                bots: [
                    {{ name: "1. The Lead Developer", icon: "fa-database", color: "indigo" }},
                    {{ name: "2. Decision-Maker & Literature Bot", icon: "fa-phone-volume", color: "cyan" }},
                    {{ name: "3. The Appointment Setter", icon: "fa-calendar-check", color: "pink" }},
                    {{ name: "4. The Cold Outreach SDR", icon: "fa-paper-plane", color: "emerald" }},
                    {{ name: "5. The Executive Sales Bot", icon: "fa-chess-king", color: "purple" }},
                    {{ name: "6. The Objection Closer", icon: "fa-handshake-angle", color: "amber" }},
                    {{ name: "7. Outbound Campaign Power Dialer", icon: "fa-headset", color: "teal" }}
                ]
            }}
        }};

        let currentPlan = "growth";

        function selectPlan(planKey) {{
            if (!PLAN_DATA[planKey]) planKey = "growth";
            currentPlan = planKey;

            const tiers = ["starter", "growth", "executive"];
            tiers.forEach(t => {{
                const card = document.getElementById(`card-plan-${{t}}`);
                const radio = document.getElementById(`radio-${{t}}`);
                const dot = document.getElementById(`dot-${{t}}`);

                if (t === planKey) {{
                    card.className = "glass-panel rounded-2xl p-5 border-2 border-indigo-500 transition cursor-pointer relative glow-indigo";
                    radio.className = "h-6 w-6 rounded-full border-2 border-indigo-500 flex items-center justify-center plan-radio-outer";
                    dot.className = "h-3 w-3 rounded-full bg-indigo-500 plan-radio-inner";
                }} else {{
                    card.className = "glass-panel rounded-2xl p-5 border-2 border-slate-800 hover:border-slate-700 transition cursor-pointer relative";
                    radio.className = "h-6 w-6 rounded-full border-2 border-slate-600 flex items-center justify-center plan-radio-outer";
                    dot.className = "h-3 w-3 rounded-full bg-transparent plan-radio-inner";
                }}
            }});

            const plan = PLAN_DATA[planKey];
            document.getElementById("summary-tier-name").innerText = plan.name;
            document.getElementById("summary-tier-price").innerText = plan.price;

            // Render Roster Chips
            const chipsContainer = document.getElementById("roster-chips");
            chipsContainer.innerHTML = plan.bots.map(b => `
                <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-900 border border-slate-800 text-slate-200">
                    <i class="fa-solid ${{b.icon}} text-${{b.color}}-400 text-[11px]"></i>
                    <span>${{b.name}}</span>
                </span>
            `).join('');
        }}

        async function handleSignupSubmit(e) {{
            e.preventDefault();
            const errBox = document.getElementById("form-error");
            const errText = document.getElementById("form-error-text");
            errBox.classList.add("hidden");

            const orgName = document.getElementById("org_name").value.trim();
            const fullName = document.getElementById("full_name").value.trim();
            const email = document.getElementById("email").value.trim();
            const password = document.getElementById("password").value;

            if (password.length < 6) {{
                errText.innerText = "Password must be at least 6 characters long.";
                errBox.classList.remove("hidden");
                return;
            }}

            const btn = document.getElementById("btn-submit");
            const btnText = document.getElementById("btn-text");
            const btnIcon = document.getElementById("btn-icon");

            btn.disabled = true;
            btnText.innerText = "Provisioning Workspace & AI Workforce...";
            btnIcon.className = "fa-solid fa-spinner fa-spin text-xs";

            try {{
                const res = await fetch(CHECKOUT_API_URL, {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{
                        organization_name: orgName,
                        full_name: fullName,
                        email: email,
                        password: password,
                        plan_tier: currentPlan,
                        success_url: window.location.origin + "{prefix}/console?welcome=1&plan=" + currentPlan,
                        cancel_url: window.location.href
                    }})
                }});

                const data = await res.json();

                if (!res.ok) {{
                    throw new Error(data.detail || "Unable to complete signup. Please check inputs.");
                }}

                if (data.token) {{
                    localStorage.setItem("access_token", data.token);
                }}

                if (data.checkout_url) {{
                    window.location.href = data.checkout_url;
                }} else {{
                    window.location.href = "{console_url}?welcome=1&plan=" + currentPlan;
                }}
            }} catch (err) {{
                btn.disabled = false;
                btnText.innerText = "Proceed to Checkout & Deploy Bots";
                btnIcon.className = "fa-solid fa-arrow-right text-xs";
                errText.innerText = err.message;
                errBox.classList.remove("hidden");
            }}
        }}

        // Initialize with URL Query Param if present (e.g. ?plan=executive)
        document.addEventListener("DOMContentLoaded", () => {{
            const urlParams = new URLSearchParams(window.location.search);
            const planParam = urlParams.get("plan");
            if (planParam && PLAN_DATA[planParam]) {{
                selectPlan(planParam);
            }} else {{
                selectPlan(DEFAULT_PLAN);
            }}
        }});
    </script>
</body>
</html>
"""
