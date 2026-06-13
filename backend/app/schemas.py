from pydantic import BaseModel, EmailStr
from typing import List, Optional, Any
from datetime import datetime

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str

class LoginIn(BaseModel):
    email: str
    password: str

class RegisterIn(BaseModel):
    email: str
    password: str
    full_name: str
    role: str  # admin | teacher | student
    a11y_profile: Optional[str] = "standard"

class QuestionIn(BaseModel):
    subject: str
    difficulty: int
    text: str
    options: List[str]
    answer_index: int

class BulkQuestionsIn(BaseModel):
    questions: List[QuestionIn]

class CompileIn(BaseModel):
    code: str = "NTA-2026-S1-PaperA"
    num_questions: int = 50
    key_release_delay_sec: int = 60  # demo: 60s = 60min in prod

class BiometricVerifyIn(BaseModel):
    paper_code: str
    face_match_score: float
    liveness_pass: bool
    faces_detected: int = 1

class AnswerIn(BaseModel):
    session_id: int
    question_idx: int
    chosen: int
    time_ms: int

class ProctorEventIn(BaseModel):
    session_id: int
    event_type: str
    payload: Any = None
    center_code: str = "DL-044"

class SubmitIn(BaseModel):
    session_id: int
