"""
GraphRAG FastAPI 应用入口
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from config import settings
from api.routes import router as api_router
from neo4j_client import neo4j_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时
    logger.info("GraphRAG 服务启动中...")
    try:
        driver = await neo4j_client.get_driver()
        await driver.verify_connectivity()
        logger.info("Neo4j 连接成功")
    except Exception as e:
        logger.warning(f"Neo4j 连接失败 (服务仍可启动): {e}")

    yield

    # 关闭时
    logger.info("GraphRAG 服务关闭中...")
    await neo4j_client.close()
    logger.info("Neo4j 连接已关闭")


app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description=(
        "基于 Neo4j 知识图谱 + Qwen LLM (LM Studio 本地部署) 的 GraphRAG 问答系统。\n\n"
        "核心功能:\n"
        "- GraphRAG 问答 (关键词提取 → 图谱检索 → LLM 生成)\n"
        "- 图谱管理 (节点/关系 CRUD)\n"
        "- 批量导入 (JSONL 格式)\n"
        "- 文档索引 (将科学文献实体+关系批量入库)\n"
        "- LLM 管理 (LM Studio 模型加载/卸载/生成)\n"
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "name": "GraphRAG API",
        "version": settings.API_VERSION,
        "docs": "/docs",
        "endpoints": {
            "health": "/api/v1/health",
            "query": "POST /api/v1/query",
            "graph_stats": "GET /api/v1/graph/stats",
            "llm_status": "GET /api/v1/llm/status",
            "index_document": "POST /api/v1/index/document",
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,
    )
