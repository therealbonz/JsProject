def render_residential_portal(api_prefix: str = "/JsProject") -> str:
    """
    Renders the modern, interactive Residential Home Services Sales Bot & Quoting Web Portal.
    Allows testing conversational quoting and instant booking across Carpet Cleaning, Lawn Care, and Roofing.
    """
    html = """<!DOCTYPE html>
<html lang="en" class="h-full bg-slate-950 text-slate-100">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Apex Home Services • Instant Quotes & Online Booking</title>
    <script src="https://cdn.tailwindcss.com">
        // =========================================================================
        // FSM & CALENDAR DISPATCH JS (PHASE 3)
        // =========================================================================
        let lastBookedAppointmentId = null;

        function openFSMModal() {
            document.getElementById('fsm-modal').classList.remove('hidden');
            loadFSMFleet();
        }

        function closeFSMModal() {
            document.getElementById('fsm-modal').classList.add('hidden');
        }

        async function loadFSMFleet() {
            const container = document.getElementById('fsm-fleet-list');
            container.innerHTML = `<span class="text-slate-400 italic">Loading fleet roster...</span>`;
            try {
                const res = await fetch(`${API_PREFIX}/api/v1/residential/fsm/crews`);
                const data = await res.json();
                container.innerHTML = "";
                (data.crews || []).forEach(c => {
                    const card = document.createElement('div');
                    card.className = "p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1";
                    card.innerHTML = `
                        <div class="flex items-center justify-between">
                            <span class="font-bold text-white">${escapeHtml(c.name)}</span>
                            <span class="text-[10px] font-bold text-amber-400 flex items-center gap-1">
                                <i class="fa-solid fa-star text-[9px]"></i> ${c.rating}
                            </span>
                        </div>
                        <p class="text-[11px] text-slate-400">Lead: <span class="text-slate-300">${escapeHtml(c.lead)}</span> • ${escapeHtml(c.vehicle)}</p>
                        <div class="flex items-center justify-between text-[10px] text-slate-500 pt-1 border-t border-slate-900">
                            <span>Trade: ${escapeHtml(c.trade.replace('_', ' ').toUpperCase())}</span>
                            <span class="text-emerald-400 font-semibold">${c.completed_jobs} Jobs Completed</span>
                        </div>
                    `;
                    container.appendChild(card);
                });
            } catch (err) {
                console.error("Fleet error", err);
            }
        }

        async function simulateEnRouteAlert() {
            const apptId = lastBookedAppointmentId || "demo_appointment";
            const resBox = document.getElementById('fsm-alert-response');
            resBox.classList.remove('hidden');
            resBox.innerHTML = `<i class="fa-solid fa-spinner fa-spin text-amber-400"></i> Dispatching 30-min en-route SMS...`;
            try {
                const res = await fetch(`${API_PREFIX}/api/v1/residential/fsm/en_route`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ appointment_id: apptId, eta_minutes: 25 })
                });
                const data = await res.json();
                if (data.success) {
                    resBox.innerHTML = `<strong>Sent:</strong> "${escapeHtml(data.message)}"`;
                } else {
                    resBox.innerHTML = `<strong>Simulated En Route SMS:</strong> "🚚 Apex Dispatch Heads-Up: Your service crew (Lead: Dave Miller) is now en route to your address! ETA: 25 minutes."`;
                }
            } catch (err) {
                resBox.innerHTML = `<strong>Simulated En Route SMS:</strong> "🚚 Apex Dispatch Heads-Up: Your service crew (Lead: Dave Miller) is now en route to your address! ETA: 25 minutes."`;
            }
        }

        async function simulateCompleteAlert() {
            const apptId = lastBookedAppointmentId || "demo_appointment";
            const resBox = document.getElementById('fsm-alert-response');
            resBox.classList.remove('hidden');
            resBox.innerHTML = `<i class="fa-solid fa-spinner fa-spin text-emerald-400"></i> Dispatching completion SMS...`;
            try {
                const res = await fetch(`${API_PREFIX}/api/v1/residential/fsm/complete`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ appointment_id: apptId })
                });
                const data = await res.json();
                if (data.success) {
                    resBox.innerHTML = `<strong>Sent:</strong> "${escapeHtml(data.message)}"`;
                } else {
                    resBox.innerHTML = `<strong>Simulated Completion SMS:</strong> "⭐ Thank you for choosing Apex Home Services! Your service is now complete. We back all work with our 100% Satisfaction Guarantee."`;
                }
            } catch (err) {
                resBox.innerHTML = `<strong>Simulated Completion SMS:</strong> "⭐ Thank you for choosing Apex Home Services! Your service is now complete. We back all work with our 100% Satisfaction Guarantee."`;
            }
        }

    </script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Plus Jakarta Sans', sans-serif; }
        code, .font-mono { font-family: 'JetBrains Mono', monospace; }
        .custom-scrollbar::-webkit-scrollbar { width: 6px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: rgba(15, 23, 42, 0.6); }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(51, 65, 85, 0.6); border-radius: 9999px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(71, 85, 105, 0.8); }
        @keyframes pulse-glow {
            0%, 100% { box-shadow: 0 0 15px rgba(99, 102, 241, 0.3); }
            50% { box-shadow: 0 0 25px rgba(99, 102, 241, 0.6); }
        }
        .glow-active { animation: pulse-glow 2.5s infinite; }
    </style>
</head>
<body class="h-full flex flex-col antialiased selection:bg-indigo-500 selection:text-white bg-slate-950">

    <!-- Top Announcement Bar -->
    <header class="bg-gradient-to-r from-indigo-950 via-slate-900 to-indigo-950 border-b border-indigo-900/40 text-xs py-2 px-4 shadow-md">
        <div class="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-2">
            <div class="flex items-center gap-2 text-indigo-300">
                <span class="flex h-2 w-2 rounded-full bg-emerald-400 animate-ping"></span>
                <span class="font-semibold text-emerald-400">Live AI Dispatch Available</span>
                <span class="text-slate-500">•</span>
                <span class="text-slate-300 hidden sm:inline">Carpet Cleaning, Lawn Maintenance & Roofing Experts</span>
            </div>
            <div class="flex items-center gap-4 text-slate-400 text-xs">
                <span class="flex items-center gap-1.5"><i class="fa-solid fa-shield-halved text-emerald-400"></i> $2M Licensed & Insured</span>
                <span class="flex items-center gap-1.5"><i class="fa-solid fa-star text-amber-400"></i> 4.9 (1,420+ Reviews)</span>
                <a href="tel:8005552739" class="text-indigo-300 font-semibold hover:text-white transition flex items-center gap-1">
                    <i class="fa-solid fa-phone"></i> (800) 555-APEX
                </a>
            </div>
        </div>
    </header>

    <!-- Main Navigation Bar -->
    <nav class="bg-slate-900/90 backdrop-blur border-b border-slate-800 sticky top-0 z-40 px-4 py-3">
        <div class="max-w-7xl mx-auto flex items-center justify-between">
            <div class="flex items-center gap-3">
                <div class="h-10 w-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center text-white text-lg shadow-lg shadow-indigo-600/30">
                    <i class="fa-solid fa-house-chimney-crack"></i>
                </div>
                <div>
                    <div class="flex items-center gap-2">
                        <span class="font-black tracking-tight text-lg text-white">APEX</span>
                        <span class="text-xs px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-semibold uppercase tracking-wider">Home Services</span>
                    </div>
                    <p class="text-[11px] text-slate-400">Autonomous Residential Sales & Dispatch Bot</p>
                </div>
            </div>

            <!-- Trade Selection Buttons -->
            <div class="hidden md:flex items-center gap-1.5 bg-slate-950/80 p-1.5 rounded-xl border border-slate-800" id="nav-trade-pills">
                <button onclick="switchTrade('carpet_cleaning')" id="tab-carpet_cleaning" class="px-3.5 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-2 bg-indigo-600 text-white shadow">
                    <i class="fa-solid fa-wand-magic-sparkles"></i> Carpet Cleaning
                </button>
                <button onclick="switchTrade('lawn_care')" id="tab-lawn_care" class="px-3.5 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-2 text-slate-400 hover:text-white hover:bg-slate-800/60">
                    <i class="fa-solid fa-seedling"></i> Lawn Care
                </button>
                <button onclick="switchTrade('roofing')" id="tab-roofing" class="px-3.5 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-2 text-slate-400 hover:text-white hover:bg-slate-800/60">
                    <i class="fa-solid fa-shield"></i> Roofing & Gutters
                </button>
            </div>

            <!-- Action Links -->
            <div class="flex items-center gap-2">
                <button onclick="openPhoneSimulator('sms')" class="px-2.5 py-1.5 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/40 border border-indigo-500/40 text-indigo-300 hover:text-white text-xs font-semibold transition flex items-center gap-1.5 shadow cursor-pointer">
                    <i class="fa-solid fa-mobile-screen-button text-indigo-400"></i> 
                    <span>Phone & SMS</span>
                    <span class="px-1 py-0.2 rounded bg-indigo-500 text-white text-[9px] uppercase font-bold">P2</span>
                </button>
                <button onclick="openFSMModal()" class="px-2.5 py-1.5 rounded-xl bg-purple-600/20 hover:bg-purple-600/40 border border-purple-500/40 text-purple-300 hover:text-white text-xs font-semibold transition flex items-center gap-1.5 shadow cursor-pointer">
                    <i class="fa-solid fa-truck-ramp-box text-purple-400"></i>
                    <span>Fleet & FSM</span>
                    <span class="px-1 py-0.2 rounded bg-purple-500 text-white text-[9px] uppercase font-bold">P3</span>
                </button>
                <a href="/" class="text-xs font-medium text-slate-400 hover:text-white transition flex items-center gap-1.5">
                    <i class="fa-solid fa-gauge"></i> <span class="hidden sm:inline">CRM</span>
                </a>
                <button onclick="openBookingModal()" class="px-3.5 py-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-semibold text-xs transition shadow-lg shadow-emerald-600/20 flex items-center gap-2 cursor-pointer">
                    <i class="fa-solid fa-calendar-check"></i> Book Crew
                </button>
            </div>
        </div>
    </nav>

    <!-- Mobile Trade Selector Bar -->
    <div class="md:hidden flex items-center justify-around bg-slate-900 border-b border-slate-800 p-2 text-xs">
        <button onclick="switchTrade('carpet_cleaning')" id="m-tab-carpet_cleaning" class="font-semibold text-indigo-400 flex items-center gap-1">
            <i class="fa-solid fa-wand-magic-sparkles"></i> Carpet
        </button>
        <button onclick="switchTrade('lawn_care')" id="m-tab-lawn_care" class="font-semibold text-slate-400 flex items-center gap-1">
            <i class="fa-solid fa-seedling"></i> Lawn
        </button>
        <button onclick="switchTrade('roofing')" id="m-tab-roofing" class="font-semibold text-slate-400 flex items-center gap-1">
            <i class="fa-solid fa-shield"></i> Roofing
        </button>
    </div>

    <!-- 1-Click Interactive Test Scenarios Bar -->
    <div class="bg-slate-900/60 border-b border-slate-800/80 px-4 py-2.5">
        <div class="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-3 text-xs">
            <div class="flex items-center gap-2 text-slate-400">
                <i class="fa-solid fa-bolt text-amber-400"></i>
                <span class="font-bold text-slate-300">1-Click Test Scenarios:</span>
            </div>
            <div class="flex flex-wrap items-center gap-2">
                <button onclick="openPhoneSimulator('sms')" class="px-2.5 py-1 rounded-lg bg-indigo-950/70 hover:bg-indigo-900 text-indigo-200 border border-indigo-700/60 transition flex items-center gap-1.5 text-xs font-semibold cursor-pointer">
                    <i class="fa-solid fa-comment-sms text-indigo-400"></i> <span>2-Way SMS</span>
                </button>
                <button onclick="openPhoneSimulator('missed')" class="px-2.5 py-1 rounded-lg bg-amber-950/70 hover:bg-amber-900 text-amber-200 border border-amber-700/60 transition flex items-center gap-1.5 text-xs font-semibold cursor-pointer">
                    <i class="fa-solid fa-phone-slash text-amber-400"></i> <span>Missed-Call Speed-to-Lead</span>
                </button>
                <button onclick="openPhoneSimulator('voice')" class="px-2.5 py-1 rounded-lg bg-emerald-950/70 hover:bg-emerald-900 text-emerald-200 border border-emerald-700/60 transition flex items-center gap-1.5 text-xs font-semibold cursor-pointer">
                    <i class="fa-solid fa-headset text-emerald-400"></i> <span>Voice AI Receptionist</span>
                </button>
                <span class="text-slate-600 hidden sm:inline">|</span>
                <button onclick="loadScenario('carpet_sarah')" class="px-2.5 py-1 rounded-lg bg-slate-800/90 hover:bg-slate-700 text-slate-200 border border-slate-700 transition flex items-center gap-1.5 text-xs">
                    <span>🧽 Sarah</span> <span class="text-slate-400 text-[11px]">(3 Beds, Pet Urine Stains)</span>
                </button>
                <button onclick="loadScenario('lawn_marcus')" class="px-2.5 py-1 rounded-lg bg-slate-800/90 hover:bg-slate-700 text-slate-200 border border-slate-700 transition flex items-center gap-1.5 text-xs">
                    <span>🌿 Marcus</span> <span class="text-slate-400 text-[11px]">(0.5 Acre, Bi-Weekly Lawn)</span>
                </button>
                <button onclick="loadScenario('roof_dave')" class="px-2.5 py-1 rounded-lg bg-rose-950/40 hover:bg-rose-900/60 text-rose-200 border border-rose-800/60 transition flex items-center gap-1.5 text-xs">
                    <span>⚠️ Dave</span> <span class="text-rose-300 text-[11px]">(Active Ceiling Leak Triage)</span>
                </button>
                <button onclick="resetConversation()" class="px-2.5 py-1 rounded-lg bg-slate-800/50 hover:bg-slate-800 text-slate-400 hover:text-white transition text-xs flex items-center gap-1">
                    <i class="fa-solid fa-arrow-rotate-left"></i> Reset
                </button>
            </div>
        </div>
    </div>

    <!-- Main Interactive Grid -->
    <main class="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6 grid grid-cols-1 lg:grid-cols-12 gap-6 overflow-hidden">
        
        <!-- Left Column: Conversational Sales AI Bot (7 Cols) -->
        <section class="lg:col-span-7 flex flex-col bg-slate-900/90 border border-slate-800 rounded-2xl shadow-xl overflow-hidden min-h-[580px]">
            
            <!-- Agent Header -->
            <div class="px-5 py-4 border-b border-slate-800 bg-slate-950/40 flex items-center justify-between">
                <div class="flex items-center gap-3">
                    <div class="relative">
                        <div class="h-10 w-10 rounded-full bg-gradient-to-tr from-indigo-500 to-fuchsia-500 flex items-center justify-center text-white font-bold text-sm shadow-md">
                            A
                        </div>
                        <span class="absolute bottom-0 right-0 h-3 w-3 rounded-full bg-emerald-400 ring-2 ring-slate-900"></span>
                    </div>
                    <div>
                        <div class="flex items-center gap-2">
                            <h2 class="font-bold text-sm text-white">Amber • Lead Service Coordinator</h2>
                            <span class="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">AI Sales Agent</span>
                        </div>
                        <p class="text-xs text-slate-400" id="agent-current-trade-desc">Master Carpet & Upholstery Care</p>
                    </div>
                </div>
                <div class="text-right">
                    <span class="text-xs text-slate-400">Response time:</span>
                    <span class="text-xs font-semibold text-emerald-400 flex items-center gap-1 justify-end">
                        <i class="fa-solid fa-bolt"></i> Instant
                    </span>
                </div>
            </div>

            <!-- Emergency Warning Banner (dynamic) -->
            <div id="emergency-banner" class="hidden bg-rose-950/80 border-b border-rose-800/80 text-rose-200 px-4 py-2.5 text-xs flex items-center gap-2.5">
                <i class="fa-solid fa-triangle-exclamation text-rose-400 text-base animate-bounce"></i>
                <div class="flex-1 font-medium" id="emergency-banner-text">Active leak alert! Crew dispatch priority flagged.</div>
                <button onclick="openBookingModal()" class="px-2.5 py-1 rounded bg-rose-600 hover:bg-rose-500 text-white font-bold text-[11px]">Dispatch Now</button>
            </div>

            <!-- Chat Message Stream -->
            <div id="chat-stream" class="flex-1 p-4 md:p-6 overflow-y-auto space-y-4 custom-scrollbar bg-gradient-to-b from-slate-900/50 to-slate-950/60">
                <!-- Messages will be injected here -->
            </div>

            <!-- Quick Reply Chips -->
            <div class="px-4 py-2.5 bg-slate-950/60 border-t border-slate-800/60 flex items-center gap-2 overflow-x-auto custom-scrollbar" id="quick-replies-container">
                <!-- Quick replies injected here -->
            </div>

            <!-- Input Box -->
            <form id="chat-form" onsubmit="handleUserSubmit(event)" class="p-4 border-t border-slate-800 bg-slate-950/80 flex items-center gap-2.5">
                <input 
                    type="text" 
                    id="chat-input" 
                    placeholder="Type your requirements (e.g., '3 bedrooms with pet stains', '0.5 acre lawn', 'roof leak')..." 
                    class="flex-1 bg-slate-900 border border-slate-700/80 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 outline-none transition"
                    autocomplete="off"
                />
                <button 
                    type="submit" 
                    id="chat-send-btn"
                    class="h-11 px-5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm transition shadow-lg shadow-indigo-600/30 flex items-center justify-center gap-2 shrink-0 cursor-pointer"
                >
                    <span>Send</span>
                    <i class="fa-solid fa-paper-plane text-xs"></i>
                </button>
            </form>
        </section>

        <!-- Right Column: Live Dynamic Upfront Quote Card & Booking (5 Cols) -->
        <section class="lg:col-span-5 flex flex-col space-y-4">
            
            <!-- Live Quote Card -->
            <div class="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4 relative overflow-hidden">
                <div class="absolute top-0 right-0 w-48 h-48 bg-indigo-600/10 rounded-full blur-3xl pointer-events-none"></div>

                <div class="flex items-center justify-between pb-3 border-b border-slate-800">
                    <div>
                        <span class="text-[10px] font-bold tracking-wider text-indigo-400 uppercase">Live Dynamic Estimate</span>
                        <h3 class="font-bold text-white text-base" id="quote-card-title">Apex Carpet Care</h3>
                    </div>
                    <span class="px-2.5 py-1 rounded-full text-[11px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
                        <i class="fa-solid fa-lock text-[10px]"></i> Price Locked
                    </span>
                </div>

                <!-- Line Items Breakdown -->
                <div class="space-y-2.5 text-xs" id="quote-line-items">
                    <!-- Dynamic line items -->
                </div>

                <!-- Promo Code Box -->
                <div class="pt-2 border-t border-slate-800/80">
                    <div class="flex items-center gap-2">
                        <input 
                            type="text" 
                            id="promo-input" 
                            placeholder="Promo Code (e.g. SPRING20)" 
                            class="flex-1 uppercase font-mono text-xs bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white placeholder-slate-500 outline-none focus:border-indigo-500"
                        />
                        <button onclick="applyPromoCode()" class="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold transition">
                            Apply
                        </button>
                    </div>
                    <p id="promo-status" class="text-[11px] mt-1 text-emerald-400 hidden"></p>
                </div>

                <!-- Totals Section -->
                <div class="pt-3 border-t border-slate-800 space-y-1.5">
                    <div class="flex items-center justify-between text-xs text-slate-400">
                        <span>Subtotal:</span>
                        <span id="quote-subtotal" class="font-mono text-slate-300">$0.00</span>
                    </div>
                    <div id="quote-discount-row" class="hidden flex items-center justify-between text-xs text-emerald-400">
                        <span id="quote-discount-label">Discount:</span>
                        <span id="quote-discount" class="font-mono font-bold">-$0.00</span>
                    </div>
                    <div class="flex items-baseline justify-between pt-2 border-t border-slate-800/60">
                        <div>
                            <span class="text-xs text-slate-400 block">Total Guaranteed Estimate:</span>
                            <span class="text-[10px] text-slate-500" id="quote-subtitle">Includes tax & all materials</span>
                        </div>
                        <div class="text-right">
                            <span id="quote-total" class="text-2xl font-black font-mono text-white tracking-tight">$0.00</span>
                        </div>
                    </div>
                </div>

                <!-- CTA Button -->
                <button 
                    onclick="openBookingModal()"
                    id="btn-lock-booking"
                    class="w-full py-3.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-white font-bold text-sm transition shadow-lg shadow-emerald-600/30 flex items-center justify-center gap-2 cursor-pointer glow-active"
                >
                    <i class="fa-solid fa-calendar-check"></i>
                    <span>Lock In Appointment & Crew Dispatch</span>
                </button>

                <!-- Guarantee bullets -->
                <div class="grid grid-cols-2 gap-2 text-[11px] text-slate-400 pt-1">
                    <div class="flex items-center gap-1.5">
                        <i class="fa-solid fa-check text-emerald-400 text-xs"></i> 100% Satisfaction Guarantee
                    </div>
                    <div class="flex items-center gap-1.5">
                        <i class="fa-solid fa-check text-emerald-400 text-xs"></i> No-Show $50 Guarantee
                    </div>
                    <div class="flex items-center gap-1.5">
                        <i class="fa-solid fa-check text-emerald-400 text-xs"></i> Zero Hidden Travel Fees
                    </div>
                    <div class="flex items-center gap-1.5">
                        <i class="fa-solid fa-check text-emerald-400 text-xs"></i> Pay After Service Is Done
                    </div>
                </div>
            </div>

            <!-- Recent Verified Bookings Ticket Feed -->
            <div class="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-4 shadow-md space-y-2.5">
                <div class="flex items-center justify-between text-xs">
                    <span class="font-bold text-slate-300 flex items-center gap-1.5">
                        <i class="fa-solid fa-truck-fast text-indigo-400"></i> Active Dispatch Schedule
                    </span>
                    <span class="text-[10px] text-emerald-400 flex items-center gap-1">
                        <span class="h-1.5 w-1.5 rounded-full bg-emerald-400"></span> Live CRM Sync
                    </span>
                </div>
                <div class="space-y-2 text-xs" id="recent-bookings-list">
                    <div class="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/60 flex items-center justify-between">
                        <div>
                            <span class="font-semibold text-white block">Robert K. • Carpet Extraction</span>
                            <span class="text-[11px] text-slate-400">Tomorrow, Morning Window (8am-12pm)</span>
                        </div>
                        <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300">Confirmed</span>
                    </div>
                    <div class="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/60 flex items-center justify-between">
                        <div>
                            <span class="font-semibold text-white block">Elena M. • Bi-Weekly Turf Care</span>
                            <span class="text-[11px] text-slate-400">Friday, Afternoon Window (12pm-4pm)</span>
                        </div>
                        <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-500/20 text-indigo-300">Scheduled</span>
                    </div>
                </div>
            </div>

        </section>
    </main>

    <!-- Appointment Booking Modal -->
    <div id="booking-modal" class="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 hidden">
        <div class="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl animate-fade-in">
            
            <div class="p-5 border-b border-slate-800 bg-slate-950/40 flex items-center justify-between">
                <div class="flex items-center gap-2.5">
                    <div class="h-9 w-9 rounded-xl bg-emerald-600/20 border border-emerald-500/40 text-emerald-400 flex items-center justify-center text-base">
                        <i class="fa-solid fa-calendar-check"></i>
                    </div>
                    <div>
                        <h3 class="font-bold text-white text-base">Confirm Crew Dispatch</h3>
                        <p class="text-xs text-slate-400" id="modal-service-desc">Lock in your reserved appointment slot</p>
                    </div>
                </div>
                <button onclick="closeBookingModal()" class="text-slate-400 hover:text-white transition text-lg">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>

            <!-- Booking Form -->
            <form id="booking-form" onsubmit="handleBookingSubmit(event)" class="p-5 space-y-4 text-xs">
                
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                        <label class="block text-slate-300 font-medium mb-1">Your Full Name *</label>
                        <input type="text" id="book-name" required placeholder="e.g. Sarah Jenkins" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-white text-xs outline-none focus:border-indigo-500">
                    </div>
                    <div>
                        <label class="block text-slate-300 font-medium mb-1">Mobile Phone (SMS dispatch) *</label>
                        <input type="tel" id="book-phone" required placeholder="(555) 234-5678" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-white text-xs outline-none focus:border-indigo-500">
                    </div>
                </div>

                <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div class="sm:col-span-2">
                        <label class="block text-slate-300 font-medium mb-1">Street Address *</label>
                        <input type="text" id="book-address" required placeholder="1428 Elm Ridge Rd" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-white text-xs outline-none focus:border-indigo-500">
                    </div>
                    <div>
                        <label class="block text-slate-300 font-medium mb-1">ZIP Code *</label>
                        <input type="text" id="book-zip" required placeholder="80202" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-white text-xs outline-none focus:border-indigo-500">
                    </div>
                </div>

                <!-- Preferred Date & Window -->
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                        <label class="block text-slate-300 font-medium mb-1">Service Date *</label>
                        <input type="date" id="book-date" required class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-white text-xs outline-none focus:border-indigo-500">
                    </div>
                    <div>
                        <label class="block text-slate-300 font-medium mb-1">Preferred Time Window *</label>
                        <select id="book-window" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-white text-xs outline-none focus:border-indigo-500">
                            <option value="morning">Morning (8:00 AM - 12:00 PM)</option>
                            <option value="afternoon">Afternoon (12:00 PM - 4:00 PM)</option>
                            <option value="evening">Late Afternoon (4:00 PM - 7:00 PM)</option>
                        </select>
                    </div>
                </div>

                <div>
                    <label class="block text-slate-300 font-medium mb-1">Special Access Notes / Pet Instructions</label>
                    <textarea id="book-notes" rows="2" placeholder="e.g. Side gate code #4412, friendly golden retriever inside..." class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-white text-xs outline-none focus:border-indigo-500"></textarea>
                </div>

                <!-- Price confirmation summary -->
                <div class="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between">
                    <div>
                        <span class="text-[11px] text-slate-400 block">Total Due Upon Service:</span>
                        <span class="font-bold text-slate-200 text-xs">Zero upfront deposit required</span>
                    </div>
                    <span id="modal-price-display" class="font-mono font-black text-xl text-emerald-400">$0.00</span>
                </div>

                <button 
                    type="submit" 
                    id="modal-submit-btn"
                    class="w-full py-3 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-xs uppercase tracking-wider transition shadow-lg shadow-emerald-600/30 flex items-center justify-center gap-2"
                >
                    <i class="fa-solid fa-circle-check"></i>
                    <span>Confirm & Schedule Dispatch</span>
                </button>
            </form>

            <!-- Success Confirmation Screen (hidden initially) -->
            <div id="booking-success-view" class="p-6 text-center space-y-4 hidden">
                <div class="h-16 w-16 mx-auto rounded-full bg-emerald-500/20 border border-emerald-500/40 text-emerald-400 flex items-center justify-center text-2xl">
                    <i class="fa-solid fa-check"></i>
                </div>
                <div class="space-y-1">
                    <h3 class="text-lg font-bold text-white">Appointment Confirmed!</h3>
                    <p class="text-xs text-slate-400" id="success-confirmation-code">Confirmation #: APX-CAR-849201</p>
                </div>
                <div class="p-4 rounded-xl bg-slate-950 border border-slate-800 text-left text-xs space-y-2">
                    <div class="flex justify-between">
                        <span class="text-slate-400">Technician Crew:</span>
                        <span class="font-semibold text-white">Apex Van #4 (Lead: Dave M.)</span>
                    </div>
                    <div class="flex justify-between">
                        <span class="text-slate-400">Arrival Window:</span>
                        <span class="font-semibold text-white" id="success-window">Morning (8:00 AM - 12:00 PM)</span>
                    </div>
                    <div class="flex justify-between">
                        <span class="text-slate-400">Property:</span>
                        <span class="font-semibold text-white" id="success-address">1428 Elm Ridge Rd</span>
                    </div>
                    <div class="flex justify-between pt-1 border-t border-slate-800">
                        <span class="text-slate-400">Guaranteed Amount:</span>
                        <span class="font-mono font-bold text-emerald-400" id="success-price">$135.00</span>
                    </div>
                <div class="grid grid-cols-2 gap-2 pt-1">
                    <a id="btn-add-google-cal" href="#" target="_blank" class="py-2.5 px-3 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/40 text-indigo-300 hover:text-white text-xs font-semibold transition flex items-center justify-center gap-1.5 shadow">
                        <i class="fa-brands fa-google text-indigo-400"></i> Google Calendar
                    </a>
                    <a id="btn-download-ics" href="#" download class="py-2.5 px-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold transition flex items-center justify-center gap-1.5 border border-slate-700">
                        <i class="fa-solid fa-calendar-arrow-down text-slate-400"></i> Apple / iCal (.ics)
                    </a>
                </div>

                <p class="text-[11px] text-slate-400">
                    A confirmation SMS has been dispatched. Our technician will send you a 30-minute arrival heads-up text.
                </p>
                <button onclick="closeBookingModal()" class="w-full py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-semibold text-xs transition cursor-pointer">
                    Done
                </button>
            </div>

        </div>
    </div>

        <!-- Field Service Management (FSM) & Fleet Dispatch Modal (Phase 3) -->
    <div id="fsm-modal" class="fixed inset-0 z-50 bg-slate-950/85 backdrop-blur-md flex items-center justify-center p-3 hidden">
        <div class="bg-slate-900 border border-slate-800 rounded-3xl w-full max-w-2xl overflow-hidden shadow-2xl animate-fade-in flex flex-col max-h-[85vh]">
            
            <div class="p-5 border-b border-slate-800 bg-slate-950/50 flex items-center justify-between shrink-0">
                <div class="flex items-center gap-3">
                    <div class="h-10 w-10 rounded-xl bg-purple-600/20 border border-purple-500/40 text-purple-400 flex items-center justify-center text-lg shadow">
                        <i class="fa-solid fa-truck-ramp-box"></i>
                    </div>
                    <div>
                        <div class="flex items-center gap-2">
                            <h3 class="font-bold text-white text-base">Fleet Dispatch & FSM Bridge</h3>
                            <span class="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30 text-[10px] font-bold uppercase">Phase 3</span>
                        </div>
                        <p class="text-xs text-slate-400">Technician Crew Routing, Jobber/Housecall Pro Sync & Universal Calendar Feeds</p>
                    </div>
                </div>
                <button onclick="closeFSMModal()" class="text-slate-400 hover:text-white transition text-lg cursor-pointer">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>

            <div class="p-5 overflow-y-auto space-y-5 custom-scrollbar text-xs">
                
                <!-- Live Fleet Roster -->
                <div class="space-y-2">
                    <div class="flex items-center justify-between">
                        <span class="font-bold text-slate-200 uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                            <i class="fa-solid fa-users text-purple-400"></i> Active Service Fleet
                        </span>
                        <span class="text-[11px] text-emerald-400 font-semibold">5 Crews Ready / GPS Dispatched</span>
                    </div>

                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5" id="fsm-fleet-list">
                        <!-- Fleet crews injected via JS -->
                    </div>
                </div>

                <!-- Technician Real-Time Alerts Simulator -->
                <div class="p-4 rounded-2xl bg-slate-950 border border-slate-800 space-y-3">
                    <span class="font-bold text-slate-200 uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                        <i class="fa-solid fa-bell text-amber-400"></i> Technician Dispatch Notification Triggers
                    </span>
                    <p class="text-slate-400 text-xs">
                        Trigger real-time automated SMS notifications from technicians to homeowners:
                    </p>
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        <button onclick="simulateEnRouteAlert()" id="btn-fsm-enroute" class="p-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-left transition flex items-center gap-2.5 cursor-pointer">
                            <i class="fa-solid fa-truck-fast text-indigo-400 text-base"></i>
                            <div>
                                <span class="font-bold block">30-Min En Route SMS</span>
                                <span class="text-[10px] text-slate-400">"Technician Dave is 25 mins away..."</span>
                            </div>
                        </button>
                        <button onclick="simulateCompleteAlert()" id="btn-fsm-complete" class="p-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-left transition flex items-center gap-2.5 cursor-pointer">
                            <i class="fa-solid fa-circle-check text-emerald-400 text-base"></i>
                            <div>
                                <span class="font-bold block">Service Completed Alert</span>
                                <span class="text-[10px] text-slate-400">"Job done! View receipt & review..."</span>
                            </div>
                        </button>
                    </div>
                    <div id="fsm-alert-response" class="hidden p-3 rounded-xl bg-emerald-950/50 border border-emerald-800/80 text-emerald-200 text-xs font-mono"></div>
                </div>

                <!-- Third-Party FSM Connectors -->
                <div class="p-4 rounded-2xl bg-slate-950/60 border border-slate-800/80 space-y-2.5">
                    <div class="flex items-center justify-between">
                        <span class="font-bold text-slate-300 text-xs flex items-center gap-1.5">
                            <i class="fa-solid fa-network-wired text-indigo-400"></i> Field Service Management (FSM) Connectors
                        </span>
                        <span class="text-[10px] text-emerald-400 font-bold bg-emerald-500/20 px-2 py-0.5 rounded border border-emerald-500/30">Webhook Sync Active</span>
                    </div>
                    <div class="grid grid-cols-3 gap-2 text-center text-xs">
                        <div class="p-3 rounded-xl bg-slate-900 border border-slate-800">
                            <span class="font-bold text-white block">Jobber</span>
                            <span class="text-[10px] text-emerald-400">Jobs & Quotes Sync</span>
                        </div>
                        <div class="p-3 rounded-xl bg-slate-900 border border-slate-800">
                            <span class="font-bold text-white block">Housecall Pro</span>
                            <span class="text-[10px] text-emerald-400">Customer & Schedule</span>
                        </div>
                        <div class="p-3 rounded-xl bg-slate-900 border border-slate-800">
                            <span class="font-bold text-white block">ServiceTitan</span>
                            <span class="text-[10px] text-emerald-400">Enterprise Dispatch</span>
                        </div>
                    </div>
                </div>

            </div>
            
            <div class="p-4 border-t border-slate-800 bg-slate-950/60 text-right shrink-0">
                <button onclick="closeFSMModal()" class="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold transition cursor-pointer">
                    Close
                </button>
            </div>

        </div>
    </div>

<!-- Virtual Smartphone & Telephony Simulator Modal (Phase 2) -->
    <div id="phone-simulator-modal" class="fixed inset-0 z-50 bg-slate-950/85 backdrop-blur-md flex items-center justify-center p-3 hidden">
        <div class="relative bg-slate-950 border-4 border-slate-700/80 rounded-[42px] w-full max-w-[420px] shadow-2xl overflow-hidden flex flex-col h-[740px] ring-1 ring-slate-800">
            
            <!-- Phone Notch & Dynamic Island -->
            <div class="bg-slate-900 px-6 pt-3 pb-2 flex items-center justify-between text-white text-[11px] select-none border-b border-slate-800/80 shrink-0">
                <span class="font-bold">9:41</span>
                <div class="h-4 w-24 bg-black rounded-full flex items-center justify-center gap-1.5 border border-slate-800">
                    <span class="h-2 w-2 rounded-full bg-slate-900"></span>
                    <span class="h-1.5 w-1.5 rounded-full bg-emerald-500/80"></span>
                </div>
                <div class="flex items-center gap-1.5 text-slate-400">
                    <i class="fa-solid fa-signal text-[10px]"></i>
                    <i class="fa-solid fa-wifi text-[10px]"></i>
                    <i class="fa-solid fa-battery-full text-xs text-white"></i>
                </div>
            </div>

            <!-- Phone Top Contact Header -->
            <div class="bg-slate-900/90 px-4 py-2.5 border-b border-slate-800 flex items-center justify-between shrink-0">
                <div class="flex items-center gap-2.5">
                    <div class="h-9 w-9 rounded-full bg-gradient-to-tr from-indigo-600 to-fuchsia-600 flex items-center justify-center text-white text-xs font-bold shadow">
                        A
                    </div>
                    <div>
                        <div class="flex items-center gap-1.5">
                            <span class="font-bold text-xs text-white">Apex Home Services</span>
                            <span class="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
                        </div>
                        <span class="text-[10px] text-slate-400">(800) 555-APEX • Verified</span>
                    </div>
                </div>
                <button onclick="closePhoneSimulator()" class="h-8 w-8 rounded-full bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white flex items-center justify-center transition text-xs cursor-pointer">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>

            <!-- Simulator Tab Selector -->
            <div class="bg-slate-900/60 p-1.5 border-b border-slate-800 flex items-center gap-1 text-[11px] font-semibold shrink-0">
                <button onclick="switchSimTab('sms')" id="sim-tab-sms" class="flex-1 py-1.5 rounded-lg bg-indigo-600 text-white transition text-center flex items-center justify-center gap-1.5 shadow cursor-pointer">
                    <i class="fa-solid fa-comment-sms"></i> 2-Way SMS
                </button>
                <button onclick="switchSimTab('missed')" id="sim-tab-missed" class="flex-1 py-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition text-center flex items-center justify-center gap-1.5 cursor-pointer">
                    <i class="fa-solid fa-phone-slash"></i> Missed Call
                </button>
                <button onclick="switchSimTab('voice')" id="sim-tab-voice" class="flex-1 py-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition text-center flex items-center justify-center gap-1.5 cursor-pointer">
                    <i class="fa-solid fa-headset"></i> Voice AI
                </button>
            </div>

            <!-- Tab 1: 2-Way SMS Container -->
            <div id="sim-view-sms" class="flex-1 flex flex-col overflow-hidden bg-slate-950">
                <div class="p-2 bg-slate-900/40 text-center text-[10px] text-slate-500 border-b border-slate-900">
                    Encrypted 2-Way SMS via Twilio Gateway (+1 303-555-0199)
                </div>
                <div id="sim-sms-stream" class="flex-1 p-3 overflow-y-auto space-y-2.5 custom-scrollbar text-xs">
                    <!-- SMS messages populated here -->
                </div>
                <!-- Quick Suggestion Buttons -->
                <div class="p-2 bg-slate-900/80 border-t border-slate-800/80 flex items-center gap-1.5 overflow-x-auto custom-scrollbar shrink-0">
                    <button onclick="sendSimSMS('Need 3 bedrooms carpet cleaned with pet urine stains')" class="px-2 py-1 rounded-md bg-slate-800 hover:bg-indigo-600 text-slate-300 hover:text-white text-[10px] whitespace-nowrap transition cursor-pointer">
                        🧽 3 Beds + Pet
                    </button>
                    <button onclick="sendSimSMS('1428 Elm St, 80202. Book for Saturday morning!')" class="px-2 py-1 rounded-md bg-slate-800 hover:bg-emerald-600 text-slate-300 hover:text-white text-[10px] whitespace-nowrap transition cursor-pointer">
                        📅 Text-to-Book (Elm St)
                    </button>
                    <button onclick="sendSimSMS('I need bi-weekly mowing for 0.5 acre yard')" class="px-2 py-1 rounded-md bg-slate-800 hover:bg-indigo-600 text-slate-300 hover:text-white text-[10px] whitespace-nowrap transition cursor-pointer">
                        🌿 0.5 Acre Lawn
                    </button>
                    <button onclick="sendSimSMS('EMERGENCY: Active roof leak in my kitchen right now!')" class="px-2 py-1 rounded-md bg-rose-900/60 hover:bg-rose-700 text-rose-200 text-[10px] whitespace-nowrap transition cursor-pointer">
                        ⚠️ Roof Leak
                    </button>
                </div>
                <!-- SMS Input Form -->
                <form onsubmit="handleSimSMSSubmit(event)" class="p-2.5 bg-slate-900 border-t border-slate-800 flex items-center gap-2 shrink-0">
                    <input type="text" id="sim-sms-input" placeholder="Text message to Apex..." class="flex-1 bg-slate-950 border border-slate-800 rounded-full px-3.5 py-2 text-xs text-white outline-none focus:border-indigo-500">
                    <button type="submit" class="h-8 w-8 rounded-full bg-indigo-600 hover:bg-indigo-500 text-white flex items-center justify-center transition text-xs shrink-0 cursor-pointer">
                        <i class="fa-solid fa-arrow-up"></i>
                    </button>
                </form>
            </div>

            <!-- Tab 2: Missed-Call Speed-to-Lead Container -->
            <div id="sim-view-missed" class="flex-1 flex flex-col p-6 items-center justify-between text-center bg-gradient-to-b from-slate-900 to-slate-950 hidden">
                <div class="space-y-2 mt-4">
                    <div class="h-16 w-16 mx-auto rounded-full bg-amber-500/20 border border-amber-500/40 text-amber-400 flex items-center justify-center text-2xl shadow-lg">
                        <i class="fa-solid fa-phone-slash"></i>
                    </div>
                    <h4 class="font-bold text-base text-white">Speed-to-Lead Missed Call</h4>
                    <p class="text-xs text-slate-400 max-w-xs">
                        62% of homeowners hire whichever contractor calls or texts first. Test the instant auto-recovery SMS!
                    </p>
                </div>

                <div id="missed-call-status-box" class="w-full p-4 rounded-2xl bg-slate-900 border border-slate-800 space-y-2">
                    <div class="flex items-center justify-between text-xs">
                        <span class="text-slate-400">Caller ID:</span>
                        <span class="font-mono font-semibold text-slate-200">+1 (303) 555-0199</span>
                    </div>
                    <div class="flex items-center justify-between text-xs">
                        <span class="text-slate-400">Call Status:</span>
                        <span id="missed-status-badge" class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300">Ready to Trigger</span>
                    </div>
                    <div id="missed-result-alert" class="hidden p-3 rounded-xl bg-emerald-950/60 border border-emerald-800/80 text-left text-xs space-y-1 text-emerald-200">
                        <span class="font-bold text-white block"><i class="fa-solid fa-bolt text-amber-400"></i> Speed-to-Lead Dispatched!</span>
                        <p id="missed-result-body" class="text-[11px] text-slate-300 font-mono"></p>
                    </div>
                </div>

                <div class="w-full space-y-2">
                    <button onclick="triggerSimMissedCall()" id="btn-trigger-missed" class="w-full py-3.5 rounded-xl bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 text-white font-bold text-xs uppercase tracking-wider transition shadow-lg shadow-amber-600/20 flex items-center justify-center gap-2 cursor-pointer">
                        <i class="fa-solid fa-phone-volume"></i>
                        <span>Simulate Homeowner Missed Call</span>
                    </button>
                    <button onclick="switchSimTab('sms')" class="text-xs text-indigo-400 hover:text-indigo-300 transition cursor-pointer">
                        View resulting 2-way SMS thread →
                    </button>
                </div>
            </div>

            <!-- Tab 3: Voice AI Caller Container -->
            <div id="sim-view-voice" class="flex-1 flex flex-col p-5 items-center justify-between text-center bg-gradient-to-b from-slate-900 to-slate-950 hidden">
                <div class="space-y-1 mt-2">
                    <div class="h-16 w-16 mx-auto rounded-full bg-emerald-500/20 border border-emerald-500/40 text-emerald-400 flex items-center justify-center text-2xl shadow-lg relative">
                        <i class="fa-solid fa-headset"></i>
                        <span class="absolute -top-1 -right-1 flex h-4 w-4">
                            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                            <span class="relative inline-flex rounded-full h-4 w-4 bg-emerald-500 text-[9px] text-white font-bold items-center justify-center">AI</span>
                        </span>
                    </div>
                    <h4 class="font-bold text-sm text-white">Amber • Voice AI Receptionist</h4>
                    <p class="text-[11px] text-slate-400">Twilio Speech Recognition + Polly Voice Synthesis</p>
                </div>

                <!-- Live Voice Speech Box -->
                <div class="w-full p-3.5 rounded-2xl bg-slate-900/90 border border-slate-800 text-left space-y-2 text-xs">
                    <div class="flex items-center justify-between text-[11px] text-slate-400 pb-1 border-b border-slate-800">
                        <span>Audio Speech Output:</span>
                        <label class="flex items-center gap-1.5 cursor-pointer text-indigo-300 hover:text-indigo-200">
                            <input type="checkbox" id="chk-audio-speak" checked class="rounded bg-slate-800 border-slate-700">
                            <span class="text-[10px]">🔊 Play Audio</span>
                        </label>
                    </div>
                    <div id="voice-spoken-output" class="p-3 rounded-xl bg-slate-950 text-slate-200 text-xs italic leading-relaxed min-h-[70px] flex items-center">
                        "Thank you for calling Apex Home Services! I am Amber. Are you calling for carpet cleaning, lawn care, or roofing today?"
                    </div>
                </div>

                <!-- Spoken Prompt Buttons -->
                <div class="w-full space-y-1.5">
                    <span class="text-[11px] text-slate-400 block font-medium">Say or Click What Homeowner Speaks:</span>
                    <div class="grid grid-cols-1 gap-1.5 text-xs">
                        <button onclick="sendSimVoice('Can I get an estimate for 3 rooms carpet cleaning with pet stains?')" class="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-left transition flex items-center gap-2 cursor-pointer">
                            <i class="fa-solid fa-microphone text-indigo-400 text-xs"></i>
                            <span class="truncate">"Estimate for 3 rooms carpet + pets"</span>
                        </button>
                        <button onclick="sendSimVoice('How much do you charge for bi-weekly lawn care on a half acre?')" class="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-left transition flex items-center gap-2 cursor-pointer">
                            <i class="fa-solid fa-microphone text-emerald-400 text-xs"></i>
                            <span class="truncate">"How much for bi-weekly half acre lawn?"</span>
                        </button>
                        <button onclick="sendSimVoice('EMERGENCY: Water is leaking through my ceiling light fixture right now!')" class="p-2 rounded-lg bg-rose-950/40 hover:bg-rose-900/60 text-rose-200 border border-rose-800/60 text-left transition flex items-center gap-2 cursor-pointer">
                            <i class="fa-solid fa-triangle-exclamation text-rose-400 text-xs"></i>
                            <span class="truncate">"EMERGENCY: Water leaking through ceiling!"</span>
                        </button>
                    </div>
                </div>

            </div>

        </div>
    </div>

    <script>
        const API_PREFIX = "{api_prefix}";
        let currentTrade = "carpet_cleaning";
        let conversationId = "conv_" + Math.random().toString(36).substring(2, 10);
        let conversationHistory = [];
        let currentQuote = null;
        let homeownerInfo = {};
        let activePromoCode = "";

        // Set default booking date to tomorrow
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        document.getElementById('book-date').value = tomorrow.toISOString().split('T')[0];

        // Initial greet
        window.addEventListener('DOMContentLoaded', () => {
            switchTrade('carpet_cleaning');
        });

        function switchTrade(trade) {
            currentTrade = trade;
            
            // Update Tab UI
            ['carpet_cleaning', 'lawn_care', 'roofing'].forEach(t => {
                const tab = document.getElementById('tab-' + t);
                const mTab = document.getElementById('m-tab-' + t);
                if (t === trade) {
                    if (tab) {
                        tab.className = "px-3.5 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-2 bg-indigo-600 text-white shadow";
                    }
                    if (mTab) {
                        mTab.className = "font-semibold text-indigo-400 flex items-center gap-1";
                    }
                } else {
                    if (tab) {
                        tab.className = "px-3.5 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-2 text-slate-400 hover:text-white hover:bg-slate-800/60";
                    }
                    if (mTab) {
                        mTab.className = "font-semibold text-slate-400 flex items-center gap-1";
                    }
                }
            });

            const titles = {
                carpet_cleaning: "Master Carpet & Upholstery Care",
                lawn_care: "Turf & Estate Lawn Maintenance",
                roofing: "Elite Roofing & Exterior Defense"
            };
            document.getElementById('agent-current-trade-desc').innerText = titles[trade] || "Home Services";

            // Recalculate baseline quote
            fetchBaselineQuote();

            // Clear chat and introduce trade
            document.getElementById('chat-stream').innerHTML = "";
            conversationHistory = [];

            if (trade === 'carpet_cleaning') {
                appendAssistantMessage(
                    "Hello! I'm Amber with Apex Carpet Care. 🧽 How many rooms or hallways would you like deep steam cleaned? (Be sure to let me know if you have any pets or high-traffic stains!)",
                    ["3 Bedrooms + Hallway", "Add Pet Urine / Odor Treatment", "Need Stairs Cleaned", "What is your dry time?"]
                );
            } else if (trade === 'lawn_care') {
                appendAssistantMessage(
                    "Hi there! Welcome to Apex Lawn Care. 🌿 What size is your yard, and would you prefer weekly maintenance (15% off) or bi-weekly mowing? We include crisp driveway edging and blow-off with every visit!",
                    ["Quarter Acre (< 0.25)", "Half Acre (0.25 - 0.50)", "Full Acre Yard", "Add Core Aeration & Overseed"]
                );
            } else {
                appendAssistantMessage(
                    "Hello! I'm Amber with Apex Roofing & Exterior Defense. 🏠 Are you noticing an active ceiling leak, checking on storm/hail damage, or interested in our Complimentary 21-Point Roof & Attic Health Inspection?",
                    ["Schedule Free Inspection", "⚠️ Active Leak / Emergency", "Hail / Wind Damage Claim", "Full Roof Replacement Estimate"]
                );
            }
        }

        async function fetchBaselineQuote() {
            try {
                const res = await fetch(`${API_PREFIX}/api/v1/residential/quote`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        trade: currentTrade,
                        promo_code: activePromoCode
                    })
                });
                const data = await res.json();
                updateQuoteDisplay(data);
            } catch (err) {
                console.error("Quote fetch error", err);
            }
        }

        function updateQuoteDisplay(quote) {
            currentQuote = quote;
            document.getElementById('quote-card-title').innerText = quote.trade_title || "Upfront Estimate";
            document.getElementById('quote-subtotal').innerText = `$${quote.subtotal.toFixed(2)}`;
            
            if (quote.discount_amount > 0) {
                document.getElementById('quote-discount-row').classList.remove('hidden');
                document.getElementById('quote-discount-label').innerText = quote.discount_label || "Discount:";
                document.getElementById('quote-discount').innerText = `-$${quote.discount_amount.toFixed(2)}`;
            } else {
                document.getElementById('quote-discount-row').classList.add('hidden');
            }

            if (quote.is_range && quote.range_low && quote.range_high) {
                document.getElementById('quote-total').innerText = `$${quote.range_low.toLocaleString()} - $${quote.range_high.toLocaleString()}`;
            } else {
                document.getElementById('quote-total').innerText = `$${quote.total_estimate.toFixed(2)}`;
            }

            document.getElementById('modal-price-display').innerText = document.getElementById('quote-total').innerText;

            // Render line items
            const container = document.getElementById('quote-line-items');
            container.innerHTML = "";
            quote.line_items.forEach(item => {
                const row = document.createElement('div');
                row.className = "flex items-start justify-between gap-2 p-2 rounded-lg bg-slate-950/40 border border-slate-800/40";
                row.innerHTML = `
                    <div class="flex-1">
                        <span class="font-semibold text-slate-200 block">${item.title}</span>
                        <span class="text-[11px] text-slate-400">${item.description}</span>
                    </div>
                    <span class="font-mono font-bold text-slate-200 shrink-0">${item.total > 0 ? '$' + item.total.toFixed(2) : 'FREE'}</span>
                `;
                container.appendChild(row);
            });

            // Emergency Banner
            const emergencyBanner = document.getElementById('emergency-banner');
            if (quote.emergency_flag) {
                emergencyBanner.classList.remove('hidden');
                document.getElementById('emergency-banner-text').innerText = quote.emergency_message || "Active leak priority flagged!";
            } else {
                emergencyBanner.classList.add('hidden');
            }
        }

        async function handleUserSubmit(e) {
            if (e) e.preventDefault();
            const input = document.getElementById('chat-input');
            const message = input.value.trim();
            if (!message) return;

            input.value = "";
            appendUserMessage(message);

            // Show typing indicator
            const typingId = appendTypingIndicator();

            try {
                const res = await fetch(`${API_PREFIX}/api/v1/residential/chat`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        message: message,
                        conversation_id: conversationId,
                        trade: currentTrade,
                        history: conversationHistory,
                        current_quote: currentQuote,
                        homeowner_info: homeownerInfo
                    })
                });
                const data = await res.json();
                removeTypingIndicator(typingId);

                // Update state
                if (data.homeowner_info) {
                    homeownerInfo = data.homeowner_info;
                    if (homeownerInfo.phone) document.getElementById('book-phone').value = homeownerInfo.phone;
                    if (homeownerInfo.zip_code) document.getElementById('book-zip').value = homeownerInfo.zip_code;
                }

                if (data.current_quote) {
                    updateQuoteDisplay(data.current_quote);
                }

                appendAssistantMessage(data.reply, data.quick_replies || []);

                if (data.suggested_action === 'open_booking_modal' || data.suggested_action === 'open_emergency_booking') {
                    setTimeout(() => openBookingModal(), 1200);
                }
            } catch (err) {
                console.error("Chat error", err);
                removeTypingIndicator(typingId);
                appendAssistantMessage("I'm having trouble connecting right now, but you can book directly using the green 'Book Crew' button above!");
            }
        }

        function appendUserMessage(text) {
            conversationHistory.push({ role: "user", content: text });
            const stream = document.getElementById('chat-stream');
            const msg = document.createElement('div');
            msg.className = "flex justify-end";
            msg.innerHTML = `
                <div class="bg-indigo-600 text-white text-xs px-4 py-2.5 rounded-2xl rounded-tr-sm max-w-[85%] sm:max-w-[75%] shadow-md leading-relaxed">
                    ${escapeHtml(text)}
                </div>
            `;
            stream.appendChild(msg);
            stream.scrollTop = stream.scrollHeight;
        }

        function appendAssistantMessage(text, quickReplies = []) {
            conversationHistory.push({ role: "assistant", content: text });
            const stream = document.getElementById('chat-stream');
            const msg = document.createElement('div');
            msg.className = "flex items-start gap-2.5";
            msg.innerHTML = `
                <div class="h-8 w-8 rounded-full bg-gradient-to-tr from-indigo-500 to-fuchsia-500 flex items-center justify-center text-white text-xs font-bold shrink-0 mt-0.5 shadow">
                    A
                </div>
                <div class="bg-slate-800 text-slate-100 text-xs px-4 py-3 rounded-2xl rounded-tl-sm max-w-[88%] sm:max-w-[80%] shadow border border-slate-700/60 leading-relaxed">
                    ${formatMarkdown(text)}
                </div>
            `;
            stream.appendChild(msg);
            stream.scrollTop = stream.scrollHeight;

            // Render quick replies
            const qrContainer = document.getElementById('quick-replies-container');
            qrContainer.innerHTML = "";
            if (quickReplies && quickReplies.length > 0) {
                quickReplies.forEach(qr => {
                    const btn = document.createElement('button');
                    btn.className = "px-3 py-1.5 rounded-full bg-slate-800 hover:bg-indigo-600/30 hover:border-indigo-500 text-slate-300 hover:text-white border border-slate-700 text-xs whitespace-nowrap transition cursor-pointer shrink-0";
                    btn.innerText = qr;
                    btn.onclick = () => {
                        document.getElementById('chat-input').value = qr;
                        handleUserSubmit();
                    };
                    qrContainer.appendChild(btn);
                });
            }
        }

        function appendTypingIndicator() {
            const stream = document.getElementById('chat-stream');
            const id = "typing-" + Date.now();
            const msg = document.createElement('div');
            msg.id = id;
            msg.className = "flex items-center gap-2 text-xs text-slate-400 italic py-1 px-2";
            msg.innerHTML = `
                <span class="flex h-2 w-2 rounded-full bg-indigo-400 animate-ping"></span>
                <span>Amber is calculating your estimate...</span>
            `;
            stream.appendChild(msg);
            stream.scrollTop = stream.scrollHeight;
            return id;
        }

        function removeTypingIndicator(id) {
            const el = document.getElementById(id);
            if (el) el.remove();
        }

        function loadScenario(type) {
            if (type === 'carpet_sarah') {
                switchTrade('carpet_cleaning');
                document.getElementById('chat-input').value = "Hi! I have 3 bedrooms and a hallway that need steam cleaning. We have 2 dogs so there are pet urine spots that need deep enzyme odor removal. Can you do Saturday morning?";
                document.getElementById('book-name').value = "Sarah Jenkins";
                document.getElementById('book-phone').value = "(303) 555-0192";
                document.getElementById('book-address').value = "4182 Ridgeview Dr";
                document.getElementById('book-zip').value = "80202";
                setTimeout(() => handleUserSubmit(), 300);
            } else if (type === 'lawn_marcus') {
                switchTrade('lawn_care');
                document.getElementById('chat-input').value = "Looking to start regular lawn mowing for our 0.5 acre yard on a bi-weekly schedule. We also want to add core aeration and overseeding this month.";
                document.getElementById('book-name').value = "Marcus Vance";
                document.getElementById('book-phone').value = "(720) 555-4819";
                document.getElementById('book-address').value = "819 Willowbrook Lane";
                document.getElementById('book-zip').value = "80014";
                setTimeout(() => handleUserSubmit(), 300);
            } else if (type === 'roof_dave') {
                switchTrade('roofing');
                document.getElementById('chat-input').value = "EMERGENCY: We had heavy rain yesterday and now have water dripping actively through our kitchen ceiling light fixture! We need someone out today to tarp and inspect.";
                document.getElementById('book-name').value = "Dave Robinson";
                document.getElementById('book-phone').value = "(303) 555-9921";
                document.getElementById('book-address').value = "1042 Evergreen Terrace";
                document.getElementById('book-zip').value = "80123";
                setTimeout(() => handleUserSubmit(), 300);
            }
        }

        function resetConversation() {
            conversationId = "conv_" + Math.random().toString(36).substring(2, 10);
            homeownerInfo = {};
            switchTrade(currentTrade);
        }

        function applyPromoCode() {
            const code = document.getElementById('promo-input').value.trim().toUpperCase();
            if (!code) return;
            activePromoCode = code;
            fetchBaselineQuote().then(() => {
                const status = document.getElementById('promo-status');
                if (currentQuote && currentQuote.discount_amount > 0) {
                    status.innerText = `Promo code '${code}' applied successfully!`;
                    status.className = "text-[11px] mt-1 text-emerald-400";
                    status.classList.remove('hidden');
                } else {
                    status.innerText = "Invalid promo code. Try 'SPRING20' or 'NEIGHBOR10'";
                    status.className = "text-[11px] mt-1 text-rose-400";
                    status.classList.remove('hidden');
                }
            });
        }

        function openBookingModal() {
            document.getElementById('booking-modal').classList.remove('hidden');
            document.getElementById('booking-form').classList.remove('hidden');
            document.getElementById('booking-success-view').classList.add('hidden');
            document.getElementById('modal-price-display').innerText = document.getElementById('quote-total').innerText;
            const titles = {
                carpet_cleaning: "Master Carpet Steam Extraction",
                lawn_care: "Turf Maintenance & Precision Mowing",
                roofing: "Exterior Defense & Roof Inspection"
            };
            document.getElementById('modal-service-desc').innerText = titles[currentTrade] || "Residential Service";
        }

        function closeBookingModal() {
            document.getElementById('booking-modal').classList.add('hidden');
        }

        async function handleBookingSubmit(e) {
            e.preventDefault();
            const btn = document.getElementById('modal-submit-btn');
            btn.disabled = true;
            btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Reserving Technician Slot...`;

            const bookingPayload = {
                conversation_id: conversationId,
                trade: currentTrade,
                service_summary: document.getElementById('quote-card-title').innerText,
                homeowner_name: document.getElementById('book-name').value.trim(),
                phone: document.getElementById('book-phone').value.trim(),
                address: document.getElementById('book-address').value.trim(),
                zip_code: document.getElementById('book-zip').value.trim(),
                scheduled_date: document.getElementById('book-date').value,
                time_window: document.getElementById('book-window').value,
                estimated_total: currentQuote ? currentQuote.total_estimate : 120.0,
                special_instructions: document.getElementById('book-notes').value.trim()
            };

            try {
                const res = await fetch(`${API_PREFIX}/api/v1/residential/book`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(bookingPayload)
                });
                const data = await res.json();
                
                // Show success view
                document.getElementById('booking-form').classList.add('hidden');
                document.getElementById('booking-success-view').classList.remove('hidden');
                document.getElementById('success-confirmation-code').innerText = `Confirmation #: ${data.confirmation_number}`;
                document.getElementById('success-window').innerText = data.time_window;
                document.getElementById('success-address').innerText = data.address;
                document.getElementById('success-price').innerText = `$${data.estimated_total.toFixed(2)}`;

                // Add to recent bookings widget
                const recentList = document.getElementById('recent-bookings-list');
                const newCard = document.createElement('div');
                newCard.className = "p-2.5 rounded-xl bg-emerald-950/40 border border-emerald-800/60 flex items-center justify-between animate-fade-in";
                newCard.innerHTML = `
                    <div>
                        <span class="font-semibold text-emerald-200 block">${data.homeowner_name} • ${data.trade.replace('_', ' ').toUpperCase()}</span>
                        <span class="text-[11px] text-slate-400">${data.scheduled_at} (${data.time_window})</span>
                    </div>
                    <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/30 text-emerald-300">Just Booked</span>
                `;
                recentList.prepend(newCard);

            } catch (err) {
                alert("Booking error: " + err.message);
            } finally {
                btn.disabled = false;
                btn.innerHTML = `<i class="fa-solid fa-circle-check"></i> <span>Confirm & Schedule Dispatch</span>`;
            }
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.innerText = text;
            return div.innerHTML;
        }

        function formatMarkdown(text) {
            let res = escapeHtml(text);
            res = res.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            res = res.replace(/\*(.*?)\*/g, '<em>$1</em>');
            res = res.replace(/\\n/g, '<br/>');
            return res;
        }

        // =========================================================================
        // VIRTUAL SMARTPHONE & TELEPHONY SIMULATOR JS (PHASE 2)
        // =========================================================================
        let simCurrentPhone = "+13035550199";

        function openPhoneSimulator(initialTab = 'sms') {
            document.getElementById('phone-simulator-modal').classList.remove('hidden');
            switchSimTab(initialTab);
            loadSimMessages();
        }

        function closePhoneSimulator() {
            document.getElementById('phone-simulator-modal').classList.add('hidden');
        }

        function switchSimTab(tab) {
            ['sms', 'missed', 'voice'].forEach(t => {
                const btn = document.getElementById('sim-tab-' + t);
                const view = document.getElementById('sim-view-' + t);
                if (t === tab) {
                    btn.className = "flex-1 py-1.5 rounded-lg bg-indigo-600 text-white transition text-center flex items-center justify-center gap-1.5 shadow cursor-pointer";
                    view.classList.remove('hidden');
                } else {
                    btn.className = "flex-1 py-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition text-center flex items-center justify-center gap-1.5 cursor-pointer";
                    view.classList.add('hidden');
                }
            });
        }

        async function loadSimMessages() {
            try {
                const res = await fetch(`${API_PREFIX}/api/v1/residential/simulate/messages?phone=${encodeURIComponent(simCurrentPhone)}`);
                const data = await res.json();
                renderSimSMS(data.messages || []);
            } catch (err) {
                console.error("Load sim error", err);
            }
        }

        function renderSimSMS(messages) {
            const stream = document.getElementById('sim-sms-stream');
            stream.innerHTML = "";

            if (!messages || messages.length === 0) {
                stream.innerHTML = `
                    <div class="text-center text-slate-500 py-8 space-y-1">
                        <i class="fa-solid fa-comments text-2xl text-slate-600"></i>
                        <p class="text-xs">No text messages yet.</p>
                        <p class="text-[11px] text-slate-600">Use the quick chips below or trigger a missed call!</p>
                    </div>
                `;
                return;
            }

            messages.forEach(m => {
                const row = document.createElement('div');
                if (m.sender === 'homeowner') {
                    row.className = "flex justify-end";
                    row.innerHTML = `
                        <div class="bg-indigo-600 text-white px-3.5 py-2 rounded-2xl rounded-tr-sm max-w-[80%] text-[11px] leading-relaxed shadow">
                            ${escapeHtml(m.text)}
                        </div>
                    `;
                } else {
                    row.className = "flex justify-start";
                    row.innerHTML = `
                        <div class="bg-slate-800 text-slate-200 px-3.5 py-2 rounded-2xl rounded-tl-sm max-w-[82%] text-[11px] leading-relaxed shadow border border-slate-700/60">
                            ${formatMarkdown(m.text)}
                        </div>
                    `;
                }
                stream.appendChild(row);
            });
            stream.scrollTop = stream.scrollHeight;
        }

        function sendSimSMS(text) {
            document.getElementById('sim-sms-input').value = text;
            handleSimSMSSubmit();
        }

        async function handleSimSMSSubmit(e) {
            if (e) e.preventDefault();
            const input = document.getElementById('sim-sms-input');
            const text = input.value.trim();
            if (!text) return;

            input.value = "";
            const stream = document.getElementById('sim-sms-stream');

            const userRow = document.createElement('div');
            userRow.className = "flex justify-end";
            userRow.innerHTML = `
                <div class="bg-indigo-600 text-white px-3.5 py-2 rounded-2xl rounded-tr-sm max-w-[80%] text-[11px] leading-relaxed shadow">
                    ${escapeHtml(text)}
                </div>
            `;
            stream.appendChild(userRow);
            stream.scrollTop = stream.scrollHeight;

            try {
                const res = await fetch(`${API_PREFIX}/api/v1/residential/simulate/sms`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        from_phone: simCurrentPhone,
                        body: text
                    })
                });
                const data = await res.json();
                renderSimSMS(data.messages);

                if (data.booked) {
                    fetchBaselineQuote();
                }
            } catch (err) {
                console.error("SMS simulate error", err);
            }
        }

        async function triggerSimMissedCall() {
            const btn = document.getElementById('btn-trigger-missed');
            const badge = document.getElementById('missed-status-badge');
            btn.disabled = true;
            btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Inbound Call Ringing (00:04)...`;
            badge.innerText = "Phone Ringing Unanswered";
            badge.className = "px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 animate-pulse";

            try {
                const res = await fetch(`${API_PREFIX}/api/v1/residential/simulate/missed_call`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ caller_phone: simCurrentPhone })
                });
                const data = await res.json();

                badge.innerText = "Missed Call (Speed-to-Lead Fired)";
                badge.className = "px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300";

                const alertBox = document.getElementById('missed-result-alert');
                alertBox.classList.remove('hidden');
                document.getElementById('missed-result-body').innerText = `"${data.dispatched_sms}"`;

                setTimeout(() => {
                    switchSimTab('sms');
                    renderSimSMS(data.session.messages);
                }, 1500);

            } catch (err) {
                alert("Missed call error: " + err.message);
            } finally {
                btn.disabled = false;
                btn.innerHTML = `<i class="fa-solid fa-phone-volume"></i> <span>Simulate Homeowner Missed Call</span>`;
            }
        }

        async function sendSimVoice(speechText) {
            const outBox = document.getElementById('voice-spoken-output');
            outBox.innerHTML = `<span class="italic text-slate-400"><i class="fa-solid fa-spinner fa-spin text-emerald-400"></i> Amber is analyzing spoken speech...</span>`;

            try {
                const res = await fetch(`${API_PREFIX}/api/v1/residential/simulate/voice`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        speech: speechText,
                        caller_phone: simCurrentPhone
                    })
                });
                const data = await res.json();

                outBox.innerHTML = `"${formatMarkdown(data.spoken_text)}"`;

                const shouldSpeak = document.getElementById('chk-audio-speak').checked;
                if (shouldSpeak && 'speechSynthesis' in window) {
                    window.speechSynthesis.cancel();
                    const cleanUtterance = data.spoken_text.replace(/[*#]/g, '');
                    const utterance = new SpeechSynthesisUtterance(cleanUtterance);
                    utterance.rate = 1.05;
                    utterance.pitch = 1.1;
                    window.speechSynthesis.speak(utterance);
                }

            } catch (err) {
                console.error("Voice simulate error", err);
            }
        }
    
        // =========================================================================
        // FSM & CALENDAR DISPATCH JS (PHASE 3)
        // =========================================================================
        let lastBookedAppointmentId = null;

        function openFSMModal() {
            document.getElementById('fsm-modal').classList.remove('hidden');
            loadFSMFleet();
        }

        function closeFSMModal() {
            document.getElementById('fsm-modal').classList.add('hidden');
        }

        async function loadFSMFleet() {
            const container = document.getElementById('fsm-fleet-list');
            container.innerHTML = `<span class="text-slate-400 italic">Loading fleet roster...</span>`;
            try {
                const res = await fetch(`${API_PREFIX}/api/v1/residential/fsm/crews`);
                const data = await res.json();
                container.innerHTML = "";
                (data.crews || []).forEach(c => {
                    const card = document.createElement('div');
                    card.className = "p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1";
                    card.innerHTML = `
                        <div class="flex items-center justify-between">
                            <span class="font-bold text-white">${escapeHtml(c.name)}</span>
                            <span class="text-[10px] font-bold text-amber-400 flex items-center gap-1">
                                <i class="fa-solid fa-star text-[9px]"></i> ${c.rating}
                            </span>
                        </div>
                        <p class="text-[11px] text-slate-400">Lead: <span class="text-slate-300">${escapeHtml(c.lead)}</span> • ${escapeHtml(c.vehicle)}</p>
                        <div class="flex items-center justify-between text-[10px] text-slate-500 pt-1 border-t border-slate-900">
                            <span>Trade: ${escapeHtml(c.trade.replace('_', ' ').toUpperCase())}</span>
                            <span class="text-emerald-400 font-semibold">${c.completed_jobs} Jobs Completed</span>
                        </div>
                    `;
                    container.appendChild(card);
                });
            } catch (err) {
                console.error("Fleet error", err);
            }
        }

        async function simulateEnRouteAlert() {
            const apptId = lastBookedAppointmentId || "demo_appointment";
            const resBox = document.getElementById('fsm-alert-response');
            resBox.classList.remove('hidden');
            resBox.innerHTML = `<i class="fa-solid fa-spinner fa-spin text-amber-400"></i> Dispatching 30-min en-route SMS...`;
            try {
                const res = await fetch(`${API_PREFIX}/api/v1/residential/fsm/en_route`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ appointment_id: apptId, eta_minutes: 25 })
                });
                const data = await res.json();
                if (data.success) {
                    resBox.innerHTML = `<strong>Sent:</strong> "${escapeHtml(data.message)}"`;
                } else {
                    resBox.innerHTML = `<strong>Simulated En Route SMS:</strong> "🚚 Apex Dispatch Heads-Up: Your service crew (Lead: Dave Miller) is now en route to your address! ETA: 25 minutes."`;
                }
            } catch (err) {
                resBox.innerHTML = `<strong>Simulated En Route SMS:</strong> "🚚 Apex Dispatch Heads-Up: Your service crew (Lead: Dave Miller) is now en route to your address! ETA: 25 minutes."`;
            }
        }

        async function simulateCompleteAlert() {
            const apptId = lastBookedAppointmentId || "demo_appointment";
            const resBox = document.getElementById('fsm-alert-response');
            resBox.classList.remove('hidden');
            resBox.innerHTML = `<i class="fa-solid fa-spinner fa-spin text-emerald-400"></i> Dispatching completion SMS...`;
            try {
                const res = await fetch(`${API_PREFIX}/api/v1/residential/fsm/complete`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ appointment_id: apptId })
                });
                const data = await res.json();
                if (data.success) {
                    resBox.innerHTML = `<strong>Sent:</strong> "${escapeHtml(data.message)}"`;
                } else {
                    resBox.innerHTML = `<strong>Simulated Completion SMS:</strong> "⭐ Thank you for choosing Apex Home Services! Your service is now complete. We back all work with our 100% Satisfaction Guarantee."`;
                }
            } catch (err) {
                resBox.innerHTML = `<strong>Simulated Completion SMS:</strong> "⭐ Thank you for choosing Apex Home Services! Your service is now complete. We back all work with our 100% Satisfaction Guarantee."`;
            }
        }

    </script>
</body>
</html>

"""
    return html.replace("{api_prefix}", api_prefix)
