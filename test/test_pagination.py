# -*- coding: utf-8 -*-
"""分页工具单元测试。"""
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.utils.pagination import PaginationParams


def test_pagination_defaults():
    p = PaginationParams()
    assert p.page == 1
    assert p.page_size == 10
    assert p.offset == 0
    assert p.limit == 10


def test_pagination_offset():
    p = PaginationParams(page=3, page_size=20)
    assert p.offset == 40
    assert p.limit == 20


def test_pagination_page_one_zero_offset():
    p = PaginationParams(page=1, page_size=50)
    assert p.offset == 0
    assert p.limit == 50