from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.core.config import settings

SERVICE_LEVEL_Z = {
    0.9: 1.28,
    0.92: 1.41,
    0.95: 1.65,
}


@dataclass
class RecommendationFrame:
    recommendations: pd.DataFrame
    abc_summary: pd.DataFrame


def classify_abc(sales_df: pd.DataFrame, sku_df: pd.DataFrame) -> pd.DataFrame:
    recent_sales = sales_df.copy()
    recent_sales["date"] = pd.to_datetime(recent_sales["date"])
    cutoff = recent_sales["date"].max() - pd.Timedelta(weeks=13)
    recent_sales = recent_sales[recent_sales["date"] >= cutoff]
    revenue = (
        recent_sales.merge(sku_df[["sku_id", "unit_price"]], on="sku_id", how="left")
        .assign(revenue=lambda df: df["units_sold"] * df["unit_price"])
        .groupby("sku_id", as_index=False)["revenue"]
        .sum()
        .sort_values("revenue", ascending=False)
    )
    revenue["cum_share"] = revenue["revenue"].cumsum() / revenue["revenue"].sum()
    revenue["abc_class"] = np.select(
        [revenue["cum_share"] <= 0.8, revenue["cum_share"] <= 0.95],
        ["A", "B"],
        default="C",
    )
    return revenue[["sku_id", "abc_class", "revenue"]]


def round_to_pack_size(quantity: float, pack_size: int) -> int:
    if pack_size <= 0:
        return int(max(quantity, 0))
    return int(np.ceil(quantity / pack_size) * pack_size)


def compute_policy(
    sku_df: pd.DataFrame,
    inventory_df: pd.DataFrame,
    forecast_df: pd.DataFrame,
    residual_std: float,
    sales_df: pd.DataFrame,
) -> RecommendationFrame:
    abc = classify_abc(sales_df, sku_df)
    inventory_latest = (
        inventory_df.copy()
        .assign(date=pd.to_datetime(inventory_df["date"]))
        .sort_values("date")
        .groupby("sku_id", as_index=False)
        .tail(1)
    )
    forecast_summary = (
        forecast_df.groupby("sku_id", as_index=False)["forecast_mean"].mean()
        .rename(columns={"forecast_mean": "forecast_weekly"})
    )

    merged = (
        sku_df.merge(abc, on="sku_id", how="left")
        .merge(inventory_latest, on="sku_id", how="left")
        .merge(forecast_summary, on="sku_id", how="left")
    )
    merged["abc_class"] = merged["abc_class"].fillna("C")
    merged["forecast_weekly"] = merged["forecast_weekly"].fillna(0)
    merged["on_hand_units"] = merged["on_hand_units"].fillna(0)
    merged["on_order_units"] = merged["on_order_units"].fillna(0)

    service_level_map = {
        "A": settings.service_level_a,
        "B": settings.service_level_b,
        "C": settings.service_level_c,
    }
    merged["service_level"] = merged["abc_class"].map(service_level_map)
    merged["lead_time_weeks"] = merged["lead_time_days"].fillna(0) / 7.0
    merged["demand_lt"] = merged["forecast_weekly"] * merged["lead_time_weeks"]
    merged["sigma_lt"] = residual_std * np.sqrt(merged["lead_time_weeks"].replace(0, 1))
    merged["z"] = merged["service_level"].map(SERVICE_LEVEL_Z).fillna(1.28)
    merged["safety_stock"] = merged["z"] * merged["sigma_lt"]
    merged["reorder_point"] = merged["demand_lt"] + merged["safety_stock"]

    merged["inventory_position"] = merged["on_hand_units"] + merged["on_order_units"]
    merged["raw_order"] = (merged["reorder_point"] - merged["inventory_position"]).clip(
        lower=0
    )
    merged["recommended_order_units"] = merged.apply(
        lambda row: round_to_pack_size(
            max(row["raw_order"], row["min_order_qty"]), row["pack_size"]
        ),
        axis=1,
    )

    coverage_map = {
        "A": settings.coverage_weeks_a,
        "B": settings.coverage_weeks_b,
        "C": settings.coverage_weeks_c,
    }
    merged["coverage_weeks_threshold"] = merged["abc_class"].map(coverage_map)
    merged["weeks_of_cover"] = merged["on_hand_units"].div(
        merged["forecast_weekly"].replace(0, np.nan)
    )
    merged["excess_inventory_flag"] = merged["weeks_of_cover"] > merged[
        "coverage_weeks_threshold"
    ]

    merged["action"] = np.select(
        [merged["recommended_order_units"] > 0, merged["excess_inventory_flag"]],
        ["BUY_MORE", "BUY_LESS"],
        default="HOLD",
    )
    merged["expected_cash_freed"] = np.where(
        merged["action"].eq("BUY_LESS"), merged["on_hand_units"] * merged["unit_cost"], 0
    )
    merged["stockout_risk"] = np.where(
        merged["inventory_position"] < merged["reorder_point"], 0.6, 0.2
    )
    merged["expected_stockout_risk_change"] = np.where(
        merged["action"].eq("BUY_MORE"), -0.2, 0.1
    )
    merged["confidence_score"] = 1 / (1 + merged["stockout_risk"])

    merged["explanation"] = ""

    return RecommendationFrame(
        recommendations=merged,
        abc_summary=abc,
    )


def _build_explanation(row: pd.Series) -> str:
    bullets = []
    trend = "up" if row["forecast_weekly"] >= row["rolling_baseline"] else "flat"
    bullets.append(f"Recent 4-week trend is {trend}.")
    bullets.append("Last-year same-week feature included in model.")
    if row.get("promo_flag", 0) > 0:
        bullets.append("Promotions recently lifted demand.")
    if row.get("stockout_week", 0) == 1:
        bullets.append("Stockout weeks detected; demand was censored.")
    if row["lead_time_days"] > 0:
        bullets.append("Lead time variability drives safety stock.")
    return " ".join(bullets[:5])


def enrich_for_explanations(
    weekly_sales: pd.DataFrame, recommendations: pd.DataFrame
) -> pd.DataFrame:
    baseline = (
        weekly_sales.groupby("sku_id")["censored_units"].tail(4).groupby("sku_id").mean()
    )
    stockout = weekly_sales.groupby("sku_id")["stockout_week"].max()
    promo = weekly_sales.groupby("sku_id")["promo_flag"].mean()
    enriched = recommendations.copy()
    enriched["rolling_baseline"] = enriched["sku_id"].map(baseline).fillna(0)
    enriched["stockout_week"] = enriched["sku_id"].map(stockout).fillna(0)
    enriched["promo_flag"] = enriched["sku_id"].map(promo).fillna(0)
    enriched["explanation"] = enriched.apply(_build_explanation, axis=1)
    return enriched
