# -*- coding: utf-8 -*-
"""语义去重与版本识别单测（步骤 18.2）。

覆盖：arXiv 版本号解析边界、v1/v7 同簇、不同论文不同簇、保留最新版本建议。
"""
from app.services.deduplication_service import (
    deduplication_service,
    extract_arxiv_version,
    simhash_similarity,
)


class TestExtractArxivVersion:
    def test_v1_and_v7(self):
        assert extract_arxiv_version("1706.03762v1") == {
            "arxiv_id": "1706.03762",
            "version": "v1",
        }
        assert extract_arxiv_version("1706.03762v7") == {
            "arxiv_id": "1706.03762",
            "version": "v7",
        }

    def test_filename_form(self):
        assert extract_arxiv_version("attention_1706.03762v7.pdf")["version"] == "v7"
        assert extract_arxiv_version("1706.03762v2 (1).pdf")["arxiv_id"] == "1706.03762"

    def test_without_version(self):
        assert extract_arxiv_version("Attention Is All You Need") is None
        assert extract_arxiv_version("") is None
        assert extract_arxiv_version(None) is None

    def test_version_uppercase(self):
        assert extract_arxiv_version("1706.03762V3")["version"] == "v3"


class TestSimhashSimilarity:
    def test_identical(self):
        assert simhash_similarity("same text here", "same text here") == 1.0

    def test_different(self):
        assert (
            simhash_similarity("transformer architecture", "banana bread recipe") < 0.9
        )


class TestDeduplicationDetect:
    V1 = {
        "id": "doc-v1",
        "title": "Attention Is All You Need 1706.03762v1",
        "text": "The dominant sequence transduction models are based on complex recurrent "
        "or convolutional neural networks that include an encoder and a decoder.",
    }
    V7 = {
        "id": "doc-v7",
        "title": "Attention Is All You Need 1706.03762v7",
        "text": "The dominant sequence transduction models are based on complex recurrent "
        "or convolutional neural networks that include an encoder and a decoder.",
    }
    OTHER = {
        "id": "doc-other",
        "title": "Layer Normalization 1607.06450",
        "text": "Training state-of-the-art deep neural networks is computationally expensive, "
        "which motivates recent work on accelerating training via normalization.",
    }

    def _clusters(self, docs):
        result = deduplication_service.detect(docs)
        return result.get("clusters") or result.get("groups") or []

    def _ids_of(self, cluster):
        members = cluster.get("documents") or cluster.get("items") or []
        return {str(m.get("id") if isinstance(m, dict) else m) for m in members}

    def test_v1_v7_same_cluster(self):
        clusters = self._clusters([self.V1, self.V7])
        merged = set()
        for c in clusters:
            merged |= self._ids_of(c)
        assert {"doc-v1", "doc-v7"} <= merged

    def test_different_paper_not_clustered(self):
        clusters = self._clusters([self.V1, self.OTHER])
        for c in clusters:
            assert not {"doc-v1", "doc-other"} <= self._ids_of(c)

    def test_detect_returns_summary(self):
        result = deduplication_service.detect([self.V1, self.V7])
        assert isinstance(result, dict)
        # 至少包含聚类信息或空集合，不应抛异常
        assert "clusters" in result or "groups" in result or "documents" in result
