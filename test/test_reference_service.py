# -*- coding: utf-8 -*-
"""
reference_service 单元测试
覆盖：参考文献区块定位、条目切分（前置/后置标记）、字段抽取、标准化输出。
"""
import fitz

from app.services.reference_service import (
    ReferenceExtractionService,
    references_to_bibtex,
    references_to_csl_json,
)


def _make_pdf(path, lines):
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for line in lines:
        page.insert_text((72, y), line, fontsize=11)
        y += 18
    doc.save(str(path))
    doc.close()


def test_extract_references_leading_markers(tmp_path):
    pdf = tmp_path / "refs.pdf"
    _make_pdf(
        pdf,
        [
            "Introduction",
            "Some body text.",
            "References",
            "[1] Vaswani A, Shazeer N, Parmar N, et al. Attention is all you need[J].",
            "Advances in Neural Information Processing Systems, 2017, 30: 5998-6008.",
            "[2] Devlin J, Chang M W, Lee K, et al. BERT: Pre-training of deep bidirectional",
            "transformers for language understanding[J]. arXiv preprint arXiv:1810.04805, 2018.",
            "doi:10.48550/arXiv.1810.04805",
        ],
    )

    refs = ReferenceExtractionService().extract_references(str(pdf))

    assert len(refs) == 2
    assert refs[0]["index"] == 1
    assert refs[0]["type"] == "journal"
    assert refs[0]["year"] == "2017"
    assert "5998-6008" in (refs[0]["pages"] or "")
    assert "Vaswani" in refs[0]["authors"]
    assert refs[1]["index"] == 2
    assert refs[1]["year"] == "2018"


def test_extract_references_trailing_markers(tmp_path):
    # 中文期刊常见：条目文本在前，序号标记在后
    pdf = tmp_path / "refs_cn.pdf"
    _make_pdf(
        pdf,
        [
            "Conclusion",
            "References",
            "Kaplan J, McCandlish S, Henighan T, et al. Scaling laws[J]. arXiv 2020",
            "[1]",
            "Brown P F. Class-based n-gram models[J]. Computational Linguistics, 1992, 18(4): 467-480",
            "[2]",
        ],
    )

    refs = ReferenceExtractionService().extract_references(str(pdf))

    assert len(refs) == 2
    assert refs[0]["index"] == 1
    assert refs[1]["index"] == 2
    assert refs[1]["year"] == "1992"
    assert refs[1]["volume"] == "18"
    assert refs[1]["issue"] == "4"


def test_chinese_section_header_normalization():
    # 纯函数级别：中文（含全角空格）参考文献标题应被识别
    from app.services.reference_service import _is_section_header

    assert _is_section_header("参考文献")
    assert _is_section_header("参　考　文　献")
    assert _is_section_header("References")
    assert _is_section_header("Bibliography")
    assert not _is_section_header("Introduction")


def test_extract_references_none(tmp_path):
    pdf = tmp_path / "plain.pdf"
    _make_pdf(pdf, ["Just some text", "Without any references."])

    refs = ReferenceExtractionService().extract_references(str(pdf))
    assert refs == []


def test_standardize_outputs():
    refs = [
        {
            "index": 1,
            "authors": "Vaswani A, Shazeer N",
            "title": "Attention is all you need",
            "journal": "NeurIPS",
            "year": "2017",
            "volume": "30",
            "issue": None,
            "pages": "5998-6008",
            "doi": "10.48550/example",
            "type": "journal",
            "raw": "...",
        }
    ]
    csl = references_to_csl_json(refs)
    assert csl[0]["DOI"] == "10.48550/example"
    assert csl[0]["issued"]["date-parts"] == [[2017]]
    assert csl[0]["author"][0]["family"] in ("Shazeer", "Vaswani")

    bib = references_to_bibtex(refs)
    assert "@journal{ref1," in bib
    assert "title = {Attention is all you need}," in bib
    assert "doi = {10.48550/example}," in bib


def test_parsing_service_extract_references_wrapper(tmp_path):
    from app.services.parsing_service import ParsingService

    pdf = tmp_path / "refs.pdf"
    _make_pdf(
        pdf,
        [
            "References",
            "[1] Doe J. Example paper[J]. Journal of Testing, 2020.",
        ],
    )
    refs = ParsingService().extract_references(str(pdf))
    assert len(refs) == 1
    assert refs[0]["year"] == "2020"
