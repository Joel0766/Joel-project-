from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from app.core.config import settings
from app.core.ingestion import read_clean_tables
from app.inventory.policy import compute_policy, enrich_for_explanations
from app.ml.features import build_feature_frame
from app.ml.forecast import generate_forecast


@dataclass
class BacktestResult:
    metrics: pd.DataFrame
    summary: dict[str, float]


def mape(actual: np.ndarray, forecast: np.ndarray) -> float:
    mask = actual != 0
    if not mask.any():
        return 0.0
    return float(np.mean(np.abs((actual[mask] - forecast[mask]) / actual[mask])))


def smape(actual: np.ndarray, forecast: np.ndarray) -> float:
    denom = (np.abs(actual) + np.abs(forecast)) / 2
    mask = denom != 0
    if not mask.any():
        return 0.0
    return float(np.mean(np.abs(actual[mask] - forecast[mask]) / denom[mask]))


def rolling_origin_backtest(dataset_dir: Path, horizon: int) -> BacktestResult:
    tables = read_clean_tables(dataset_dir)
    feature_frames = build_feature_frame(
        tables["sales_orders"], tables["inventory_snapshots"]
    )
    weekly = feature_frames.weekly_sales
    metrics_rows = []

    for sku_id, group in weekly.groupby("sku_id"):
        group = group.sort_values("week_start")
        if len(group) < horizon + 10:
            continue
        train = group.iloc[:-horizon]
        test = group.iloc[-horizon:]
        feature_frame = feature_frames.feature_frame[feature_frames.feature_frame["sku_id"] == sku_id]
        feature_frame = feature_frame[feature_frame["week_start"].isin(train["week_start"])]
        forecast_result = generate_forecast(feature_frame, horizon)
        forecast_values = forecast_result.forecast_df["forecast_mean"].values
        actual = test["censored_units"].values
        metrics_rows.append(
            {
                "sku_id": sku_id,
                "mape": mape(actual, forecast_values),
                "smape": smape(actual, forecast_values),
            }
        )

    metrics_df = pd.DataFrame(metrics_rows)
    summary = {
        "mape": float(metrics_df["mape"].mean()) if not metrics_df.empty else 0.0,
        "smape": float(metrics_df["smape"].mean()) if not metrics_df.empty else 0.0,
    }
    return BacktestResult(metrics=metrics_df, summary=summary)


def simulate_service_level(dataset_dir: Path, horizon: int) -> dict[str, float]:
    tables = read_clean_tables(dataset_dir)
    feature_frames = build_feature_frame(
        tables["sales_orders"], tables["inventory_snapshots"]
    )
    forecast_result = generate_forecast(feature_frames.feature_frame, horizon)
    policy = compute_policy(
        tables["sku_master"],
        tables["inventory_snapshots"],
        forecast_result.forecast_df,
        forecast_result.residual_std,
        tables["sales_orders"],
    )
    enriched = enrich_for_explanations(feature_frames.weekly_sales, policy.recommendations)
    service_level = (enriched["inventory_position"] >= enriched["reorder_point"]).mean()
    avg_inventory = enriched["on_hand_units"].mean()
    target_inventory = enriched["reorder_point"].mean()
    cash_freed = (
        (enriched["on_hand_units"] - enriched["reorder_point"]).clip(lower=0)
        * enriched["unit_cost"]
    ).mean()
    baseline_risk = (enriched["inventory_position"] < enriched["demand_lt"]).mean()
    new_risk = (enriched["inventory_position"] < enriched["reorder_point"]).mean()
    risk_reduction = baseline_risk - new_risk
    return {
        "service_level": float(service_level),
        "average_inventory": float(avg_inventory),
        "target_inventory": float(target_inventory),
        "cash_freed": float(cash_freed),
        "stockout_risk_reduction": float(risk_reduction),
    }


def write_report(dataset_dir: Path, result: BacktestResult, service_sim: dict[str, float]) -> Path:
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = settings.reports_dir / "latest.md"
    with report_path.open("w") as handle:
        handle.write("# Backtest Report\n\n")
        handle.write(f"Dataset: {dataset_dir}\n\n")
        handle.write("## Forecast Metrics\n")
        handle.write(f"- MAPE: {result.summary['mape']:.3f}\n")
        handle.write(f"- SMAPE: {result.summary['smape']:.3f}\n\n")
        handle.write("## Service Level Simulation\n")
        handle.write(
            f"- Simulated service level: {service_sim['service_level']:.2%}\n"
        )
        handle.write(
            f"- Average inventory on hand: {service_sim['average_inventory']:.1f}\n"
        )
        handle.write(
            f"- Target inventory (policy ROP): {service_sim['target_inventory']:.1f}\n"
        )
        handle.write(f"- Estimated cash freed: {service_sim['cash_freed']:.2f}\n")
        handle.write(
            f"- Stockout risk reduction (proxy): {service_sim['stockout_risk_reduction']:.2%}\n"
        )
        handle.write("\n## Notes\n")
        handle.write(
            "Assumes weekly planning, lead time in days converted to weeks, and censored demand\n"
        )
    return report_path
