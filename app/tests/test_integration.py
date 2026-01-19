from pathlib import Path

from app.core.ingestion import ingest_dataset
from app.core.pipeline import run_forecast_job


def test_end_to_end_pipeline(tmp_path):
    sample_dir = Path("sample_data")
    result = ingest_dataset(
        {
            "sku_master": sample_dir / "sku_master.csv",
            "sales_orders": sample_dir / "sales_orders.csv",
            "inventory_snapshots": sample_dir / "inventory_snapshots.csv",
            "purchase_orders": sample_dir / "purchase_orders.csv",
        }
    )
    output = run_forecast_job(result["dataset_dir"], horizon=4)
    assert output["recommendation_count"] > 0
