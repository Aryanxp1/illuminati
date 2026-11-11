from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone
from .config import settings

DATABASE_URL = f"sqlite:///{settings.DATABASE_PATH}"

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------- Unified Platform Database Models -----------------

class FreshnessCheckRecord(Base):
    __tablename__ = "freshness_checks"
    id = Column(String, primary_key=True, index=True)
    mode = Column(String, default="check") # check or ask
    query = Column(Text, nullable=True)
    answer = Column(Text, nullable=False)
    freshness_score = Column(Integer, default=100)
    verdict_label = Column(String, default="fresh") # fresh, review, stale, unverified
    claims_total = Column(Integer, default=0)
    claims_stale = Column(Integer, default=0)
    corrected_answer = Column(Text, nullable=True)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class MeetingBriefRecord(Base):
    __tablename__ = "meeting_briefs"
    id = Column(String, primary_key=True, index=True)
    target_name = Column(String, nullable=False)
    target_type = Column(String, default="company") # company or person
    meeting_time = Column(String, nullable=False)
    purpose = Column(String, default="sales")
    summary = Column(Text, nullable=True)
    verified_stories_count = Column(Integer, default=0)
    rejected_stories_count = Column(Integer, default=0)
    full_brief_json = Column(Text, nullable=True)
    markdown_content = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class CodingTaskRecord(Base):
    __tablename__ = "coding_tasks"
    id = Column(String, primary_key=True, index=True)
    prompt = Column(Text, nullable=False)
    status = Column(String, default="completed")
    tokens_input = Column(Integer, default=0)
    tokens_output = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    receipt_hash = Column(String, nullable=True)
    result_text = Column(Text, nullable=True)
    diff_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

def init_db():
    Base.metadata.create_all(bind=engine)
    try:
        from arena_db import Base as ArenaBase, engine as arena_engine
        import models
        ArenaBase.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Error initializing arena tables: {e}")
