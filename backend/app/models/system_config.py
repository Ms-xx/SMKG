from sqlalchemy import JSON, Column, DateTime, String, Text, func

from app.models.base import Base, generate_uuid


class SystemConfig(Base):
    __tablename__ = "system_configs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(JSON, nullable=False)
    description = Column(Text)
    updated_by = Column(String(36))
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
