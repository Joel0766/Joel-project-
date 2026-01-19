from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from app.core.ingestion import read_clean_tables
from app.db.models import DatasetVersion, Forecast, Recommendation
from app.db.session import SessionLocal
from app.inventory.policy import compute_policy, enrich_for_explanations
from app.inventory.recommendations import rank_recommendations
from app.ml.features import build_feature_frame
from app.ml.forecast import generate_forecast


def run_forecast_job(
    dataset_dir: Path, horizon: int, dataset_id: int | None = None
) -> dict[str, int]:
    tables = read_clean_tables(dataset_dir)
    feature_frames = build_feature_frame(
        tables["sales_orders"], tables["inventory_snapshots"]
    )
    forecast_result = generate_forecast(feature_frames.feature_frame, horizon)

    policy_frame = compute_policy(
        tables["sku_master"],
        tables["inventory_snapshots"],
        forecast_result.forecast_df,
        forecast_result.residual_std,
        tables["sales_orders"],
    )
    enriched = enrich_for_explanations(feature_frames.weekly_sales, policy_frame.recommendations)
    ranked = rank_recommendations(enriched)

    with SessionLocal() as session:
        if dataset_id is None:
            dataset = DatasetVersion(raw_paths={"dataset_dir": str(dataset_dir)})
            session.add(dataset)
            session.flush()
        else:
            dataset = session.get(DatasetVersion, dataset_id)
            if dataset is None:
                dataset = DatasetVersion(raw_paths={"dataset_dir": str(dataset_dir)})
                session.add(dataset)
                session.flush()

        forecast_rows = []
        for _, row in forecast_result.forecast_df.iterrows():
            forecast_rows.append(
                Forecast(
                    dataset_id=dataset.id,
                    sku_id=row["sku_id"],
                    week_start=row["week_start"],
                    forecast_mean=float(row["forecast_mean"]),
                    forecast_p10=float(row["forecast_p10"]),
                    forecast_p90=float(row["forecast_p90"]),
                    model_name=row.get("model_name", forecast_result.model_name),
                )
            )
        session.add_all(forecast_rows)

        rec_rows = []
        for _, row in ranked.iterrows():
            rec_rows.append(
                Recommendation(
                    dataset_id=dataset.id,
                    sku_id=row["sku_id"],
                    recommendation_date=date.today(),
                    action=row["action"],
                    recommended_order_units=int(row["recommended_order_units"]),
                    reorder_point=float(row["reorder_point"]),
                    safety_stock=float(row["safety_stock"]),
                    explanation=row["explanation"],
                    confidence_score=float(row["confidence_score"]),
                    expected_cash_freed=float(row["expected_cash_freed"]),
                    expected_stockout_risk_change=float(row["expected_stockout_risk_change"]),
                    abc_class=row["abc_class"],
                )
            )
        session.add_all(rec_rows)
        session.commit()

    return {
        "dataset_id": dataset.id,
        "forecast_count": len(forecast_rows),
        "recommendation_count": len(rec_rows),
    }
