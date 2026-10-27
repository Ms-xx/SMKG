# -*- coding: utf-8 -*-
"""PaddleOCR 真实端到端实测：扫描件（无文本层）PDF → OCR 出非空文本。

覆盖链路：
1. 用 PIL + 中文字体生成含中文的 PNG；
2. 用 PyMuPDF 把 PNG 嵌入 PDF（不放文本层，模拟扫描件）→ `page.get_text()` 为空；
3. `OCRService.recognize` / `recognize_with_boxes` 走真实 PaddleOCR（3.x 适配后）；
4. `ParsingService.extract_text_with_pymupdf` 触发 OCR 回退，校验 `ocr_used` / `ocr_pages`。

产物：`outputs/ocr_e2e.json`。
在无 paddleocr 的环境下本脚本会如实记录 `backend=unavailable` 并判定为环境态失败（退出码 1）。
"""
from __future__ import annotations

import json
import os
import sys
import time

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_DIR = os.path.join(ROOT_DIR, "outputs")
TMP_DIR = os.path.join(ROOT_DIR, "outputs", "_ocr_tmp")

LINE_1 = "多模态科学文献智能解析"
LINE_2 = "知识图谱构建与OCR识别"
EXPECT_1 = ["科学文献", "智能解析"]
EXPECT_2 = ["知识图谱", "OCR"]


def _find_cjk_font() -> str | None:
    candidates = ["simhei.ttf", "msyh.ttc", "simsun.ttc", "Deng.ttf"]
    for name in candidates:
        path = os.path.join(r"C:\Windows\Fonts", name)
        if os.path.exists(path):
            return path
    return None


def _build_png(png_path: str) -> str:
    """渲染两行中文到白底 PNG，返回使用字体路径（供报告记录）。"""
    from PIL import Image, ImageDraw, ImageFont

    font_path = _find_cjk_font()
    if font_path is None:
        raise RuntimeError("未找到可用中文字体（C:\\Windows\\Fonts）")

    img = Image.new("RGB", (1200, 400), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, 64)
    draw.text((60, 90), LINE_1, font=font, fill="black")
    draw.text((60, 240), LINE_2, font=font, fill="black")
    img.save(png_path, "PNG")
    return font_path


def _png_to_scanned_pdf(png_path: str, pdf_path: str) -> None:
    """把 PNG 铺满整页写入 PDF，且不叠加任何文本层（模拟扫描件）。"""
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=600, height=200)
    page.insert_image(page.rect, filename=png_path)
    doc.save(pdf_path)
    doc.close()


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)
    png_path = os.path.join(TMP_DIR, "ocr_sample.png")
    pdf_path = os.path.join(TMP_DIR, "scanned_sample_ocr.pdf")

    report: dict = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "expected_lines": [LINE_1, LINE_2],
        "checks": {},
    }

    font_path = _build_png(png_path)
    report["font"] = font_path
    _png_to_scanned_pdf(png_path, pdf_path)

    import fitz

    doc = fitz.open(pdf_path)
    raw_layer = doc[0].get_text()
    doc.close()
    report["pdf_text_layer_len"] = len(raw_layer)
    report["checks"]["可以构造无文本层的扫描件 PDF"] = len(raw_layer.strip()) == 0

    from app.services.ocr_service import OCRService
    from app.services.parsing_service import ParsingService

    svc = OCRService()
    t0 = time.time()
    text = svc.recognize(png_path)
    report["ocr_seconds"] = round(time.time() - t0, 2)

    report["backend"] = svc.backend
    report["available"] = svc.available
    report["load_error"] = svc._load_error
    report["recognized_text"] = text
    report["checks"]["PaddleOCR 加载成功（backend=paddleocr）"] = svc.backend == "paddleocr"
    report["checks"]["单图 OCR 返回非空文本"] = bool(text.strip())

    joined = text.replace("\n", "")
    report["checks"]["识别命中第一行关键词"] = all(k in joined for k in EXPECT_1)
    report["checks"]["识别命中第二行关键词"] = all(k in joined for k in EXPECT_2)

    boxes = svc.recognize_with_boxes(png_path)
    report["box_count"] = len(boxes)
    report["sample_boxes"] = boxes[:6]
    report["checks"]["词框输出含文本与 bbox"] = bool(boxes) and all(
        b.get("text") and b.get("bbox") for b in boxes[:3]
    )

    parsing = ParsingService(ocr=svc)
    t1 = time.time()
    result = parsing.extract_text_with_pymupdf(pdf_path)
    report["parsing_seconds"] = round(time.time() - t1, 2)

    page0 = result["pages"][0]
    report["parsing_page_text"] = page0["text"]
    report["parsing_ocr_used"] = page0["ocr_used"]
    report["parsing_ocr_pages"] = result["metadata"]["ocr_pages"]
    report["checks"]["解析链路触发 OCR 回退（ocr_used=True）"] = page0["ocr_used"] is True
    report["checks"]["解析链路 ocr_pages=1"] = result["metadata"]["ocr_pages"] == 1
    report["checks"]["解析链路输出非空中文文本"] = bool(page0["text"].strip())

    passed = sum(1 for v in report["checks"].values() if v)
    total = len(report["checks"])
    report["summary"] = {"passed": passed, "total": total, "all_passed": passed == total}

    out_path = os.path.join(OUT_DIR, "ocr_e2e.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    for name, ok in report["checks"].items():
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    print(f"backend={report['backend']} box_count={report['box_count']}")
    print(f"recognized={text!r}")
    print(f"summary={passed}/{total} -> {out_path}")

    return 0 if report["summary"]["all_passed"] else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())
