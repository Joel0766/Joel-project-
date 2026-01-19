from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


class ValidationError(Exception):
    """Raised when a dataset fails validation."""


@dataclass
class ColumnSpec:
    name: str
    required: bool = True


SKU_MASTER_COLUMNS = [
    ColumnSpec("sku_id"),
    ColumnSpec("sku_name", required=False),
    ColumnSpec("category", required=False),
    ColumnSpec("uom", required=False),
    ColumnSpec("unit_cost"),
    ColumnSpec("unit_price"),
    ColumnSpec("supplier_id", required=False),
    ColumnSpec("lead_time_days", required=False),
    ColumnSpec("min_order_qty", required=False),
    ColumnSpec("pack_size", required=False),
    ColumnSpec("discontinued", required=False),
]

SALES_COLUMNS = [
    ColumnSpec("date"),
    ColumnSpec("sku_id"),
    ColumnSpec("units_sold"),
    ColumnSpec("customer_id", required=False),
    ColumnSpec("promo_flag", required=False),
    ColumnSpec("channel", required=False),
]

INVENTORY_COLUMNS = [
    ColumnSpec("date"),
    ColumnSpec("sku_id"),
    ColumnSpec("on_hand_units"),
    ColumnSpec("on_order_units", required=False),
]

PO_COLUMNS = [
    ColumnSpec("po_id"),
    ColumnSpec("sku_id"),
    ColumnSpec("order_date"),
    ColumnSpec("expected_receipt_date", required=False),
    ColumnSpec("actual_receipt_date", required=False),
    ColumnSpec("units_ordered"),
]


def _check_columns(df: pd.DataFrame, specs: list[ColumnSpec]) -> None:
    missing = [spec.name for spec in specs if spec.required and spec.name not in df.columns]
    if missing:
        raise ValidationError(f"Missing required columns: {missing}")


def _check_non_negative(df: pd.DataFrame, column: str) -> None:
    if (df[column].fillna(0) < 0).any():
        raise ValidationError(f"Column {column} has negative values")


def validate_sku_master(df: pd.DataFrame) -> pd.DataFrame:
    _check_columns(df, SKU_MASTER_COLUMNS)
    _check_non_negative(df, "unit_cost")
    _check_non_negative(df, "unit_price")
    if df["sku_id"].isna().any():
        raise ValidationError("sku_id contains missing values")
    if df["sku_id"].duplicated().any():
        raise ValidationError("sku_id must be unique")
    return df


def validate_sales(df: pd.DataFrame) -> pd.DataFrame:
    _check_columns(df, SALES_COLUMNS)
    _check_non_negative(df, "units_sold")
    return df


def validate_inventory(df: pd.DataFrame) -> pd.DataFrame:
    _check_columns(df, INVENTORY_COLUMNS)
    _check_non_negative(df, "on_hand_units")
    if "on_order_units" in df.columns:
        _check_non_negative(df, "on_order_units")
    return df


def validate_purchase_orders(df: pd.DataFrame) -> pd.DataFrame:
    _check_columns(df, PO_COLUMNS)
    _check_non_negative(df, "units_ordered")
    return df
