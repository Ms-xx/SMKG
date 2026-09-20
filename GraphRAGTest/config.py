import os

# 解决 Anaconda MKL(numpy) 与 torch 的 libiomp5md.dll 冲突(OMP Error #15)
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# 国内镜像下载 HuggingFace 模型（BGE-M3 / bge-reranker 等），已被真实环境变量优先
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_BASE_DIR)

# 模型统一存放目录（moulds，每个模型单独一个子文件夹）
MODELS_DIR = os.path.join(_PROJECT_ROOT, "moulds")


def resolve_model_source(hf_name: str, local_dir: str | None) -> str:
    """优先使用本地模型目录（`moulds/<模型>`），不存在或为空时回退到 HuggingFace 名称。"""
    if local_dir and os.path.isdir(local_dir) and os.listdir(local_dir):
        return local_dir
    return hf_name


class Settings(BaseSettings):
    # LM Studio
    LMSTUDIO_BASE_URL: str = "http://localhost:1234"
    LMSTUDIO_MODEL: str = "qwen/qwen3-4b-2507"

    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "CHANGE_ME"
    NEO4J_DATABASE: str = "neo4j"

    # GraphRAG
    GRAPHRAG_MAX_NODES: int = 20
    GRAPHRAG_MAX_RELATIONS: int = 50
    GRAPHRAG_MAX_CONTEXT_TOKENS: int = 4096
    GRAPHRAG_EMBEDDING_MODEL: str = "BAAI/bge-m3"
    GRAPHRAG_EMBEDDING_DEVICE: str = "cpu"
    GRAPHRAG_EMBEDDING_MODEL_PATH: str = os.path.join(MODELS_DIR, "bge-m3")
    GRAPHRAG_RERANK_MODEL: str = "BAAI/bge-reranker-base"
    GRAPHRAG_RERANK_DEVICE: str = "cpu"
    GRAPHRAG_RERANK_MODEL_PATH: str = os.path.join(MODELS_DIR, "bge-reranker-base")

    # FastAPI
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8001
    API_TITLE: str = "GraphRAG API"
    API_VERSION: str = "1.0.0"

    # GraphRAG Prompts
    GRAPHRAG_KEYWORD_EXTRACT_PROMPT: str = (
        "从以下问题中提取3-5个关键词，用于在知识图谱中检索相关信息。"
        "只返回关键词列表，格式：关键词1, 关键词2, ..."
        "问题: {question}"
    )

    GRAPHRAG_CONTEXT_PROMPT: str = (
        "你是一个基于知识图谱的问答助手。根据以下图谱上下文信息，回答用户问题。"
        "如果上下文中没有足够信息来回答问题，请明确说明。"
        "回答要准确、简洁、有条理。\n\n"
        "=== 知识图谱上下文 ===\n{graph_context}\n\n"
        "=== 用户问题 ===\n{question}\n\n"
        "=== 回答 ==="
    )

    model_config = SettingsConfigDict(
        env_file=os.path.join(_BASE_DIR, ".env"), env_file_encoding="utf-8"
    )


settings = Settings()
