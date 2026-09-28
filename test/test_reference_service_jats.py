# -*- coding: utf-8 -*-
"""
reference_service JATS 序列化单元测试
覆盖：references_to_jats 合法性、字段拼装、XML 转义、缺字段降级。
"""
import xml.etree.ElementTree as ET

from app.services.reference_service import (
    ReferenceExtractionService,
    references_to_jats,
)


def _sample_refs(**overrides):
    base = {
        "index": 1,
        "authors": "Vaswani A, Shazeer N",
        "title": "Attention is all you need",
        "journal": "NeurIPS",
        "year": "2017",
        "volume": "30",
        "issue": "4",
        "pages": "5998-6008",
        "doi": "10.48550/example",
        "type": "journal",
    }
    base.update(overrides)
    return [base]


def test_references_to_jats_xml_declaration_and_namespace():
    xml = references_to_jats(_sample_refs())
    assert xml.startswith("<?xml")
    assert "http://www.ncbi.nlm.nih.gov/JATS1" in xml
    # 可被 xml.etree 正常解析（well-formed）
    root = ET.fromstring(xml)
    assert root.tag == "{http://www.ncbi.nlm.nih.gov/JATS1}ref-list"


def test_references_to_jats_contains_fields():
    xml = references_to_jats(_sample_refs())
    root = ET.fromstring(xml)
    ref = root.find("{http://www.ncbi.nlm.nih.gov/JATS1}ref")
    citation = ref.find("{http://www.ncbi.nlm.nih.gov/JATS1}mixed-citation")
    text = ET.tostring(citation, encoding="unicode", method="text")
    assert citation.get("publication-type") == "journal"
    assert "Attention is all you need" in text
    assert "Vaswani A, Shazeer N" in text or "Shazeer" in text
    ext = citation.find("{http://www.ncbi.nlm.nih.gov/JATS1}ext-link")
    assert ext is not None
    assert "10.48550/example" in ext.text


def test_references_to_jats_escapes_special_chars():
    refs = _sample_refs(title="R&D <Gen> \"X\" & Y 'Z'")
    xml = references_to_jats(refs)
    assert "&lt;" in xml
    assert "&amp;" in xml
    ET.fromstring(xml)  # 不抛异常 = 转义正确


def test_references_to_jats_missing_fields_skipped():
    refs = [
        {
            "index": 2,
            "authors": "",  # 缺作者
            "title": "Only title here",
            # 缺 journal/year/volume/issue/pages/doi
            "type": "conference",
        }
    ]
    xml = references_to_jats(refs)
    root = ET.fromstring(xml)
    citation = root.find(".//{http://www.ncbi.nlm.nih.gov/JATS1}mixed-citation")
    assert citation.get("publication-type") == "conference"
    text = ET.tostring(citation, encoding="unicode", method="text")
    assert "Only title here" in text
    # 缺字段不该出现在输出里
    assert "10.48550" not in xml
    assert "N/A" not in xml


def test_service_to_jats_method_and_empty_refs():
    service = ReferenceExtractionService()
    xml = service.to_jats([])
    assert xml.startswith("<?xml")
    root = ET.fromstring(xml)
    assert root.tag == "{http://www.ncbi.nlm.nih.gov/JATS1}ref-list"
    assert len(list(root)) == 0  # 空 ref-list，不编造
