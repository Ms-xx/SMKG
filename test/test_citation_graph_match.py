# -*- coding: utf-8 -*-
"""citation_graph_match 纯函数单测（步骤 16.1.2）。"""
from app.services.citation_graph_match import (
    MatchType,
    build_candidate_index,
    match_reference_to_document,
    normalize_arxiv_id,
    normalize_doi,
    normalize_title,
)


class TestNormalizeDoi:
    def test_strips_url_prefix(self):
        assert normalize_doi("https://doi.org/10.1000/abc") == "10.1000/abc"
        assert normalize_doi("HTTP://DOI.ORG/10.1000/ABC") == "10.1000/abc"

    def test_none_and_invalid(self):
        assert normalize_doi(None) is None
        assert normalize_doi("") is None
        assert normalize_doi("not-a-doi") is None
        assert normalize_doi("   ") is None


class TestNormalizeTitle:
    def test_lower_and_strip_punct(self):
        assert normalize_title("Perovskite: A Review!") == "perovskite a review"
        assert normalize_title("  Hello   World  ") == "hello world"

    def test_none(self):
        assert normalize_title(None) == ""


class TestNormalizeArxivId:
    def test_plain_and_marked_forms(self):
        assert normalize_arxiv_id("arXiv:1607.06450") == "1607.06450"
        assert normalize_arxiv_id("arXiv:1607.06450v2") == "1607.06450"
        assert normalize_arxiv_id("1607.06450v11") == "1607.06450"

    def test_extract_from_doi_and_filename(self):
        assert normalize_arxiv_id("10.48550/arXiv.1706.03762") == "1706.03762"
        assert normalize_arxiv_id("103.tar_1408.2982.gz_paper_black.pdf") == "1408.2982"

    def test_old_style_id(self):
        assert normalize_arxiv_id("arXiv:cs/0112017") == "cs/0112017"

    def test_none_and_invalid(self):
        assert normalize_arxiv_id(None) is None
        assert normalize_arxiv_id("") is None
        assert normalize_arxiv_id("Attention Is All You Need") is None
        assert normalize_arxiv_id("10.1016/j.exmath.2015.12.005") is None


class TestMatchReference:
    CANDIDATES = [
        {"doc_id": "d1", "doi": "10.1000/abc", "title": "Perovskite Solar Cells"},
        {"doc_id": "d2", "doi": "10.2000/xyz", "title": "Graph Neural Networks"},
        {"doc_id": "d3", "title": "Attention Is All You Need"},
    ]

    def test_doi_match(self):
        ref = {"doi": "https://doi.org/10.1000/abc", "title": "Different Title"}
        r = match_reference_to_document(ref, self.CANDIDATES)
        assert r.match_type == MatchType.DOI
        assert r.doc_id == "d1"
        assert r.confidence == 1.0

    def test_doi_normalization_case_insensitive(self):
        ref = {"doi": "10.1000/ABC"}
        r = match_reference_to_document(ref, self.CANDIDATES)
        assert r.match_type == MatchType.DOI
        assert r.doc_id == "d1"

    def test_arxiv_match_via_doi_field(self):
        """参考文献无 DOI 命中键、但有 arXiv id 时，走 arXiv 档。"""
        ref = {"doi": "10.48550/arXiv.1706.03762", "title": "Totally different wording"}
        candidates = [
            {
                "doc_id": "attn",
                "title": "Attention Is All You Need",
                "arxiv_id": "1706.03762",
            }
        ]
        r = match_reference_to_document(ref, candidates)
        assert r.match_type == MatchType.ARXIV_ID
        assert r.doc_id == "attn"

    def test_arxiv_match_via_raw_and_filepath(self):
        """原始条目含 'arXiv:1607.06450'，候选以 file_path 承载 id。"""
        ref = {
            "raw": "Jimmy Lei Ba et al. Layer normalization. "
            "arXiv preprint arXiv:1607.06450, 2016."
        }
        candidates = [
            {
                "doc_id": "ln",
                "title": "banach.pdf",
                "file_path": "minio://documents/1607.06450.pdf",
            }
        ]
        r = match_reference_to_document(ref, candidates)
        assert r.match_type == MatchType.ARXIV_ID
        assert r.doc_id == "ln"

    def test_priority_doi_before_arxiv(self):
        """DOI 应优先于 arXiv id。"""
        ref = {"doi": "10.1000/abc", "raw": "arXiv:1607.06450"}
        candidates = [
            {"doc_id": "d1", "doi": "10.1000/abc"},
            {"doc_id": "ln", "arxiv_id": "1607.06450"},
        ]
        r = match_reference_to_document(ref, candidates)
        assert r.match_type == MatchType.DOI
        assert r.doc_id == "d1"

    def test_priority_arxiv_before_title(self):
        """arXiv 命中应优先于题名命中（且优先于更弱的相似题名）。"""
        ref = {"raw": "arXiv:1607.06450", "title": "Graph Neural Networks"}
        candidates = [
            {"doc_id": "gnn", "title": "Graph Neural Networks"},
            {"doc_id": "ln", "arxiv_id": "1607.06450", "title": "Layer Normalization"},
        ]
        r = match_reference_to_document(ref, candidates)
        assert r.match_type == MatchType.ARXIV_ID
        assert r.doc_id == "ln"

    def test_title_exact_match(self):
        ref = {"title": "Attention Is All You Need"}
        r = match_reference_to_document(ref, self.CANDIDATES)
        assert r.match_type == MatchType.TITLE_EXACT
        assert r.doc_id == "d3"

    def test_title_fuzzy_match(self):
        ref = {"title": "Perovskite Solar Cells Review"}
        candidates = [{"doc_id": "d1", "title": "Perovskite Solar Cells"}]
        r = match_reference_to_document(ref, candidates)
        # token Jaccard: {perovskite,solar,cells,review} vs {perovskite,solar,cells} = 3/4 = 0.75 < 0.9
        assert r.match_type == MatchType.UNMATCHED

    def test_title_fuzzy_match_high_jaccard(self):
        ref = {"title": "Graph Neural Networks Survey"}
        candidates = [{"doc_id": "d2", "title": "Graph Neural Networks"}]
        # {graph,neural,networks,survey} vs {graph,neural,networks} = 3/4 = 0.75 < 0.9
        r = match_reference_to_document(ref, candidates)
        assert r.match_type == MatchType.UNMATCHED

    def test_title_fuzzy_match_pass_threshold(self):
        ref = {"title": "Graph Neural Networks Networks"}
        candidates = [{"doc_id": "d2", "title": "Graph Neural Networks"}]
        # 归一化后 "graph neural networks networks" != "graph neural networks"（多一个 networks）
        # 但 set 去重后 token 集合相同 → Jaccard=1.0，走 fuzzy 分支
        r = match_reference_to_document(ref, candidates)
        assert r.match_type == MatchType.TITLE_FUZZY
        assert r.confidence == 1.0
        assert r.doc_id == "d2"

    def test_priority_doi_before_title(self):
        """DOI 命中应优先于题名命中。"""
        ref = {"doi": "10.1000/abc", "title": "Graph Neural Networks"}
        r = match_reference_to_document(ref, self.CANDIDATES)
        assert r.match_type == MatchType.DOI
        assert r.doc_id == "d1"

    def test_unmatched(self):
        ref = {"title": "Completely Unknown Topic XYZ123"}
        r = match_reference_to_document(ref, self.CANDIDATES)
        assert r.match_type == MatchType.UNMATCHED
        assert r.doc_id is None
        assert r.confidence == 0.0

    def test_empty_candidates(self):
        r = match_reference_to_document({"doi": "10.1/x"}, [])
        assert r.match_type == MatchType.UNMATCHED


class TestBuildCandidateIndex:
    def test_index(self):
        docs = [
            {"doc_id": "d1", "doi": "10.1/a", "title": "Alpha"},
            {"doc_id": "d2", "title": "Beta"},
        ]
        idx = build_candidate_index(docs)
        assert idx["by_doi"] == {"10.1/a": "d1"}
        assert idx["by_title"] == {"alpha": "d1", "beta": "d2"}

    def test_index_arxiv(self):
        docs = [
            {
                "doc_id": "d1",
                "title": "Attention Is All You Need",
                "arxiv_id": "1706.03762",
            },
            {"doc_id": "d2", "title": "1408.2982.pdf"},
        ]
        idx = build_candidate_index(docs)
        assert idx["by_arxiv"] == {"1706.03762": "d1", "1408.2982": "d2"}
