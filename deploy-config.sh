#!/bin/bash
# Deployment Configuration Helper
# Usage: source ./deploy-config.sh <environment>

set_env() {
    local ENV=$1
    
    case "$ENV" in
        local)
            echo "🔧 Configuring for LOCAL DEVELOPMENT"
            export API_BASE="http://localhost:8000"
            export DATABASE_URL="sqlite:///./exam.db"
            export SECRET_KEY="dev-key-change-in-production"
            export CORS_ORIGINS="http://localhost:3000,http://localhost:5000,http://localhost:8080"
            echo "✓ Backend: http://localhost:8000"
            echo "✓ Database: SQLite (./exam.db)"
            echo "✓ Frontend: Open frontend/index.html"
            ;;
        
        production-vercel)
            echo "🚀 Configuring for VERCEL + EXTERNAL BACKEND"
            echo "⚠️  NOTE: This architecture is NOT RECOMMENDED for WebSocket/SQLite workloads"
            read -p "Enter your backend domain (e.g., zt-backend.fly.dev): " BACKEND_DOMAIN
            export API_BASE="https://$BACKEND_DOMAIN"
            echo "✓ Frontend: Deploy to Vercel"
            echo "✓ Backend: Deploy to Fly.io/Railway/Render"
            echo "✓ Add to vercel.json env: REACT_APP_API_BASE=$API_BASE"
            ;;
        
        production-fly)
            echo "🚀 Configuring for FLY.IO (RECOMMENDED)"
            read -p "Enter your Fly.io app name: " FLY_APP
            export API_BASE="https://$FLY_APP.fly.dev"
            export DATABASE_URL="sqlite:///data/exam.db"  # Persistent volume
            export CORS_ORIGINS="https://$FLY_APP.fly.dev,https://yourdomain.com"
            export SECRET_KEY="$(openssl rand -hex 32)"
            
            echo "✓ Backend will run at: https://$FLY_APP.fly.dev"
            echo "✓ Database: SQLite on persistent volume"
            echo "✓ Add to fly.toml env:"
            echo "  CORS_ORIGINS=\"$CORS_ORIGINS\""
            echo "  DATABASE_URL=\"$DATABASE_URL\""
            echo "  SECRET_KEY=\"$SECRET_KEY\""
            ;;
        
        production-railway)
            echo "🚀 Configuring for RAILWAY.APP (RECOMMENDED)"
            read -p "Enter your Railway project/service name: " RAILWAY_SERVICE
            export API_BASE="https://$RAILWAY_SERVICE.up.railway.app"
            export DATABASE_URL="sqlite:///data/exam.db"
            export CORS_ORIGINS="https://yourdomain.com"
            export SECRET_KEY="$(openssl rand -hex 32)"
            
            echo "✓ Backend: https://$RAILWAY_SERVICE.up.railway.app"
            echo "✓ Create PostgreSQL addon in Railway dashboard"
            echo "✓ Railway will auto-set DATABASE_URL"
            ;;
        
        *)
            echo "Usage: source deploy-config.sh <environment>"
            echo ""
            echo "Available environments:"
            echo "  local              - Local development"
            echo "  production-vercel  - Vercel (frontend only) + separate backend"
            echo "  production-fly     - Fly.io full stack"
            echo "  production-railway - Railway.app full stack"
            return 1
            ;;
    esac
}

verify_env() {
    echo ""
    echo "📋 Verification:"
    echo "  API_BASE=$API_BASE"
    echo "  DATABASE_URL=$DATABASE_URL"
    echo "  CORS_ORIGINS=$CORS_ORIGINS"
    echo ""
    echo "Next steps:"
    if [[ "$ENV" == "local" ]]; then
        echo "  1. cd backend && pip install -r requirements.txt"
        echo "  2. python seed.py"
        echo "  3. python -m uvicorn app.main:app --reload"
        echo "  4. Open frontend/index.html in browser"
    else
        echo "  1. Commit changes to git"
        echo "  2. Push to your cloud provider"
        echo "  3. Monitor deployment"
    fi
}

# Main
ENV=$1
if [ -z "$ENV" ]; then
    echo "❌ No environment specified"
    echo ""
    set_env help
    exit 1
fi

set_env "$ENV"
verify_env
