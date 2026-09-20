# -*- coding: utf-8 -*-
"""minio_client 测试：本地回退 + mock MinIO 服务两套路径。"""
import io
import os

import pytest

from app.utils.minio_client import MinioClient


class _FakeResponse:
    def __init__(self, data):
        self._data = io.BytesIO(data)

    def read(self):
        return self._data.read()

    def close(self):
        pass

    def release_conn(self):
        pass


class _FakeMinio:
    def __init__(self, bucket_exists=True):
        self._bucket = bucket_exists

    def bucket_exists(self, name):
        return self._bucket

    def make_bucket(self, name):
        self._bucket = True

    def put_object(self, bucket, name, data, length, content_type):
        pass

    def get_object(self, bucket, name):
        return _FakeResponse(b"hello")

    def presigned_get_object(self, bucket, name, expires):
        return "http://signed"

    def remove_object(self, bucket, name):
        pass


@pytest.fixture
def mc():
    MinioClient._instance = None
    yield MinioClient()
    MinioClient._instance = None


# ── 上传 ────────────────────────────────────────────────────────────────
def test_upload_file_minio(mc):
    mc._client = _FakeMinio(bucket_exists=False)  # 触发 make_bucket
    mc._available = True
    assert mc.upload_file("a.pdf", b"data") == "a.pdf"


def test_upload_file_local_fallback(mc, tmp_path, monkeypatch):
    monkeypatch.setattr("app.utils.minio_client.LOCAL_STORAGE_DIR", str(tmp_path / "storage"))
    mc._available = False
    assert mc.upload_file("a.pdf", b"data") == "local://a.pdf"
    assert (tmp_path / "storage" / "a.pdf").exists()


def test_upload_file_minio_error_fallback(mc, tmp_path, monkeypatch):
    monkeypatch.setattr("app.utils.minio_client.LOCAL_STORAGE_DIR", str(tmp_path / "storage"))

    class BadMinio(_FakeMinio):
        def put_object(self, *a, **k):
            raise RuntimeError("boom")

    mc._client = BadMinio()
    mc._available = True
    assert mc.upload_file("a.pdf", b"data") == "local://a.pdf"
    assert (tmp_path / "storage" / "a.pdf").exists()


def test_check_available_false_on_error(mc):
    class BadBucket(_FakeMinio):
        def bucket_exists(self, name):
            raise RuntimeError("down")

    mc._client = BadBucket()
    mc._available = True
    assert mc._check_available() is False
    assert mc._available is False


# ── 下载 ────────────────────────────────────────────────────────────────
def test_download_file_local(mc, tmp_path, monkeypatch):
    monkeypatch.setattr("app.utils.minio_client.LOCAL_STORAGE_DIR", str(tmp_path / "storage"))
    (tmp_path / "storage").mkdir(parents=True)
    (tmp_path / "storage" / "a.pdf").write_bytes(b"localdata")
    assert mc.download_file("local://a.pdf") == b"localdata"


def test_download_file_minio(mc):
    mc._client = _FakeMinio()
    mc._available = True
    assert mc.download_file("a.pdf") == b"hello"


def test_download_file_error(mc):
    class BadMinio(_FakeMinio):
        def get_object(self, *a):
            raise RuntimeError("boom")

    mc._client = BadMinio()
    mc._available = True
    with pytest.raises(Exception):
        mc.download_file("a.pdf")


# ── 预签名 URL ──────────────────────────────────────────────────────────
def test_get_presigned_url_local(mc):
    assert mc.get_presigned_url("local://a.pdf") == "/api/v1/documents/local-file/local://a.pdf"


def test_get_presigned_url_minio(mc):
    mc._client = _FakeMinio()
    mc._available = True
    assert mc.get_presigned_url("a.pdf") == "http://signed"


# ── 删除 ────────────────────────────────────────────────────────────────
def test_delete_file_local(mc, tmp_path, monkeypatch):
    monkeypatch.setattr("app.utils.minio_client.LOCAL_STORAGE_DIR", str(tmp_path / "storage"))
    (tmp_path / "storage").mkdir(parents=True)
    p = tmp_path / "storage" / "a.pdf"
    p.write_bytes(b"x")
    mc.delete_file("local://a.pdf")
    assert not p.exists()


def test_delete_file_minio(mc):
    mc._client = _FakeMinio()
    mc._available = True
    mc.delete_file("a.pdf")  # 不抛异常