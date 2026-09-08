# AI Sales Automation Platform (B2B SaaS)

An enterprise-grade, multi-tenant AI sales platform built with **FastAPI**, **PostgreSQL** (with local-first fallback), and **Google Gemini AI**.

The platform automates the B2B sales lifecycle across account research, lead qualification, catalog-grounded cold outreach, and inbound reply processing while enforcing strict **Human-in-the-Loop (HITL)** guardrails against hallucinated pricing, unauthorized discounts, and rogue commitments.

---

## 🌟 Key Features

1. **Multi-Tenant SaaS from Day One**:
   - Strict tenant isolation across all organizations, users, leads, catalogs, conversations, and audit streams.
   - Role-Based Access Control (`super_admin`, `admin`, `sales_manager`, `sales_rep`, `viewer`).

2. **Google Gemini Sales Agent Engine**:
   - **Lead Research & ICP Scoring**: Extracts pain points, purchasing angles, and scores leads.
   - **Catalog-Grounded Outreach Drafting**: Generates hyper-personalized cold emails referencing only authorized catalog items and approved pricing.
   - **Inbound Intent Classification & Sentiment Analysis**: Detects inquiries, out-of-office, objections, competitor comparisons, and opt-outs.

3. **Human-in-the-Loop (HITL) & Hallucination Guardrails**:
   - Hard policy enforcement in code: Any discount request exceeding the tenant's configured `max_discount_pct` (default: 10%) immediately **halts autonomous execution**.
   - Creates a `HumanAssistanceRequest` in the manager queue with context, situation summary, and recommended action.
   - Allows sales managers to **Approve**, **Reject**, or **Take Over** conversations in real time.

4. **Internal CRM & Pipeline Engine**:
   - Companies, Contacts, Leads, Products, and Opportunities.
   - Visual Kanban pipeline stages: `new` ➔ `researching` ➔ `ready_contact` ➔ `contacted` ➔ `connected` ➔ `qualified` ➔ `proposal` ➔ `negotiation` ➔ `won` / `lost`.

5. **Local-First & Production-Ready**:
   - Works immediately out-of-the-box with an embedded local database and simulation fallbacks.
   - Plugs directly into PostgreSQL via `docker compose up -d` or native Postgres.
   - Includes a built-in interactive Web Console at `http://127.0.0.1:8000/`.

---

## 🚀 Quick Start Guide

### 1. Launch the Server
You can start the local platform with either:
- **Option A (Double Click)**: Run `run_backend.bat` in the root folder.
- **Option B (PowerShell)**:
  ```powershell
  .\run_backend.ps1
  ```
- **Option C (Manual Python)**:
  ```powershell
  cd backend
  .venv\Scripts\uvicorn main:app --host 127.0.0.1 --port 8000 --reload
  ```

### 2. Access the Interactive Interfaces
- **Interactive Web Console**: Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) in your browser.
- **Swagger / OpenAPI Documentation**: Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

---

## 🔑 Configuring Google Gemini & PostgreSQL

Edit `backend/.env`:

### 1. Enable Live Google Gemini Calls
Add your Gemini API key from [Google AI Studio](https://aistudio.google.com/):
```env
GEMINI_API_KEY="your_actual_gemini_api_key_here"
GEMINI_MODEL="gemini-2.5-flash"
```
*(If left empty, the platform automatically runs in Local Simulation Mode with context-aware responses and active deterministic guardrail checks).*

### 2. Connect PostgreSQL via Docker
Run the provided `docker-compose.yml` in the project root:
```bash
docker compose up -d
```
Update `backend/.env`:
```env
DATABASE_URL="postgresql+asyncpg://postgres:postgrespassword@localhost:5432/ai_sales_crm"
```

---

## 🧪 Running the Verification Test Suite

Run the full end-to-end integration test suite verifying multi-tenant isolation, AI lead research, email drafting, policy guardrail halting, and HITL approval:
```powershell
cd backend
.venv\Scripts\pytest -v tests/test_e2e_platform.py
```

---

## 📁 Project Architecture

```
JsProject/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── auth.py          # Register, Login, JWT tokens
│   │   │   │   ├── crm.py           # Leads, Companies, Products, Pipeline
│   │   │   │   ├── agent.py         # Gemini AI Research, Drafting, Inbound
│   │   │   │   ├── hitl.py          # Human Assistance Requests, Audit Logs
│   │   │   │   └── conversations.py # Message threads
│   │   │   └── deps.py              # Multi-tenant security context injection
│   │   ├── core/
│   │   │   ├── config.py            # Pydantic settings (.env)
│   │   │   ├── security.py          # Bcrypt hashing & PyJWT
│   │   │   └── database.py          # Async SQLAlchemy engine (Postgres + SQLite)
│   │   ├── models/                  # SQLAlchemy ORM models with TenantMixin
│   │   ├── schemas/                 # Pydantic v2 schemas
│   │   └── services/
│   │       └── gemini_service.py    # Google GenAI SDK & guardrails
│   ├── tests/
│   │   └── test_e2e_platform.py     # 100% passing E2E integration test
│   ├── requirements.txt
│   └── main.py                      # FastAPI app & local web console
├── docker-compose.yml               # Local PostgreSQL (pgvector) + Redis
├── run_backend.bat                  # One-click Windows batch launcher
├── run_backend.ps1                  # PowerShell launcher
└── README.md
```
