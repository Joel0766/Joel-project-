from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.core.config import settings


@dataclass
class FeatureFrames:
    weekly_sales: pd.DataFrame
    feature_frame: pd.DataFrame


def aggregate_weekly_sales(sales_df: pd.DataFrame) -> pd.DataFrame:
    sales_df = sales_df.copy()
    sales_df["date"] = pd.to_datetime(sales_df["date"])
    sales_df["week_start"] = sales_df["date"].dt.to_period("W").dt.start_time
    weekly = (
        sales_df.groupby(["sku_id", "week_start"], as_index=False)
        .agg({"units_sold": "sum", "promo_flag": "mean"})
        .sort_values(["sku_id", "week_start"])
    )
    return weekly


def add_stockout_flags(weekly_sales: pd.DataFrame, inventory_df: pd.DataFrame) -> pd.DataFrame:
    inventory_df = inventory_df.copy()
    inventory_df["date"] = pd.to_datetime(inventory_df["date"])
    inventory_df["week_start"] = inventory_df["date"].dt.to_period("W").dt.start_time
    weekly_inventory = (
        inventory_df.groupby(["sku_id", "week_start"], as_index=False)
        .agg({"on_hand_units": "min"})
        .rename(columns={"on_hand_units": "week_min_on_hand"})
    )
    merged = weekly_sales.merge(weekly_inventory, on=["sku_id", "week_start"], how="left")
    merged["stockout_week"] = merged["week_min_on_hand"].fillna(0).eq(0).astype(int)
    return merged


def cap_outliers(weekly_sales: pd.DataFrame) -> pd.DataFrame:
    df = weekly_sales.copy()

    def _cap(group: pd.DataFrame) -> pd.DataFrame:
        cap_value = group["units_sold"].quantile(0.95)
        group["units_sold"] = group["units_sold"].clip(upper=cap_value)
        return group

    return df.groupby("sku_id", group_keys=False).apply(_cap)


def censor_demand(weekly_sales: pd.DataFrame) -> pd.DataFrame:
    df = weekly_sales.copy()
    if settings.censoring_strategy == "nearest":
        df["censored_units"] = df["units_sold"].where(
            df["stockout_week"].eq(0), df["units_sold"].shift(1)
        )
    else:
        df["censored_units"] = df["units_sold"]
        rolling = df.groupby("sku_id")["units_sold"].transform(
            lambda x: x.rolling(4, min_periods=1).median()
        )
        df.loc[df["stockout_week"].eq(1), "censored_units"] = rolling
    df["censored_units"] = df["censored_units"].fillna(df["units_sold"])
    return df


def add_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    lags = [1, 2, 4, 8, 13, 26, 52]
    for lag in lags:
        df[f"lag_{lag}"] = df.groupby("sku_id")["censored_units"].shift(lag)
    df["rolling_mean_4"] = df.groupby("sku_id")["censored_units"].transform(
        lambda x: x.rolling(4, min_periods=1).mean()
    )
    df["rolling_mean_8"] = df.groupby("sku_id")["censored_units"].transform(
        lambda x: x.rolling(8, min_periods=1).mean()
    )
    df["rolling_std_8"] = df.groupby("sku_id")["censored_units"].transform(
        lambda x: x.rolling(8, min_periods=1).std().fillna(0)
    )
    return df


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["week_of_year"] = df["week_start"].dt.isocalendar().week.astype(int)
    df["month"] = df["week_start"].dt.month.astype(int)
    df["holiday_flag"] = 0
    df["promo_intensity_4"] = df.groupby("sku_id")["promo_flag"].transform(
        lambda x: x.rolling(4, min_periods=1).mean()
    )
    return df


def build_feature_frame(
    sales_df: pd.DataFrame, inventory_df: pd.DataFrame
) -> FeatureFrames:
    weekly_sales = aggregate_weekly_sales(sales_df)
    weekly_sales = add_stockout_flags(weekly_sales, inventory_df)
    weekly_sales = cap_outliers(weekly_sales)
    weekly_sales = censor_demand(weekly_sales)
    features = add_lag_features(weekly_sales)
    features = add_time_features(features)
    return FeatureFrames(weekly_sales=weekly_sales, feature_frame=features)
