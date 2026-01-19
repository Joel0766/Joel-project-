from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class UploadResponse(BaseModel):
    dataset_version_id: int


class RunForecastRequest(BaseModel):
    dataset_version_id: int
    horizon_weeks: int


class RecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sku_id: str
    action: str
    recommended_order_units: int
    reorder_point: float
    safety_stock: float
    explanation: str
    confidence_score: float
    expected_cash_freed: float
    expected_stockout_risk_change: float
    abc_class: str
    recommendation_date: date


class OverrideRequest(BaseModel):
    new_order_qty: int
    reason_text: str
    user_name: str | None = None


class OverrideResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    override_id: int
    recommendation_id: int
    new_order_qty: int
    reason_text: str
