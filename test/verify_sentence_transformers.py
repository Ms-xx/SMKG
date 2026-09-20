# -*- coding: utf-8 -*-
"""
验证 sentence-transformers 真实嵌入(BGE-M3) 与精排(bge-reranker) 可用。

首次运行会从 hf-mirror.com 下载模型(约 3.3GB)到 ~/.cache/huggingface/hub，
之后复用缓存。仅在已安装 torch + sentence-transformers 的环境下有意义。

注意：只加载一个 BGE-M3 实例(通过 HybridRetriever 内部的 VectorStore)，避免
同时加载多份大模型导致内存不足(OOM)。
"""
import os
import sys

GRAPHRAG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "GraphRAGTest"))
if GRAPHRAG_DIR not in sys.path:
    sys.path.insert(0, GRAPHRAG_DIR)

# 必须早于 numpy/torch 导入设置，用于规避 Anaconda MKL 与 torch 的 OpenMP 冲突
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from hybrid_retrieval import HybridRetriever  # noqa: E402


def main() -> None:
    # 只实例化一个 HybridRetriever：内部仅加载一份 BGE-M3 + 一份 bge-reranker
    hr = HybridRetriever()

    # ─── 1. 真实嵌入(BGE-M3) ───────────────────────────────────────
    vs = hr.vs
    print(f"[嵌入] backend = {vs.embedding_backend}, dim = {vs.dim}")
    assert vs.embedding_backend.startswith("sentence-transformers"), (
        f"未加载真实 BGE-M3 嵌入: {vs.embedding_backend}"
    )
    assert vs.dim == 1024, f"BGE-M3 应为 1024 维，实际 {vs.dim}"

    # ─── 2. 真实精排(bge-reranker) ─────────────────────────────────
    print(f"[精排] rerank_backend = {hr.rerank_backend}")
    assert hr.rerank_backend == "cross-encoder", (
        f"未加载真实 bge-reranker 精排: {hr.rerank_backend}"
    )

    # ─── 3. 写入数据并检索 ─────────────────────────────────────────
    hr.add_entity("钙钛矿", "Material", {"name": "钙钛矿"})
    hr.add_entity("高效率", "Property", {"name": "高效率"})
    hr.add_relation("钙钛矿", "HAS_PROPERTY", "高效率")
    hr.add_chunk("钙钛矿太阳能电池具有高光电转换效率", {"doc_id": "d1"})
    hr.add_chunk("perovskite solar cells achieve high efficiency", {"doc_id": "d2"})

    # 纯向量检索(嵌入路径)
    vec_hits = hr.vs.search("光电转换效率", top_k=2)
    assert vec_hits, "向量检索应返回结果"
    print(f"[嵌入] 向量检索 top1: {vec_hits[0]['text']!r} score={vec_hits[0]['score']:.4f}")

    # 混合检索 + 精排
    res = hr.search("钙钛矿的光电转换效率", top_k=3)
    assert res["rerank_backend"] == "cross-encoder"
    assert res["results"], "混合检索应返回结果"
    assert all(r["rerank_score"] is not None for r in res["results"]), "精排后应有 rerank_score"

    print("[精排] 混合检索结果(按精排分降序):")
    for r in res["results"]:
        print(
            f"  [{r['type']:>8}] score={r['score']:.4f} "
            f"rerank={r['rerank_score']:.4f} text={r['text'][:40]!r}"
        )

    print("\nOK: sentence-transformers 真实嵌入 + 精排验证通过")


if __name__ == "__main__":
    main()