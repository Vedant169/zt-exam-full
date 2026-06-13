from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import json, hashlib, secrets
import os

from .database import Base, engine, get_db
from . import models, schemas, auth, crypto_vault, compiler

Base.metadata.create_all(bind=engine)

# Auto-seed database on startup if empty
def init_db():
    db = next(get_db())
    try:
        # Check if users exist
        user_count = db.query(models.User).count()
        if user_count == 0:
            # Seed test users
            from . import auth
            test_users = [
                ("admin@zt.local", "admin123", "Admin User", "admin"),
                ("teacher@zt.local", "teacher123", "Teacher User", "teacher"),
                ("student@zt.local", "student123", "Student User", "student"),
            ]
            for email, password, name, role in test_users:
                user = models.User(
                    email=email,
                    password_hash=auth.get_password_hash(password),
                    full_name=name,
                    role=role,
                    a11y_profile="standard"
                )
                db.add(user)
            db.commit()
            print(f"✅ Seeded {len(test_users)} test users")
    except Exception as e:
        print(f"⚠️ Database init error: {e}")
    finally:
        db.close()

init_db()

app = FastAPI(title="ZT-EXAM API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ---------- Auth ----------
@app.post("/api/auth/register", response_model=schemas.Token)
def register(inp: schemas.RegisterIn, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == inp.email).first():
        raise HTTPException(400, "Email exists")
    if inp.role not in ("admin","teacher","student"):
        raise HTTPException(400, "bad role")
    u = models.User(
        email=inp.email,
        password_hash=auth.get_password_hash(inp.password),
        full_name=inp.full_name,
        role=inp.role,
        a11y_profile=inp.a11y_profile or "standard"
    )
    db.add(u); db.commit(); db.refresh(u)
    token = auth.create_access_token({"sub": u.email, "role": u.role})
    return {"access_token": token, "role": u.role, "full_name": u.full_name}

@app.post("/api/auth/login", response_model=schemas.Token)
def login(inp: schemas.LoginIn, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == inp.email).first()
    if not user or not auth.verify_password(inp.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    token = auth.create_access_token({"sub": user.email, "role": user.role})
    return {"access_token": token, "role": user.role, "full_name": user.full_name}

# ---------- Teacher ----------
@app.post("/api/teacher/questions/bulk")
def teacher_bulk(inp: schemas.BulkQuestionsIn, user: models.User = Depends(auth.require_role("teacher","admin")), db: Session = Depends(get_db)):
    created = []
    # get last custody tx
    last = db.query(models.CustodyLedger).order_by(models.CustodyLedger.id.desc()).first()
    prev_tx = last.tx_hash if last else "0xgenesis"
    for q in inp.questions:
        content = q.text + "".join(q.options)
        cid = crypto_vault.mock_ipfs_cid(content)
        tx = crypto_vault.custody_tx(prev_tx, "SUBMIT", cid)
        prev_tx = tx
        qid = f"Q-{secrets.token_hex(3).upper()}"
        row = models.Question(
            qid=qid,
            subject=q.subject,
            difficulty=q.difficulty,
            text=q.text,
            options_json=json.dumps(q.options),
            answer_index=q.answer_index,
            author_id=user.id,
            ipfs_cid=cid,
            custody_tx=tx
        )
        db.add(row)
        db.flush()
        created.append(qid)
        db.add(models.CustodyLedger(tx_hash=tx, action="SUBMIT", details=f"{qid} by {user.email}"))
    db.commit()
    return {"created": created, "count": len(created)}

@app.get("/api/teacher/questions/mine")
def teacher_mine(user: models.User = Depends(auth.require_role("teacher","admin")), db: Session = Depends(get_db)):
    qs = db.query(models.Question).filter(models.Question.author_id == user.id).order_by(models.Question.id.desc()).limit(500).all()
    return [{"qid": q.qid, "subject": q.subject, "difficulty": q.difficulty, "text": q.text, "cid": q.ipfs_cid, "tx": q.custody_tx} for q in qs]

# ---------- Admin ----------
@app.get("/api/admin/vault/stats")
def admin_vault_stats(user: models.User = Depends(auth.require_role("admin")), db: Session = Depends(get_db)):
    total = db.query(models.Question).count()
    return {"vault_size": total, "shards": total*3 + 847, "cycle": "NTA-2026-S1"}

@app.get("/api/admin/vault/questions")
def admin_vault_questions(user: models.User = Depends(auth.require_role("admin")), db: Session = Depends(get_db)):
    qs = db.query(models.Question).order_by(models.Question.id.desc()).limit(200).all()
    return [{"qid": q.qid, "subject": q.subject, "difficulty": q.difficulty, "cid": q.ipfs_cid, "tx": q.custody_tx} for q in qs]

@app.get("/api/admin/vault/ledger")
def admin_ledger(user: models.User = Depends(auth.require_role("admin")), db: Session = Depends(get_db)):
    rows = db.query(models.CustodyLedger).order_by(models.CustodyLedger.id.desc()).limit(120).all()
    return [{"ts": r.ts.isoformat(), "tx": r.tx_hash, "action": r.action, "details": r.details} for r in rows]

@app.post("/api/admin/compiler/run")
def admin_compile(inp: schemas.CompileIn, user: models.User = Depends(auth.require_role("admin")), db: Session = Depends(get_db)):
    try:
        paper, blob = compiler.compile_paper(db, inp.code, inp.num_questions, inp.key_release_delay_sec, user.id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {
        "code": paper.code,
        "paper_hash": paper.paper_hash,
        "manifest": json.loads(paper.manifest_json),
        "key_release_at": paper.key_release_at.isoformat(),
        "num_questions": inp.num_questions
    }

@app.get("/api/admin/compiler/status")
def compiler_status(code: str = "NTA-2026-S1-PaperA", user: models.User = Depends(auth.require_role("admin","teacher","student")), db: Session = Depends(get_db)):
    paper = db.query(models.ExamPaper).filter(models.ExamPaper.code == code).first()
    if not paper:
        return {"compiled": False}
    now = datetime.utcnow()
    unlocked = now >= paper.key_release_at
    return {
        "compiled": True,
        "code": paper.code,
        "paper_hash": paper.paper_hash,
        "manifest": json.loads(paper.manifest_json),
        "key_release_at": paper.key_release_at.isoformat(),
        "unlocked": unlocked,
        "seconds_left": max(0, int((paper.key_release_at - now).total_seconds()))
    }

@app.post("/api/admin/vdf/unlock")
def admin_vdf_unlock(code: str = "NTA-2026-S1-PaperA", user: models.User = Depends(auth.require_role("admin")), db: Session = Depends(get_db)):
    paper = db.query(models.ExamPaper).filter(models.ExamPaper.code == code).first()
    if not paper: raise HTTPException(404, "no paper")
    paper.key_release_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    return {"unlocked": True}

@app.post("/api/admin/vault/rotate")
def admin_rotate(user: models.User = Depends(auth.require_role("admin")), db: Session = Depends(get_db)):
    count = db.query(models.Question).delete()
    db.add(models.CustodyLedger(tx_hash="0x"+secrets.token_hex(8), action="VAULT_ROTATE", details=f"purged {count} questions"))
    db.commit()
    return {"purged": count}

@app.get("/api/admin/proctor/center-stats")
def center_stats(user: models.User = Depends(auth.require_role("admin","proctor")), db: Session = Depends(get_db)):
    # mock aggregated, in real compute from sessions
    return [
        {"center":"DL-044 Rohini", "candidates":242, "mean_pct":51.2, "p":0.41, "action":"Pass"},
        {"center":"MH-112 Nagpur East", "candidates":188, "mean_pct":53.8, "p":0.18, "action":"Pass"},
        {"center":"RJ-009 Kota North", "candidates":310, "mean_pct":92.7, "p":2.1e-7, "action":"Flag — Manual audit"},
        {"center":"UP-087 Prayagraj", "candidates":176, "mean_pct":49.4, "p":0.63, "action":"Pass"},
    ]

# ---------- Student Exam ----------
@app.post("/api/exam/biometric/verify")
def biometric_verify(inp: schemas.BiometricVerifyIn, user: models.User = Depends(auth.require_role("student")), db: Session = Depends(get_db)):
    paper = db.query(models.ExamPaper).filter(models.ExamPaper.code == inp.paper_code).first()
    if not paper: raise HTTPException(404, "paper not found")
    # find or create session
    sess = db.query(models.ExamSession).filter(models.ExamSession.student_id == user.id, models.ExamSession.paper_code == inp.paper_code).first()
    if not sess:
        sess = models.ExamSession(student_id=user.id, paper_code=inp.paper_code, paper_id=paper.id)
        db.add(sess); db.flush()
    sess.biometric_verified = inp.liveness_pass and inp.face_match_score >= 0.82 and inp.faces_detected == 1
    sess.face_match_score = inp.face_match_score
    sess.liveness_pass = inp.liveness_pass
    if sess.biometric_verified and not sess.started_at:
        sess.started_at = datetime.utcnow()
    db.commit()
    return {"session_id": sess.id, "verified": sess.biometric_verified, "started": bool(sess.started_at)}

@app.get("/api/exam/paper")
def get_paper(code: str, session_id: int, user: models.User = Depends(auth.require_role("student")), db: Session = Depends(get_db)):
    sess = db.query(models.ExamSession).filter(models.ExamSession.id == session_id, models.ExamSession.student_id == user.id).first()
    if not sess or not sess.biometric_verified:
        raise HTTPException(403, "biometric not verified")
    paper = db.query(models.ExamPaper).filter(models.ExamPaper.code == code).first()
    if not paper: raise HTTPException(404, "no paper")
    now = datetime.utcnow()
    if now < paper.key_release_at:
        return {"unlocked": False, "seconds_left": int((paper.key_release_at - now).total_seconds())}
    # Decrypt the JIT-compiled paper
    if paper.encrypted_blob:
        try:
            full = crypto_vault.decrypt_paper(paper.encryption_key, paper.encrypted_blob)
            questions_out = []
            for q in full["questions"]:
                questions_out.append({
                    "subject": q["subject"],
                    "difficulty": q["difficulty"],
                    "text": q["text"],
                    "options": q["options"]
                })
            return {"unlocked": True, "code": code, "questions": questions_out, "session_id": sess.id}
        except Exception:
            pass
    # Fallback: reconstruct from DB
    qids = json.loads(paper.question_ids_json)
    qs = db.query(models.Question).filter(models.Question.id.in_(qids)).all()
    q_map = {q.id: q for q in qs}
    questions = []
    for qid in qids:
        q = q_map.get(qid)
        if not q: continue
        questions.append({
            "subject": q.subject,
            "difficulty": q.difficulty,
            "text": q.text,
            "options": json.loads(q.options_json)
        })
    return {"unlocked": True, "code": code, "questions": questions, "session_id": sess.id}

@app.post("/api/exam/answer")
def save_answer(inp: schemas.AnswerIn, user: models.User = Depends(auth.require_role("student")), db: Session = Depends(get_db)):
    sess = db.query(models.ExamSession).filter(models.ExamSession.id == inp.session_id, models.ExamSession.student_id == user.id).first()
    if not sess: raise HTTPException(404, "session")
    # find correct answer
    paper = db.query(models.ExamPaper).filter(models.ExamPaper.code == sess.paper_code).first()
    qids = json.loads(paper.question_ids_json)
    if inp.question_idx < 0 or inp.question_idx >= len(qids): raise HTTPException(400, "bad idx")
    q = db.query(models.Question).filter(models.Question.id == qids[inp.question_idx]).first()
    is_correct = (inp.chosen == q.answer_index)
    # upsert answer
    ans = db.query(models.Answer).filter(models.Answer.session_id == inp.session_id, models.Answer.question_idx == inp.question_idx).first()
    if ans:
        ans.chosen = inp.chosen; ans.time_ms = inp.time_ms; ans.is_correct = is_correct
    else:
        ans = models.Answer(session_id=inp.session_id, question_idx=inp.question_idx, chosen=inp.chosen, time_ms=inp.time_ms, is_correct=is_correct)
        db.add(ans)
    # heuristic update
    expected_ms = {1:18000,2:38000,3:52000,4:95000,5:145000}.get(q.difficulty, 45000)
    if is_correct and inp.time_ms < expected_ms * 0.22 and q.difficulty >= 4:
        sess.anomaly_score = min(0.97, (sess.anomaly_score or 0.12) + 0.24)
        sess.camera_warnings = (sess.camera_warnings or 0) + 1
    db.commit()
    return {"saved": True, "is_correct": is_correct, "anomaly_score": sess.anomaly_score, "camera_warnings": sess.camera_warnings}

@app.post("/api/exam/proctor_event")
def proctor_event(inp: schemas.ProctorEventIn, user: models.User = Depends(auth.require_role("student")), db: Session = Depends(get_db)):
    sess = db.query(models.ExamSession).filter(models.ExamSession.id == inp.session_id, models.ExamSession.student_id == user.id).first()
    if not sess: raise HTTPException(404, "session")
    ev = models.ProctorEvent(session_id=inp.session_id, event_type=inp.event_type, payload_json=json.dumps(inp.payload), center_code=inp.center_code)
    db.add(ev)
    # simple scoring
    if inp.event_type in ("multi_face","gaze_off","spoof_detect"):
        sess.camera_warnings = (sess.camera_warnings or 0) + 1
        sess.anomaly_score = min(0.97, (sess.anomaly_score or 0.12) + 0.08)
    db.commit()
    return {"ok": True, "anomaly_score": sess.anomaly_score}

@app.post("/api/exam/submit")
def submit_exam(inp: schemas.SubmitIn, user: models.User = Depends(auth.require_role("student")), db: Session = Depends(get_db)):
    sess = db.query(models.ExamSession).filter(models.ExamSession.id == inp.session_id, models.ExamSession.student_id == user.id).first()
    if not sess: raise HTTPException(404, "session")
    sess.submitted_at = datetime.utcnow()
    # sign receipt
    receipt = hashlib.sha3_256(f"{sess.id}{user.email}{sess.submitted_at.isoformat()}".encode()).hexdigest()
    sess.receipt_tx = "0x" + receipt[:16]
    db.commit()
    # compute score
    correct = db.query(models.Answer).filter(models.Answer.session_id == sess.id, models.Answer.is_correct == True).count()
    total = db.query(models.Answer).filter(models.Answer.session_id == sess.id).count()
    return {"submitted": True, "receipt_tx": sess.receipt_tx, "score": correct, "answered": total, "anomaly_score": sess.anomaly_score}

@app.get("/api/exam/session/{session_id}")
def get_session(session_id: int, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    sess = db.query(models.ExamSession).filter(models.ExamSession.id == session_id).first()
    if not sess: raise HTTPException(404, "no")
    if user.role == "student" and sess.student_id != user.id: raise HTTPException(403, "forbidden")
    return {
        "session_id": sess.id,
        "anomaly_score": sess.anomaly_score,
        "camera_warnings": sess.camera_warnings,
        "biometric_verified": sess.biometric_verified,
        "submitted_at": sess.submitted_at.isoformat() if sess.submitted_at else None,
        "receipt_tx": sess.receipt_tx
    }

# ---------- Proctor Live WebRTC Signaling ----------
# Simple in-memory SFU-style signaling relay.
# Clients join /ws/proctor/{room_id}?peer=NAME&role=proctor|student
# Messages: {type:"join"|"offer"|"answer"|"ice"|"bye", from, to, sdp, candidate}
proctor_rooms: dict[str, dict[str, WebSocket]] = {}

@app.websocket("/ws/proctor/{room_id}")
async def proctor_ws(websocket: WebSocket, room_id: str):
    await websocket.accept()
    peer_id = None
    try:
        # first message must be join
        init = await websocket.receive_text()
        try:
            msg = json.loads(init)
        except:
            await websocket.close(); return
        peer_id = msg.get("peer") or secrets.token_hex(4)
        role = msg.get("role", "student")
        if room_id not in proctor_rooms:
            proctor_rooms[room_id] = {}
        proctor_rooms[room_id][peer_id] = websocket
        # notify others
        for pid, ws in list(proctor_rooms[room_id].items()):
            if pid == peer_id: continue
            try:
                await ws.send_text(json.dumps({"type":"peer_join", "peer": peer_id, "role": role}))
                await websocket.send_text(json.dumps({"type":"peer_join", "peer": pid, "role": "unknown"}))
            except: pass
        # relay loop
        while True:
            data = await websocket.receive_text()
            try:
                m = json.loads(data)
            except:
                continue
            target = m.get("to")
            # broadcast if no target
            targets = []
            if target and target in proctor_rooms.get(room_id, {}):
                targets = [target]
            else:
                targets = [p for p in proctor_rooms.get(room_id, {}).keys() if p != peer_id]
            m["from"] = peer_id
            out = json.dumps(m)
            for t in targets:
                ws = proctor_rooms[room_id].get(t)
                if ws:
                    try: await ws.send_text(out)
                    except: pass
    except WebSocketDisconnect:
        pass
    finally:
        if room_id in proctor_rooms and peer_id in proctor_rooms[room_id]:
            del proctor_rooms[room_id][peer_id]
            # notify peers
            for ws in list(proctor_rooms[room_id].values()):
                try: await ws.send_text(json.dumps({"type":"peer_leave", "peer": peer_id}))
                except: pass
            if not proctor_rooms[room_id]:
                del proctor_rooms[room_id]

@app.get("/api/proctor/sessions")
def proctor_sessions(user: models.User = Depends(auth.require_role("admin","proctor","teacher")), db: Session = Depends(get_db)):
    rows = db.query(models.ExamSession).order_by(models.ExamSession.id.desc()).limit(80).all()
    out = []
    for s in rows:
        stu = db.query(models.User).filter(models.User.id == s.student_id).first()
        out.append({
            "session_id": s.id,
            "student": stu.email if stu else "?",
            "paper_code": s.paper_code,
            "anomaly": s.anomaly_score,
            "warnings": s.camera_warnings,
            "verified": s.biometric_verified,
            "submitted": bool(s.submitted_at)
        })
    return out

# ========== STATIC FILE SERVING FOR SPA ==========
# Serve frontend static files and index.html for all non-API routes
frontend_dir = os.path.join(os.path.dirname(__file__), "../../frontend")
index_file = os.path.join(frontend_dir, "index.html")

# Root path - serve index.html for SPA
@app.get("/", include_in_schema=False)
async def serve_root():
    if os.path.exists(index_file):
        return FileResponse(index_file, media_type="text/html")
    return {"ok": True, "name": "ZT-EXAM API"}

# Catch-all route: serve index.html for SPA routing (all other paths)
@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str):
    # Don't interfere with API routes, WebSocket, or docs
    if any(full_path.startswith(p) for p in ["api/", "ws/", "docs", "redoc", "openapi"]):
        raise HTTPException(status_code=404)
    
    # Serve index.html for all other routes (SPA routing)
    if os.path.exists(index_file):
        return FileResponse(index_file, media_type="text/html")
    raise HTTPException(status_code=404, detail="Frontend not found")

# Mount static files (CSS, JS, images, etc.) - after catch-all
if os.path.isdir(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

# ========== DEPLOYMENT EXPORTS ==========
# For Vercel / serverless: the ASGI app is exposed at module level (above)
# For local development with uvicorn:
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
