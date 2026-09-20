from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model import Model
from app.schemas.model import ModelCreate


class ModelService:
    async def list_models(self, db: AsyncSession, model_type: str = None, is_active: bool = None):
        query = select(Model)
        if model_type:
            query = query.where(Model.model_type == model_type)
        if is_active is not None:
            query = query.where(Model.is_active == is_active)
        result = await db.execute(query.order_by(Model.created_at.desc()))
        return result.scalars().all()

    async def get_model(self, db: AsyncSession, model_id: str):
        result = await db.execute(select(Model).where(Model.id == model_id))
        return result.scalar_one_or_none()

    async def create_model(self, db: AsyncSession, model_data: ModelCreate, created_by: str):
        model = Model(
            name=model_data.name,
            version=model_data.version,
            model_type=model_data.model_type,
            framework=model_data.framework,
            file_path=model_data.file_path,
            metrics=model_data.metrics,
            created_by=created_by,
        )
        db.add(model)
        await db.flush()
        await db.refresh(model)
        return model

    async def update_status(self, db: AsyncSession, model_id: str, is_active: bool):
        model = await self.get_model(db, model_id)
        if not model:
            return None
        model.is_active = is_active
        await db.flush()
        await db.refresh(model)
        return model

    async def delete_model(self, db: AsyncSession, model_id: str):
        model = await self.get_model(db, model_id)
        if not model:
            return False
        await db.delete(model)
        return True
