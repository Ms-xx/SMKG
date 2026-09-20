import os
import tempfile
from typing import Dict, List

import fitz
import pdfplumber

from app.core.config import settings
from app.services.ocr_service import ocr_service


class ParsingService:
    def __init__(self, ocr=None):
        # 可注入 mock 便于测试；默认使用全局单例（懒加载 PaddleOCR）
        self.ocr = ocr if ocr is not None else ocr_service

    def extract_text_with_pymupdf(self, file_path: str, enable_ocr: bool = True) -> Dict:
        doc = fitz.open(file_path)
        result = {
            "metadata": {
                "title": doc.metadata.get("title", ""),
                "author": doc.metadata.get("author", ""),
                "page_count": len(doc),
            },
            "pages": [],
        }
        ocr_pages = 0
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            ocr_used = False

            # 文本层为空（扫描件 / 图片文字页）时回退到 OCR
            if enable_ocr and settings.OCR_ENABLED and not text.strip():
                ocr_text = self._ocr_page(page)
                if ocr_text:
                    text = ocr_text
                    ocr_used = True
                    ocr_pages += 1

            result["pages"].append(
                {
                    "page_number": page_num + 1,
                    "text": text,
                    "width": page.rect.width,
                    "height": page.rect.height,
                    "ocr_used": ocr_used,
                }
            )
        doc.close()
        result["metadata"]["ocr_pages"] = ocr_pages
        return result

    def _ocr_page(self, page, dpi: int | None = None) -> str:
        """将页面渲染为图片后用 OCR 识别文字。"""
        dpi = dpi or settings.OCR_DPI
        pix = page.get_pixmap(dpi=dpi)
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                tmp_path = f.name
            pix.save(tmp_path)
            return self.ocr.recognize(tmp_path)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def _render_page(self, page, dpi: int | None = None) -> str | None:
        """将页面渲染为临时 PNG 并返回路径；失败返回 None（供版面/公式分析使用）。"""
        dpi = dpi or settings.OCR_DPI
        try:
            pix = page.get_pixmap(dpi=dpi)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                tmp_path = f.name
            pix.save(tmp_path)
            return tmp_path
        except Exception:
            return None

    def extract_page_elements(self, file_path: str) -> Dict:
        """
        解析每页版面结构：OCR 词框 → LayoutLMv3 版面分析 → 页眉页脚判定。

        Returns:
            {"metadata": {"page_count": int},
             "pages": [{"page_number": int, "elements": [{"type", "text", "bbox"}]}]}
        """
        from app.services.layout_service import layout_service

        doc = fitz.open(file_path)
        result = {"metadata": {"page_count": len(doc)}, "pages": []}
        for page_num in range(len(doc)):
            page = doc[page_num]
            elements: List[Dict] = []
            image_path = self._render_page(page)
            if image_path:
                try:
                    if hasattr(self.ocr, "recognize_with_boxes"):
                        items = self.ocr.recognize_with_boxes(image_path)
                    else:
                        items = []
                    words = [it.get("text", "") for it in items]
                    boxes = [it.get("bbox") or [0, 0, 0, 0] for it in items]
                    res = layout_service.analyze(image_path, words, boxes)
                    elements = res.get("elements", [])
                finally:
                    if os.path.exists(image_path):
                        os.unlink(image_path)
            result["pages"].append(
                {
                    "page_number": page_num + 1,
                    "elements": elements,
                }
            )
        doc.close()
        return result

    def recognize_formula(self, image_path: str) -> str:
        """识别公式区域图像 → LaTeX（复用 formula_service 单例）。"""
        from app.services.formula_service import formula_service

        return formula_service.recognize(image_path)

    def detect_figures(self, image_path: str) -> List[Dict]:
        """检测图像中的图表/公式区域（复用 figure_detection_service）。"""
        from app.services.figure_detection_service import figure_detection_service

        return figure_detection_service.detect(image_path)

    def describe_chart(self, image_path: str, prompt: str | None = None) -> str:
        """生成图表图像描述（复用 chart_description_service）。"""
        from app.services.chart_description_service import chart_description_service

        if prompt:
            return chart_description_service.describe(image_path, prompt)
        return chart_description_service.describe(image_path)

    def _crop_region(self, image_path: str, bbox: List[float]) -> str | None:
        """按 bbox [x0, y0, x1, y1] 裁剪图像到临时文件并返回路径；失败返回 None。"""
        try:
            from PIL import Image

            x0, y0, x1, y1 = [int(round(v)) for v in bbox]
            img = Image.open(image_path).convert("RGB")
            crop = img.crop((x0, y0, x1, y1))
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                tmp_path = f.name
            crop.save(tmp_path)
            return tmp_path
        except Exception:
            return None

    def extract_figures(self, file_path: str) -> Dict:
        """
        逐页检测图表/公式区域并理解内容：
        渲染页面 → YOLOv8 检测 → 公式区域转 LaTeX / 图表区域生成 BLIP-2 描述。

        Returns:
            {"metadata": {"page_count": int},
             "figures": [{"page_number", "class", "confidence", "bbox",
                          "latex" | "caption"}]}
        """
        doc = fitz.open(file_path)
        result = {"metadata": {"page_count": len(doc)}, "figures": []}
        for page_num in range(len(doc)):
            page = doc[page_num]
            image_path = self._render_page(page)
            if not image_path:
                continue
            try:
                detections = self.detect_figures(image_path)
                for det in detections:
                    region = self._crop_region(image_path, det.get("bbox") or [0, 0, 0, 0])
                    if not region:
                        continue
                    try:
                        cls = (det.get("class") or "").lower()
                        entry = {
                            "page_number": page_num + 1,
                            "class": det.get("class"),
                            "confidence": det.get("confidence"),
                            "bbox": det.get("bbox"),
                        }
                        if "formula" in cls and "table" not in cls:
                            entry["latex"] = self.recognize_formula(region)
                        else:
                            entry["caption"] = self.describe_chart(region)
                        result["figures"].append(entry)
                    finally:
                        if os.path.exists(region):
                            os.unlink(region)
            finally:
                if os.path.exists(image_path):
                    os.unlink(image_path)
        doc.close()
        return result

    def extract_references(self, file_path: str) -> List[Dict]:
        """抽取 PDF 尾部参考文献并结构化为条目列表（复用 reference_service）。"""
        from app.services.reference_service import reference_service

        return reference_service.extract_references(file_path)

    def extract_tables_with_pdfplumber(self, file_path: str) -> List[Dict]:
        tables = []
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                page_tables = page.extract_tables()
                for table in page_tables:
                    tables.append(
                        {
                            "page_number": page_num + 1,
                            "data": table,
                        }
                    )
        return tables

    def extract_images(self, file_path: str, output_dir: str) -> List[str]:
        images = []
        doc = fitz.open(file_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images(full=True)
            for img_index, img in enumerate(image_list):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_path = f"{output_dir}/page_{page_num+1}_img_{img_index+1}.{base_image['ext']}"
                with open(image_path, "wb") as f:
                    f.write(image_bytes)
                images.append(image_path)
        doc.close()
        return images
