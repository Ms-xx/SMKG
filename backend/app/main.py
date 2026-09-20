import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.middleware.logging import LoggingMiddleware
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
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(LoggingMiddleware)

setup_metrics(app)

setup_business_metrics(app)

app.include_router(api_router, prefix=settings.API_PREFIX)


@app.on_event("startup")
async def startup():
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
    # 关闭 Neo4j 连接
    try:
        neo4j_client = Neo4jClient()
        await neo4j_client.close()
    except Exception as e:
        logger.warning(f"Neo4j cleanup error: {e}")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": settings.APP_VERSION}


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "redoc": "/redoc",
        "api": settings.API_PREFIX,
    }
