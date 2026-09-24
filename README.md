# AI-Powered Financial Intelligence & Trading Research Platform

An end-to-end financial intelligence platform combining automated financial statement ETL, data validation, forecasting, multi-scenario DCF financial modeling, automated MD&A report generation, and an LLM-powered financial analyst chatbot.

---

## 📌 Features

- **Automated Ingestion & ETL**: Ingest messy multi-period balance sheets, income statements, and cash flow statements with fuzzy header matching into DuckDB.
- **Data Validation & Quality Engine**: Automatic balance checks, line item validation, anomaly alerts, and confidence scoring.
- **Financial Modeling & Forecasting**:
  - Income statement & balance sheet projection.
  - Working capital and debt schedules.
  - Multi-year Free Cash Flow (FCF) calculations.
  - Discounted Cash Flow (DCF) intrinsic valuation with sensitivity tables.
- **Scenario & What-If Analysis**: Stress test revenue growth, margin contraction, discount rate (WACC), and terminal growth assumptions in real-time.
- **AI Financial Analyst Chatbot**: Grounded conversational assistant powered by Groq and LLaMA 3.3 70B, executing live tool calls over the financial warehouse.
- **Professional Report Generation**: Automatic generation of comprehensive Word (`.docx`) and PDF research and executive reports with MD&A commentary.
- **Interactive Multi-Page Streamlit UI**: Sleek Power BI / institutional trading terminal aesthetic.

---

## 🏗️ Architecture

```
AI-Financial-Intelligence/
├── ai_agent/                 # AI Chatbot & automated report generator
│   ├── chatbot.py            # Groq LLaMA 3.3 financial agent with tool calls
│   └── report_generator.py   # Word / PDF generation engine
├── common/                   # Shared UI styling & Power BI theme helpers
├── database/                 # DuckDB financial warehouse schema & migrations
├── etl/                      # File parsers, fuzzy column mapping & cleaners
├── financial_model/          # DCF, balance sheet, working capital schedules
├── forecasting/              # Revenue, expense, and cash flow forecasting
├── pages/                    # Multi-page Streamlit dashboards
├── validation_engine/        # Rules engine, quality scoring & anomaly checks
├── app_main.py               # Streamlit application entry point
├── config.py                 # Configuration, canonical line items & aliases
└── requirements.txt          # Python dependencies
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.11 / 3.12 / 3.13)
- Git

### 2. Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Aastha-2304/AI-Powered-Financial-Intelligence-Trading-Research-Platform.git
   cd AI-Powered-Financial-Intelligence-Trading-Research-Platform
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
   Open `.env` and configure your API keys:
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   ```

---

## 💻 Running the Application

Launch the Streamlit app:
```bash
streamlit run app_main.py
```
Or run the multi-page home app:
```bash
streamlit run "🏠_Home.py"
```

Open your browser at `http://localhost:8501`.

---

## 🛡️ License

This project is licensed under the MIT License.
