"""
论文定时追踪 Celery 任务（对应 XiangMu 8.4）

功能：
- 周期性轮询已注册的领域查询（arXiv/PubMed），发现新论文；
- 去重（按标题集合持久化，避开重复入库）；
- 可选用自动「下载 PDF → 上传 MinIO → 创建文档 → 触发解析」入库闭环。

运行前提（生产）：
- 需 Redis（追踪注册表/已见集合持久化），Redis 不可用时自动降级为进程内内存态；
- 需同时启动 worker 与 beat 进程：
    celery -A app.core.celery_app worker  --pool=solo --loglevel=info
    celery -A app.core.celery_app beat    --loglevel=info
- 自动入库需配置 PAPER_TRACKING_DEFAULT_USER（系统调度用户 UUID），
  否则仅检测并记录新论文，不执行入库。

降级策略：
- 网络失败、Redis 缺失、数据库/存储不可用时仅返回记录，不抛异常；
- 未配置默认用户时不触发自动入库（跳过并说明）。
"""
import asyncio
import datetime
import json
import logging

logger = logging.getLogger(__name__)

try:
    import redis as _redis_cli  # type: ignore
except Exception:  # noqa: BLE001
    _redis_cli = None

from app.core.celery_app import celery_app
from app.core.config import settings
from app.services.paper_retrieval_service import search_arxiv, search_pubmed

# Redis 追踪存储（持久化，跨 worker/beat 进程共享）；不可用时降级为内存态
_redis_client = None
_redis_ready = None
_memory_store: dict[str, dict] = {}


def _get_redis():
    """懒加载同步 Redis 客户端并探活；失败返回 None（降级内存态）。"""
    global _redis_client, _redis_ready
    if _redis_ready is False:
        return None
    if _redis_client is None:
        if _redis_cli is None:
            _redis_ready = False
            return None
        try:
            _redis_client = _redis_cli.from_url(settings.REDIS_URL, decode_responses=True)
            _redis_client.ping()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Redis 不可用，论文追踪降级为内存态: {e}")
            _redis_ready = False
            _redis_client = None
            return None
    return _redis_client


def _load_json(key: str) -> dict:
    """读取追踪状态 JSON；Redis 优先，缺失时用内存态。"""
    r = _get_redis()
    if r is not None:
        try:
            raw = r.get(key)
            if raw:
                return json.loads(raw)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"读取追踪状态失败 {key}: {e}")
    return _memory_store.get(key, {})


def _save_json(key: str, data: dict) -> None:
    r = _get_redis()
    if r is not None:
        try:
            r.set(key, json.dumps(data, ensure_ascii=False))
            return
        except Exception as e:  # noqa: BLE001
            logger.warning(f"写入追踪状态失败 {key}: {e}")
    _memory_store[key] = data


def _list_tracking() -> list[dict]:
    """载入追踪注册表。优先级：Redis > 内存 > 服务单例内存态。"""
    data = _load_json("paper:tracking")
    records = data.get("items", [])
    if not records:
        # 兜底读取进程内服务注册的追踪（跨进程不可见，仅供单进程演示）
        try:
            from app.services.paper_retrieval_service import paper_retrieval_service

            records = paper_retrieval_service.list_tracking().get("items", [])
        except Exception:  # noqa: BLE001
            records = []
    return records


def _search(query: str, source: str) -> list[dict]:
    try:
        if source == "pubmed":
            return search_pubmed(query).get("results", [])
        return search_arxiv(query).get("results", [])
    except Exception as e:  # noqa: BLE001
        logger.warning(f"追踪查询 {query}[{source}] 失败: {e}")
        return []


async def _ingest_result(result: dict) -> dict:
    """下载→上传 MinIO→创建文档→触发解析（异步链路）。缺失依赖时降级。"""
    from app.services.document_service import DocumentService

    user_id = settings.PAPER_TRACKING_DEFAULT_USER
    if not user_id:
        return {"ingested": False, "skip": "未配置 PAPER_TRACKING_DEFAULT_USER"}
    try:
        from app.core.database import async_session
        from app.services.paper_retrieval_service import paper_retrieval_service

        meta, data = paper_retrieval_service.download_bytes(result)
        if not data:
            return {"ingested": False, "download": meta}
        title = result.get("title") or meta["filename"]
        async with async_session() as db:
            doc = await DocumentService().create_document_from_bytes(
                db, meta["filename"], data, "application/pdf", title, user_id
            )
            parsing = await DocumentService().trigger_parsing(
                db, doc.id, user_id, scope_all=True
            )
            await db.commit()
            return {"ingested": True, "document_id": doc.id, "download": meta, "parsing": parsing}
    except Exception as e:  # noqa: BLE001
        logger.warning(f"论文自动入库失败: {e}")
        return {"ingested": False, "error": str(e)}


def _run_poll() -> dict:
    """单轮调度：遍历追踪、检索、去重、可选入库。返回本轮摘要。"""
    if not settings.PAPER_TRACKING_ENABLED or not settings.PAPER_RETRIEVAL_ENABLED:
        return {"status": "disabled"}

    records = _list_tracking()
    summary = {"status": "ok", "checked": len(records), "new_papers": 0, "ingested": 0, "items": []}

    for rec in records:
        query = rec.get("query", "")
        source = rec.get("source", "arxiv")
        seen_key = f"paper:seen:{rec.get('id', '')}"
        seen = set(_load_json(seen_key).get("titles", []))
        results = _search(query, source)
        new = [r for r in results if r.get("title") and r["title"] not in seen]

        for r in new:
            seen.add(r["title"])
            item = {
                "query": query,
                "source": source,
                "title": r.get("title"),
                "arxiv_id": r.get("arxiv_id"),
                "pubmed_id": r.get("pubmed_id"),
                "published": r.get("published"),
                "detected_at": datetime.datetime.utcnow().isoformat() + "Z",
            }
            if settings.PAPER_TRACKING_AUTO_INGEST:
                ingest = asyncio.run(_ingest_result(r))
                item["ingest"] = ingest
                if ingest.get("ingested"):
                    summary["ingested"] += 1
            summary["new_papers"] += 1
            summary["items"].append(item)

        if new:
            _save_json(seen_key, {"titles": sorted(seen)})
            try:
                from app.services.paper_retrieval_service import paper_retrieval_service

                for r in new:
                    paper_retrieval_service.mark_seen(rec.get("id"), r)  # 内存态记录
            except Exception:  # noqa: BLE001
                pass

    return summary


@celery_app.task(name="paper_tracking_poll", queue="extraction")
def paper_tracking_poll_task():
    """Celery 周期任务：论文定时轮询（由 beat_schedule 触发，见 celery_app）。"""
    try:
        return _run_poll()
    except Exception as e:  # noqa: BLE001
        logger.exception("论文追踪轮询异常")
        return {"status": "error", "error": str(e)}