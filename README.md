[![Python](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/FastAPI-async-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-BSL%201.1-orange.svg)](LICENSE)
[![Build](https://img.shields.io/badge/build-passing-brightgreen.svg)]()
[![Platform](https://img.shields.io/badge/platform-Azure%20%7C%20Windows-lightgrey.svg)]()
[![Author](https://img.shields.io/badge/author-Jay%20Lee-blueviolet.svg)](https://github.com/jaylee-dev)

> AI-driven financial analytics and forecasting platform for gold, silver, and stock markets.  
> Combining Python (FastAPI + PyTorch) and Azure Synapse to deliver end-to-end market insights.

---

## 🌐 Overview
MarketGemini is a multi-layer financial analytics project combining **Python (FastAPI, PyTorch)**, **Azure Synapse / Fabric**, and **C# pipelines** to analyze, forecast, and visualize time-series market data.  

It ingests live and historical data, cleans and normalizes it, computes advanced indicators, runs anomaly/regime detection models, and exposes APIs and dashboards for interactive analytics.

---

## 🧩 Architecture

```
Ingestion & Normalization ─▶ Feature & Indicator Engine ─▶ 
Regime Detection ─▶ Forecasting ─▶ Publish Layer (API / Dashboard)

```

| Layer | Description | Tech |
|--------|-------------|------|
| **Ingestion & Normalization** | Collects market data (gold, silver, equities) and stores normalized series. | Python, Azure Synapse, Pandas |
| **Feature & Indicator Engine** | Generates SMA, RSI, MACD, volatility, and drawdown metrics. | Pandas / NumPy |
| **Regime Detection** | Detects structural market shifts and volatility clusters. | PyTorch / ML models |
| **Forecasting** | Predicts short-term trends using neural time-series models. | FastAPI / PyTorch |
| **Publish Layer** | REST APIs, dashboards, and analytics UI. | FastAPI, React, Power BI |

---

## ⚙️ Tech Stack

| Area | Technologies |
|------|---------------|
| **Backend (Python)** | FastAPI, Pandas, NumPy, PyTorch, pytest |
| **Backend (C#)** | .NET 8, Azure Fabric Services, DocumentDB |
| **Data / Cloud** | Azure Synapse, Cosmos DB, Kusto |
| **Frontend** | React, Node.js |
| **Testing / CI** | pytest, GitHub Actions |
| **Auth Modes** | HS256 (local) / OIDC (Google ID tokens) |

---

## 📁 Project Structure

```text
ProjectAI/
├── marketgemini/
│   ├── backend/
│   │   ├── app/                 # FastAPI app
│   │   ├── data/                # Ingestion and processing scripts
│   │   └── tests/               # pytest test suite
│   └── tools/                   # CLI utilities
│
├── conftest.py                  # Root pytest configuration & fixtures
├── pytest.ini                   # Test discovery and markers
├── requirements.txt             # Python dependencies
├── .env                         # Environment variables
├── .gitignore
└── README.md
```

---

## 🚀 Setup & Installation

### 1. Clone and initialize environment
```bash
git clone https://github.com/jaylee-dev/MarketGemini.git
cd ProjectAI
python -m venv .venv
.\.venv\Scriptsctivate        # (Windows)
pip install -r requirements.txt
```

### 2. Environment variables
Create a `.env` file at the project root:

```env
# Selector
AUTH_MODE=HS256              # HS256 or OIDC
ENABLE_GOOGLE_TESTS=false    # true to run OIDC tests
GOOGLE_AUDIENCE=             # OIDC client_id / audience
GOOGLE_TEST_ID_TOKEN=        # Real Google ID token if testing live OIDC
```

### 3. Run locally
```bash
uvicorn marketgemini.backend.app.main:app --reload
```
API available at: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🧪 Testing

### Run the full suite
```bash
pytest
```

### Run Google / OIDC integration tests
```bash
$env:AUTH_MODE="OIDC"
$env:ENABLE_GOOGLE_TESTS="true"
pytest -m google
```

### Run only local HS256 tests
```bash
$env:AUTH_MODE="HS256"
pytest
```

> The test fixtures in `conftest.py` automatically choose between HS256 (local dev tokens) and OIDC (Google tokens) based on `AUTH_MODE`.

---

## 🧰 Key Pytest Markers

| Marker | Description |
|---------|-------------|
| `@pytest.mark.google` | Tests requiring live Google OIDC tokens. Skipped by default unless enabled. |
| `@pytest.mark.slow` | Long-running or heavy data tests. |
| `@pytest.mark.integration` | Cross-service integration flows. |

Run with:
```bash
pytest -m google
pytest -m "not slow"
```

---

## 🔐 Authentication Modes

| Mode | Use Case | Description |
|------|-----------|-------------|
| **HS256** | Local Development | Uses symmetric key for issuing dev tokens (`make_dev_token`). |
| **OIDC** | Integration / Google Cloud | Uses Google ID token exchange to authenticate users. |

The test clients (`authed_client`, `google_authed_client`) handle both modes automatically.

---

## 💻 Development Tips

- Run VS Code with the workspace interpreter:  
  `.venv/Scripts/python.exe`
- All test results appear in `pytest` output with detailed verbosity (`-vv -rA`).
- Use `pytest --collect-only` to see discovered tests.

---

## 🧠 To Keep Updated

| Section | What to update | When |
|----------|----------------|------|
| **Overview / Architecture** | Add new features, diagrams | After major feature merges |
| **Setup** | Installation or dependency changes | When adding new packages |
| **Testing** | New markers, fixtures, or test flows | When tests evolve |
| **Environment variables** | New configuration or credentials | When backend auth logic changes |
| **Changelog (optional)** | Add version updates | With each tagged release |

---

## 🧭 Project Scope

MarketGemini is an AI-powered backend for financial analytics that includes:
- ✅ **Secure authentication** with JWT and Google OIDC (in progress)
- ✅ **REST API layer** built with FastAPI for data ingestion and analysis
- 🔄 **Integration with Google Cloud OIDC** for live user login (next milestone)
- 🔄 **Anomaly detection engine** spike detection, moving averages (future milestone)
- 🔄 **Frontend dashboard** with React (future milestone)
- 🔄 **Model training pipeline** for forecasting (future milestone)

---

## 📄 License
```
MIT License © 2025 Jay Lee
```

---

## 📬 Contact

**Author:** Jay Lee  
**Location:** Seattle, WA  
**Email:** jay@jaylee.dev  
**LinkedIn:** [linkedin.com/in/jaylee-dev](https://www.linkedin.com/in/jay-lee-489b11/)  
**GitHub:** [github.com/jaylee-dev](https://github.com/jaylee-dev)
