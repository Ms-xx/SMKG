from sqlalchemy import JSON, Column, DateTime, Integer, String, UniqueConstraint, func

from app.models.base import Base, generate_uuid


class RecommendRecord(Base):
    """推荐记录：一次生成的推荐结果快照（可回溯排序构成与理由）。"""

    __tablename__ = "recommend_records"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), nullable=False, index=True)
    title = Column(String(512), nullable=False)
    correlation_score = Column(Integer, nullable=False, default=0)
    reproducibility_score = Column(Integer, nullable=False, default=0)
    feedback_score = Column(Integer, nullable=False, default=0)
    total_score = Column(Integer, nullable=False, default=0)
    repos = Column(JSON, default=list)  # [{repo, star_count, license, source, ...}]
    reason = Column(String(1000))
    backend = Column(String(20), nullable=False, default="builtin")
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class RecommendFeedback(Base):
    """点赞/踩互动：用户对某个开源仓库的可复现性反馈，参与后续推荐排序。"""

    __tablename__ = "recommend_feedback"
    __table_args__ = (UniqueConstraint("user_id", "repo", name="uq_rec_feedback_user_repo"),)

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), nullable=False)
    record_id = Column(String(36), index=True)
    repo = Column(String(300), nullable=False)  # owner/repo
    sentiment = Column(String(10), nullable=False)  # like | dislike
    comment = Column(String(500))
    created_at = Column(DateTime, nullable=False, server_default=func.now())
