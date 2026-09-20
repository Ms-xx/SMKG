import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（backend/app/core/config.py 之上三级）
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # backend/app/core
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_BASE_DIR)))

# 模型统一存放目录（moulds），每个模型单独一个子文件夹
MODELS_DIR = os.path.join(PROJECT_ROOT, "moulds")


def resolve_model_source(hf_name: str, local_dir: str | None) -> str:
    """优先使用本地模型目录（`moulds/<模型>`），不存在或为空时回退到 HuggingFace 名称。"""
    if local_dir and os.path.isdir(local_dir) and os.listdir(local_dir):
        return local_dir
    return hf_name


class Settings(BaseSettings):
    APP_NAME: str = "Scientific Document Parser"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    DATABASE_URL: str = "mysql+aiomysql://root:20020522@127.0.0.1:3306/wx"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    REDIS_URL: str = "redis://localhost:6379/0"

    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "wang245484@"

    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_NAME: str = "documents"
    MINIO_SECURE: bool = False

    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    EMBEDDING_MODEL_PATH: str = os.path.join(MODELS_DIR, "bge-m3")
    LLM_MODEL_PATH: str = os.path.join(MODELS_DIR, "qwen-7b")
    LLM_MAX_TOKENS: int = 4096
    LLM_TEMPERATURE: float = 0.7
    LLM_DEVICE: str = "cpu"

    # OCR（PaddleOCR，中文优先，处理扫描件/图片文字页）
    OCR_ENABLED: bool = True
    OCR_LANGUAGE: str = "ch"
    OCR_USE_ANGLE_CLS: bool = True
    OCR_DPI: int = 200
    # PaddleOCR 模型目录（可选，缺省使用 PaddleOCR 内置下载）
    OCR_MODEL_PATH: str = os.path.join(MODELS_DIR, "paddleocr")

    # 版面分析（LayoutLMv3，PubLayNet 微调；LAYOUT_MODEL 为 HF 名回退，LAYOUT_MODEL_PATH 为本地 moulds 目录）
    LAYOUT_ENABLED: bool = True
    LAYOUT_MODEL: str = "HYPJUDY/layoutlmv3-base-finetuned-publaynet"
    LAYOUT_MODEL_PATH: str = os.path.join(MODELS_DIR, "layoutlmv3")
    LAYOUT_DEVICE: str = "cpu"

    # 公式识别（LaTeX-OCR / pix2tex，公式图 → LaTeX；前端 KaTeX 已有渲染）
    FORMULA_ENABLED: bool = True
    FORMULA_MODEL: str = "lukas-blecher/LaTeX-OCR"  # 回退模型名（pix2tex 内置下载权重）
    FORMULA_MODEL_PATH: str = os.path.join(MODELS_DIR, "latex-ocr")  # 本地 checkpoint 目录
    FORMULA_DEVICE: str = "cpu"

    # 图表/公式检测（YOLOv8；检测 figure/table/formula 区域）
    FIGURE_DETECT_ENABLED: bool = True
    FIGURE_DETECT_MODEL_PATH: str = os.path.join(MODELS_DIR, "yolov8")  # 目录，放 *.pt
    FIGURE_DETECT_CONF: float = 0.25

    # 图表描述（BLIP-2，图像 → 文本描述；CHART_CAPTION_MODEL 为 HF 名回退）
    CHART_CAPTION_ENABLED: bool = True
    CHART_CAPTION_MODEL: str = "Salesforce/blip2-opt-2.7b"
    CHART_CAPTION_MODEL_PATH: str = os.path.join(MODELS_DIR, "blip2")
    CHART_CAPTION_DEVICE: str = "cpu"

    # NER（SciBERT/领域模型微调的 token classification，替换/增强"规则 + LLM"抽取）
    NER_ENABLED: bool = True
    NER_MODEL: str = (
        "allenai/scibert_scivocab_uncased"  # HF 回退名（基座无 id2label，需微调后使用）
    )
    NER_MODEL_PATH: str = os.path.join(MODELS_DIR, "scibert")  # 微调后的 NER checkpoint
    # NER 微调基座（LoRA/QLoRA 再训练的起点；与 NER_MODEL_PATH 的「微调后含 id2label」checkpoint 区分）
    NER_BASE_MODEL: str = "allenai/scibert_scivocab_uncased"  # HF 回退名
    NER_BASE_MODEL_PATH: str = os.path.join(MODELS_DIR, "scibert-base")  # 本地基座目录
    NER_DEVICE: str = "cpu"
    NER_AGGREGATION: str = "max"  # 实体聚合策略（max 无需 nltk）

    # 关系抽取（REBEL 关系分类 seq2seq，替代/补充“规则 + LLM”，可插拔可降级）
    RELATION_EXTRACTION_ENABLED: bool = True
    REBEL_MODEL: str = "Babelscape/rebel-large"  # HF 回退名
    REBEL_MODEL_PATH: str = os.path.join(MODELS_DIR, "rebel")  # 本地 checkpoint 目录
    REBEL_DEVICE: str = "cpu"
    REBEL_MAX_LENGTH: int = 256
    REBEL_NUM_BEAMS: int = 3
    REBEL_CONFIDENCE: float = 0.85  # REBEL 无逐条置信度，统一默认值

    # 实体链接（Wikidata/DBpedia 公共知识图谱 + 实体消歧/同义词合并，可插拔可降级）
    ENTITY_LINKING_ENABLED: bool = True
    ENTITY_LINKING_BACKEND: str = (
        "wikidata"  # 逗号分隔：wikidata,dbpedia；"none" 禁用外部查询（仅本地降级）
    )
    ENTITY_LINKING_LANGUAGE: str = "zh"
    ENTITY_LINKING_TIMEOUT: float = 5.0

    # 关系推理 / 图谱补全（规则推理 + TransE 链路预测，可插拔可降级）
    RELATION_INFERENCE_ENABLED: bool = True
    RELATION_INFERENCE_BACKEND: str = "transe"  # transe | statistical | none（none 仅规则推理）
    TRANSE_DIM: int = 50
    TRANSE_EPOCHS: int = 300
    TRANSE_LR: float = 0.01
    TRANSE_MARGIN: float = 1.0
    TRANSE_SEED: int = 42

    # 语义搜索（分面搜索 + 搜索建议；向量+BM25 混合检索由 GraphRAGTest 提供）
    SEMANTIC_SEARCH_ENABLED: bool = True

    # Text-to-Cypher（自然语言 → Cypher；规则模板，LLM 后端预留可降级）
    TEXT_TO_CYPHER_ENABLED: bool = True
    TEXT_TO_CYPHER_BACKEND: str = "rule"  # rule（规则模板，零依赖）| llm（预留）

    # 主动学习采样（不确定性 / 多样性 / QBC / 混合；纯 Python 零依赖可降级）
    ACTIVE_LEARNING_ENABLED: bool = True
    ACTIVE_LEARNING_STRATEGY: str = "hybrid"  # uncertainty | diversity | qbc | hybrid
    ACTIVE_LEARNING_UNCERTAINTY: str = "entropy"  # entropy | least_confidence | margin
    ACTIVE_LEARNING_DIVERSITY: str = "core_set"  # core_set | kmeans
    ACTIVE_LEARNING_QBC: str = "vote_entropy"  # vote_entropy | disagreement
    ACTIVE_LEARNING_SEED: int = 42

    # 标注一致性评估（Fleiss' Kappa / Cohen's Kappa / Krippendorff's Alpha；纯 Python 零依赖）
    ANNOTATION_AGREEMENT_ENABLED: bool = True

    # 数据/模型版本管理（DVC 数据版本 + MLflow 实验追踪/模型注册 + 自动重训管道；纯 Python 零依赖可降级）
    VERSION_MGMT_ENABLED: bool = True
    VERSION_MGMT_BACKEND: str = "builtin"  # builtin（内存注册表）| dvc_mlflow（预留，外部工具）
    VERSION_MGMT_STORE_PATH: str = ""  # 留空 = 内存存储；否则 JSON 文件路径
    RETRAIN_THRESHOLD: int = 100  # 新标注数据达到阈值触发自动重训
    RETRAIN_PERIODIC_DAYS: int = 7  # 定期触发间隔（天）
    RETRAIN_MAX_RETRIES: int = 3  # 单分段失败最大重试次数

    # 置信度校准与漂移检测（Temperature/Platt Scaling、数据漂移告警；纯 Python 零依赖）
    CALIBRATION_DRIFT_ENABLED: bool = True
    CALIBRATION_ECE_BINS: int = 10  # ECE 分箱数
    DRIFT_PSI_WARNING: float = 0.1  # PSI/卡方 ≥ 0.1 轻微漂移
    DRIFT_PSI_ALERT: float = 0.25  # PSI/卡方 ≥ 0.25 显著漂移

    # 监控告警（Alertmanager → 后端 webhook → 外部渠道转发）
    ALERT_WEBHOOK_URL: str = ""  # 钉钉/企业微信/通用 webhook 地址；留空仅本地日志（进入 ELK）
    ALERT_WEBHOOK_SECRET: str = ""  # 机器人加签密钥（可选，钉钉/企业微信）

    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024
    ALLOWED_EXTENSIONS: set = {"pdf"}

    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_JSON: bool = False  # 为 True 时输出 JSON 结构化日志（供 Filebeat/ELK 采集）
    LOG_FILE: str = ""  # 留空 = 仅 stdout；否则追加写 JSON 日志到该文件（供 Filebeat 采集）

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
