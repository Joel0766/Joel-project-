import pandas as pd

from app.inventory.policy import compute_policy, round_to_pack_size


def test_round_to_pack_size():
    assert round_to_pack_size(25, 10) == 30
    assert round_to_pack_size(0, 12) == 0


def test_compute_policy_reorder_point():
    sku_df = pd.DataFrame(
        {
            "sku_id": ["SKU-1"],
            "unit_cost": [2.0],
            "unit_price": [4.0],
            "lead_time_days": [7],
            "min_order_qty": [5],
            "pack_size": [5],
        }
    )
    inventory_df = pd.DataFrame(
        {
            "date": ["2024-01-01"],
            "sku_id": ["SKU-1"],
            "on_hand_units": [2],
            "on_order_units": [0],
        }
    )
    forecast_df = pd.DataFrame(
        {
            "sku_id": ["SKU-1"],
            "forecast_mean": [10.0],
        }
    )
    sales_df = pd.DataFrame(
        {
            "date": ["2024-01-01"],
            "sku_id": ["SKU-1"],
            "units_sold": [8],
        }
    )
    policy = compute_policy(sku_df, inventory_df, forecast_df, 1.0, sales_df)
    rec = policy.recommendations.iloc[0]
    assert rec["reorder_point"] > 0
    assert rec["recommended_order_units"] % 5 == 0
