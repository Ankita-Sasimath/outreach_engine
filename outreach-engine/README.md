# Outreach Engine

Production-style outreach pipeline.

## What it does
Provide a single company domain (e.g. `zoho.com`). The system runs a 4-stage automated pipeline:
1. Ocean.io — find lookalike companies
2. Prospeo — find decision makers (CEO, CTO, Founder, VP Engineering, Head of Product)
3. Eazyreach — resolve verified work emails
4. Generate personalized outreach email and send via Brevo

A confirmation step is shown before sending.

## Tech
- Backend: FastAPI, SQLAlchemy, SQLite
- Frontend: HTML/CSS/JS
- HTTP: httpx

## Setup
### 1) Create a virtual environment
```bash
python -m venv .venv
```
Activate:
- Windows (PowerShell):
```bash
.\.venv\Scripts\Activate.ps1
```

### 2) Install dependencies
```bash
pip install -r requirements.txt
```

### 3) Configure environment variables
Copy `.env.example` to `.env`.

```bash
cp .env.example .env
```

### 4) Run migrations (no external tool required)
This project creates tables automatically on startup.

### 5) Start server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open: `http://localhost:8000`

## API
POST `/api/pipeline/run` with JSON:
```json
{ "domain": "zoho.com" }
```

POST `/api/pipeline/confirm-send` with JSON:
```json
{ "domain": "zoho.com", "send": true }
```

## Notes
- Real provider APIs require valid API keys.
- This code includes robust timeouts, retries, and graceful failures per company.

