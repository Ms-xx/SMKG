# -*- coding: utf-8 -*-
"""
parsing_service 单元测试
覆盖：文本提取、表格提取、图像提取（纯函数，无 DB / MinIO 依赖）
"""
import fitz  # PyMuPDF

from app.services.parsing_service import ParsingService


def _make_text_pdf(path, pages=2):
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"Text content on page {i + 1}", fontsize=12)
    doc.save(path)
    doc.close()


def test_extract_text_with_pymupdf(tmp_path):
    pdf = tmp_path / "sample.pdf"
    _make_text_pdf(pdf, pages=2)

    svc = ParsingService()
    result = svc.extract_text_with_pymupdf(str(pdf))

    assert result["metadata"]["page_count"] == 2
    assert len(result["pages"]) == 2
    assert result["pages"][0]["page_number"] == 1
    assert "Text content on page 1" in result["pages"][0]["text"]
    assert result["pages"][0]["width"] > 0
    assert result["pages"][0]["height"] > 0


def test_extract_tables_with_pdfplumber_no_tables(tmp_path):
    pdf = tmp_path / "sample.pdf"
    _make_text_pdf(pdf, pages=1)

    svc = ParsingService()
    tables = svc.extract_tables_with_pdfplumber(str(pdf))

    # 纯文本 PDF 无表格，返回空列表但不应报错
    assert isinstance(tables, list)
    assert tables == []


def test_extract_images_text_only(tmp_path):
    pdf = tmp_path / "sample.pdf"
    _make_text_pdf(pdf, pages=1)
    output_dir = tmp_path / "images"
    output_dir.mkdir()

    svc = ParsingService()
    images = svc.extract_images(str(pdf), str(output_dir))

    # 无嵌入图片的 PDF 返回空列表
    assert images == []