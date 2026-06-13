from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String)  # admin | teacher | student
    full_name = Column(String)
    a11y_profile = Column(String, default="standard")
    created_at = Column(DateTime, default=datetime.utcnow)

class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True)
    qid = Column(String, unique=True, index=True)
    subject = Column(String)
    difficulty = Column(Integer)
    text = Column(Text)
    options_json = Column(Text)  # JSON list
    answer_index = Column(Integer)
    author_id = Column(Integer, ForeignKey("users.id"))
    ipfs_cid = Column(String)
    custody_tx = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    vault_cycle = Column(String, default="NTA-2026-S1")

class ExamPaper(Base):
    __tablename__ = "exam_papers"
    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, index=True)
    manifest_json = Column(Text)
    paper_hash = Column(String)
    question_ids_json = Column(Text)
    encrypted_blob = Column(Text)  # Fernet encrypted paper JSON
    compiled_at = Column(DateTime, default=datetime.utcnow)
    key_release_at = Column(DateTime)
    encryption_key = Column(String)  # base64 fernet key, in real life in HSM
    compiled_by = Column(Integer, ForeignKey("users.id"))

class ExamSession(Base):
    __tablename__ = "exam_sessions"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id"))
    paper_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    paper_code = Column(String)
    biometric_verified = Column(Boolean, default=False)
    face_match_score = Column(Float, nullable=True)
    liveness_pass = Column(Boolean, default=False)
    started_at = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    anomaly_score = Column(Float, default=0.12)
    camera_warnings = Column(Integer, default=0)
    receipt_tx = Column(String, nullable=True)

class Answer(Base):
    __tablename__ = "answers"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("exam_sessions.id"))
    question_idx = Column(Integer)
    chosen = Column(Integer, nullable=True)
    time_ms = Column(Integer)
    is_correct = Column(Boolean, default=False)

class ProctorEvent(Base):
    __tablename__ = "proctor_events"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("exam_sessions.id"))
    event_type = Column(String)
    payload_json = Column(Text)
    ts = Column(DateTime, default=datetime.utcnow)
    center_code = Column(String, default="DL-044")

class CustodyLedger(Base):
    __tablename__ = "custody_ledger"
    id = Column(Integer, primary_key=True)
    tx_hash = Column(String)
    action = Column(String)
    details = Column(Text)
    ts = Column(DateTime, default=datetime.utcnow)
