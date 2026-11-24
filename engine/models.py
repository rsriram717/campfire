"""Engine-only SQLAlchemy models.

We store IDs, tags, outcomes and predictions. No Google-derived content is
stored: no names, addresses, ratings, hours or review text.
"""
from datetime import datetime

from sqlalchemy import (Boolean, CheckConstraint, Column, DateTime, Float,
                        ForeignKey, Integer, LargeBinary, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import declarative_base

# Own metadata: never shared with the legacy app's `db`.
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    external_id = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Restaurant(Base):
    """Place ID only. Hashes detect website changes."""
    __tablename__ = "restaurants"
    place_id = Column(String(255), primary_key=True)
    website_url_hash = Column(String(64))
    website_content_hash = Column(String(64))
    tags_extracted_at = Column(DateTime)
    extraction_status = Column(String(16), default="none", nullable=False)
    __table_args__ = (
        CheckConstraint(
            "extraction_status IN ('none','pending','done','failed','no_website')",
            name="ck_restaurants_extraction_status"),
    )


class Tag(Base):
    """One row per distinct tag text (lowercased, trimmed). No merging:
    embeddings handle similarity at scoring time."""
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True)
    text = Column(String(255), unique=True, nullable=False)
    embedding = Column(LargeBinary)  # float32 blob; pgvector in Phase 8
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class RestaurantTag(Base):
    """Descriptive only: what the place *is*. Ratings never write here."""
    __tablename__ = "restaurant_tags"
    place_id = Column(String(255), ForeignKey("restaurants.place_id"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), primary_key=True)
    source = Column(String(16), primary_key=True)  # website | user | agent
    count = Column(Integer, default=1, nullable=False)
    first_seen = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen = Column(DateTime, default=datetime.utcnow, nullable=False)


class UserTag(Base):
    """Signed weight: positive = likes, negative = dislikes."""
    __tablename__ = "user_tags"
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), primary_key=True)
    weight = Column(Float, default=0.0, nullable=False)
    evidence_count = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Request(Base):
    """One per discover or score_candidates call."""
    __tablename__ = "requests"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    lat = Column(Float)
    lng = Column(Float)
    request_text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Outcome(Base):
    """Match data: feeds the user profile and the people signal."""
    __tablename__ = "outcomes"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    place_id = Column(String(255), ForeignKey("restaurants.place_id"), nullable=False)
    verdict = Column(String(16), nullable=False)  # loved | meh | disliked
    request_id = Column(Integer, ForeignKey("requests.id"))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (
        CheckConstraint("verdict IN ('loved','meh','disliked')",
                        name="ck_outcomes_verdict"),
    )


class OutcomeTag(Base):
    """Descriptive tags given at feedback time, e.g. "loud"."""
    __tablename__ = "outcome_tags"
    outcome_id = Column(Integer, ForeignKey("outcomes.id"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), primary_key=True)


class Prediction(Base):
    """Logged so text-prediction error can be measured against outcomes."""
    __tablename__ = "predictions"
    request_id = Column(Integer, ForeignKey("requests.id"), primary_key=True)
    place_id = Column(String(255), ForeignKey("restaurants.place_id"), primary_key=True)
    query_bucket = Column(String(255))
    text_score = Column(Float)
    text_var = Column(Float)
    people_score = Column(Float)
    people_var = Column(Float)
    n_raters = Column(Integer, default=0)
    final_score = Column(Float)
    returned = Column(Boolean, default=False, nullable=False)


class ExtractionQueue(Base):
    """Tag extraction that didn't fit the latency budget."""
    __tablename__ = "extraction_queue"
    place_id = Column(String(255), ForeignKey("restaurants.place_id"), primary_key=True)
    enqueued_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    last_error = Column(Text)
