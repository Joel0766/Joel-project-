# AI-Assisted Inventory Planning MVP

This repository contains a production-grade MVP for AI-assisted inventory planning focused on **excess inventory reduction + stockout prevention** for mid-sized FMCG distributors (200–2,000 SKUs).

## Architecture & Repo Layout

```
.
├── app
│   ├── api          # FastAPI endpoints + UI routes
│   ├── cli          # CLI entrypoints
│   ├── core         # ingestion, config, validation, pipeline
│   ├── db           # SQLAlchemy models + session
│   ├── inventory    # policy + recommendation ranking
│   ├── ml           # features, forecasting, backtesting
│   ├── tests        # unit + integration tests
│   └── ui           # templates + static assets
├── migrations       # Alembic migrations
├── reports          # Backtest reports
├── sample_data      # CSV inputs for quickstart
└── docker-compose.yml
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run migrations (optional for MVP, tables auto-create on startup):

```bash
alembic upgrade head
```

## Run API + UI

```bash
uvicorn app.api.main:app --reload
```

Open:
- UI: http://localhost:8000/ui
- API docs: http://localhost:8000/docs

## Run with Docker Compose

```bash
docker-compose up --build
```

## CLI Usage

Ingest CSVs:

```bash
python -m app.cli ingest \
  sample_data/sku_master.csv \
  sample_data/sales_orders.csv \
  sample_data/inventory_snapshots.csv \
  sample_data/purchase_orders.csv
```

Run forecast + recommendations:

```bash
python -m app.cli run-forecast --dataset-version-id <id>
```

Run backtest + report:

```bash
python -m app.cli backtest --dataset-version-id <id> --horizon 8
```

Report output: `reports/latest.md`

## Domain Assumptions (encoded in code comments + defaults)
- Weekly planning is the default periodicity.
- Lead time is stored in days and converted to weeks in policy calculations.
- Demand is observed sales; stockout weeks (on-hand == 0) are censored.
- Service level targets: A=95%, B=92%, C=90%.
- Holding cost proxy: 20% annual rate of unit cost.
- Stockout cost proxy: fallback penalty if margin is unknown.

## Data Contracts
Inputs follow the CSV schemas in `sample_data/`:
- `sku_master.csv`
- `sales_orders.csv`
- `inventory_snapshots.csv`
- `purchase_orders.csv`

The ingestion pipeline validates schema + constraints and produces clean canonical tables.

## Forecasting
- Baseline: moving average (fallback for sparse history).
- ML: global LightGBM model with lag + seasonal + promo features.
- Confidence intervals: residual-based p10/p90.
- Backtesting: rolling-origin with MAPE + SMAPE.
- Outlier handling: per-SKU 95th percentile cap before feature generation.
- Stockout censoring: configurable strategy using rolling median for zero on-hand weeks.

## Inventory Policy
- Dynamic reorder point (ROP) and safety stock from forecast + lead time.
- Order quantities respect min order and pack size rounding.
- ABC classification from trailing 13-week revenue.

## Explainability
Recommendations surface top drivers in plain English:
- Recent 4-week trend
- Last-year same-week seasonality
- Promo intensity
- Stockout history
- Lead time variability

## Human-in-the-loop Overrides
Overrides are persisted via `/recommendations/{rec_id}/override` and shown in the UI.

## Tests

```bash
pytest
```

## How to Extend to Route Optimization Later
- Add a `routing` module with a new data contract (`delivery_stops.csv`).
- Persist vehicle constraints + depot locations in SQLite.
- Feed optimized routes into the inventory policy as a capacity constraint.
- Add a batch job to recompute delivery calendars alongside reorder quantities.

## Repo Tree (deliverable)

```
app/
  api/
  cli/
  core/
  db/
  inventory/
  ml/
  tests/
  ui/
    templates/
    static/
migrations/
reports/
sample_data/
Dockerfile
docker-compose.yml
```
