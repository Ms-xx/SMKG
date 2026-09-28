# -*- coding: utf-8 -*-
"""
图谱节点元数据纯函数（步骤 16.2）。

职责：从容错解析发布日期抽取四位数年份，供节点属性回填与索引器共用。
设计约束：纯函数、无 I/O、无外部依赖；非法/超范围输入返回 None，不抛异常。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

_YEAR_MIN = 1900
_YEAR_MAX = 2100


def extract_year(publication_date: datetime | str | None) -> str | None:
    """从容错解析发布日期抽取四位数年份字符串。

    规则：
    - None → None
    - datetime 对象 → .year 四位字符串（超范围返回 None）
    - 字符串 → 优先 ISO 前 4 位；非数字/超范围/解析失败 → None
    - 其他类型 → 尝试 str() 后按字符串规则解析
    """
    if publication_date is None:
        return None

    if isinstance(publication_date, datetime):
        year = publication_date.year
    elif isinstance(publication_date, str):
        year = _parse_year_from_str(publication_date)
    else:
        year = _parse_year_from_str(str(publication_date))

    if year is None or year < _YEAR_MIN or year > _YEAR_MAX:
        return None
    return f"{year:04d}"


def _parse_year_from_str(raw: str) -> int | None:
    """从字符串解析年份：优先前 4 位数字；否则尝试 ISO datetime 解析。"""
    s = raw.strip()
    if not s:
        return None
    # 优先取前 4 位数字（覆盖 "2023-01-01"、"2023/01/01"、"20230101" 等）
    digits = ""
    for ch in s:
        if ch.isdigit():
            digits += ch
        elif digits:
            break
    if len(digits) >= 4:
        try:
            return int(digits[:4])
        except ValueError:
            return None
    # 兜底：尝试 ISO datetime 解析
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).year
    except (ValueError, TypeError):
        return None


def _parse_json_list(text: str) -> list[Any] | None:
    """尝试把 JSON 数组文本解析为 Python list，失败返回 None。"""
    if not text.startswith("["):
        return None
    try:
        parsed = json.loads(text)
    except ValueError:
        return None
    return parsed if isinstance(parsed, list) else None


def _clean_token(value: str) -> str:
    """去除单个作者名两侧残留的 JSON 方括号与引号。"""
    return value.strip().strip("[]\"'").strip()


def _split_authors_text(text: str) -> list[str]:
    """分号分隔文本的兜底拆分（无法解析为 JSON 数组时使用）。"""
    parts = [_clean_token(a) for a in text.split(";") if a.strip()]
    parts = [p for p in parts if p]
    return parts or [_clean_token(text)]


def extract_authors(authors: Any) -> list[str]:
    """归一化作者字段为字符串列表。

    容错范围：None / JSON 数组字符串 / 分号分隔字符串 / 列表（元素可为 str 或 dict）。
    MySQL JSON 列经驱动常返回 JSON 文本，此处先尝试反序列化，避免整串被当成单个作者。
    """
    if authors is None:
        return []
    if isinstance(authors, str):
        text = authors.strip()
        if not text:
            return []
        parsed = _parse_json_list(text)
        if parsed is not None:
            return extract_authors(parsed)
        return _split_authors_text(text)
    if isinstance(authors, list):
        return _extract_authors_from_list(authors)
    return []


def _extract_authors_from_list(authors: list[Any]) -> list[str]:
    """从列表形态的作者字段提取姓名（元素可为 str 或 dict）。"""
    result: list[str] = []
    for item in authors:
        if item is None:
            continue
        if isinstance(item, dict):
            name = item.get("name") or item.get("author") or ""
            if name:
                result.append(str(name).strip())
            continue
        text = str(item).strip()
        if text:
            result.append(text)
    return result


def extract_venue(journal: Any) -> str | None:
    """归一化期刊/载体字段为字符串（空值返回 None）。"""
    if journal is None:
        return None
    s = str(journal).strip()
    return s or None
