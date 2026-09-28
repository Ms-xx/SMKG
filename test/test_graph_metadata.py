# -*- coding: utf-8 -*-
"""graph_metadata 纯函数单测（步骤 16.2.1）。"""
from datetime import datetime

from app.services.graph_metadata import (
    extract_authors,
    extract_venue,
    extract_year,
)


class TestExtractYear:
    def test_normal_date_string(self):
        assert extract_year("2023-01-15") == "2023"
        assert extract_year("2023/03/01") == "2023"
        assert extract_year("20230101") == "2023"

    def test_none_and_invalid(self):
        assert extract_year(None) is None
        assert extract_year("") is None
        assert extract_year("not-a-date") is None
        assert extract_year("abc") is None
        assert extract_year("999") is None

    def test_datetime_object_and_out_of_range(self):
        assert extract_year(datetime(2020, 6, 1)) == "2020"
        assert extract_year(datetime(1899, 1, 1)) is None  # 超范围下界
        assert extract_year(datetime(2101, 1, 1)) is None  # 超范围上界

    def test_iso_with_timezone(self):
        assert extract_year("2024-12-31T23:59:59+08:00") == "2024"
        assert extract_year("2019-05-20T10:00:00Z") == "2019"


class TestExtractAuthors:
    def test_none(self):
        assert extract_authors(None) == []

    def test_string_semicolon(self):
        assert extract_authors("张三;李四;王五") == ["张三", "李四", "王五"]

    def test_list_of_dict(self):
        authors = [{"name": "Alice"}, {"name": "Bob"}, {"author": "Carol"}]
        assert extract_authors(authors) == ["Alice", "Bob", "Carol"]

    def test_list_of_str(self):
        assert extract_authors(["A", "B", ""]) == ["A", "B"]

    def test_json_array_string(self):
        """MySQL JSON 列常以文本形式返回，需反序列化后再归一化。"""
        assert extract_authors('["Alice", "Bob"]') == ["Alice", "Bob"]
        assert extract_authors('["Rafal Jozefowicz"]') == ["Rafal Jozefowicz"]

    def test_malformed_json_string_falls_back(self):
        assert extract_authors('["未闭合') == ["未闭合"]
        assert extract_authors("[]") == []


class TestExtractVenue:
    def test_none(self):
        assert extract_venue(None) is None

    def test_empty(self):
        assert extract_venue("") is None
        assert extract_venue("   ") is None

    def test_normal(self):
        assert extract_venue("Nature") == "Nature"
        assert extract_venue("  Science  ") == "Science"
