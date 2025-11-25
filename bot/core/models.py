from sqlalchemy import Column, Integer, BigInteger, String, Boolean, Float, Text, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    __tablename__ = "users"


    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    first_seen = Column(DateTime(timezone=True), server_default=func.now())

class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content_type = Column(String(10), nullable=False)
    raw_content = Column(Text, nullable=True)
    confirmed = Column(Boolean, default=True)  # всегда True при сохранении
    suspicious = Column(Boolean, default=False)
    reviewed_by_expert = Column(Boolean, default=False)
    ai_response = Column(Text, nullable=True)
    final_response = Column(Text, nullable=True)
    ai_confidence = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(content_type.in_(["text", "image", "pdf"]), name="valid_content_type"),
    )