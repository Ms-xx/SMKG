"""
hybrid_retrieval.py

混合检索：向量相似度 + BM25 关键词打分，RRF 融合，可选 Cross-Encoder（bge-reranker）精排。

检索流程：
  1. 向量检索（复用 VectorStore，BGE-M3 嵌入或哈希降级）。
  2. BM25 关键词检索。
  3. 对两个排序列表做 RRF（Reciprocal Rank Fusion）融合。
  4. 若 `sentence-transformers` + 本地 bge-reranker 可用，对融合后的候选做 Cross-Encoder 精排；
     否则直接返回融合结果（rerank_backend = "none"）。

所有依赖均可插拔：无 faiss/sentence-transformers 时仍可运行（降级路径）。
"""
from __future__ import annotations

import logging
import math
from typing import Any, Optional

import numpy as np

from config import resolve_model_source, settings
from vector_store import VectorStore, _text_features

logger = logging.getLogger("hybrid_retrieval")

try:
    from sentence_transformers import CrossEncoder  # type: ignore

    _HAS_CROSS = True
except Exception:  # pragma: no cover
    CrossEncoder = None
    _HAS_CROSS = False

RRF_K = 60


class BM25:
    """轻量 BM25（无需外部依赖），corpus 为 token 序列列表。"""

    def __init__(self, corpus: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.corpus = corpus
        self.k1 = k1
        self.b = b
        self.N = len(corpus)
        self.doc_len = [len(d) for d in corpus]
        self.avgdl = (sum(self.doc_len) / self.N) if self.N else 0.0

        self.df: dict[str, int] = {}
        for doc in corpus:
            for token in set(doc):
                self.df[token] = self.df.get(token, 0) + 1

        self.idf: dict[str, float] = {}
        for token, freq in self.df.items():
            self.idf[token] = math.log(1 + (self.N - freq + 0.5) / (freq + 0.5))

    def get_scores(self, query_tokens: list[str]) -> np.ndarray:
        scores = np.zeros(self.N, dtype=np.float32)
        if self.N == 0:
            return scores
        for token in query_tokens:
            if token not in self.df:
                continue
            idf = self.idf[token]
            for i in range(self.N):
                tf = self.corpus[i].count(token)
                if tf == 0:
                    continue
                dl = self.doc_len[i]
                denom = tf + self.k1 * (1 - self.b + self.b * dl / max(self.avgdl, 1e-9))
                scores[i] += idf * (tf * (self.k1 + 1)) / denom
        return scores


def _tokenize(text: str) -> list[str]:
    return _text_features(text)


class HybridRetriever:
    """自包含的混合检索器（自带向量库与 BM25 索引，二者按追加顺序对齐）。"""

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        rerank_model: Optional[str] = None,
    ):
        self.vs = vector_store or VectorStore()
        self.rerank_model_name = rerank_model or settings.GRAPHRAG_RERANK_MODEL
        self.rerank_device = settings.GRAPHRAG_RERANK_DEVICE

        self._docs: list[dict[str, Any]] = []  # 与 self.vs._records 对齐
        self._bm25: Optional[BM25] = None

        self._reranker = None
        self.rerank_backend = "none"
        self._load_reranker()

    # ─── 写入 ───────────────────────────────────────────────────────────────
    def _add(self, record_type: str, text: str, metadata: dict[str, Any] | None) -> dict[str, Any]:
        self.vs.add(record_type, text, metadata)
        self._docs.append({"type": record_type, "text": text, "metadata": metadata or {}})
        self._bm25 = None  # 语料变化后重建
        return {"id": len(self._docs) - 1, "type": record_type, "text": text}

    def add_entity(
        self, name: str, label: str = "Entity", metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self._add("entity", f"{label}: {name}", {"name": name, "label": label, **(metadata or {})})

    def add_relation(
        self, source: str, rel_type: str, target: str, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self._add(
            "relation",
            f"{source} {rel_type} {target}",
            {"source": source, "relation": rel_type, "target": target, **(metadata or {})},
        )

    def add_chunk(self, content: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._add("chunk", content, metadata or {})

    # ─── 索引构建 ───────────────────────────────────────────────────────────
    def _ensure_bm25(self) -> BM25:
        if self._bm25 is None:
            corpus = [_tokenize(d["text"]) for d in self._docs]
            self._bm25 = BM25(corpus)
        return self._bm25

    # ─── 重排序 ─────────────────────────────────────────────────────────────
    def _load_reranker(self) -> None:
        if _HAS_CROSS:
            try:
                model_source = resolve_model_source(self.rerank_model_name, settings.GRAPHRAG_RERANK_MODEL_PATH)
                self._reranker = CrossEncoder(model_source, max_length=512, device=self.rerank_device)
                self.rerank_backend = "cross-encoder"
                logger.info("Loaded reranker %s", model_source)
            except Exception as e:  # pragma: no cover
                logger.warning("Failed to load reranker %s: %s", self.rerank_model_name, e)
        else:  # pragma: no cover
            logger.warning("sentence-transformers not installed, skip cross-encoder rerank")

    def _rerank(self, query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if self._reranker is None:
            for c in candidates:
                c["rerank_score"] = None
            return candidates
        try:
            pairs = [(query, c["text"]) for c in candidates]
            scores = self._reranker.predict(pairs)
            for c, s in zip(candidates, scores):
                c["rerank_score"] = float(s)
                c["score"] = float(s)  # 用精排分覆盖最终排序
            candidates.sort(key=lambda c: -(c["score"] or 0.0))
        except Exception as e:  # pragma: no cover
            logger.warning("Rerank failed, returning fused order: %s", e)
            for c in candidates:
                c["rerank_score"] = None
        return candidates

    # ─── 检索 ───────────────────────────────────────────────────────────────
    def search(
        self,
        query: str,
        top_k: int = 5,
        candidate_k: int = 20,
        use_rerank: bool = True,
    ) -> dict[str, Any]:
        """
        混合检索。

        Returns:
            {
                "query": str,
                "rerank_backend": str,
                "results": [{"id", "type", "text", "metadata", "score",
                             "vector_score", "bm25_score", "rerank_score"} ...]
            }
        """
        if not self._docs:
            return {"query": query, "rerank_backend": self.rerank_backend, "results": []}

        # 1. 向量检索
        vector_hits = self.vs.search(query, top_k=candidate_k)

        # 2. BM25 检索
        bm25 = self._ensure_bm25()
        bm25_scores = bm25.get_scores(_tokenize(query))
        order = np.argsort(-bm25_scores)[:candidate_k]
        bm25_ranked = [(int(i), float(bm25_scores[i])) for i in order if bm25_scores[i] > 0]

        # 3. RRF 融合
        fused_scores: dict[int, float] = {}
        for rank, h in enumerate(vector_hits):
            fused_scores[h["id"]] = fused_scores.get(h["id"], 0.0) + 1.0 / (RRF_K + rank + 1)
        for rank, (doc_id, _) in enumerate(bm25_ranked):
            fused_scores[doc_id] = fused_scores.get(doc_id, 0.0) + 1.0 / (RRF_K + rank + 1)

        ranked_ids = sorted(fused_scores.items(), key=lambda kv: -kv[1])

        # 组装候选
        vec_score_map = {h["id"]: h["score"] for h in vector_hits}
        bm25_score_map = {doc_id: s for doc_id, s in bm25_ranked}

        candidates: list[dict[str, Any]] = []
        for doc_id, fused in ranked_ids:
            doc = self._docs[doc_id]
            candidates.append(
                {
                    "id": doc_id,
                    "type": doc["type"],
                    "text": doc["text"],
                    "metadata": doc["metadata"],
                    "score": fused,
                    "vector_score": vec_score_map.get(doc_id),
                    "bm25_score": bm25_score_map.get(doc_id, 0.0),
                    "rerank_score": None,
                }
            )

        # 4. 可选精排（对融合后前列候选）
        if use_rerank and self._reranker is not None:
            rerank_pool = candidates[: max(top_k, 10)]
            reranked = self._rerank(query, rerank_pool)
            reranked += candidates[len(rerank_pool):]
            candidates = reranked

        return {
            "query": query,
            "rerank_backend": self.rerank_backend,
            "results": candidates[:top_k],
        }


def index_document_vectors(
    doc_id: str,
    entities: list[dict[str, Any]],
    relations: list[dict[str, Any]],
    chunks: Optional[list[str]] = None,
    retriever: Optional[HybridRetriever] = None,
) -> dict[str, Any]:
    """
    将文档的实体 / 关系 / chunk 写入混合检索器（向量库 + BM25）。

    - entity 格式：{"text": "钙钛矿", "entity_type": "Material", ...}
    - relation 格式：{"source": "...", "source_type": "...", "target": "...",
                      "target_type": "...", "relation_type": "HAS_PROPERTY", ...}
    - chunks：原始文本分块列表。

    无 sentence-transformers / faiss 时自动降级为哈希向量；接口不变。
    """
    if retriever is None:
        retriever = hybrid_retriever

    entities_indexed = 0
    relations_indexed = 0
    chunks_indexed = 0

    for e in entities:
        name = e.get("text") or e.get("id") or e.get("name") or ""
        if not name:
            continue
        label = e.get("entity_type") or e.get("type") or "Entity"
        meta = {
            k: v for k, v in e.items()
            if k not in ("text", "id", "name", "entity_type", "type", "start", "end")
        }
        retriever.add_entity(name, label, {"doc_id": doc_id, **meta})
        entities_indexed += 1

    for r in relations:
        src = r.get("source") or ""
        tgt = r.get("target") or ""
        rtype = r.get("relation_type") or r.get("rel_type") or "RELATED_TO"
        if not src or not tgt:
            continue
        meta = {
            k: v for k, v in r.items()
            if k not in ("source", "source_type", "target", "target_type", "relation_type", "rel_type")
        }
        retriever.add_relation(src, rtype, tgt, {"doc_id": doc_id, **meta})
        relations_indexed += 1

    for i, c in enumerate(chunks or []):
        retriever.add_chunk(c, {"doc_id": doc_id, "chunk_index": i})
        chunks_indexed += 1

    return {
        "doc_id": doc_id,
        "entities_indexed": entities_indexed,
        "relations_indexed": relations_indexed,
        "chunks_indexed": chunks_indexed,
    }


# 全局单例
hybrid_retriever = HybridRetriever()