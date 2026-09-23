# -*- coding: utf-8 -*-
"""论文检索 PDF 下载与定时追踪测试。"""
from app.services import paper_retrieval_service as prs

_PDF_BYTES = b"%PDF-1.4 fake bytes for test"


def test_pdf_url_arxiv():
    assert prs.pdf_url({"source": "arxiv", "arxiv_id": "1706.03762"}) == (
        "https://arxiv.org/pdf/1706.03762"
    )


def test_pdf_url_pubmed_none():
    assert prs.pdf_url({"source": "pubmed", "pubmed_id": "123"}) is None


def test_download_pdf_success(monkeypatch):
    monkeypatch.setattr(prs, "_http_get_bytes", lambda url, timeout=15.0: _PDF_BYTES)
    out = prs.paper_retrieval_service.download_pdf({"source": "arxiv", "arxiv_id": "1706.03762"})
    assert out["downloaded"] is True
    assert out["filename"] == "1706.03762.pdf"
    assert out["file_size"] == len(_PDF_BYTES)


def test_download_pdf_network_degrades(monkeypatch):
    def boom(url, timeout=15.0):
        raise OSError("timeout")

    monkeypatch.setattr(prs, "_http_get_bytes", boom)
    out = prs.paper_retrieval_service.download_pdf({"source": "arxiv", "arxiv_id": "1706.03762"})
    assert out["downloaded"] is False
    assert "error" in out


def test_download_pdf_pubmed_degrades():
    out = prs.paper_retrieval_service.download_pdf({"source": "pubmed", "pubmed_id": "123"})
    assert out["downloaded"] is False
    assert out["pdf_url"] is None


def test_register_and_list_tracking():
    svc = prs.PaperRetrievalService()
    svc.register_tracking("graph neural networks", source="arxiv", interval_days=7)
    listing = svc.list_tracking()
    assert listing["count"] == 1
    assert listing["items"][0]["query"] == "graph neural networks"


def test_register_tracking_fields():
    svc = prs.PaperRetrievalService()
    rec = svc.register_tracking("materials informatics", source="pubmed", interval_days=30)
    assert rec["id"]
    assert rec["source"] == "pubmed"
    assert rec["interval_days"] == 30
    assert svc.list_tracking()["count"] == 1
