"""
vector_store.py

基于 FAISS + BGE-M3 的向量存储与相似度检索。

- 支持将「实体 / 关系 / 文档 chunk」向量化写入。
- 支持余弦相似度检索（BGE-M3 输出经 L2 归一化后，用内积近似余弦相似度）。
- 依赖策略（可插拔、可降级）：
  * 已安装 `sentence-transformers` + 本地有 `BAAI/bge-m3` 模型 -> 真实 BGE-M3 嵌入。
  * 已安装 `faiss` -> 用 FAISS IndexFlatIP 加速检索。
  * 否则自动降级为「确定性哈希向量 + numpy 暴力检索」，便于离线开发与 CI 测试，接口不变。

用法示例：
    from vector_store import vector_store

    vector_store.add_entity("钙钛矿", "Material", {"source": "doc-1"})
    vector_store.add_relation("钙钛矿", "HAS_PROPERTY", "高效率", "doc-1")
    vector_store.add_chunk("钙钛矿太阳能电池具有高光电转换效率。", "doc-1")

    hits = vector_store.search("钙钛矿的光电转换效率", top_k=5)
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Optional

import numpy as np

from config import resolve_model_source, settings

logger = logging.getLogger("vector_store")

# ─── 可选依赖 ────────────────────────────────────────────────────────────────
try:
    import faiss  # type: ignore

    _HAS_FAISS = True
except Exception:  # pragma: no cover - 环境未安装 faiss
    faiss = None
    _HAS_FAISS = False

try:
    from sentence_transformers import SentenceTransformer  # type: ignore

    _HAS_ST = True
except Exception:  # pragma: no cover - 环境未安装 sentence-transformers
    SentenceTransformer = None
    _HAS_ST = False

# BGE-M3 输出维度
DEFAULT_DIM = 1024


def _token_hash(token: str) -> int:
    """确定性哈希（跨进程稳定），用于无模型时的降级向量。"""
    return int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)


def _text_features(text: str) -> list[str]:
    """提取降级嵌入使用的特征：拉丁词元 + CJK 字符二元组。"""
    lowered = text.lower()
    features: list[str] = re.findall(r"[a-z0-9]+", lowered)
    compact = re.sub(r"\s+", "", lowered)
    features += [compact[i : i + 2] for i in range(len(compact) - 1)]
    return features


class VectorStore:
    """实体 / 关系 / 文档 chunk 的向量写入与相似度检索。"""

    VALID_TYPES = ("entity", "relation", "chunk")

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        dim: int = DEFAULT_DIM,
    ):
        self.model_name = model_name or settings.GRAPHRAG_EMBEDDING_MODEL
        self.device = device or settings.GRAPHRAG_EMBEDDING_DEVICE
        self.dim = dim
        self._model = None
        self.embedding_backend = "hash-fallback"
        self._load_model()

        self._records: list[dict[str, Any]] = []
        self._vectors: Optional[np.ndarray] = None
        self._index = None
        if _HAS_FAISS:
            self._index = faiss.IndexFlatIP(self.dim)
            logger.info("FAISS IndexFlatIP initialized (dim=%d)", self.dim)

    # ─── 模型加载 ───────────────────────────────────────────────────────────
    def _load_model(self) -> None:
        """尝试加载 BGE-M3（本地 moulds/bge-m3 优先，否则 HF 名）；失败则使用哈希降级。"""
        if _HAS_ST:
            try:
                model_source = resolve_model_source(self.model_name, settings.GRAPHRAG_EMBEDDING_MODEL_PATH)
                self._model = SentenceTransformer(model_source, device=self.device)
                self.dim = self._embedding_dim(self._model)
                self.embedding_backend = "sentence-transformers-bge-m3"
                logger.info("Loaded embedding model %s (dim=%d)", model_source, self.dim)
                return
            except Exception as e:  # pragma: no cover
                logger.warning("Failed to load %s, fallback to hash embedding: %s", self.model_name, e)
        else:  # pragma: no cover
            logger.warning(
                "sentence-transformers not installed, using hash-fallback embedding "
                "(install torch + sentence-transformers and place BAAI/bge-m3 locally for real embeddings)"
            )

    @staticmethod
    def _embedding_dim(model) -> int:
        """兼容 sentence-transformers 不同版本获取输出维度（方法名随版本变化）。"""
        for attr in ("get_embedding_dimension", "get_sentence_embedding_dimension"):
            fn = getattr(model, attr, None)
            if fn is None:
                continue
            if callable(fn):
                return int(fn())
            return int(fn)
        raise AttributeError("无法从 SentenceTransformer 获取嵌入维度")

    # ─── 嵌入 ───────────────────────────────────────────────────────────────
    def _encode(self, texts: list[str]) -> np.ndarray:
        """返回 shape=(len(texts), dim) 的 L2 归一化 float32 向量。"""
        if self._model is not None:
            vecs = self._model.encode(
                texts, normalize_embeddings=True, show_progress_bar=False
            )
            return np.asarray(vecs, dtype=np.float32)

        vecs = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            for feat in _text_features(text):
                vecs[i, _token_hash(feat) % self.dim] += 1.0
            norm = float(np.linalg.norm(vecs[i]))
            if norm > 0:
                vecs[i] /= norm
        return vecs

    # ─── 写入 ───────────────────────────────────────────────────────────────
    def _add(self, record_type: str, text: str, metadata: dict[str, Any] | None) -> dict[str, Any]:
        if record_type not in self.VALID_TYPES:
            raise ValueError(f"record_type must be one of {self.VALID_TYPES}, got {record_type!r}")
        record = {"type": record_type, "text": text, "metadata": metadata or {}}
        record["id"] = len(self._records)
        vec = self._encode([text])

        self._records.append(record)
        if self._vectors is None:
            self._vectors = vec
        else:
            self._vectors = np.vstack([self._vectors, vec])

        if self._index is not None:
            self._index.add(vec)
        return record

    def add_entity(
        self, name: str, label: str = "Entity", metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        text = f"{label}: {name}"
        return self._add("entity", text, {"name": name, "label": label, **(metadata or {})})

    def add_relation(
        self,
        source: str,
        rel_type: str,
        target: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        text = f"{source} {rel_type} {target}"
        return self._add(
            "relation", text, {"source": source, "relation": rel_type, "target": target, **(metadata or {})}
        )

    def add_chunk(self, content: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._add("chunk", content, metadata or {})

    def add(self, record_type: str, text: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        """通用写入，record_type ∈ {entity, relation, chunk}。"""
        return self._add(record_type, text, metadata)

    # ─── 检索 ───────────────────────────────────────────────────────────────
    def search(self, query: str, top_k: int = 5, record_type: Optional[str] = None) -> list[dict[str, Any]]:
        """
        相似度检索。

        Args:
            query: 查询文本
            top_k: 返回数量
            record_type: 可选过滤，仅返回该类型（entity/relation/chunk）

        Returns:
            [{"type", "text", "metadata", "score"} ...] 按 score 降序
        """
        if not self._records:
            return []

        q = self._encode([query])

        if self._index is not None and self._index.ntotal > 0:
            k = min(top_k, self._index.ntotal)
            scores, ids = self._index.search(q, k)
            scores, ids = scores[0], ids[0]
        else:
            sims = (q @ self._vectors.T)[0]
            order = np.argsort(-sims)
            k = min(top_k, len(self._records))
            ids, scores = order[:k], sims[order[:k]]

        results: list[dict[str, Any]] = []
        for idx, score in zip(ids, scores):
            idx = int(idx)
            if idx < 0 or idx >= len(self._records):
                continue
            rec = self._records[idx]
            if record_type and rec["type"] != record_type:
                continue
            results.append(
                {
                    "id": int(idx),
                    "type": rec["type"],
                    "text": rec["text"],
                    "metadata": rec["metadata"],
                    "score": float(score),
                }
            )
        return results

    # ─── 工具 ───────────────────────────────────────────────────────────────
    def clear(self) -> None:
        self._records = []
        self._vectors = None
        if _HAS_FAISS:
            self._index = faiss.IndexFlatIP(self.dim)

    @property
    def size(self) -> int:
        return len(self._records)


# 全局单例
vector_store = VectorStore()