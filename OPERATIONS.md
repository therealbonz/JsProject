# AI Sales Automation Platform — Operations & Production Runbook

This operational guide provides procedures and quick-reference commands for operating, deploying, backing up, and monitoring the AI Sales Automation Platform running on `therealbonz.com`.

---

## 1. System Architecture & Live URLs

- **Public Base URL**: `https://therealbonz.com/JsProject/`
- **Management Web Console**: `https://therealbonz.com/JsProject/console`
- **System Health & Telemetry**: `https://therealbonz.com/JsProject/health`
- **Customer Tracking Portal**: `https://therealbonz.com/JsProject/track/{po_number}`
- **Server Location**: Ubuntu VPS (`bonz@therealbonz.com`)
- **Backend Directory**: `/home/bonz/JsProject/backend`
- **Systemd Service**: `jsproject.service` (User: `bonz`, Restart: `always`)
- **Database**: PostgreSQL 16 (`ai_sales_crm`)

---

## 2. 1-Click Automated Deployment

Whenever you make code changes locally on your Windows machine, run:

```powershell
.\deploy.ps1
```
or double-click:
```cmd
deploy.bat
```

### What this does automatically:
1. Pushes commits to GitHub (`origin/main`).
2. SSHes into `therealbonz.com` and hard-resets `/home/bonz/JsProject` to `origin/main`.
3. Restarts the `uvicorn` ASGI service cleanly via `pkill -u bonz -f uvicorn`.
4. Polls the live `/health` endpoint to verify zero-downtime recovery.

---

## 3. Database Maintenance & Backups

### 1-Click Backup (Remote Dump + Local Download)
Run:
```powershell
.\backup_db.ps1
```
This dumps PostgreSQL on `therealbonz.com` using `pg_dump`, compresses it with `gzip`, stores it in `/home/bonz/backups/`, and immediately downloads a copy to your local `D:\JsProject\backups\` folder.

### Manual Remote Dump & Restore Commands
```bash
# SSH into the server
ssh bonz@therealbonz.com

# Create backup
pg_dump -U bonz ai_sales_crm | gzip > /home/bonz/backups/manual_backup.sql.gz

# Restore database from backup
gunzip -c /home/bonz/backups/manual_backup.sql.gz | psql -U bonz ai_sales_crm
```

---

## 4. Google Gemini Generative AI Configuration

The platform operates in **Dual-Engine Mode**:
1. **Live Generative AI Mode**: When a valid `GEMINI_API_KEY` is configured, Gemini 2.5 Flash powers real-time research scoring, executive closing dossiers, and customer reply triage.
2. **Deterministic Guardrail Mode**: If no key is set or Google API is unreachable, the system automatically falls back to deterministic rule engines and simulations without dropping customer requests.

### Updating the Gemini Key via Web UI
1. Navigate to `https://therealbonz.com/JsProject/console`
2. Click **Settings** in the left sidebar.
3. Locate the **Google Gemini AI Engine & Generative Models** card.
4. Enter your API key (begins with `AIzaSy...`) and select model (`gemini-2.5-flash`).
5. Click **Test Connection** to measure latency, then click **Save & Activate AI Key**.

---

## 5. Automated Verification & Regression Testing

To verify all 8 production lifecycle stages (Auth, 6-Bot DAG, CRM Lead Conversion, AI Order Filler, EDI dropship, Carrier Tracking, and Public Portal), run:

```powershell
Get-Content test_e2e_runner.py -Raw | ssh bonz@therealbonz.com "/home/bonz/JsProject/backend/.venv/bin/python -"
```

---

## 6. Service Management & Troubleshooting

```bash
# Check service logs (last 50 lines)
ssh bonz@therealbonz.com "journalctl -u jsproject -n 50 --no-pager"

# Follow logs in real-time
ssh bonz@therealbonz.com "journalctl -u jsproject -f"

# Restart application service
ssh bonz@therealbonz.com "pkill -u bonz -f uvicorn"

# Check PostgreSQL connection
ssh bonz@therealbonz.com "psql -U bonz -d ai_sales_crm -c '\dt'"
```
