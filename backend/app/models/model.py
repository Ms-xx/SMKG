from sqlalchemy import JSON, Boolean, Column, DateTime, String, func

from app.models.base import Base, generate_uuid


class Model(Base):
    __tablename__ = "models"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    version = Column(String(20), nullable=False)
    model_type = Column(String(30), nullable=False)
    framework = Column(String(30))
    file_path = Column(String(500))
    metrics = Column(JSON, default=dict)
    is_active = Column(Boolean, nullable=False, default=False)
    created_by = Column(String(36))
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class TrainingExperiment(Base):
    __tablename__ = "training_experiments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    model_id = Column(String(36))
    dataset_version = Column(String(50))
    hyperparameters = Column(JSON, default=dict)
    metrics = Column(JSON, default=dict)
    status = Column(String(20), nullable=False, default="running")
    mlflow_run_id = Column(String(100))
    started_at = Column(DateTime, nullable=False, server_default=func.now())
    completed_at = Column(DateTime)
