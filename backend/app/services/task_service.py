from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.task import Task


class TaskService:
    async def create_task(self, db: AsyncSession, task_data, user_id: str) -> Task:
        task = Task(
            task_type=task_data.task_type,
            document_id=task_data.document_id,
            assigned_to=task_data.assigned_to,
            assigned_by=user_id,
            priority=task_data.priority,
            due_at=task_data.due_at,
            params=task_data.params,
            status="pending",
        )
        db.add(task)
        await db.flush()
        await db.refresh(task)
        return task

    async def assign_task(self, db: AsyncSession, task_id: str, task_data, user_id: str):
        """手动分配任务：设置负责人、优先级、截止日期。"""
        task = await self.get_task(db, task_id)
        if not task:
            return None
        task.assigned_to = task_data.assigned_to
        if task_data.priority is not None:
            task.priority = task_data.priority
        if task_data.due_at is not None:
            task.due_at = task_data.due_at
        task.assigned_by = user_id
        await db.flush()
        await db.refresh(task)
        return task

    async def get_task(self, db: AsyncSession, task_id: str):
        result = await db.execute(select(Task).where(Task.id == task_id))
        return result.scalar_one_or_none()

    async def get_task_scoped(
        self, db: AsyncSession, task_id: str, user_id: str = None, scope_all: bool = False
    ):
        """带归属校验的任务查询：非全局范围时仅负责人/创建人可访问。"""
        task = await self.get_task(db, task_id)
        if not task:
            return None
        if user_id is not None and not scope_all:
            if task.assigned_to != user_id and task.assigned_by != user_id:
                raise HTTPException(status_code=403, detail="无权访问该任务")
        return task

    async def get_task_with_celery_status(self, db: AsyncSession, task_id: str):
        """获取任务及其 Celery 实时状态"""
        task = await self.get_task(db, task_id)
        if not task:
            return None

        # 如果有 Celery task_id，查询实时状态
        celery_status = None
        if task.celery_task_id:
            celery_status = self._get_celery_task_status(task.celery_task_id)

        return {
            "task": task,
            "celery_status": celery_status,
        }

    def _get_celery_task_status(self, celery_task_id: str) -> Optional[dict]:
        """查询 Celery 任务实时状态"""
        try:
            from app.core.celery_app import celery_app

            inspector = celery_app.control.inspect()

            # 尝试获取任务状态
            if hasattr(inspector, "query_task"):
                # Flower 风格的查询
                try:
                    info = inspector.query_task(celery_task_id)
                    if info:
                        return {
                            "state": info.get("state", "PENDING"),
                            "info": info,
                        }
                except Exception:
                    pass

            # 尝试主动任务查询
            try:
                result = celery_app.AsyncResult(celery_task_id)
                return {
                    "state": result.state,
                    "info": result.info if not result.ready() else None,
                }
            except Exception:
                pass

            return None
        except Exception:
            return None

    async def sync_task_progress(self, db: AsyncSession, task_id: str) -> dict:
        """
        同步 Celery 任务进度到数据库
        返回同步后的进度信息
        """
        task = await self.get_task(db, task_id)
        if not task or not task.celery_task_id:
            return {
                "progress": task.progress if task else 0,
                "status": task.status if task else None,
            }

        celery_status = self._get_celery_task_status(task.celery_task_id)

        if celery_status:
            state = celery_status.get("state", "PENDING")
            info = celery_status.get("info", {})

            # 同步状态
            if state == "PROGRESS":
                progress = info.get("progress", 0) if isinstance(info, dict) else 0
                if task.status != "running":
                    task.status = "running"
                task.progress = progress
            elif state == "SUCCESS":
                task.status = "completed"
                task.progress = 100
            elif state == "FAILURE":
                task.status = "failed"
                task.error_message = str(info) if info else "任务执行失败"
            elif state == "REVOKED":
                task.status = "cancelled"

            await db.flush()
            await db.refresh(task)

        return {
            "progress": task.progress,
            "status": task.status,
            "celery_state": celery_status.get("state") if celery_status else None,
        }

    async def list_tasks(
        self,
        db: AsyncSession,
        page: int,
        page_size: int,
        status: str = None,
        task_type: str = None,
        assigned_to: str = None,
        user_id: str = None,
        scope_all: bool = False,
        sync_progress: bool = True,
    ):
        """
        获取任务列表，可选同步 Celery 进度
        """
        query = select(Task)
        if not scope_all and user_id is not None:
            query = query.where(or_(Task.assigned_to == user_id, Task.assigned_by == user_id))
        if status:
            query = query.where(Task.status == status)
        if task_type:
            query = query.where(Task.task_type == task_type)
        if assigned_to:
            query = query.where(Task.assigned_to == assigned_to)

        count_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_query)

        query = (
            query.offset((page - 1) * page_size).limit(page_size).order_by(Task.created_at.desc())
        )
        result = await db.execute(query)
        tasks = result.scalars().all()

        # 同步运行中任务的进度
        if sync_progress:
            for task in tasks:
                if task.celery_task_id and task.status in ("pending", "running"):
                    celery_status = self._get_celery_task_status(task.celery_task_id)
                    if celery_status:
                        state = celery_status.get("state", "PENDING")
                        info = celery_status.get("info", {})

                        if state == "PROGRESS" and isinstance(info, dict):
                            task.progress = info.get("progress", task.progress)
                            task.status = "running"
                        elif state == "SUCCESS":
                            task.status = "completed"
                            task.progress = 100
                        elif state == "FAILURE":
                            task.status = "failed"
                        elif state == "REVOKED":
                            task.status = "cancelled"

            if tasks:
                await db.flush()

        return tasks, total

    async def cancel_task(self, db: AsyncSession, task_id: str):
        task = await self.get_task(db, task_id)
        if not task:
            return None
        if task.status in ("completed", "cancelled", "failed"):
            return task
        task.status = "cancelled"
        # Revoke Celery task if exists
        if task.celery_task_id:
            self._revoke_celery_task(task.celery_task_id)
        await db.flush()
        await db.refresh(task)
        return task

    async def pause_task(self, db: AsyncSession, task_id: str):
        task = await self.get_task(db, task_id)
        if not task:
            return None
        if task.status != "running":
            return task
        task.status = "paused"
        # Revoke Celery task if exists
        if task.celery_task_id:
            self._revoke_celery_task(task.celery_task_id)
        await db.flush()
        await db.refresh(task)
        return task

    async def resume_task(self, db: AsyncSession, task_id: str):
        task = await self.get_task(db, task_id)
        if not task:
            return None
        if task.status != "paused":
            return task
        task.status = "running"
        await db.flush()
        await db.refresh(task)
        return task

    def _revoke_celery_task(self, celery_task_id: str):
        try:
            from app.core.celery_app import celery_app

            celery_app.control.revoke(celery_task_id, terminate=True)
        except Exception:
            pass

    async def retry_task(self, db: AsyncSession, task_id: str):
        task = await self.get_task(db, task_id)
        if not task:
            return None
        if task.status not in ("failed", "cancelled"):
            return {"error": "只能重试失败或已取消的任务"}

        if not task.document_id:
            return {"error": "该任务没有关联文档，无法重试"}

        # Dispatch a new Celery task
        new_task = None
        try:
            if task.task_type == "parsing":
                from app.workers.parsing_tasks import parse_document_task

                celery_t = parse_document_task.delay(task.document_id)
                new_task = Task(
                    task_type=task.task_type,
                    document_id=task.document_id,
                    status="pending",
                    celery_task_id=celery_t.id,
                )
            elif task.task_type == "extraction":
                from app.workers.extraction_tasks import extract_entities

                celery_t = extract_entities.delay(task.document_id)
                new_task = Task(
                    task_type=task.task_type,
                    document_id=task.document_id,
                    status="pending",
                    celery_task_id=celery_t.id,
                )
            elif task.task_type == "graph":
                from app.workers.graph_tasks import build_knowledge_graph

                celery_t = build_knowledge_graph.delay(task.document_id)
                new_task = Task(
                    task_type=task.task_type,
                    document_id=task.document_id,
                    status="pending",
                    celery_task_id=celery_t.id,
                )
        except Exception:
            return {"error": "Celery 未运行，无法重试"}

        if new_task:
            db.add(new_task)
            await db.flush()
            await db.refresh(new_task)
            return {"message": "任务已重新提交", "task": new_task}

        return {"error": "未知任务类型"}

    async def terminate_task(self, db: AsyncSession, task_id: str):
        """终止任务：删除任务记录，并将关联文档状态改为 failed（不删除文档）"""
        task = await self.get_task(db, task_id)
        if not task:
            return None

        # Revoke Celery task if exists
        if task.celery_task_id:
            self._revoke_celery_task(task.celery_task_id)

        # Update document status to failed (if associated document exists)
        if task.document_id:
            doc_result = await db.execute(select(Document).where(Document.id == task.document_id))
            doc = doc_result.scalar_one_or_none()
            if doc and doc.status in ("parsing", "pending"):
                doc.status = "failed"
                await db.flush()

        # Delete the task record
        await db.delete(task)
        await db.commit()
        return {"message": "任务已终止并删除"}
