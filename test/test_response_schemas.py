# -*- coding: utf-8 -*-
"""schemas/response 响应结构体（APIResponse / ErrorResponse / PaginatedResponse）测试。"""
import pytest

from app.schemas.response import APIResponse, ErrorResponse, PaginatedResponse


def test_api_response_defaults():
    r = APIResponse()
    assert r.code == 200
    assert r.message == "success"
    assert r.data is None
    assert r.timestamp is not None


def test_api_response_generic_data():
    r = APIResponse[int](data=5, message="ok")
    assert r.data == 5


def test_error_response():
    e = ErrorResponse(code=400, message="bad request", errors=["field required"])
    assert e.code == 400
    assert e.errors == ["field required"]


def test_paginated_response():
    p = PaginatedResponse[int](items=[1, 2, 3], total=3, page=1, page_size=10)
    assert p.items == [1, 2, 3]
    assert p.total == 3
    assert p.page == 1
    assert p.page_size == 10