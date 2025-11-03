#!/bin/bash

# Green Means Go Production Deployment Script for greenmeansgo.ai
# Run this script on your AWS EC2 instance

set -e  # Exit on any error

echo "🚀 Starting Green Means Go Production Deployment for greenmeansgo.ai"

# Configuration
PROJECT_DIR="/var/www/green_means_go"
BACKEND_DIR="$PROJECT_DIR/african_lca_backend"
API_DIR="$PROJECT_DIR/app"
FRONTEND_DIR="$PROJECT_DIR/african-lca-frontend"
VENV_DIR="$API_DIR/venv"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Function to ensure virtual environment is activated
activate_venv() {
    if [ ! -f "$VENV_DIR/bin/activate" ]; then
        print_error "Virtual environment not found at $VENV_DIR"
        exit 1
    fi

    source $VENV_DIR/bin/activate

    if [ "$VIRTUAL_ENV" != "$VENV_DIR" ]; then
        print_error "Failed to activate virtual environment"
        exit 1
    fi

    print_status "Virtual environment active: $VIRTUAL_ENV"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root for security reasons"
   exit 1
fi

echo "========================================"
echo "  Green Means Go Deployment"
echo "  Domain: greenmeansgo.ai"
echo "  IP: 16.52.214.205"
echo "========================================"
echo ""

# 1. System Dependencies
print_step "Step 1: Installing system dependencies..."
sudo apt update
sudo apt install -y \
    python3-pip python3-venv python3-dev \
    nginx supervisor certbot python3-certbot-nginx \
    curl wget git build-essential \
    pkg-config libssl-dev

# Install Rust
print_status "Installing Rust..."
if ! command -v cargo &> /dev/null; then
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source $HOME/.cargo/env
    print_status "Rust installed ✓"
else
    print_status "Rust already installed ✓"
fi

# Verify Rust installation
rustc --version
cargo --version

# Install Node.js 20.x for frontend
print_status "Installing Node.js 20.x for frontend..."
if ! command -v node &> /dev/null || ! node --version | grep -q "v20"; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt install -y nodejs
fi
node --version
npm --version

# 2. Verify project structure
print_step "Step 2: Verifying project structure..."

# Check if we're in the right directory
if [ ! -f "$API_DIR/main.py" ]; then
    print_error "Project structure not found. Make sure the repository is cloned to $PROJECT_DIR"
    print_error "Expected file: $API_DIR/main.py"
    exit 1
fi

if [ ! -f "$BACKEND_DIR/Cargo.toml" ]; then
    print_error "Rust backend not found at $BACKEND_DIR/Cargo.toml"
    exit 1
fi

# Check for requirements.txt
if [ ! -f "$PROJECT_DIR/requirements.txt" ] && [ ! -f "$API_DIR/requirements.txt" ]; then
    print_error "requirements.txt not found in project root or app directory"
    exit 1
fi

print_status "Project structure verified ✓"

# 3. Create project directory permissions
print_status "Setting up project directory permissions..."
sudo chown -R $USER:$USER $PROJECT_DIR

# 4. Build Rust Backend
print_step "Step 3: Building Rust backend (this may take a while)..."
cd $BACKEND_DIR

print_status "Running Rust release build with optimizations..."
cargo build --release

# Check for binary (multiple possible names)
if [ -f "$BACKEND_DIR/target/release/server" ]; then
    RUST_BINARY="$BACKEND_DIR/target/release/server"
    print_status "Found Rust binary: server"
elif [ -f "$BACKEND_DIR/target/release/african_lca_backend" ]; then
    RUST_BINARY="$BACKEND_DIR/target/release/african_lca_backend"
    print_status "Found Rust binary: african_lca_backend"
elif [ -f "$BACKEND_DIR/target/release/african-lca-backend" ]; then
    RUST_BINARY="$BACKEND_DIR/target/release/african-lca-backend"
    print_status "Found Rust binary: african-lca-backend"
else
    # Try to find any executable binary
    print_warning "Standard binary names not found, searching for executables..."
    RUST_BINARY=$(find "$BACKEND_DIR/target/release/" -maxdepth 1 -type f -executable ! -name "*.so" ! -name "*.d" ! -name "build-*" | head -1)
    
    if [ -n "$RUST_BINARY" ]; then
        print_status "Found executable: $RUST_BINARY"
    else
        print_error "Rust build failed - no executable binary found"
        print_error "Checked locations:"
        print_error "  - $BACKEND_DIR/target/release/server"
        print_error "  - $BACKEND_DIR/target/release/african_lca_backend"
        print_error "  - $BACKEND_DIR/target/release/african-lca-backend"
        print_status "Listing actual files in target/release/:"
        ls -la "$BACKEND_DIR/target/release/" | grep -E '^-.*x' || true
        exit 1
    fi
fi

print_status "Rust backend built successfully ✓"
print_status "Binary location: $RUST_BINARY"

# 5. Setup Python virtual environment for FastAPI
print_step "Step 4: Setting up Python virtual environment for FastAPI..."
cd $API_DIR

# Remove existing venv if it exists
if [ -d "$VENV_DIR" ]; then
    print_warning "Removing existing virtual environment..."
    rm -rf $VENV_DIR
fi

# Create new virtual environment
python3 -m venv $VENV_DIR

# Verify venv was created
if [ ! -f "$VENV_DIR/bin/activate" ]; then
    print_error "Failed to create virtual environment"
    exit 1
fi

# Activate virtual environment
activate_venv

# 6. Install Python dependencies
print_status "Installing Python/FastAPI dependencies..."
pip install --upgrade pip

# Check for requirements.txt in multiple locations
if [ -f "$API_DIR/requirements.txt" ]; then
    print_status "Installing from $API_DIR/requirements.txt"
    pip install -r "$API_DIR/requirements.txt"
elif [ -f "$PROJECT_DIR/requirements.txt" ]; then
    print_status "Installing from $PROJECT_DIR/requirements.txt"
    pip install -r "$PROJECT_DIR/requirements.txt"
else
    print_error "requirements.txt not found in $API_DIR or $PROJECT_DIR"
    exit 1
fi

# Verify FastAPI is installed
python -c "import fastapi; print(f'FastAPI {fastapi.__version__} installed')"

# 7. Environment configuration
print_step "Step 5: Setting up environment configuration..."

# Create or update .env file for API
print_status "Configuring API environment file..."
cat > $API_DIR/.env << EOF
# Production Environment Configuration
API_HOST=127.0.0.1
API_PORT=8000
RUST_BACKEND_PATH=$RUST_BINARY

# CORS Settings
CORS_ORIGINS=https://greenmeansgo.ai,https://www.greenmeansgo.ai

# Environment
ENVIRONMENT=production

# Logging
LOG_LEVEL=info
EOF

# Verify the .env file was created
if [ -f "$API_DIR/.env" ]; then
    print_status "Environment file created successfully ✓"
    print_status "Rust binary path set to: $RUST_BINARY"
else
    print_error "Failed to create .env file"
    exit 1
fi

print_warning "Remember to add your ANTHROPIC_API_KEY to $API_DIR/.env for AI report generation"

# 8. Frontend Build and Deployment
print_step "Step 6: Building and deploying frontend..."
cd $FRONTEND_DIR

# Clear existing cache and builds
print_status "Clearing frontend cache and old builds..."
rm -rf .next
rm -rf node_modules/.cache 2>/dev/null || true

# Create production environment file
if [ ! -f "$FRONTEND_DIR/.env.production.local" ]; then
    print_status "Creating production environment for frontend..."
    cat > $FRONTEND_DIR/.env.production.local << EOF
NEXT_PUBLIC_API_URL=https://greenmeansgo.ai/api
NEXT_PUBLIC_SITE_URL=https://greenmeansgo.ai
NEXT_PUBLIC_DOMAIN=greenmeansgo.ai
EOF
fi

# Install frontend dependencies
print_status "Installing frontend dependencies..."
npm ci

# Build the frontend
print_status "Building frontend for production (this may take a few minutes)..."
npm run build

print_status "Frontend build completed ✓"

# 9. Nginx configuration - HTTP only (SSL will be added after certbot)
print_step "Step 7: Configuring Nginx..."

# Create initial HTTP-only nginx configuration
sudo tee /etc/nginx/sites-available/greenmeansgo.ai > /dev/null << 'EOF'
# Upstream definitions
upstream fastapi_backend {
    server 127.0.0.1:8000 fail_timeout=30s;
}

upstream nextjs_frontend {
    server 127.0.0.1:3000 fail_timeout=30s;
}

# HTTP server - temporary configuration for SSL setup
server {
    listen 80;
    listen [::]:80;
    server_name greenmeansgo.ai www.greenmeansgo.ai 16.52.214.205;

    # Allow Let's Encrypt challenges
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # Security headers
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Client body size limit
    client_max_body_size 20M;

    # Common proxy settings
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_redirect off;
    proxy_read_timeout 300;
    proxy_connect_timeout 300;
    proxy_send_timeout 300;

    # FastAPI endpoints - strip /api prefix before passing to backend
    location /api/ {
        rewrite ^/api/(.*)$ /$1 break;
        proxy_pass http://fastapi_backend;
    }

    location /api {
        rewrite ^/api$ / break;
        proxy_pass http://fastapi_backend;
    }

    # Exact match for /assess to avoid matching /assessment
    location = /assess {
        proxy_pass http://fastapi_backend;
    }

    # Match /assess/{anything} but not /assessment
    location ~ ^/assess/(.*)$ {
        proxy_pass http://fastapi_backend;
    }

    location /assessments {
        proxy_pass http://fastapi_backend;
    }

    location /health {
        proxy_pass http://fastapi_backend;
    }

    location /docs {
        proxy_pass http://fastapi_backend;
    }

    location /openapi.json {
        proxy_pass http://fastapi_backend;
    }

    location /reports {
        proxy_pass http://fastapi_backend;
    }

    location /reports/ {
        proxy_pass http://fastapi_backend;
    }

    # Next.js static files
    location /_next/static/ {
        proxy_pass http://nextjs_frontend;
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    # Next.js frontend - all other routes
    location / {
        proxy_pass http://nextjs_frontend;

        # WebSocket support for Next.js
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_cache_bypass $http_upgrade;
    }

    # Error pages
    error_page 502 503 504 /50x.html;
    location = /50x.html {
        root /var/www/html;
        internal;
    }
}
EOF

# Enable the site and test configuration
sudo ln -sf /etc/nginx/sites-available/greenmeansgo.ai /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test nginx configuration
if ! sudo nginx -t; then
    print_error "Nginx configuration test failed"
    exit 1
fi

print_status "Nginx HTTP configuration completed ✓"

# Create a simple error page
sudo mkdir -p /var/www/html
sudo tee /var/www/html/50x.html > /dev/null << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>Green Means Go - Service Temporarily Unavailable</title>
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; 
            text-align: center; 
            margin-top: 100px;
            background: linear-gradient(135deg, #059669 0%, #10b981 50%, #34d399 100%);
            color: white;
            padding: 20px;
        }
        h1 { color: white; font-size: 2.5em; margin-bottom: 20px; }
        p { color: #d1fae5; font-size: 1.2em; }
        .container {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 40px;
            max-width: 600px;
            margin: 0 auto;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🌱 Green Means Go</h1>
        <h2>Service Temporarily Unavailable</h2>
        <p>Our services are starting up. Please try again in a moment.</p>
        <p style="font-size: 0.9em; margin-top: 30px;">African Food Systems LCA Platform</p>
    </div>
</body>
</html>
EOF

# 10. Supervisor configuration for services
print_step "Step 8: Configuring Supervisor for service management..."

# FastAPI backend configuration
# Note: Environment variables must be on a single line with proper escaping
sudo tee /etc/supervisor/conf.d/greenmeansgo-api.conf > /dev/null << EOF
[program:greenmeansgo-api]
command=$VENV_DIR/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 4 --env-file .env
directory=$API_DIR
user=$USER
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/greenmeansgo-api.log
stderr_logfile=/var/log/greenmeansgo-api-error.log
environment=PATH="$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin",RUST_BACKEND_PATH="$RUST_BINARY",PYTHONPATH="$API_DIR"
stopwaitsecs=60
EOF

# Next.js frontend configuration
sudo tee /etc/supervisor/conf.d/greenmeansgo-frontend.conf > /dev/null << EOF
[program:greenmeansgo-frontend]
command=/usr/bin/npm start
directory=$FRONTEND_DIR
user=$USER
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/greenmeansgo-frontend.log
stderr_logfile=/var/log/greenmeansgo-frontend-error.log
environment=NODE_ENV="production",PORT="3000"
stopwaitsecs=60
EOF

print_status "Supervisor configuration completed ✓"

# 11. Create log files with proper permissions
print_status "Setting up log files..."
sudo touch /var/log/greenmeansgo-api.log
sudo touch /var/log/greenmeansgo-api-error.log
sudo touch /var/log/greenmeansgo-frontend.log
sudo touch /var/log/greenmeansgo-frontend-error.log
sudo chown $USER:$USER /var/log/greenmeansgo-*.log

# 12. SSL Certificate with Let's Encrypt
print_step "Step 9: Setting up SSL certificate with Let's Encrypt..."

# Ensure required certbot files exist
sudo mkdir -p /etc/letsencrypt
if [ ! -f "/etc/letsencrypt/options-ssl-nginx.conf" ]; then
    print_status "Downloading certbot SSL configuration files..."
    sudo curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf -o /etc/letsencrypt/options-ssl-nginx.conf
    sudo curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem -o /etc/letsencrypt/ssl-dhparams.pem
fi

# Start nginx for Let's Encrypt challenge
print_status "Starting Nginx for SSL certificate verification..."
sudo systemctl start nginx

# Get SSL certificate
print_status "Requesting SSL certificate from Let's Encrypt..."
print_warning "Make sure your DNS is configured: greenmeansgo.ai → 16.52.214.205"
print_warning "Press Ctrl+C to cancel if DNS is not ready, or wait..."
sleep 5

if sudo certbot --nginx -d greenmeansgo.ai -d www.greenmeansgo.ai --non-interactive --agree-tos --email ebenezer.miezah@mcgill.ca --redirect; then
    print_status "SSL certificate installed successfully ✓"

    # Verify SSL certificate was installed
    if [ -f "/etc/letsencrypt/live/greenmeansgo.ai/fullchain.pem" ]; then
        # Test configuration and reload
        if sudo nginx -t; then
            sudo systemctl reload nginx
            print_status "HTTPS configuration activated ✓"
        else
            print_error "Nginx configuration test failed after SSL setup"
        fi
    fi
else
    print_error "SSL certificate installation failed"
    print_warning "Continuing with HTTP-only configuration"
    print_warning "You can run 'sudo certbot --nginx -d greenmeansgo.ai -d www.greenmeansgo.ai' manually later"
    print_warning "Make sure your domain DNS is properly configured and pointing to 16.52.214.205"
fi

# 13. Start services
print_step "Step 10: Starting services..."
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start all
sudo systemctl enable nginx supervisor
sudo systemctl restart supervisor
sudo systemctl reload nginx

# Wait for services to start
print_status "Waiting for services to initialize..."
sleep 10

# Check service status
print_status "Checking service status..."
sudo supervisorctl status

# 14. Firewall configuration
print_step "Step 11: Configuring firewall..."
sudo ufw allow 'Nginx Full'
sudo ufw allow ssh
sudo ufw --force enable

# 15. Setup automatic SSL renewal
print_status "Setting up automatic SSL certificate renewal..."
(sudo crontab -l 2>/dev/null || true; echo "0 12 * * * /usr/bin/certbot renew --quiet && systemctl reload nginx") | sudo crontab -

# 16. Health check
print_step "Step 12: Running health checks..."
sleep 5

print_status "Testing API endpoint..."
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    print_status "✓ API is responding"
else
    print_warning "API health check failed - check logs: sudo tail -f /var/log/greenmeansgo-api.log"
fi

print_status "Testing frontend..."
if curl -f http://localhost:3000 > /dev/null 2>&1; then
    print_status "✓ Frontend is responding"
else
    print_warning "Frontend health check failed - check logs: sudo tail -f /var/log/greenmeansgo-frontend.log"
fi

# 17. Performance optimization
print_step "Step 13: Performance optimization..."

# Enable gzip compression in nginx
print_status "Enabling gzip compression..."
if ! grep -q "gzip on;" /etc/nginx/nginx.conf; then
    sudo sed -i '/http {/a \        gzip on;\n        gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;\n        gzip_min_length 1000;' /etc/nginx/nginx.conf
    sudo systemctl reload nginx
fi

# 18. Create update script for easy redeployment
print_status "Creating update script..."
sudo tee /usr/local/bin/greenmeansgo-update.sh > /dev/null << 'EOFUPDATE'
#!/bin/bash
set -e

echo "🔄 Updating Green Means Go..."

cd /var/www/green_means_go

# Pull latest changes
git pull origin main

# Rebuild Rust backend
echo "Building Rust backend..."
cd african_lca_backend
cargo build --release

# Update Python dependencies
echo "Updating FastAPI dependencies..."
cd ../app
source venv/bin/activate
pip install -r requirements.txt

# Rebuild frontend
echo "Rebuilding frontend..."
cd ../african-lca-frontend
npm ci
npm run build

# Restart services
echo "Restarting services..."
sudo supervisorctl restart greenmeansgo-api
sudo supervisorctl restart greenmeansgo-frontend
sudo systemctl reload nginx

echo "✅ Update complete!"
EOFUPDATE

sudo chmod +x /usr/local/bin/greenmeansgo-update.sh

print_status "✅ Green Means Go Production Deployment Complete!"
echo ""
echo "=========================================="
echo "  🎉 Deployment Successful!"
echo "=========================================="
echo ""
print_status "Your Green Means Go application is now running at:"
print_status "🌍 https://greenmeansgo.ai (once DNS propagates)"
print_status "📍 http://16.52.214.205 (direct IP access)"
echo ""
print_status "Services deployed:"
print_status "├─ Frontend (Next.js): https://greenmeansgo.ai → port 3000"
print_status "├─ API (FastAPI): https://greenmeansgo.ai/api/ → port 8000"
print_status "└─ Rust Backend: Compiled binary at $RUST_BINARY"
echo ""
print_status "Architecture:"
print_status "├─ Rust (Computation Engine): ~100-200ms processing"
print_status "├─ FastAPI (REST API): Python interface to Rust"
print_status "└─ Next.js (Frontend): Modern React application"
echo ""
print_status "Next steps:"
print_status "1. Verify DNS propagation: dig greenmeansgo.ai"
print_status "2. Test the deployment: curl https://greenmeansgo.ai"
print_status "3. Test API: curl https://greenmeansgo.ai/health"
print_status "4. Monitor logs:"
print_status "   • API: sudo tail -f /var/log/greenmeansgo-api.log"
print_status "   • Frontend: sudo tail -f /var/log/greenmeansgo-frontend.log"
echo ""
print_status "Service management:"
print_status "• Status: sudo supervisorctl status"
print_status "• Restart API: sudo supervisorctl restart greenmeansgo-api"
print_status "• Restart Frontend: sudo supervisorctl restart greenmeansgo-frontend"
print_status "• Reload Nginx: sudo systemctl reload nginx"
echo ""
print_status "Quick update:"
print_status "• Run: sudo /usr/local/bin/greenmeansgo-update.sh"
echo ""
print_status "🚀 Performance:"
print_status "• Rust backend: <200ms for complex LCA calculations"
print_status "• API response: <500ms end-to-end"
print_status "• 4 Uvicorn workers for concurrent requests"
echo ""
print_status "📚 Documentation:"
print_status "• API Docs: https://greenmeansgo.ai/docs"
print_status "• GitHub: https://github.com/Amankrah/green_means_go.git"
echo ""
print_status "🎉 Deployment complete! Your platform is ready for African food systems LCA!"

