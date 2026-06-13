# ZT-EXAM — Zero-Trust Decentralized Examination System
Full-stack working model

Backend: FastAPI + SQLAlchemy (SQLite) + JWT
Frontend: Single-file SPA, vanilla JS, real webcam FaceDetector

## Features — all 6 Phases

**Phase 1 — Decentralized Question Vault**
- Teacher Panel uploads questions → IPFS CID mock, custody_tx hash-chain, blinded submissions
- Admin vault explorer, blockchain ledger, annual rotate/purge

**Phase 2 — JIT AI Compiler**
- Admin-only `POST /api/admin/compiler/run`
- Stratified sampling, Dirichlet-style weights, paper_hash = SHA3-256
- Paper encrypted with Fernet (AES-128-CBC + HMAC), key time-locked
- VDF countdown, admin force-unlock

**Phase 3 — Zero-Trust Transmission**
- Encrypted paper delivered direct-to-terminal, bypass center LAN
- Decryption key only released after biometric + VDF

**Phase 4 — Edge Endpoint Security**
- Student terminal: on-device FaceDetector (Chrome/Edge native)
- Face match, multi-face detection, active liveness challenge
- All CV stays local, only scores posted

**Phase 5 — Psychometric Behavioral Heuristics**
- Item-time latency tracking per question
- Impossible-speed trap: correct high-difficulty in <22% expected time → anomaly + camera_warning
- Composite scoring: anomaly_score + camera_warnings → Clean / Watch / Hold

**Phase 6 — Failsafes & A11y**
- a11y_profile on User: standard / adhd / motor / visual / anxiety
- Statistical center anomaly API (Benjamini-Hochberg mock)
- Proctor live session dashboard

---

## Quick start

### 1. Backend
```bash
cd zt-exam-full/backend
pip install -r requirements.txt
python seed.py   # creates DB + 3 accounts + 120 questions
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
API at http://localhost:8000/docs

Seeded accounts:
- admin:   admin@zt.local / admin123
- teacher: teacher@zt.local / teacher123
- student: student@zt.local / student123

### 2. Frontend
Open `zt-exam-full/frontend/index.html` in a real browser (Chrome/Edge).
File:// works, but for camera use http://localhost serve:
```bash
cd zt-exam-full/frontend
python -m http.server 5173
# open http://localhost:5173
```

Login with the accounts above. Role switches the UI automatically.

---

## Role flows

**Teacher**
1. Login → Teacher — Upload
2. Paste JSON array of questions → Upload to Vault
3. My Questions tab shows CID + custody_tx

**Admin**
1. Login → Vault: see 120 questions, ledger, rotate
2. JIT Compiler → Run Compiler (default 50 Q, 60s unlock)
3. Time-Lock Status → Force Unlock if you want instant
4. Proctor → Center Stats + Live Sessions

**Student**
1. Login → Exam Terminal
2. Enable Camera → Run Liveness → Verify & Decrypt Paper
   - Paper must be compiled + VDF unlocked by admin first
   - Biometric: face_match >=0.82, liveness_pass=true
3. Answer questions — latency tracked, anomalies posted live
4. Submit & Sign → receipt_tx (SHA3)

API auth: `Authorization: Bearer <jwt>`, role enforced server-side.

---

## API cheatsheet

- POST /api/auth/login
- POST /api/auth/register
- POST /api/teacher/questions/bulk  (teacher/admin)
- GET  /api/teacher/questions/mine
- GET  /api/admin/vault/stats|questions|ledger  (admin)
- POST /api/admin/compiler/run  (admin)
- GET  /api/admin/compiler/status
- POST /api/admin/vdf/unlock  (admin)
- POST /api/exam/biometric/verify  (student)
- GET  /api/exam/paper?code=&session_id=  (student, locked until biometric + VDF)
- POST /api/exam/answer
- POST /api/exam/proctor_event
- POST /api/exam/submit
- GET  /api/proctor/sessions  (admin)

---

## Production hardening notes
- Replace Fernet key storage with HSM/KMS, per-terminal key wrapping
- Replace mock IPFS / custody_tx with real IPFS + Tendermint / Cosmos SDK
- Replace time-lock delay with drand VDF / VRF
- Move FaceDetector to ONNX/TFLite with liveness anti-spoof model
- Postgres, rate-limiting, audit log immutability, hardware kiosk (Electron Tauri)
- ECDSA receipt signing on TPM

MIT — demo / research build.
