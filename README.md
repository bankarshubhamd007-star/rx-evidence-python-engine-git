# RX Evidence Engine

FastAPI backend for the RX Evidence Chrome extension. Phase 2: API surface only —
returns randomized mock analyses (same shape the real retrieval pipeline will
eventually produce). Swap `mock_analysis.generate_mock_analysis` for the real
claim-extraction/retrieval/verdict pipeline in a later phase without touching
the API contract.

## Setup & Installation

This project uses `uv` for lightning-fast dependency management. You do not need a `requirements.txt` file; all required packages are listed in `pyproject.toml`.

1. **Install Dependencies**:
   Simply run the following command to automatically install all required packages:
   ```bash
   uv sync
   ```

2. **Environment Variables**:
   Copy the example environment file and add your OpenRouter and openFDA API keys:
   ```bash
   cp .env.example .env
   ```

## Run

```bash
uv run rx-evidence-engine
# or
uv run uvicorn rx_evidence_engine.app:app --reload --port 8000
```

Interactive docs: http://127.0.0.1:8000/docs

## Endpoints

| Method | Path                       | Purpose                                  |
|--------|----------------------------|-------------------------------------------|
| GET    | `/v1/health`               | Liveness check                            |
| POST   | `/v1/claims/analyze`       | Analyze a claim, returns `AnalysisResult` |
| GET    | `/v1/claims/analyze/{id}`  | Fetch a previously computed analysis      |
| POST   | `/v1/feedback`             | Submit helpful/not-helpful feedback       |

Request/response bodies use camelCase (matches the extension's TypeScript
types in `rx-evidence-chrome-extension/src/types`). See `models.py`.

## Structure

```
src/rx_evidence_engine/
  app.py             FastAPI app factory, CORS (chrome-extension://* + localhost)
  models.py          Pydantic schemas, camelCase aliasing
  mock_analysis.py    Randomized mock verdict/evidence generator
  store.py            In-memory analysis/feedback store
  routers/
    health.py
    claims.py
    feedback.py
```

Storage is in-memory only — restarting the server clears it. Swap `store.py`
for a real database (PostgreSQL) in a later phase.
