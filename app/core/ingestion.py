from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import settings
from app.core.validation import (
    validate_inventory,
    validate_purchase_orders,
    validate_sales,
    validate_sku_master,
)


def _ensure_data_dir() -> Path:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings.data_dir


def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def infer_lead_time_days(po_df: pd.DataFrame) -> pd.Series:
    if "actual_receipt_date" in po_df.columns:
        receipts = po_df["actual_receipt_date"].fillna(po_df.get("expected_receipt_date"))
    else:
        receipts = po_df.get("expected_receipt_date")
    po_df = po_df.copy()
    po_df["order_date"] = pd.to_datetime(po_df["order_date"])
    po_df["receipt_date"] = pd.to_datetime(receipts)
    po_df["lead_time_days"] = (po_df["receipt_date"] - po_df["order_date"]).dt.days
    lead_times = po_df.groupby("sku_id")["lead_time_days"].median().dropna()
    return lead_times


def clean_sku_master(df: pd.DataFrame, lead_time_by_sku: pd.Series) -> pd.DataFrame:
    df = df.copy()
    df["lead_time_days"] = df["lead_time_days"].fillna(df["sku_id"].map(lead_time_by_sku))
    df["lead_time_days"] = df["lead_time_days"].fillna(0).astype(int)
    df["min_order_qty"] = df.get("min_order_qty", 0).fillna(0).astype(int)
    df["pack_size"] = df.get("pack_size", 1).fillna(1).astype(int)
    df["discontinued"] = df.get("discontinued", False).fillna(False).astype(bool)
    return df


def clean_inventory(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["on_order_units"] = df.get("on_order_units", 0).fillna(0).astype(int)
    df["date"] = pd.to_datetime(df["date"])
    return df


def clean_sales(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["promo_flag"] = df.get("promo_flag", 0).fillna(0).astype(int)
    return df


def clean_purchase_orders(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["order_date"] = pd.to_datetime(df["order_date"])
    if "expected_receipt_date" in df.columns:
        df["expected_receipt_date"] = pd.to_datetime(df["expected_receipt_date"])
    if "actual_receipt_date" in df.columns:
        df["actual_receipt_date"] = pd.to_datetime(df["actual_receipt_date"])
    return df


def ingest_dataset(raw_paths: dict[str, Path], notes: str | None = None) -> dict[str, Any]:
    """Validate and store cleaned datasets.

    Returns metadata with dataset_version_id placeholder for persistence.
    """

    _ensure_data_dir()
    sku_df = validate_sku_master(load_csv(raw_paths["sku_master"]))
    sales_df = validate_sales(load_csv(raw_paths["sales_orders"]))
    inv_df = validate_inventory(load_csv(raw_paths["inventory_snapshots"]))
    po_df = validate_purchase_orders(load_csv(raw_paths["purchase_orders"]))

    lead_time_by_sku = infer_lead_time_days(po_df)
    sku_df = clean_sku_master(sku_df, lead_time_by_sku)
    sales_df = clean_sales(sales_df)
    inv_df = clean_inventory(inv_df)
    po_df = clean_purchase_orders(po_df)

    dataset_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    dataset_dir = settings.data_dir / f"dataset_{dataset_id}"
    dataset_dir.mkdir(parents=True, exist_ok=True)

    raw_copy_paths = {}
    for key, path in raw_paths.items():
        dest = dataset_dir / f"{key}_raw.csv"
        shutil.copy(path, dest)
        raw_copy_paths[key] = dest

    cleaned_paths = {
        "sku_master": dataset_dir / "sku_master_clean.csv",
        "sales_orders": dataset_dir / "sales_orders_clean.csv",
        "inventory_snapshots": dataset_dir / "inventory_snapshots_clean.csv",
        "purchase_orders": dataset_dir / "purchase_orders_clean.csv",
    }
    sku_df.to_csv(cleaned_paths["sku_master"], index=False)
    sales_df.to_csv(cleaned_paths["sales_orders"], index=False)
    inv_df.to_csv(cleaned_paths["inventory_snapshots"], index=False)
    po_df.to_csv(cleaned_paths["purchase_orders"], index=False)

    raw_manifest = {key: str(path) for key, path in raw_copy_paths.items()}
    with (dataset_dir / "manifest.json").open("w") as handle:
        json.dump({"raw_paths": raw_manifest, "notes": notes}, handle, indent=2)

    return {
        "dataset_id": dataset_id,
        "dataset_dir": dataset_dir,
        "cleaned_paths": cleaned_paths,
    }


def read_clean_tables(dataset_dir: Path) -> dict[str, pd.DataFrame]:
    return {
        "sku_master": pd.read_csv(dataset_dir / "sku_master_clean.csv"),
        "sales_orders": pd.read_csv(dataset_dir / "sales_orders_clean.csv"),
        "inventory_snapshots": pd.read_csv(dataset_dir / "inventory_snapshots_clean.csv"),
        "purchase_orders": pd.read_csv(dataset_dir / "purchase_orders_clean.csv"),
    }
