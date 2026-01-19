from __future__ import annotations

from pathlib import Path

import typer

from app.core.config import settings
from app.core.ingestion import ingest_dataset
from app.core.pipeline import run_forecast_job
from app.db.models import DatasetVersion
from app.db.session import SessionLocal
from app.ml.backtest import rolling_origin_backtest, simulate_service_level, write_report

app = typer.Typer(help="Inventory planning CLI")


@app.command()
def ingest(
    sku_master: Path,
    sales_orders: Path,
    inventory_snapshots: Path,
    purchase_orders: Path,
    notes: str = "",
) -> None:
    """Ingest CSVs into the local dataset store."""
    result = ingest_dataset(
        {
            "sku_master": sku_master,
            "sales_orders": sales_orders,
            "inventory_snapshots": inventory_snapshots,
            "purchase_orders": purchase_orders,
        },
        notes=notes or None,
    )
    with SessionLocal() as session:
        dataset = DatasetVersion(raw_paths={"dataset_dir": str(result["dataset_dir"])})
        session.add(dataset)
        session.commit()
        session.refresh(dataset)
    typer.echo(f"Dataset stored in {result['dataset_dir']} (version {dataset.id})")


@app.command()
def run_forecast(
    dataset_dir: Path | None = None,
    dataset_version_id: int | None = None,
    horizon: int = settings.forecast_horizon_weeks,
) -> None:
    """Run forecast and recommendation generation."""
    if dataset_version_id is not None:
        with SessionLocal() as session:
            dataset = session.get(DatasetVersion, dataset_version_id)
            if not dataset:
                raise typer.BadParameter("Dataset version not found")
            dataset_dir = Path(dataset.raw_paths["dataset_dir"])
    if dataset_dir is None:
        raise typer.BadParameter("Provide dataset_dir or dataset_version_id")
    result = run_forecast_job(dataset_dir, horizon, dataset_id=dataset_version_id)
    typer.echo(result)


@app.command()
def backtest(
    dataset_dir: Path | None = None,
    dataset_version_id: int | None = None,
    horizon: int = settings.forecast_horizon_weeks,
) -> None:
    """Run rolling-origin backtest and write a report."""
    if dataset_version_id is not None:
        with SessionLocal() as session:
            dataset = session.get(DatasetVersion, dataset_version_id)
            if not dataset:
                raise typer.BadParameter("Dataset version not found")
            dataset_dir = Path(dataset.raw_paths["dataset_dir"])
    if dataset_dir is None:
        raise typer.BadParameter("Provide dataset_dir or dataset_version_id")
    result = rolling_origin_backtest(dataset_dir, horizon)
    service = simulate_service_level(dataset_dir, horizon)
    report_path = write_report(dataset_dir, result, service)
    typer.echo(f"Report written to {report_path}")


if __name__ == "__main__":
    app()
