from __future__ import annotations

import pandas as pd


def rank_recommendations(df: pd.DataFrame) -> pd.DataFrame:
    ranked = df.copy()
    ranked["cash_tied"] = ranked["on_hand_units"] * ranked["unit_cost"]
    ranked["over_coverage"] = ranked["weeks_of_cover"].fillna(0)
    ranked = ranked.sort_values(
        ["cash_tied", "over_coverage", "stockout_risk"], ascending=False
    )
    ranked["priority"] = range(1, len(ranked) + 1)
    return ranked
