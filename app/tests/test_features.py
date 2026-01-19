import pandas as pd

from app.ml.features import build_feature_frame


def test_build_feature_frame_adds_lags():
    sales = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-08", "2024-01-15"],
            "sku_id": ["SKU-1", "SKU-1", "SKU-1"],
            "units_sold": [10, 12, 14],
            "promo_flag": [0, 0, 1],
        }
    )
    inventory = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-08", "2024-01-15"],
            "sku_id": ["SKU-1", "SKU-1", "SKU-1"],
            "on_hand_units": [5, 3, 2],
            "on_order_units": [0, 0, 0],
        }
    )
    feature_frames = build_feature_frame(sales, inventory)
    assert "lag_1" in feature_frames.feature_frame.columns
    assert "rolling_mean_4" in feature_frames.feature_frame.columns
