# -*- coding: utf-8 -*-
"""步骤 8.3 真实环境验证：服务连通 + 下载 arXiv PDF + MinIO 上传 + 建档 + 触发解析。"""
import asyncio
import os
import sys

# 从 backend 目录运行（需本地 backend/.env 被 pydantic 加载）
sys.path.insert(0, os.path.abspath("."))


async def main():
    from sqlalchemy import text

    from app.core.config import settings
    from app.core.database import async_session
    from app.models.document import Document
    from app.services.document_service import DocumentService
    from app.services.paper_retrieval_service import paper_retrieval_service

    print("== 连通性 ==")
    # Redis
    try:
        import redis

        r = redis.from_url(settings.REDIS_URL, decode_responses=True)
        print("Redis ping:", r.ping())
    except Exception as e:  # noqa: BLE001
        print("Redis FAIL:", e)
    # MinIO
    try:
        from app.utils.minio_client import MinioClient

        mc = MinioClient()
        print("MinIO bucket exists:", mc.client.bucket_exists(settings.MINIO_BUCKET_NAME))
    except Exception as e:  # noqa: BLE001
        print("MinIO FAIL:", e)
    # MySQL
    try:
        async with async_session() as db:
            await db.execute(text("SELECT 1"))
            print("MySQL SELECT 1: ok")
            total = (await db.execute(text("SELECT COUNT(*) c FROM documents"))).scalar()
            print("documents count:", total)
    except Exception as e:  # noqa: BLE001
        print("MySQL FAIL:", e)

    print("== 8.3 真实下载入库 ===")
    # 取一个真实用户 UUID（uploaded_by 为外键 → users.id）
    async with async_session() as db:
        uid = (await db.execute(text("SELECT id FROM users LIMIT 1"))).scalar()
    print("using user_id:", uid)
    if not uid:
        print("SKIP: users 表为空")
        return

    # 清理上轮可能的 MinIO 孤儿对象
    from app.utils.minio_client import MinioClient

    mc = MinioClient()
    try:
        mc.client.remove_object(settings.MINIO_BUCKET_NAME, "original/admin/1706.03762.pdf")
    except Exception:  # noqa: BLE001
        pass

    result = {"source": "arxiv", "arxiv_id": "1706.03762"}
    meta, data = paper_retrieval_service.download_bytes(result)
    print("download:", meta.get("downloaded"), meta.get("error", ""))
    if not data:
        print("SKIP: 无法下载 PDF（网络或 arXiv 受限）")
        return
    print("PDF bytes:", len(data))
    async with async_session() as db:
        doc = await DocumentService().create_document_from_bytes(
            db, meta["filename"], data, "application/pdf", "Attention Is All You Need (实测)", uid
        )
        print("document_id:", doc.id, "status:", doc.status, "MinIO object:", doc.file_path)
        parsing = await DocumentService().trigger_parsing(db, doc.id, uid, scope_all=True)
        print("parsing:", parsing)
        await db.commit()


asyncio.run(main())