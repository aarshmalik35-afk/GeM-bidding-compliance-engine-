# GeM Bid Compliance Verification — Backend Prototype

FastAPI backend for the AI-powered bid compliance verification hackathon prototype.
Uses the **free-tier Gemini API** for two jobs:

1. **Document extraction** — reads uploaded PAN/GST/Udyam/EPFO documents (image or PDF)
   and pulls out the registration number, entity name, and validity date.
2. **AI summary/insight generation** — turns the structured pass/fail checks into a
   plain-English recommendation for the procurement officer.

Statutory cross-checks (GST, PAN, Udyam, EPFO, NSIC, debarment) run against a
**mock in-memory registry** (`app/mock_registry.py`) instead of live government
APIs — those need paid access or NIC/MeitY sanction you won't get before a
hackathon deadline. The function signatures are written so you can swap the
body of each `check_*()` function for a real HTTP call later without touching
anything else.

## 1. Setup

```bash
cd gem_compliance_backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Get a **free** Gemini API key at https://aistudio.google.com/app/apikey and put it in `.env`:

```
GEMINI_API_KEY=your_key_here
```

## 2. Run

```bash
uvicorn main:app --reload --port 8000
```

Interactive API docs: http://localhost:8000/docs

## 3. Endpoints

| Method | Path                     | Purpose                                                            |
|--------|--------------------------|---------------------------------------------------------------------|
| GET    | `/api/health`            | Liveness check                                                     |
| POST   | `/api/extract-documents` | Upload PAN/GST/Udyam/EPFO files → Gemini extracts structured fields |
| POST   | `/api/verify-compliance` | Runs all checks + Gemini AI summary → full compliance report       |

### Example: verify compliance (curl)

```bash
curl -X POST http://localhost:8000/api/verify-compliance \
  -F "bidder_name=ACME TECH SOLUTIONS PVT LTD" \
  -F "gstin=27AAAPL1234C1ZV" \
  -F "pan=AAAPL1234C" \
  -F "udyam_number=UDYAM-DL-01-0012345" \
  -F "epfo_code=DLCPM1234567000"
```

### Example: extract fields from an uploaded document (curl)

```bash
curl -X POST http://localhost:8000/api/extract-documents \
  -F "gst_doc=@sample_gst_certificate.pdf"
```

## 4. Demo data (already seeded in mock_registry.py)

Use these to show a clean **ELIGIBLE** bidder:

- Bidder name: `ACME TECH SOLUTIONS PVT LTD`
- GSTIN: `27AAAPL1234C1ZV`
- PAN: `AAAPL1234C`
- Udyam: `UDYAM-DL-01-0012345`
- EPFO: `DLCPM1234567000`

Use this to demo a **NOT_ELIGIBLE** (debarred) bidder:

- Bidder name: `SAMPLE ENGINEERING WORKS`
- GSTIN: `07BBBPL5678D1Z2`
- PAN: `BBBPL5678D`
- NSIC: `NSIC-REG-998877`

## 5. Project structure

```
gem_compliance_backend/
├── main.py                  # FastAPI app entry point
├── requirements.txt
├── .env.example
└── app/
    ├── config.py             # env var loading
    ├── models.py             # Pydantic request/response schemas
    ├── mock_registry.py      # simulated GST/PAN/Udyam/EPFO/NSIC/debarment DBs
    ├── gemini_service.py     # Gemini API calls (extraction + summary)
    ├── compliance_engine.py  # orchestration, scoring, status logic
    └── routes.py             # API endpoints
```

## 6. Moving beyond the hackathon prototype

- Replace each function body in `mock_registry.py` with a real API call
  (GSTN search API, NSDL/Protean PAN verification, Udyam Assist API, EPFO
  employer API, NSIC vendor database, CVC/GeM debarment list) — the
  `CheckResult` return shape doesn't need to change.
- Add persistent storage (Postgres/SQLite) for bidder submissions and reports
  instead of computing everything in-memory per request.
- Add authentication for procurement officers and audit logging of who
  reviewed which report.
- Consider caching Gemini extraction results per uploaded file hash to avoid
  re-processing identical documents.
