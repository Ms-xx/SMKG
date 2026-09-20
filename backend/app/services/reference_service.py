"""
参考文献解析与结构化服务

规则 + 正则兜底方案（无 GROBID/Cermine 时可用），职责：
1. 定位参考文献区块（Section 头正则 + 版面位置启发式）
2. 条目切分（按序号标记 [1] / ［1］ 前置或后置）
3. 字段抽取（作者、标题、期刊/会议、年份、卷、期、页码、DOI、类型）
4. 标准化输出（CSL-JSON 风格字典 + BibTeX 序列化）

纯 Python 实现，无外部模型依赖；缺失降级返回空列表。
"""

import re
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 定位参考文献区块
# ---------------------------------------------------------------------------

# 去除空白与全角空格后的“标题关键词”（归一化后匹配，避免中英/全半角空格差异）
_SECTION_KEYWORDS = (
    "references",
    "bibliography",
    "literaturecited",  # "Literature Cited"
    "workscited",  # "Works Cited"
    "referencesandnotes",
    "参考文献",
    "主要参考文献",
    "参考资料",
)

# 参考文献之后的截断关键词（作者简介/收稿信息等，避免误纳入条目）
_CUTOFF_KEYWORDS = (
    "authorbiograph",
    "biographies",
    "作者简介",
    "收稿日期",
    "基金项目",
    "received",
    "accepted",
    "correspondingauthor",
    "correspondence",
    "参考文献的标注",
    "注释",
)


def _normalize(text: str) -> str:
    """去除所有空白（含全角空格 \u3000），用于标题关键词匹配。"""
    return re.sub(r"[\s\u3000\u00a0]+", "", text)


def _is_section_header(line: str) -> bool:
    norm = _normalize(line).lower()
    if not norm:
        return False
    for kw in _SECTION_KEYWORDS:
        if norm == kw or norm.startswith(kw):
            return True
    return False


def _is_cutoff_line(line: str) -> bool:
    norm = _normalize(line).lower()
    for kw in _CUTOFF_KEYWORDS:
        if norm.startswith(kw):
            return True
    return False


def _locate_reference_section(pages_text: List[str]) -> str:
    """
    从后向前扫描页面，定位参考文献区块并返回其后的正文。

    返回参考文献区块文本（从 Section 头下一行到文档末尾/截断点）。
    """
    start_page = None
    start_line_idx = None
    for idx in range(len(pages_text) - 1, -1, -1):
        lines = pages_text[idx].splitlines()
        for li, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            if _is_section_header(stripped):
                start_page = idx
                start_line_idx = li
                break
        if start_page is not None:
            break

    if start_page is None:
        return ""

    # 从命中的头部开始收集后续文本
    collected: List[str] = []
    for idx in range(start_page, len(pages_text)):
        lines = pages_text[idx].splitlines()
        if idx == start_page:
            lines = lines[start_line_idx + 1 :] if start_line_idx is not None else lines
        for line in lines:
            if _is_cutoff_line(line.strip()):
                return "\n".join(collected)
            collected.append(line)

    return "\n".join(collected)


# ---------------------------------------------------------------------------
# 条目切分
# ---------------------------------------------------------------------------

_MARKER_RE = re.compile(r"[\[［【]\s*(\d{1,4})\s*[\]］】]")


def _split_entries(block: str) -> List[Tuple[str, str]]:
    """
    将参考文献区块切分为 (序号, 条目文本) 列表。

    兼容两种常见排版：
    - 前置标记（英文常见）："[1] Author. Title..."
    - 后置标记（中文常见）："Author. Title... ［1］"
    """
    # 统一全角/半角方括号
    normalized = block.replace("［", "[").replace("］", "]")
    matches = list(_MARKER_RE.finditer(normalized))
    if not matches:
        return []

    # 首个标记前若已有实质正文，则标记为后置（条目在其序号之前）
    prefix = normalized[: matches[0].start()].strip()
    leading = len(prefix) < 40

    entries: List[Tuple[str, str]] = []
    if leading:
        for i, m in enumerate(matches):
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(normalized)
            seg = normalized[start:end].strip()
            if seg:
                entries.append((m.group(1), _clean_segment(seg)))
    else:
        for i, m in enumerate(matches):
            start = 0 if i == 0 else matches[i - 1].end()
            end = m.start()
            seg = normalized[start:end].strip()
            if seg:
                entries.append((m.group(1), _clean_segment(seg)))
    return entries


def _clean_segment(seg: str) -> str:
    """合并条目内部换行，压缩连续空白，保留可读的空格。"""
    seg = re.sub(r"\s*\n\s*", " ", seg)
    seg = re.sub(r"[ \t\u3000]+", " ", seg)
    return seg.strip()


# ---------------------------------------------------------------------------
# 字段抽取
# ---------------------------------------------------------------------------

_DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+\b")
_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")

# 文献类型标记（GB/T 7714 / 常见英文引用类型）
_TYPE_MARKS = {
    "journal": r"\[J\]|\[Journal\]",
    "conference": r"\[C\]|\[Conference\]",
    "book": r"\[M\]|\[B\]",
    "thesis": r"\[D\]",
    "report": r"\[R\]",
    "patent": r"\[P\]",
    "standard": r"\[S\]",
    "online": r"\[EB/OL\]|\[DB/OL\]|\[EB\]|\[OL\]|\[DB\]",
    "journal_article": r"\[J/OL\]",
}


def _extract_doi(entry: str) -> Optional[str]:
    m = _DOI_RE.search(entry)
    return m.group(0).rstrip(".,;") if m else None


def _extract_year(entry: str) -> Optional[str]:
    # 取最后一个四位年份（更接近发表年）
    years = _YEAR_RE.findall(entry)
    return years[-1] if years else None


def _extract_type(entry: str) -> str:
    for typ, pattern in _TYPE_MARKS.items():
        if re.search(pattern, entry):
            return "journal" if typ == "journal_article" else typ
    if "[J]" in entry or re.search(r"\.\s*[A-Z][a-z]+,\s*(19|20)\d{2}", entry):
        return "journal"
    return "other"


def _extract_pages(entry: str) -> Optional[str]:
    # 形如 "100-110", "467−480", "20841−20855"
    m = re.search(r"[:：]\s*(\d{1,6}\s*[-\u2212–—]\s*\d{1,6})", entry)
    if m:
        return re.sub(r"\s+", "", m.group(1))
    # 卷(期): 页码 常见形式 "18(4): 467−480"
    m2 = re.search(r"\(\d+\)\s*[:：]\s*(\d{1,6}\s*[-\u2212–—]\s*\d{1,6})", entry)
    if m2:
        return re.sub(r"\s+", "", m2.group(1))
    return None


def _extract_volume_issue(entry: str) -> Tuple[Optional[str], Optional[str]]:
    # "18(4)" / "56(10)" 卷(期) 形式
    m = re.search(r"\b(\d{1,3})\s*\(\s*(\d{1,3})\s*\)", entry)
    if m:
        return m.group(1), m.group(2)
    # 单独卷 "35," "61 (2)" 等
    m2 = re.search(r"\b(\d{1,3})\s*,\s*(\d{1,6})\s*[-\u2212]", entry)
    if m2:
        return m2.group(1), None
    return None, None


def _split_authors_title(head: str) -> Tuple[str, str]:
    """
    head 形如 "Author A, Author B. Title ..."，
    按首个句点/et al 切分作者与标题（尽力而为）。
    """
    head = head.strip()
    # "et al." 后跟标题
    etal = re.search(r"\bet\s+al\.\s*", head, re.IGNORECASE)
    if etal:
        authors = head[: etal.end()].strip()
        title = head[etal.end() :].strip()
        # 去掉作者末尾句点
        authors = authors.rstrip(".,;")
        title = title.lstrip(".,; ")
        return authors, title
    # 按 ". " 后跟大写字母切分（作者末句点）
    m = re.search(r"\.\s+(?=[A-Z\u4e00-\u9fff])", head)
    if m:
        authors = head[: m.start()].strip()
        title = head[m.end() :].strip()
        return authors.rstrip(".,;"), title
    return head, ""


def _extract_fields(entry: str) -> Dict:
    fields: Dict = {
        "authors": "",
        "title": "",
        "journal": "",
        "year": _extract_year(entry),
        "volume": None,
        "issue": None,
        "pages": _extract_pages(entry),
        "doi": _extract_doi(entry),
        "type": _extract_type(entry),
    }

    # 用文献类型标记切分 head（作者+标题）与 tail（期刊/会议+年卷期页）
    mark_match = re.search(
        r"\[(?:J|C|M|D|R|P|S|EB/OL|DB/OL|J/OL|Book|Conference|Journal)\]", entry
    )
    if mark_match:
        head = entry[: mark_match.start()]
        tail = entry[mark_match.end() :]
    else:
        head = entry
        tail = ""

    authors, title = _split_authors_title(head)
    fields["authors"] = authors
    fields["title"] = title

    if tail:
        tail = tail.strip()
        # 期刊/会议名到年份之前
        year = fields["year"]
        if year:
            year_idx = tail.find(year)
            if year_idx >= 0:
                fields["journal"] = tail[:year_idx].strip(" .,;:")
    if not fields["journal"]:
        fields["journal"] = (
            re.sub(r"[:：].*$", "", tail or head.split(".")[-1:]).strip()
            if tail
            else ""
        )

    vol, issue = _extract_volume_issue(entry)
    fields["volume"] = vol
    fields["issue"] = issue

    return fields


# ---------------------------------------------------------------------------
# 服务主体
# ---------------------------------------------------------------------------


class ReferenceExtractionService:
    """参考文献抽取服务单例（纯规则，可插拔降级）。"""

    def extract_references(self, file_path: str) -> List[Dict]:
        """从 PDF 抽取结构化参考文献列表。"""
        try:
            import fitz
        except Exception:
            return []

        doc = None
        try:
            doc = fitz.open(file_path)
            pages_text = [page.get_text() for page in doc]
        except Exception:
            return []
        finally:
            if doc is not None:
                try:
                    doc.close()
                except Exception:
                    pass

        block = _locate_reference_section(pages_text)
        if not block.strip():
            return []

        refs: List[Dict] = []
        for idx_str, entry in _split_entries(block):
            fields = _extract_fields(entry)
            fields["index"] = int(idx_str)
            fields["raw"] = entry
            refs.append(fields)
        return refs

    def extract_references_dict(self, file_path: str) -> Dict:
        """返回 {"count": int, "references": [...]} 结构。"""
        refs = self.extract_references(file_path)
        return {"count": len(refs), "references": refs, "format": "csl-json"}


# ---------------------------------------------------------------------------
# 标准化输出
# ---------------------------------------------------------------------------


def references_to_csl_json(references: List[Dict]) -> List[Dict]:
    """将结构化条目映射为 CSL-JSON 风格（type/author/title/container-title 等）。"""

    def _split_authors(text: str) -> List[Dict]:
        if not text:
            return []
        text = re.sub(r"\bet\s+al\.?", "", text, flags=re.IGNORECASE)
        parts = [p.strip().rstrip(".,") for p in re.split(r"[;,]", text) if p.strip()]
        result = []
        for p in parts:
            words = p.split()
            if not words:
                continue
            if len(words) >= 2 and re.fullmatch(r"[A-Z]\.?", words[-1]):
                # "Vaswani A" -> family Vaswani, given A（姓 + 首字母）
                result.append({"family": words[-2], "given": words[-1]})
            elif len(words) >= 2:
                result.append({"family": words[-1], "given": " ".join(words[:-1])})
            else:
                result.append({"literal": words[0]})
        return result

    csl: List[Dict] = []
    for r in references:
        item = {
            "id": str(r.get("index", "")),
            "type": r.get("type") or "article",
            "title": r.get("title") or "",
            "author": _split_authors(r.get("authors") or ""),
        }
        if r.get("journal"):
            item["container-title"] = r.get("journal")
        if r.get("year"):
            item["issued"] = {"date-parts": [[int(r["year"])]]}
        if r.get("volume"):
            item["volume"] = r.get("volume")
        if r.get("issue"):
            item["issue"] = r.get("issue")
        if r.get("pages"):
            item["page"] = r.get("pages")
        if r.get("doi"):
            item["DOI"] = r.get("doi")
        csl.append(item)
    return csl


def references_to_bibtex(references: List[Dict]) -> str:
    """将结构化条目序列化为 BibTeX 文本。"""
    lines: List[str] = []
    for r in references:
        idx = r.get("index", "ref")
        key = f"ref{idx}"
        lines.append(f"@{r.get('type') or 'article'}{{{key},")
        lines.append(f"  author = {{{r.get('authors') or ''}}},")
        lines.append(f"  title = {{{r.get('title') or ''}}},")
        if r.get("journal"):
            lines.append(f"  journal = {{{r.get('journal')}}},")
        if r.get("year"):
            lines.append(f"  year = {{{r.get('year')}}},")
        if r.get("volume"):
            lines.append(f"  volume = {{{r.get('volume')}}},")
        if r.get("issue"):
            lines.append(f"  number = {{{r.get('issue')}}},")
        if r.get("pages"):
            lines.append(f"  pages = {{{r.get('pages')}}},")
        if r.get("doi"):
            lines.append(f"  doi = {{{r.get('doi')}}},")
        lines.append("}")
    return "\n".join(lines)


# 全局单例
reference_service = ReferenceExtractionService()
