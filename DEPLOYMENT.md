# ZT-EXAM Deployment Guide

## Architecture Overview

This project uses:
- **Frontend**: Static HTML/JS single-page app (can run on CDN or any static host)
- **Backend**: FastAPI Python application (ASGI-compatible)
- **Database**: SQLite (requires persistent filesystem)
- **Real-time**: WebSockets for live proctoring (requires long-lived connections)
- **Media**: Webcam access (browser-based, client-side)

## ⚠️ Important: Vercel Limitations

**Vercel's serverless model is NOT ideal for this project** because:

1. **Stateless functions**: Vercel runs ephemeral functions with no persistent state between requests
2. **Ephemeral filesystem**: `/tmp` is wiped after function execution → SQLite data is lost
3. **15-minute timeout**: Long-running proctor sessions will timeout
4. **No WebSocket persistence**: Complex WebSocket management across function invocations
5. **No file attachments**: Can't store uploaded proctor video/biometric data

## Recommended Deployment Strategy

### Option 1: Backend on Fly.io / Railway / Render (Recommended for Production)

Best for this use case:

```
┌─────────────────────────────────────────────────┐
│  Vercel                                         │
│  └─ Frontend (static HTML/JS)                   │
│     points to backend API URL                   │
└─────────────────────────────────────────────────┘
                      ↓ API calls
┌─────────────────────────────────────────────────┐
│  Fly.io / Railway / Render                      │
│  ├─ FastAPI app (uvicorn process)               │
│  ├─ SQLite database (persistent volume)         │
│  └─ WebSocket support (TCP connections)         │
└─────────────────────────────────────────────────┘
```

**Setup:**

1. **Frontend on Vercel:**
   - Deploy the `frontend/index.html` folder
   - Set environment variable or inject script:
     ```html
     <script>window.ZT_API_BASE = 'https://zt-backend.fly.dev'</script>
     ```
   - Or use a `vercel.json` that redirects `/api/*` calls

2. **Backend on Fly.io (example):**
   ```bash
   flyctl launch --name zt-exam-backend
   ```
   Create `fly.toml`:
   ```toml
   [env]
   CORS_ORIGINS = "https://zt-exam.vercel.app,https://yourdomain.com"
   DATABASE_URL = "sqlite:///data/exam.db"
   
   [mounts]
   source = "sqlite_data"
   destination = "/data"
   ```

3. **Update frontend to point to backend:**
   - Frontend automatically uses `/api` on same-origin (for local dev)
   - For production: set `ZT_API_BASE` environment variable before deployment

### Option 2: Full Stack on Single VPS (Railway/Render/Fly)

Deploy both frontend and backend together on a single persistent instance:

```
┌──────────────────────────────────────┐
│  Fly.io / Railway / Render           │
│  ├─ Nginx (reverse proxy)            │
│  │  ├─ /                  → frontend  │
│  │  └─ /api/*             → backend   │
│  ├─ FastAPI (uvicorn)                │
│  └─ SQLite (persistent volume)       │
└──────────────────────────────────────┘
```

**Advantages:**
- No CORS headaches
- Frontend can use relative `/api` paths
- Single database, single process
- Easier debugging

**Deploy on Railway:**
1. Link your GitHub repo
2. Railway auto-detects `requirements.txt` and Python
3. Set build command: `pip install -r backend/requirements.txt`
4. Set start command: `cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
5. Add volume for SQLite persistence

### Option 3: Local Development

```bash
# Terminal 1: Backend
cd backend
pip install -r requirements.txt
python seed.py  # populate test data
python -m uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend
# Just open frontend/index.html in browser
# or serve with: python -m http.server 5000 -d frontend
```

Frontend will auto-detect local dev and use `http://localhost:8000`.

## Environment Variables

### Frontend Configuration

Set ONE of these (in order of precedence):

1. **localStorage** (user/debug):
   ```javascript
   localStorage.setItem('zt_api', 'https://api.example.com');
   ```

2. **Global window variable** (deployment script):
   ```html
   <script>window.ZT_API_BASE = 'https://api.example.com'</script>
   ```

3. **Build-time env** (build tools):
   ```bash
   REACT_APP_API_BASE=https://api.example.com npm build
   ```

4. **Auto-detect**:
   - Local dev (localhost): `http://localhost:8000`
   - Production: relative `/api` path (same-origin)

### Backend Configuration

Create `.env` file or set environment variables:

```env
# Database
DATABASE_URL=sqlite:///./exam.db
# or for production
DATABASE_URL=postgresql://user:pass@host/dbname

# CORS
CORS_ORIGINS=https://zt-exam.vercel.app,https://example.com,http://localhost:3000

# JWT
SECRET_KEY=your-secret-key-here

# Logging
LOG_LEVEL=info
```

## Deployment Checklist

### Before Production:

- [ ] Database: Migrate from SQLite to PostgreSQL (Vercel-friendly)
- [ ] Authentication: Implement proper JWT refresh token rotation
- [ ] CORS: Set `CORS_ORIGINS` to your actual frontend domain(s)
- [ ] Secrets: Rotate `SECRET_KEY` in `auth.py`
- [ ] WebSocket: Test live proctoring with timeout/reconnection logic
- [ ] Monitoring: Add logging/error tracking (Sentry, etc.)
- [ ] Rate limiting: Add to prevent API abuse
- [ ] SSL/TLS: Ensure all connections are HTTPS

### Vercel Frontend Deploy:

```bash
# If using Vercel CLI
vercel env add REACT_APP_API_BASE https://zt-backend.fly.dev
vercel --prod
```

### Fly.io Backend Deploy:

```bash
flyctl auth login
flyctl launch  # creates app
flyctl deploy  # deploys from git
flyctl logs    # view logs
flyctl volumes create sqlite_data --size 10
```

## API Integration (Frontend → Backend)

Frontend now supports multiple deployment patterns:

1. **Same-origin** (static + API on same host):
   ```javascript
   const API = '/api';  // relative path
   ```

2. **Cross-origin** (separate hosts):
   ```javascript
   const API = 'https://api.example.com';
   ```

3. **Environment-aware** (automatic):
   ```javascript
   // Detects deployment and uses appropriate URL
   const API = getOptimalAPIBase();
   ```

## Troubleshooting

### 403 CORS errors on frontend → backend

**Cause**: Backend doesn't allow frontend's origin

**Fix**: Update backend's `CORS_ORIGINS` environment variable:
```bash
# Railway / Fly.io dashboard
CORS_ORIGINS="https://zt-exam.vercel.app,https://yourdomain.com"
```

### 404 on `/api/auth/login`

**Cause**: Frontend using wrong API base URL

**Check**:
1. Open browser console: `console.log(API)` → should show actual backend URL
2. Network tab → what's the full URL of failed request?
3. Backend logs → is request reaching backend?

### WebSocket connection fails

**Cause**: Proxy/firewall blocking WebSocket upgrade

**Fix**: Ensure your host supports WebSocket upgrades:
- Fly.io: ✅ Built-in
- Railway: ✅ Built-in
- Render: ✅ Built-in
- Vercel: ❌ Not recommended for WebSocket

### SQLite "database is locked"

**Cause**: Vercel running multiple concurrent functions

**Fix**: Migrate to PostgreSQL:
```python
# backend/app/database.py
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:pass@host/db"  # Production
)
```

## Production Hardening

1. **Disable CORS wildcard**:
   ```python
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["https://yourdomain.com"],  # Specific domain
       allow_credentials=True,
   )
   ```

2. **Add rate limiting**:
   ```python
   from slowapi import Limiter
   limiter = Limiter(key_func=get_remote_address)
   app.state.limiter = limiter
   
   @app.post("/api/auth/login")
   @limiter.limit("5/minute")
   def login(...): ...
   ```

3. **Add logging & monitoring**:
   ```python
   import sentry_sdk
   sentry_sdk.init("your-sentry-dsn")
   ```

4. **Use secrets manager**:
   ```python
   import os
   SECRET_KEY = os.getenv("SECRET_KEY")  # Don't hardcode!
   ```

## See Also

- [Fly.io Python Deployment](https://fly.io/docs/languages-and-frameworks/python/)
- [Railway Python Guide](https://docs.railway.app/deploy/deployments)
- [Render PostgreSQL](https://render.com/docs/databases)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
