# AI-Powered Financial Intelligence Platform

> **MCA Minor Project**  
> **Student:** Aastha Setia (Roll No: 06214004425)  
> **Institution:** Master of Computer Applications (MCA)  
> **Status:** Production-Grade Complete · Auditable Local Workspace · 33 / 33 Tests Passing

---

## ⚖️ Mandatory Research & Educational Disclaimer

> **DISCLAIMER**: This platform is designed strictly for research, academic, and educational analysis. The financial projections, intrinsic valuations, and AI interpretations generated are deterministic model estimates and **do not constitute financial advice, investment recommendations, or trade solicitations**.

---

## 📌 Executive Summary & Architecture

The **AI-Powered Financial Intelligence Platform** is an auditable financial modeling and intelligence workspace. It ingests messy financial statements (CSV/Excel), normalizes line items and units into an embedded **DuckDB** analytical warehouse, verifies double-entry accounting integrity, computes driver-based multi-period forecasts and DCF valuations, answers evidence-backed queries via a grounded AI analyst, and generates publication-grade Word/PDF dossiers with complete audit provenance.

### 🛡️ Non-Negotiable Engineering Guarantees
1. **Zero LLM Arithmetic**: All math, forecasts, margins, and valuations are computed strictly in deterministic Python functions (`numpy`, `pandas`, `statsmodels`, `scipy`).
2. **DuckDB as Source of Truth**: Original reported labels and values are preserved immutably alongside normalized figures, scaling factors, and source spreadsheet coordinates.
3. **Evidence-Grounded AI Analyst**: The AI assistant runs against typed, parameterized DuckDB tools; freeform unconstrained text-to-SQL is strictly prohibited.
4. **Precondition Guards**: DCF valuation strictly enforces mathematical guards (rejecting $WACC \le g$).
5. **Human-in-the-Loop Checkpoints**: Fuzzy schema mapping triggers an explicit interrupt via LangGraph and pauses in SQLite until approved by an analyst.

---

## 📂 Repository Structure

```
AI-Financial-Intelligence/
├── app/
│   ├── api/                 # FastAPI REST server & endpoints
│   │   ├── server.py        # /health, /pipeline/start, /state, /resume
│   │   └── checkpoints.db   # SQLite checkpointer for LangGraph state
│   ├── core/                # Core configuration, logging & security
│   │   ├── config.py        # Pydantic BaseSettings (.env loading)
│   │   ├── constants.py     # Regulatory disclaimers & canonical taxonomy
│   │   ├── logging.py       # Secret-redacting logger (scrubs keys/tokens)
│   │   └── security.py      # AuthContext, ID isolation & tenant validation
│   ├── database/            # DuckDB schema & typed repository layer
│   │   ├── connection.py    # Connection manager
│   │   ├── schema.py        # 13-table DDL warehouse schema
│   │   └── repositories/    # Typed repositories (facts, reviews, valuations, etc.)
│   ├── ingestion/           # File parser, alias dictionary & RapidFuzz matcher
│   ├── validation/          # Accounting rules (Assets=Liab+Equity) & Quality Scoring
│   ├── forecasting/         # Driver forecasting, baselines (Holt) & backtesting
│   ├── valuation/           # WACC, DCF valuation, scenario manager & sensitivity
│   ├── analyst/             # Grounded AI Analyst & parameterized query tools
│   ├── reports/             # python-docx & reportlab PDF exporters
│   ├── workflow/            # LangGraph StateGraph & Human-in-the-Loop interrupt
│   └── ui/                  # UI components, dark-mode styling & provenance badges
├── pages/                   # Multi-page Streamlit Application
│   ├── 1_📥_Upload_and_Ingest.py
│   ├── 2_🔍_Data_Quality.py
│   ├── 3_📈_Forecasting.py
│   ├── 4_💰_DCF_Valuation.py
│   ├── 5_🤖_AI_Analyst.py
│   ├── 6_📋_Reports.py
│   ├── 7_⚙️_Settings_and_Audit.py
│   └── 8_⚖️_Human_Approval_Center.py
├── 🏠_Home.py               # Streamlit Executive Dashboard
├── tests/
│   ├── fixtures/            # Messy data fixtures (parentheses, billions, misalignments)
│   ├── unit/                # Unit tests for all sub-engines (analyst, DCF, workflow, etc.)
│   ├── integration/         # Vertical slice end-to-end integration tests
│   └── evaluation/          # Formal benchmark scripts for project report citation
├── evaluation_results.md    # Formal reproduced benchmark metrics
├── requirements.txt         # Pinned production dependencies
└── pytest.ini               # Pytest environment & filter configuration
```

---

## 🚀 Setup & Execution

### 1. Prerequisites
- Python 3.11, 3.12, or 3.13
- Git

### 2. Virtual Environment Setup
```powershell
# Clone and enter workspace
git clone https://github.com/Aastha-2304/AI-Powered-Financial-Intelligence-Trading-Research-Platform.git
cd AI-Financial-Intelligence

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install pinned dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:
```ini
APP_ENV=development
LOG_LEVEL=INFO
DATABASE_PATH=database/financial_warehouse.duckdb
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```
*(Note: If `GROQ_API_KEY` is omitted, the platform automatically activates its cited deterministic fallback analyst, ensuring 100% test and query reliability offline).*

### 4. Running the Platform
- **Streamlit Web Application**:
  ```powershell
  streamlit run 🏠_Home.py
  ```
  Open `http://localhost:8501` in your browser.

- **FastAPI Backend Server (Phase 9 LangGraph)**:
  ```powershell
  uvicorn app.api.server:app --port 8000 --reload
  ```
  Open Swagger documentation at `http://localhost:8000/docs`.

---

## 🧪 Automated Testing & Evaluation

Run the full platform test suite:
```powershell
pytest tests/unit/ tests/integration/ -v
```
**Results:** `33 passed in ~14s (100% pass rate)`

### Verified Evaluation Benchmarks (`evaluation_results.md`)
- **Fuzzy Header Mapping**: 92.59% accuracy (Balance Sheet: 100%, Income Statement: 85.7% / F1: 0.923).
- **Data Quality Engine**: 100% error detection rate on injected violations; 0.0% false alarm rate on clean statements. Hard failure cap enforced (max 40/100).
- **Forecasting Backtest**: Driver-based revenue projection achieves 1.26% MAPE vs. Holt Linear (2.14%) vs. Naive Baseline (8.57%).
- **DCF Intrinsic Valuation**: Matches independent financial analyst benchmark within $0.01 tolerance (EV: $1504.14M vs. $1504.13M; Implied Share: $13.54 vs. $13.54). Rejects $WACC \le g$.
- **Grounded AI Analyst**: 100% factual agreement with DuckDB warehouse; 100% citation rate; 100% abstention on unsupported advice or unobserved periods.
- **Report Generation**: Word (.docx) generated in 0.140s; PDF generated in 0.033s with complete SHA-256 provenance logging.
