from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.schemas import (
    OverrideRequest,
    OverrideResponse,
    RecommendationOut,
    RunForecastRequest,
    UploadResponse,
)
from app.core.config import settings
from app.core.ingestion import ingest_dataset
from app.core.pipeline import run_forecast_job
from app.db.models import Base, DatasetVersion, Forecast, Override, Recommendation
from app.db.session import SessionLocal, engine

app = FastAPI(title="Inventory Planning MVP")
Base.metadata.create_all(bind=engine)

app.mount("/static", StaticFiles(directory="app/ui/static"), name="static")


templates = Jinja2Templates(directory="app/ui/templates")


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/datasets/upload", response_model=UploadResponse)
async def upload_dataset(
    sku_master: UploadFile = File(...),
    sales_orders: UploadFile = File(...),
    inventory_snapshots: UploadFile = File(...),
    purchase_orders: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> UploadResponse:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    upload_dir = settings.data_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_map = {
        "sku_master": sku_master,
        "sales_orders": sales_orders,
        "inventory_snapshots": inventory_snapshots,
        "purchase_orders": purchase_orders,
    }
    raw_paths = {}
    for key, upload in file_map.items():
        file_path = upload_dir / f"{key}_{upload.filename}"
        content = await upload.read()
        file_path.write_bytes(content)
        raw_paths[key] = file_path

    ingest_info = ingest_dataset(raw_paths)
    dataset = DatasetVersion(raw_paths={"dataset_dir": str(ingest_info["dataset_dir"])})
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return UploadResponse(dataset_version_id=dataset.id)


@app.post("/jobs/run_forecast")
def run_forecast(payload: RunForecastRequest, db: Session = Depends(get_db)) -> dict[str, int]:
    dataset = db.get(DatasetVersion, payload.dataset_version_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset version not found")
    dataset_dir = Path(dataset.raw_paths["dataset_dir"])
    result = run_forecast_job(dataset_dir, payload.horizon_weeks, dataset_id=dataset.id)
    return result


@app.get("/recommendations", response_model=list[RecommendationOut])
def list_recommendations(
    date: Optional[date] = None,
    abc: Optional[str] = None,
    action: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[RecommendationOut]:
    query = db.query(Recommendation)
    if date:
        query = query.filter(Recommendation.recommendation_date == date)
    if abc:
        query = query.filter(Recommendation.abc_class == abc)
    if action:
        query = query.filter(Recommendation.action == action)
    return [RecommendationOut.model_validate(row) for row in query.all()]


@app.post("/recommendations/{rec_id}/override", response_model=OverrideResponse)
def override_recommendation(
    rec_id: int,
    payload: OverrideRequest,
    db: Session = Depends(get_db),
) -> OverrideResponse:
    recommendation = db.get(Recommendation, rec_id)
    if not recommendation:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    override = Override(
        recommendation_id=rec_id,
        new_order_qty=payload.new_order_qty,
        reason_text=payload.reason_text,
        user_name=payload.user_name,
    )
    db.add(override)
    db.commit()
    db.refresh(override)
    return OverrideResponse(
        override_id=override.id,
        recommendation_id=rec_id,
        new_order_qty=override.new_order_qty,
        reason_text=override.reason_text,
    )


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return HTMLResponse("<h2>Inventory Planning MVP</h2><p>Visit /ui</p>")


@app.get("/ui", response_class=HTMLResponse)
def ui_dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/ui/upload", response_class=HTMLResponse)
def ui_upload(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})


@app.get("/ui/job", response_class=HTMLResponse)
def ui_job(request: Request, db: Session = Depends(get_db)):
    datasets = db.query(DatasetVersion).order_by(DatasetVersion.id.desc()).all()
    return templates.TemplateResponse(
        "job.html", {"request": request, "datasets": datasets}
    )


@app.get("/ui/recommendations", response_class=HTMLResponse)
def ui_recommendations(request: Request, db: Session = Depends(get_db)):
    recommendations = db.query(Recommendation).order_by(Recommendation.id.desc()).all()
    return templates.TemplateResponse(
        "recommendations.html", {"request": request, "recommendations": recommendations}
    )


@app.get("/ui/sku/{sku_id}", response_class=HTMLResponse)
def ui_sku_detail(sku_id: str, request: Request, db: Session = Depends(get_db)):
    rec = db.query(Recommendation).filter(Recommendation.sku_id == sku_id).first()
    forecasts = (
        db.query(Forecast).filter(Forecast.sku_id == sku_id).order_by(Forecast.week_start)
    ).all()
    return templates.TemplateResponse(
        "sku_detail.html",
        {
            "request": request,
            "rec": rec,
            "forecasts": forecasts,
        },
    )
