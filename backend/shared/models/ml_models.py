"""
Database models for operational ML models (non-LLM).

These are used for streaming decision tasks such as anomaly detection, routing/TE, and MANO ops.
Artifacts are stored on disk (named volume) and referenced by path.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, JSON, String, Text

from .base import Base


class MLModel(Base):
    __tablename__ = "ml_model"

    id = Column(String(64), primary_key=True)  # uuid
    task = Column(String(64), nullable=False, index=True)  # anomaly_detection, routing_policy, mano_policy, ...

    name = Column(String(255), nullable=False)
    algorithm = Column(String(128), nullable=True)  # e.g. tranad, gdn, ppo, ewma_zscore
    framework = Column(String(32), nullable=False, default="builtin")  # builtin, onnx, torchscript, ...
    version = Column(String(64), nullable=True)
    description = Column(Text, nullable=True)

    artifact_path = Column(Text, nullable=True)  # absolute path inside container, or null for builtin
    artifact_filename = Column(String(255), nullable=True)
    artifact_sha256 = Column(String(64), nullable=True)
    artifact_size_bytes = Column(Integer, nullable=True)

    input_schema = Column(JSON, nullable=False, default=dict)
    output_schema = Column(JSON, nullable=False, default=dict)
    meta = Column(JSON, nullable=False, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MLModelAssignment(Base):
    __tablename__ = "ml_model_assignment"

    task = Column(String(64), primary_key=True)
    model_id = Column(String(64), nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
