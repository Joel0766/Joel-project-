from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    raw_paths: Mapped[dict] = mapped_column(JSON, default=dict)

    forecasts: Mapped[list[Forecast]] = relationship(back_populates="dataset")
    recommendations: Mapped[list[Recommendation]] = relationship(back_populates="dataset")


class Forecast(Base):
    __tablename__ = "forecasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("dataset_versions.id"))
    sku_id: Mapped[str] = mapped_column(String, index=True)
    week_start: Mapped[datetime] = mapped_column(Date)
    forecast_mean: Mapped[float] = mapped_column(Float)
    forecast_p10: Mapped[float] = mapped_column(Float)
    forecast_p90: Mapped[float] = mapped_column(Float)
    model_name: Mapped[str] = mapped_column(String)

    dataset: Mapped[DatasetVersion] = relationship(back_populates="forecasts")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("dataset_versions.id"))
    sku_id: Mapped[str] = mapped_column(String, index=True)
    recommendation_date: Mapped[datetime] = mapped_column(Date)
    action: Mapped[str] = mapped_column(String)
    recommended_order_units: Mapped[int] = mapped_column(Integer)
    reorder_point: Mapped[float] = mapped_column(Float)
    safety_stock: Mapped[float] = mapped_column(Float)
    explanation: Mapped[str] = mapped_column(String)
    confidence_score: Mapped[float] = mapped_column(Float)
    expected_cash_freed: Mapped[float] = mapped_column(Float)
    expected_stockout_risk_change: Mapped[float] = mapped_column(Float)
    abc_class: Mapped[str] = mapped_column(String)

    override: Mapped[Override | None] = relationship(back_populates="recommendation")
    dataset: Mapped[DatasetVersion] = relationship(back_populates="recommendations")


class Override(Base):
    __tablename__ = "overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(ForeignKey("recommendations.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    new_order_qty: Mapped[int] = mapped_column(Integer)
    reason_text: Mapped[str] = mapped_column(String)
    user_name: Mapped[str | None] = mapped_column(String, nullable=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=True)

    recommendation: Mapped[Recommendation] = relationship(back_populates="override")
