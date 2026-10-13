import os

# 解决 Anaconda MKL(numpy) 与 torch 的 libiomp5md.dll 冲突(OMP Error #15)
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# 国内镜像下载 HuggingFace 模型（BGE-M3 / bge-reranker 等），已被真实环境变量优先
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from pydantic_settings import BaseSettings, SettingsConfigDict


_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_BASE_DIR)

# 集中化配置目录：共享凭据与子服务专有配置统一放 <repo>/config（见 config/README.md）
_CONFIG_DIR = os.path.join(_PROJECT_ROOT, "config")

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

    # ─── 创新点 B：图谱增强检索 + grounding_score（可插拔、可降级）───
    # 1) 图谱邻居扩跳重排序：对检索出的候选节点按其在图谱中的 1/2 跳邻居的
    #    连接强度（频次/度）加权重排上下文，突出"中心实体"。
    GRAPH_HOP_RERANK_ENABLED: bool = True
    GRAPH_HOP_DEPTH: int = 2  # 邻居扩跳深度（1=一跳，2=一跳+二跳）
    GRAPH_HOP_BOOST_WEIGHT: float = 0.5  # 图谱邻居分相对原始检索分的权重(0~1)
    # 2) grounding_score：评估"最终答案"是否被检索到的证据（页码片段/图节点名）支撑。
    GROUNDING_ENABLED: bool = True
    GROUNDING_DEVICE: str = "cpu"  # 预留语义加密设备（当前纯词法比对，预留 cuda）
    GROUNDING_MIN_TOKEN_LEN: int = 2  # 支撑比对的有效 token 最小长度
    GROUNDING_MAX_EVIDENCE_CHARS: int = 8000  # 证据拼接上限字符数

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
        # 依次加载共享配置与子服务专有配置（后者优先级更高）
        env_file=(
            os.path.join(_CONFIG_DIR, "common.env"),
            os.path.join(_CONFIG_DIR, "graphrag.env"),
        ),
        env_file_encoding="utf-8",
    )


settings = Settings()
