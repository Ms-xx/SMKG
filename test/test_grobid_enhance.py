# -*- coding: utf-8 -*-
"""
步骤 13.5：GROBID 增强逻辑单测（确定性，不依赖运行中的 GROBID 容器）
- _grobid_parse_bibl：解析 GROBID processReferences 的 TEI XML，抽取作者/标题/期刊/年份/卷/期/页码/DOI
- enhance_references_with_grobid：仅回填缺失字段、顺序对应、禁用/不可达/无pdf时降级原样返回
"""

import pytest

from app.core.config import settings
from app.plugins.reference.service import (
    _grobid_parse_bibl,
    enhance_references_with_grobid,
    grobid_available,
)

# 一份精简但代表真实 GROBID 输出的 TEI（含 analytic/monogr/imprint/idno/biblScope/page from-to）
SAMPLE_TEI = b"""<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader/>
  <text><back><div type="references"><listBibl>
    <biblStruct xml:id="b0">
      <analytic>
        <title level="a" type="main">You Only Look Once: Unified, Real-Time Object Detection</title>
        <author><persName><forename type="first">Joseph</forename><surname>Redmon</surname></persName></author>
      </analytic>
      <monogr>
        <title level="m">Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition</title>
        <imprint>
          <date type="published" when="2016" />
          <biblScope unit="volume">1</biblScope>
          <biblScope unit="page" from="779" to="788" />
          <idno type="DOI">10.1109/CVPR.2016.91</idno>
        </imprint>
      </monogr>
    </biblStruct>
  </listBibl></div></back></text>
</TEI>
"""


def test_parse_bibl_extracts_fields():
    entries = _grobid_parse_bibl(SAMPLE_TEI)
    assert len(entries) == 1
    e = entries[0]
    assert e["authors"] == "Joseph Redmon"
    assert e["title"] == "You Only Look Once: Unified, Real-Time Object Detection"
    assert e["journal"] == "Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition"
    assert e["year"] == "2016"
    assert e["volume"] == "1"
    assert e["pages"] == "779\u2013788"
    assert e["doi"] == "10.1109/CVPR.2016.91"
    assert e["issue"] == ""


def test_parse_bibl_empty_xml_yields_empty():
    assert _grobid_parse_bibl(b"<TEI xmlns='http://www.tei-c.org/ns/1.0'><text/></TEI>") == []


def test_enhance_fills_only_missing_and_preserves_existing(monkeypatch, tmp_path):
    refs = [
        # DOI/期刊缺失 -> 由 GROBID 填充
        {"index": 1, "title": "You Only Look Once", "year": "2016", "raw": "[1] ..."},
        # 已有 DOI -> 保留，不被覆盖
        {"index": 2, "doi": "10.KEEP", "title": "已有", "year": "2015", "raw": "[2] ..."},
    ]

    def fake_process(pdf, endpoint):
        return SAMPLE_TEI

    monkeypatch.setattr(
        "app.plugins.reference.service._grobid_process_references", fake_process
    )
    monkeypatch.setattr(settings, "GROBID_ENABLED", True)
    monkeypatch.setattr(settings, "GROBID_ENDPOINT", "http://localhost:8070")

    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    out = enhance_references_with_grobid(refs, pdf_path=str(pdf))

    # 顺序一致、条数不变
    assert [r["index"] for r in out] == [1, 2]
    assert len(out) == 2
    # 第一条：缺 DOI/journal -> 被填充
    assert out[0]["doi"] == "10.1109/CVPR.2016.91"
    assert "Computer Vision and Pattern Recognition" in out[0]["journal"]
    # 第二条：已有 DOI 不被覆盖
    assert out[1]["doi"] == "10.KEEP"


def test_enhance_degrades_when_disabled(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "GROBID_ENABLED", False)
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    refs = [{"index": 1}]
    assert enhance_references_with_grobid(refs, pdf_path=str(pdf)) == refs


def test_enhance_degrades_when_no_pdf(monkeypatch):
    monkeypatch.setattr(settings, "GROBID_ENABLED", True)
    monkeypatch.setattr(settings, "GROBID_ENDPOINT", "http://localhost:8070")
    refs = [{"index": 1}]
    assert enhance_references_with_grobid(refs) == refs
    assert enhance_references_with_grobid(refs, pdf_path="") == refs


def test_enhance_degrades_on_exception(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "GROBID_ENABLED", True)
    monkeypatch.setattr(settings, "GROBID_ENDPOINT", "http://localhost:8070")

    def boom(pdf, endpoint):
        raise RuntimeError("grobid down")

    monkeypatch.setattr(
        "app.plugins.reference.service._grobid_process_references", boom
    )
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    refs = [{"index": 1}]
    assert enhance_references_with_grobid(refs, pdf_path=str(pdf)) == refs


def test_grobid_available_requires_config(monkeypatch):
    monkeypatch.setattr(settings, "GROBID_ENABLED", False)
    monkeypatch.setattr(settings, "GROBID_ENDPOINT", "")
    # 未启用/未配置 -> False，且不发起网络调用
    assert grobid_available() is False
    monkeypatch.setattr(settings, "GROBID_ENDPOINT", "http://localhost:8070")
    assert grobid_available() is False  # 未启用仍为 False

    monkeypatch.setattr(settings, "GROBID_ENABLED", True)
    monkeypatch.setattr(
        "app.plugins.reference.service.urlopen", lambda url, timeout: object()
    )
    assert grobid_available() is True  # 启用 + 配置 + 端口可达