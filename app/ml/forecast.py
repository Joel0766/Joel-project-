from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.preprocessing import LabelEncoder

from app.core.config import settings


@dataclass
class ForecastResult:
    forecast_df: pd.DataFrame
    residual_std: float
    model_name: str


def moving_average_forecast(weekly_sales: pd.DataFrame, horizon: int) -> ForecastResult:
    rows = []
    for sku_id, group in weekly_sales.groupby("sku_id"):
        group = group.sort_values("week_start")
        mean_value = group["censored_units"].tail(8).mean()
        last_week = group["week_start"].max()
        for step in range(1, horizon + 1):
            week = last_week + pd.Timedelta(weeks=step)
            rows.append(
                {
                    "sku_id": sku_id,
                    "week_start": week,
                    "forecast_mean": float(mean_value),
                }
            )
    forecast_df = pd.DataFrame(rows)
    forecast_df["forecast_p10"] = forecast_df["forecast_mean"] * 0.8
    forecast_df["forecast_p90"] = forecast_df["forecast_mean"] * 1.2
    forecast_df["model_name"] = "moving_average"
    return ForecastResult(forecast_df=forecast_df, residual_std=0.0, model_name="moving_average")


def train_global_model(feature_frame: pd.DataFrame) -> tuple[LGBMRegressor, LabelEncoder]:
    train_df = feature_frame.dropna()
    encoder = LabelEncoder()
    train_df = train_df.copy()
    train_df["sku_encoded"] = encoder.fit_transform(train_df["sku_id"])
    feature_cols = [
        col
        for col in train_df.columns
        if col
        not in {
            "week_start",
            "units_sold",
            "censored_units",
            "sku_id",
        }
    ]
    X = train_df[feature_cols]
    y = train_df["censored_units"]
    model = LGBMRegressor(
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=31,
        random_state=42,
    )
    model.fit(X, y)
    return model, encoder


def forecast_with_model(
    feature_frame: pd.DataFrame,
    horizon: int,
) -> ForecastResult:
    model, encoder = train_global_model(feature_frame)
    df = feature_frame.copy()
    df["sku_encoded"] = encoder.transform(df["sku_id"])
    feature_cols = [
        col
        for col in df.columns
        if col
        not in {
            "week_start",
            "units_sold",
            "censored_units",
            "sku_id",
        }
    ]

    rows = []
    residuals = []
    for sku_id, group in df.groupby("sku_id"):
        group = group.sort_values("week_start")
        history = group.copy()
        for step in range(1, horizon + 1):
            latest = history.tail(1).copy()
            latest["week_start"] = latest["week_start"] + pd.Timedelta(weeks=1)
            latest["week_of_year"] = latest["week_start"].dt.isocalendar().week.astype(int)
            latest["month"] = latest["week_start"].dt.month.astype(int)
            X_pred = latest[feature_cols]
            y_pred = float(model.predict(X_pred)[0])
            rows.append({
                "sku_id": sku_id,
                "week_start": latest["week_start"].iloc[0],
                "forecast_mean": max(y_pred, 0.0),
            })
            latest["censored_units"] = y_pred
            history = pd.concat([history, latest], ignore_index=True)
        fitted = model.predict(group[feature_cols])
        residuals.extend(group["censored_units"].values - fitted)

    residual_std = float(np.std(residuals)) if residuals else 0.0
    forecast_df = pd.DataFrame(rows)
    forecast_df["forecast_p10"] = forecast_df["forecast_mean"] - 1.28 * residual_std
    forecast_df["forecast_p90"] = forecast_df["forecast_mean"] + 1.28 * residual_std
    forecast_df[["forecast_p10", "forecast_p90"]] = forecast_df[["forecast_p10", "forecast_p90"]].clip(
        lower=0
    )
    forecast_df["model_name"] = "lightgbm"
    return ForecastResult(forecast_df=forecast_df, residual_std=residual_std, model_name="lightgbm")


def generate_forecast(feature_frame: pd.DataFrame, horizon: int) -> ForecastResult:
    history_counts = feature_frame.groupby("sku_id")["week_start"].nunique()
    short_history = history_counts[history_counts < settings.history_min_weeks_for_ml].index
    long_history = history_counts[history_counts >= settings.history_min_weeks_for_ml].index

    forecast_frames = []
    residual_std = 0.0
    model_name = "hybrid"

    if len(long_history) > 0:
        model_result = forecast_with_model(
            feature_frame[feature_frame["sku_id"].isin(long_history)], horizon
        )
        forecast_frames.append(model_result.forecast_df)
        residual_std = model_result.residual_std

    if len(short_history) > 0:
        baseline_result = moving_average_forecast(
            feature_frame[feature_frame["sku_id"].isin(short_history)], horizon
        )
        forecast_frames.append(baseline_result.forecast_df)

    if not forecast_frames:
        return moving_average_forecast(feature_frame, horizon)

    combined = pd.concat(forecast_frames, ignore_index=True)
    return ForecastResult(forecast_df=combined, residual_std=residual_std, model_name=model_name)
