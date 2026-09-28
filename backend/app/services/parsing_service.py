import os
import tempfile
from typing import Dict, List

import fitz
import pdfplumber

from app.core.config import settings
from app.services.latex_format import (
    SOURCE_IMAGE,
    NormalizedFormula,
    extract_formulas_from_text,
)
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
        doc = fitz.open(file_path)
        result = {"metadata": {"page_count": len(doc)}, "pages": []}
        for page_num in range(len(doc)):
            page = doc[page_num]
            elements: List[Dict] = []
            # 关闭版面分析时直接跳过渲染，避免无谓的 200 DPI 页面位图开销
            if not settings.LAYOUT_ENABLED:
                result["pages"].append({"page_number": page_num + 1, "elements": elements})
                continue
            image_path = self._render_page(page)
            if image_path:
                from app.services.layout_service import layout_service

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

    def _page_lines(self, page) -> list[dict]:
        """抽取页面文本行候选：文本 / 字号 / 是否加粗 / bbox。"""
        lines: list[dict] = []
        for block in page.get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                spans = [s for s in line.get("spans", []) if (s.get("text") or "").strip()]
                if not spans:
                    continue
                lines.append(
                    {
                        "text": " ".join(s["text"].strip() for s in spans),
                        "size": round(max(s.get("size", 0) for s in spans), 1),
                        "bold": any("bold" in (s.get("font") or "").lower() for s in spans),
                        "bbox": list(line.get("bbox") or []),
                    }
                )
        return lines

    @staticmethod
    def _body_font_size(lines: list[dict]) -> float:
        """以出现频次最高的字号作为正文字号。"""
        counts: dict[float, int] = {}
        for line in lines:
            counts[line["size"]] = counts.get(line["size"], 0) + 1
        if not counts:
            return 0.0
        return max(counts.items(), key=lambda kv: kv[1])[0]

    @staticmethod
    def _classify_heading(line: dict, body_size: float) -> int | None:
        """按字号/加粗判定标题层级（1/2/3），非标题返回 None。"""
        if not body_size or len(line["text"]) > 120 or len(line["text"].strip()) < 2:
            return None
        size = line["size"]
        if size >= body_size * 1.5:
            return 1
        if size >= body_size * 1.25:
            return 2
        if size >= body_size * 1.15 or (line["bold"] and size >= body_size):
            return 3
        return None

    def extract_headings_by_fontsize(self, file_path: str) -> Dict:
        """不依赖模型的标题树抽取（版面模型不可用时的兜底，步骤 18 补强）。

        依据：字号显著大于正文 / 加粗 → 标题；按相对字号划分 1/2/3 级。
        Returns: {"metadata": {"page_count": int},
                  "pages": [{"page_number": int, "elements": [
                      {"type": "title", "text", "bbox", "level"}]}]}
        """
        doc = fitz.open(file_path)
        result: Dict = {"metadata": {"page_count": len(doc)}, "pages": []}
        for page_num in range(len(doc)):
            page = doc[page_num]
            lines = self._page_lines(page)
            body_size = self._body_font_size(lines)
            elements = []
            for line in lines:
                level = self._classify_heading(line, body_size)
                if level:
                    elements.append(
                        {
                            "type": "title",
                            "text": line["text"].strip(),
                            "bbox": line["bbox"],
                            "level": level,
                        }
                    )
            result["pages"].append({"page_number": page_num + 1, "elements": elements})
        doc.close()
        return result

    def recognize_formula_detail(self, image_path: str, display: bool = True) -> NormalizedFormula:
        """识别公式区域图像并规范化为 LaTeX（返回结构化结果）。

        Args:
            image_path: 公式区域图像路径。
            display: 公式方向。独立裁剪出的公式区域多为行间公式，故默认 ``True``。

        Returns:
            :class:`NormalizedFormula`；公式识别关闭/不可用时以 ``normalized=False``
            + ``error`` 返回，便于上游标注而非静默丢弃。
        """
        if not settings.FORMULA_ENABLED:
            return NormalizedFormula(
                latex="",
                display=display,
                source=SOURCE_IMAGE,
                normalized=False,
                error="formula_disabled",
            )
        from app.services.formula_service import formula_service

        return formula_service.recognize_detail(image_path, display=display)

    def recognize_formula(self, image_path: str) -> str:
        """识别公式区域图像 → 规范 LaTeX 主体（复用 formula_service 单例）。"""
        return self.recognize_formula_detail(image_path).latex

    def extract_text_formulas(self, text: str) -> List[Dict]:
        """从正文文本层抽取公式并统一规范为 LaTeX。

        覆盖 ``$$...$$`` / ``\\[...\\]`` / ``$...$`` / ``\\(...\\)`` 与数学环境，
        使"文本层公式"不再以裸文本留在正文里。
        """
        return [f.as_dict() for f in extract_formulas_from_text(text or "")]

    def extract_formulas_by_page(self, text_result: Dict) -> List[Dict]:
        """按页抽取文本层公式并附 ``page_number``，供落库为公式元素。"""
        collected: List[Dict] = []
        for page in (text_result or {}).get("pages", []):
            for item in self.extract_text_formulas(page.get("text") or ""):
                item["page_number"] = page.get("page_number")
                collected.append(item)
        return collected

    def detect_figures(self, image_path: str) -> List[Dict]:
        """检测图像中的图表/公式区域（复用 figure_detection_service）。"""
        if not settings.FIGURE_DETECT_ENABLED:
            return []
        from app.services.figure_detection_service import figure_detection_service

        return figure_detection_service.detect(image_path)

    def describe_chart(self, image_path: str, prompt: str | None = None) -> str:
        """生成图表图像描述（复用 chart_description_service）。"""
        if not settings.CHART_CAPTION_ENABLED:
            return ""
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

        公式条目额外携带统一 LaTeX 字段：``latex``（规范主体，无定界符）、
        ``latex_display``（带 ``$$`` 定界符）、``is_display``、``number``、
        ``source``、``normalized``、``original``（识别原始输出）、``error``（失败原因）。
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
                            formula = self.recognize_formula_detail(region)
                            entry.update(
                                {
                                    "latex": formula.latex,
                                    "latex_display": formula.latex_delimited,
                                    "is_display": formula.display,
                                    "number": formula.number,
                                    "source": formula.source,
                                    "normalized": formula.normalized,
                                    "original": formula.original,
                                }
                            )
                            if formula.error:
                                entry["error"] = formula.error
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
