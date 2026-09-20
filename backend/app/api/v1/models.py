from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.schemas.model import ModelCreate, ModelResponse, ModelStatusUpdate
from app.services.model_service import ModelService

router = APIRouter()
model_service = ModelService()


@router.get("/", response_model=list[ModelResponse])
async def list_models(
    model_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await model_service.list_models(db, model_type, is_active)


@router.post("/", response_model=ModelResponse, status_code=201)
async def register_model(
    model_data: ModelCreate,
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    return await model_service.create_model(db, model_data, current_user["user_id"])


@router.get("/{model_id}", response_model=ModelResponse)
async def get_model(
    model_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    model = await model_service.get_model(db, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.put("/{model_id}/status", response_model=ModelResponse)
async def update_model_status(
    model_id: str,
    status_update: ModelStatusUpdate,
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    model = await model_service.update_status(db, model_id, status_update.is_active)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.delete("/{model_id}", status_code=204)
async def delete_model(
    model_id: str,
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    deleted = await model_service.delete_model(db, model_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Model not found")
