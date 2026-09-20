from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import TASK_READ, TASK_WRITE, has_permission, require_permission
from app.schemas.task import TaskAssign, TaskCreate, TaskListResponse, TaskResponse
from app.services.task_service import TaskService

router = APIRouter()
task_service = TaskService()


@router.post("/", response_model=TaskResponse, status_code=201)
async def create_task(
    task_data: TaskCreate,
    current_user: dict = Depends(require_permission(TASK_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    return await task_service.create_task(db, task_data, current_user["user_id"])


@router.get("/", response_model=TaskListResponse)
async def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: Optional[str] = None,
    task_type: Optional[str] = None,
    assigned_to: Optional[str] = None,
    current_user: dict = Depends(require_permission(TASK_READ)),
    db: AsyncSession = Depends(get_db),
):
    scope_all = has_permission(current_user, TASK_WRITE)
    tasks, total = await task_service.list_tasks(
        db, page, page_size, status, task_type, assigned_to, current_user["user_id"], scope_all
    )
    return TaskListResponse(items=tasks, total=total, page=page, page_size=page_size)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    current_user: dict = Depends(require_permission(TASK_READ)),
    db: AsyncSession = Depends(get_db),
):
    scope_all = has_permission(current_user, TASK_WRITE)
    task = await task_service.get_task_scoped(db, task_id, current_user["user_id"], scope_all)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/{task_id}/assign", response_model=TaskResponse)
async def assign_task(
    task_id: str,
    task_data: TaskAssign,
    current_user: dict = Depends(require_permission(TASK_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    """手动分配任务：指定负责人、优先级、截止日期。"""
    task = await task_service.assign_task(db, task_id, task_data, current_user["user_id"])
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/{task_id}/progress")
async def get_task_progress(
    task_id: str,
    current_user: dict = Depends(require_permission(TASK_READ)),
    db: AsyncSession = Depends(get_db),
):
    scope_all = has_permission(current_user, TASK_WRITE)
    task = await task_service.get_task_scoped(db, task_id, current_user["user_id"], scope_all)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    result = await task_service.sync_task_progress(db, task_id)
    return result


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    current_user: dict = Depends(require_permission(TASK_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    task = await task_service.cancel_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task cancelled", "task": task}


@router.post("/{task_id}/pause")
async def pause_task(
    task_id: str,
    current_user: dict = Depends(require_permission(TASK_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    task = await task_service.pause_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task paused", "task": task}


@router.post("/{task_id}/resume")
async def resume_task(
    task_id: str,
    current_user: dict = Depends(require_permission(TASK_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    task = await task_service.resume_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task resumed", "task": task}


@router.post("/{task_id}/retry")
async def retry_task(
    task_id: str,
    current_user: dict = Depends(require_permission(TASK_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    result = await task_service.retry_task(db, task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


@router.delete("/{task_id}/terminate")
async def terminate_task(
    task_id: str,
    current_user: dict = Depends(require_permission(TASK_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    result = await task_service.terminate_task(db, task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result
