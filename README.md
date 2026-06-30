# Clinical Pattern Recognition and Decision Support System (Web Application + Chat bot (micro-service))

## A. Web Interface 

A web-based platform that ingests CMS synthetic claims (DE-SynPUF), cross-references them against NCCI code pair edits, and flags upcoded/unbundled claims **before payment release**.

Built for payer analytics teams with a FastAPI backend, SQLite persistence, and a React dashboard.


## Quick Start


### 1. Start the backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 2. Start the dashboard

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** and click **Run Full Pipeline**.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/api/v1/pipeline/run?use_sample=true` | Full ingest → analyze pipeline |
| POST | `/api/v1/ingest/claims?use_sample=true` | Load DE-SynPUF claims |
| POST | `/api/v1/ingest/ncci?use_sample=true` | Load NCCI code pairs |
| POST | `/api/v1/analyze` | Run detection on loaded data |
| GET | `/api/v1/flags` | List flagged claims |
| GET | `/api/v1/flags/{id}` | Single flag detail |
| GET | `/api/v1/dashboard/summary` | Dashboard KPIs |

### Example JSON response (flagged claim)

```json
{
  "id": 1,
  "flag_type": "unbundling",
  "clm_id": "CLM2001",
  "desynpuf_id": "PAT010",
  "service_date": "2009-08-01",
  "financial_risk": 18.33,
  "confidence_score": 0.95,
  "rule_id": "NCCI-PTP-99213-36415",
  "rule_description": "NCCI PTP edit: 36415 is bundled into 99213...",
  "violated_codes": ["99213", "36415"],
  "evidence": {
    "billed_codes": ["36415", "99213"],
    "column_one": "99213",
    "column_two": "36415"
  },
  "status": "open"
}
```

## Using Real CMS Data

### DE-SynPUF Claims

```bash
python scripts/download_cms_data.py
```

Or manually download from [CMS DE-SynPUF Sample 1](https://www.cms.gov/data-research/statistics-trends-and-reports/medicare-claims-synthetic-public-use-files/cms-2008-2010-data-entrepreneurs-synthetic-public-use-file-de-synpuf/de10-sample-1).

Then ingest:

```bash
curl -X POST "http://localhost:8000/api/v1/ingest/claims" \
  -F "file=@data/raw/synpuf/outpatient_claims.csv" \
  -F "limit=5000"
```

### NCCI Code Pair Edits

Download Hospital or Practitioner PTP edits from [CMS NCCI PTP Edits](https://www.cms.gov/medicare/coding-billing/national-correct-coding-initiative-ncci-edits/medicare-ncci-procedure-procedure-ptp-edits) (AMA license acceptance required).

```bash
curl -X POST "http://localhost:8000/api/v1/ingest/ncci" \
  -F "file=@data/raw/ncci/hospital_ptp.csv"
```

## Detection Logic

### Unbundling (Step 3)
- Groups claim lines by **patient ID + date of service**
- Scans all HCPCS/CPT codes billed that day
- Matches against NCCI Column 1 / Column 2 forbidden pairs
- Flags when both codes appear on the same patient-day
- Computes **financial risk** from the denied (Column 2) line payment

### Upcoding (Step 4)
- Builds diagnosis-group baselines (ICD-9 3-digit groups / DRG proxies)
- Computes average procedure complexity (RVU-weighted) and payment stats
- Flags claims where procedure complexity exceeds baseline by **z ≥ 2.5** or above **P90 + margin**
- Example: minor respiratory infection (465) billed with cardiac cath (93458)

## Project Structure

```
HEALTH_PROJECT/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI routes
│   │   ├── models.py            # SQLAlchemy models
│   │   └── services/
│   │       ├── ingestion.py     # CMS data loading
│   │       ├── timeline.py      # Patient-day grouping
│   │       ├── unbundling.py    # NCCI detection
│   │       ├── upcoding.py      # Statistical upcoding
│   │       └── engine.py        # Pipeline orchestration
│   └── requirements.txt
├── frontend/                    # React analyst dashboard
├── data/
│   ├── sample/                  # Demo CSV files
│   └── raw/                     # Downloaded CMS files
├── scripts/
│   ├── generate_sample_data.py
│   └── download_cms_data.py
└── docker-compose.yml
```

## Docker

```bash
docker compose up --build
```

- API: http://localhost:8000
- Dashboard: http://localhost:5173
- API docs: http://localhost:8000/docs




# B. LangGraph Text-to-SQL Microservice

This microservice provides a high-performance **FastAPI** backend that links a React frontend application to a **LangGraph** autonomous state machine. The service specializes in translating healthcare auditor queries into accurate SQL, querying local databases (`claims.db`), and generating natural language compliance summaries.

## Stack

| Concern | Tech |
|---|---|
| UI | Streamlit |
| LLM | Groq `llama-3.3-70b-versatile` |
| Orchestration | LangGraph (state machine + self-correction loop) |
| Vector store | ChromaDB (local MiniLM embeddings) |
| Data store | SQLite (`claims.db`, seeded from synthetic data) |
| NLP | NLTK (stop words) |

---
---

## ✨ Features

* **LangGraph Core Integration** – Direct asynchronous pipeline execution into the multi-agent graph state machine.
* **Context-Aware Prompt Injection** – Automatically detects and appends active auditor viewer contexts (e.g., specific `clm_id` flags) to upstream LLM requests.
* **Resilient Output Parsing** – Normalizes diverse model dictionary response formats (`answer`, `response`, `messages`, or `text`) into sanitized strings.
* **Hardened Fault-Tolerance** – Fallback configuration checks and an analytical hardcoded regex-router guarantee uptime if dependencies break.
* **Secured CORS Layers** – Tailored defaults safely handle cross-origin traffic from Vite/React clients operating on port `5173`.

---

## 🛠️ Tech Stack & Requirements

* **Python 3.10+**
* **FastAPI** & **Uvicorn** (Asynchronous Server Gateway)
* **Pydantic v2** (Strict Request Schema Validations)
* **LangGraph / LangChain Core** (State-driven LLM Routing)

---

## Quick Start

### 1. Installation
Ensure your virtual environment is active and install the required dependencies:
```bash
pip install fastapi uvicorn pydantic langchain langgraph
```

### 2. File Architecture Alignment
Make sure your package tree remains aligned for the absolute paths module resolver (`/src` must be the project root layer):
```text
src/
└── cotiviti/
    ├── __init__.py
    ├── server.py         <-- This File
    └── assistant/
        ├── __init__.py
        ├── agent.py      (Provides: answer_question)
        └── config.py     (Provides: MODEL_NAME / DB_PATH)
```

### 3. Launching the Server
Execute the server script via Python to trigger local hosting configurations:
```bash
python src/cotiviti/server.py
```
The application will spin up at **`http://localhost:8001`** with hot-reloading enabled.

---

## API Specification

### Execute Agentic Loop
Processes natural language text, runs safety/schema traces, executes queries on SQLite, and responds with clean strings.

* **Endpoint:** `POST /api/v1/chat`
* **Content-Type:** `application/json`

#### Request Payload Structure
```json
{
  "message": "Which DRG code exhibits the highest overpayment exposure?",
  "claim_context": {
    "clm_id": "CLM_77810"
  }
}
```
*Note: Set `"clm_id": "NONE_SELECTED"` if an auditor is not actively focusing on a target line item.*

#### Response Payload Structure
```json
{
  "response": "[LANGCHAIN AGENT] Running SQL Trace against claims.db... SELECT drg_code, SUM(overpayment_amt) as exposure FROM claims GROUP BY drg_code ORDER BY exposure DESC LIMIT 1; Result Summary: MS-DRG 291 (Heart Failure and Shock with MCC) exhibits the highest overpayment exposure across the synthetic CMS dataset."
}
```

---

##  Fallback Mechanism
If the module fails to safely import `cotiviti.assistant.agent`, the engine automatically drops down to an analytical pattern router (`run_live_langchain_fallback`). This local backup handles:
1. **Financial Metrics:** Highest overpayment traces.
2. **Aggregations:** Unique base MS-DRG frequency summaries.
3. **Compliance Codes:** National NCCI edit validations and unbundling exceptions.
