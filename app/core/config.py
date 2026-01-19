from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings for the MVP.

    Domain assumptions:
    - Weekly planning is default.
    - Lead time is provided in days, converted to weeks.
    - Holding cost defaults to 20% of unit cost annually.
    """

    model_config = SettingsConfigDict(env_prefix="INV_", env_file=".env")

    data_dir: Path = Field(default=Path("data"))
    database_url: str = Field(default="sqlite:///./data/app.db")
    reports_dir: Path = Field(default=Path("reports"))

    forecast_horizon_weeks: int = Field(default=8)
    history_min_weeks_for_ml: int = Field(default=20)

    service_level_a: float = Field(default=0.95)
    service_level_b: float = Field(default=0.92)
    service_level_c: float = Field(default=0.9)

    annual_holding_cost_rate: float = Field(default=0.2)
    fallback_stockout_penalty: float = Field(default=1.0)

    coverage_weeks_a: int = Field(default=8)
    coverage_weeks_b: int = Field(default=10)
    coverage_weeks_c: int = Field(default=12)

    censoring_strategy: Literal["nearest", "rolling_median"] = Field(
        default="rolling_median"
    )


settings = Settings()
