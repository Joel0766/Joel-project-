import pandas as pd

from app.core.validation import (
    ValidationError,
    validate_inventory,
    validate_sales,
    validate_sku_master,
)


def test_validate_sku_master_success():
    df = pd.DataFrame(
        {
            "sku_id": ["SKU-1"],
            "unit_cost": [1.0],
            "unit_price": [2.0],
        }
    )
    assert validate_sku_master(df).shape[0] == 1


def test_validate_sales_negative_units():
    df = pd.DataFrame(
        {"date": ["2024-01-01"], "sku_id": ["SKU-1"], "units_sold": [-1]}
    )
    try:
        validate_sales(df)
        assert False, "Expected ValidationError"
    except ValidationError:
        assert True


def test_validate_inventory_missing_column():
    df = pd.DataFrame({"date": ["2024-01-01"], "sku_id": ["SKU-1"]})
    try:
        validate_inventory(df)
        assert False, "Expected ValidationError"
    except ValidationError:
        assert True
