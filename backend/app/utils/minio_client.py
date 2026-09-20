import logging
import os
from io import BytesIO

from minio import Minio
from minio.error import S3Error

from app.core.config import settings

logger = logging.getLogger(__name__)

# Fallback local storage directory when MinIO is unavailable
LOCAL_STORAGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storage", "uploads"
)


class MinioClient:
    _instance = None
    _available: bool = True

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._client = None
        return cls._instance

    @property
    def client(self) -> Minio:
        if self._client is None:
            self._client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE,
            )
        return self._client

    @property
    def is_available(self) -> bool:
        return self._available

    def _check_available(self):
        """Try a lightweight call to see if MinIO is reachable."""
        if not self._available:
            return False
        try:
            self.client.bucket_exists(settings.MINIO_BUCKET_NAME)
            return True
        except Exception:
            self._available = False
            logger.warning("MinIO not available, using local file storage fallback")
            return False

    def _ensure_bucket(self):
        try:
            if not self.client.bucket_exists(settings.MINIO_BUCKET_NAME):
                self.client.make_bucket(settings.MINIO_BUCKET_NAME)
        except S3Error as e:
            logger.warning(f"MinIO bucket error: {e}")

    def upload_file(
        self, object_name: str, data: bytes, content_type: str = "application/pdf"
    ) -> str:
        if not self._check_available():
            # Fallback: save to local filesystem
            local_path = os.path.join(LOCAL_STORAGE_DIR, object_name)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(data)
            logger.info(f"File saved locally (MinIO unavailable): {local_path}")
            return f"local://{object_name}"
        try:
            self._ensure_bucket()
            self.client.put_object(
                settings.MINIO_BUCKET_NAME,
                object_name,
                BytesIO(data),
                length=len(data),
                content_type=content_type,
            )
            return object_name
        except Exception as e:
            # Fallback to local storage on any error
            self._available = False
            local_path = os.path.join(LOCAL_STORAGE_DIR, object_name)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(data)
            logger.warning(f"MinIO upload failed, saved locally: {e}")
            return f"local://{object_name}"

    def download_file(self, object_name: str) -> bytes:
        if object_name.startswith("local://"):
            local_path = os.path.join(LOCAL_STORAGE_DIR, object_name[len("local://") :])
            with open(local_path, "rb") as f:
                return f.read()
        try:
            response = self.client.get_object(settings.MINIO_BUCKET_NAME, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except Exception as e:
            raise Exception(f"Failed to download file: {e}") from e

    def get_presigned_url(self, object_name: str, expires: int = 3600) -> str:
        if object_name.startswith("local://"):
            return f"/api/v1/documents/local-file/{object_name}"
        try:
            return self.client.presigned_get_object(
                settings.MINIO_BUCKET_NAME, object_name, expires=expires
            )
        except Exception as e:
            raise Exception(f"Failed to get presigned URL: {e}") from e

    def delete_file(self, object_name: str):
        if object_name.startswith("local://"):
            local_path = os.path.join(LOCAL_STORAGE_DIR, object_name[len("local://") :])
            if os.path.exists(local_path):
                os.remove(local_path)
            return
        try:
            self.client.remove_object(settings.MINIO_BUCKET_NAME, object_name)
        except Exception as e:
            logger.warning(f"Failed to delete file from MinIO: {e}")
