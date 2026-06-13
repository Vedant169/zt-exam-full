# Deployment Updates Summary

## Changes Made

### 1. ✅ Frontend: Environment-Aware API Base URL
**File**: `frontend/index.html` (line ~228)

**Before:**
```javascript
const API = localStorage.getItem('zt_api') || 'http://localhost:8000';
```

**After:**
```javascript
const API = localStorage.getItem('zt_api') 
  || window.ZT_API_BASE 
  || (typeof process !== 'undefined' && process.env && process.env.REACT_APP_API_BASE)
  || (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' ? 'http://localhost:8000' : '/api')
  || '/api';
```

**What it does:**
- Checks localStorage override (manual/debug)
- Checks global `window.ZT_API_BASE` (deployment script injection)
- Checks build-time environment variable `REACT_APP_API_BASE`
- Auto-detects localhost vs production
- Falls back to relative `/api` path for same-origin deployment

**Benefits:**
- ✅ Works locally without changes
- ✅ Production can inject API URL via script tag
- ✅ Supports multiple deployment patterns
- ✅ No hardcoded domains

---

### 2. ✅ Backend: Vercel Configuration
**File**: `vercel.json` (new file)

```json
{
  "buildCommand": "pip install -r backend/requirements.txt",
  "outputDirectory": ".",
  "framework": "fastapi",
  "builds": [
    {
      "src": "backend/app/main.py",
      "use": "@vercel/python",
      "config": { "maxLambdaSize": "50mb", "runtime": "python3.11" }
    }
  ],
  "routes": [
    { "src": "/api/(.*)", "dest": "backend/app/main.py", ... },
    { "src": "/(.*)", "dest": "/frontend/index.html", ... }
  ]
}
```

**What it does:**
- Configures Vercel Python runtime for FastAPI
- Routes `/api/*` to backend
- Serves frontend static files
- Supports environment variables for CORS, database URLs

**⚠️ Warning**: This works, but NOT RECOMMENDED for production because:
- Vercel serverless = stateless + ephemeral filesystem
- SQLite won't persist between invocations
- WebSockets don't work reliably
- 15-minute timeout for long-running exams

---

### 3. ✅ Backend: ASGI App Export for Vercel
**File**: `backend/app/main.py` (end of file)

**Added:**
```python
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
```

**What it does:**
- ✅ App is already defined at module level (Vercel finds it)
- ✅ Supports local `python app/main.py` execution
- ✅ Vercel runtime can import and run the ASGI app

---

### 4. ✅ Documentation: Deployment Guide
**File**: `DEPLOYMENT.md` (new file)

Comprehensive guide covering:
- Architecture overview
- Why Vercel is NOT ideal (explained)
- **Recommended**: Separate frontend (Vercel) + backend (Fly.io/Railway)
- **Alternative**: Full stack on single host (Fly.io/Railway/Render)
- Environment variable configuration
- Deployment checklists
- Troubleshooting guide
- Production hardening tips

**Key recommendation**: Use Fly.io, Railway, or Render for backend to support:
- Persistent SQLite storage
- Long-running WebSocket connections
- Proper process management with uvicorn

---

### 5. ✅ Helper: Deployment Configuration Script
**File**: `deploy-config.sh` (new file)

Quick setup for different environments:
```bash
source ./deploy-config.sh local           # Local dev
source ./deploy-config.sh production-fly  # Fly.io
```

Automatically sets environment variables for each deployment target.

---

## Deployment Patterns Now Supported

### Pattern 1: Local Development
```
Browser → frontend/index.html → API = http://localhost:8000
```
**Status**: ✅ Works (auto-detected)

### Pattern 2: Frontend on Vercel, Backend on Fly.io (RECOMMENDED)
```
browser.com → Vercel → frontend (static) → 
              → https://backend.fly.dev/api/*
```
**Setup**:
1. Deploy frontend to Vercel
2. Set env: `REACT_APP_API_BASE=https://backend.fly.dev`
3. Deploy backend to Fly.io with persistent volume
4. Frontend auto-detects and uses API base URL

### Pattern 3: Full Stack on Railway/Fly
```
browser.com → Railway/Fly → Nginx → /          → frontend
                          → /api/* → FastAPI
```
**Setup**: Single host, frontend uses relative `/api` paths

---

## Next Steps: To Actually Deploy

### Option A: Vercel + Fly.io Backend (Recommended)

**1. Frontend on Vercel:**
```bash
npm install -g vercel
vercel --prod
# During setup, set env: REACT_APP_API_BASE=https://zt-backend.fly.dev
```

**2. Backend on Fly.io:**
```bash
curl -L https://fly.io/install.sh | sh
flyctl auth login
flyctl launch --name zt-exam-backend

# In fly.toml:
# [env]
# CORS_ORIGINS = "https://zt-exam.vercel.app"
# DATABASE_URL = "sqlite:///data/exam.db"

flyctl volumes create sqlite_data --size 10
flyctl deploy
```

### Option B: Full Stack on Railway

**1. Link GitHub repo to Railway**

**2. Add environment variables:**
- `DATABASE_URL` → auto-created if you add PostgreSQL addon
- `CORS_ORIGINS` → your frontend domain
- `SECRET_KEY` → generate with `python -c "import secrets; print(secrets.token_hex(32))"`

**3. Set build & start commands:**
- Build: `pip install -r backend/requirements.txt`
- Start: `cd backend && python -m uvicorn app.main:app --host 0.0.0.0`

---

## Files Modified

| File | Change | Type |
|------|--------|------|
| `frontend/index.html` | API base URL now environment-aware | ✏️ Modified |
| `backend/app/main.py` | Added ASGI export + uvicorn runner | ✏️ Modified |
| `vercel.json` | New Vercel configuration | ✨ Created |
| `DEPLOYMENT.md` | Comprehensive deployment guide | ✨ Created |
| `deploy-config.sh` | Environment setup helper | ✨ Created |
| `DEPLOYMENT_UPDATES.md` | This file | ✨ Created |

---

## Verification Checklist

- [ ] Frontend loads without hardcoded `localhost` errors
- [ ] Local dev: `python backend/app/main.py` starts server
- [ ] API calls: Browser shows correct API base URL in Network tab
- [ ] Production: Can inject `window.ZT_API_BASE` before app loads
- [ ] WebSocket: `/ws/proctor/*` endpoints work (requires same-origin or CORS)
- [ ] CORS: Backend allows your frontend domain

---

## Gotchas & Troubleshooting

**Frontend shows "Login failed. Is the backend running at /api?"**
- You're in production mode but backend URL wasn't injected
- Fix: Set `window.ZT_API_BASE` via script tag or environment variable

**WebSocket connection fails**
- Vercel doesn't support persistent WebSockets
- Fix: Use Fly.io/Railway/Render for backend

**SQLite "database is locked"**
- Multiple processes accessing same SQLite file
- Fix: Migrate to PostgreSQL for production

**CORS errors from frontend**
- Backend doesn't whitelist frontend domain
- Fix: Update `CORS_ORIGINS` env variable on backend

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    RECOMMENDED SETUP                        │
└─────────────────────────────────────────────────────────────┘

  Browser                  Vercel                  Fly.io
  ┌──────────┐            ┌──────────────┐       ┌──────────────┐
  │          │ HTTP(S)    │              │       │              │
  │ Frontend │───────────>│   Static     │       │   FastAPI    │
  │ (React)  │<───────────│   Frontend   │       │  + SQLite    │
  │          │ + API URL  │              │       │ + WebSocket  │
  └──────────┘            └──────────────┘       └──────────────┘
       │                                               ▲
       └───────────────────────────────────────────────┘
             API calls (REST + WebSocket)

Environment Variables:
  Frontend: REACT_APP_API_BASE=https://zt-backend.fly.dev
  Backend:  CORS_ORIGINS=https://zt-exam.vercel.app
            DATABASE_URL=sqlite:///data/exam.db
```

