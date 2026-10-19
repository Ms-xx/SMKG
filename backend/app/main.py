import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.plugin.manager import PluginManager
from app.middleware.logging import LoggingMiddleware
from app.services.graphrag_integration import _close_async_client
from app.utils.business_metrics import setup_business_metrics
from app.utils.metrics import setup_metrics
from app.utils.neo4j_client import Neo4jClient
from app.utils.redis_client import get_redis_client

setup_logging()

logger = logging.getLogger(__name__)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Request-ID"],
)

app.add_middleware(LoggingMiddleware)

setup_metrics(app)

setup_business_metrics(app)

app.include_router(api_router, prefix=settings.API_PREFIX)

# ── 插件化架构（见 others/PROJECT/08-插件化架构设计.md）─────────────
# 默认关闭：不改变既有启动行为；显式 PLUGIN_ENABLED=true 时启用框架。
# app.state.plugin_manager 供管理接口 /system/plugins 与门面寻址使用。
app.state.plugin_manager = None
if settings.PLUGIN_ENABLED:
    app.state.plugin_manager = PluginManager(settings)
    app.state.plugin_manager.pm.hook.on_app_startup(ctx={"app": app})


@app.on_event("startup")
async def startup():
    # 部署模式声明：本项目唯一官方支持的部署模式为本地部署；
    # cloud 取值仅作为代码层扩展预留，进入后仅告警、不阻断运行。
    logger.info("deploy mode: %s (official support: local only)", settings.DEPLOY_MODE)
    if settings.DEPLOY_MODE != "local":
        logger.warning(
            "DEPLOY_MODE=%s 为非官方支持模式；本项目当前唯一官方支持的模式为本地部署",
            settings.DEPLOY_MODE,
        )

    # 插件框架启动：发现 + 依赖解析 + 按拓扑激活
    if app.state.plugin_manager is not None:
        try:
            await app.state.plugin_manager.boot()
            logger.info(
                "plugin framework booted: %d plugins",
                len(app.state.plugin_manager.list_plugins()),
            )
        except Exception as e:
            logger.error(f"plugin framework boot failed: {e}", exc_info=True)

    # 尝试连接 Neo4j（非阻塞）
    try:
        neo4j_client = Neo4jClient()
        await neo4j_client.verify_connectivity()
        logger.info("Neo4j connected successfully")
    except Exception as e:
        logger.warning(f"Neo4j connection failed (continuing without Neo4j): {e}")

    # 尝试连接 Redis（非阻塞）
    try:
        rc = await get_redis_client()
        await rc.ping()
        logger.info("Redis connected successfully")
    except Exception as e:
        logger.warning(f"Redis connection failed (continuing without Redis): {e}")


@app.on_event("shutdown")
async def shutdown():
    # 插件框架收尾：逆序停用已激活插件
    if app.state.plugin_manager is not None:
        try:
            await app.state.plugin_manager.shutdown()
            logger.info("plugin framework shutdown complete")
        except Exception as e:
            logger.warning(f"plugin framework shutdown error: {e}")
        app.state.plugin_manager.pm.hook.on_app_shutdown(ctx={"app": app})

    # 关闭 Neo4j 连接
    try:
        neo4j_client = Neo4jClient()
        await neo4j_client.close()
    except Exception as e:
        logger.warning(f"Neo4j cleanup error: {e}")

    # 关闭 GraphRAGTest 共享 AsyncClient
    try:
        await _close_async_client()
    except Exception as e:
        logger.warning(f"GraphRAGTest AsyncClient cleanup error: {e}")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": settings.APP_VERSION}


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "deploy_mode": settings.DEPLOY_MODE,
        "docs": "/docs",
        "redoc": "/redoc",
        "api": settings.API_PREFIX,
    }
