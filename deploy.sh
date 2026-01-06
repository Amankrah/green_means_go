#!/bin/bash

# =============================================================================
# Green Means Go - Secure Production Deployment Script
# Domain: greenmeansgo.ai
# =============================================================================
# 
# This script deploys the Green Means Go application with security hardening
# Run on a fresh Ubuntu 24.04 EC2 instance
#
# Usage: ./deploy-greenmeansgo.sh [--skip-security] [--skip-ssl]
#
# =============================================================================

set -euo pipefail

# =============================================================================
# CONFIGURATION - Modify these variables for your environment
# =============================================================================

# Your public IP for SSH access (CHANGE THIS!)
ALLOWED_SSH_IP="${ALLOWED_SSH_IP:-YOUR_IP_HERE}"

# Project configuration
PROJECT_DIR="/var/www/green_means_go"
BACKEND_DIR="$PROJECT_DIR/african_lca_backend"
API_DIR="$PROJECT_DIR/app"
FRONTEND_DIR="$PROJECT_DIR/african-lca-frontend"
VENV_DIR="$API_DIR/venv"

# Domain and email for SSL
DOMAIN="greenmeansgo.ai"
SSL_EMAIL="ebenezer.miezah@mcgill.ca"

# Git repository
GIT_REPO="https://github.com/Amankrah/green_means_go.git"

# =============================================================================
# COLORS AND HELPERS
# =============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════════╗"
    echo "║           Green Means Go - Secure Production Deployment          ║"
    echo "║                    greenmeansgo.ai                               ║"
    echo "╚══════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_status() { echo -e "${GREEN}[✓]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }
print_step() { echo -e "\n${BLUE}[STEP]${NC} $1\n"; }
print_section() {
    echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

# Parse command line arguments
SKIP_SECURITY=false
SKIP_SSL=false
for arg in "$@"; do
    case $arg in
        --skip-security) SKIP_SECURITY=true ;;
        --skip-ssl) SKIP_SSL=true ;;
    esac
done

# =============================================================================
# PRE-FLIGHT CHECKS
# =============================================================================

print_banner

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    print_error "Do not run this script as root. Run as ubuntu user with sudo access."
    exit 1
fi

# Check SSH IP is set
if [[ "$ALLOWED_SSH_IP" == "YOUR_IP_HERE" ]]; then
    print_error "You must set ALLOWED_SSH_IP before running this script!"
    print_warning "Find your IP: curl -s ifconfig.me"
    print_warning "Then run: ALLOWED_SSH_IP=your.ip.here ./deploy-greenmeansgo.sh"
    exit 1
fi

print_status "SSH access will be restricted to: $ALLOWED_SSH_IP"
print_warning "Make sure this is YOUR IP or you will be locked out!"
echo ""
read -p "Press Enter to continue or Ctrl+C to abort..."

# =============================================================================
# PHASE 1: SECURITY HARDENING (BEFORE ANYTHING ELSE)
# =============================================================================

if [[ "$SKIP_SECURITY" == false ]]; then
    print_section "PHASE 1: SECURITY HARDENING"

    print_step "1.1 System Updates"
    sudo apt update
    sudo DEBIAN_FRONTEND=noninteractive apt upgrade -y
    print_status "System updated"

    print_step "1.2 Installing Security Tools"
    sudo apt install -y \
        fail2ban \
        ufw \
        unattended-upgrades \
        apt-listchanges \
        logwatch \
        rkhunter
    print_status "Security tools installed"

    print_step "1.3 Configuring Firewall (UFW)"
    
    # Reset UFW to default
    sudo ufw --force reset
    
    # Default policies
    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    
    # Allow SSH only from your IP
    sudo ufw allow from "$ALLOWED_SSH_IP" to any port 22 proto tcp comment 'SSH from allowed IP'
    
    # Allow web traffic
    sudo ufw allow 80/tcp comment 'HTTP'
    sudo ufw allow 443/tcp comment 'HTTPS'
    
    # Block known malicious IPs
    sudo ufw deny from 38.150.0.118 comment 'Known attacker'
    sudo ufw deny from 67.210.97.41 comment 'Known attacker'
    
    # Block outbound connections to mining pools
    sudo ufw deny out to any port 10128 comment 'Block mining pool port'
    sudo ufw deny out to any port 3333 comment 'Block mining pool port'
    
    # Enable firewall
    sudo ufw --force enable
    print_status "Firewall configured"
    sudo ufw status verbose

    print_step "1.4 Configuring fail2ban"
    sudo tee /etc/fail2ban/jail.local > /dev/null << 'EOF'
[DEFAULT]
bantime = 86400
findtime = 600
maxretry = 5
backend = systemd
banaction = ufw

[sshd]
enabled = true
port = ssh
filter = sshd
maxretry = 3
bantime = 86400
findtime = 600
EOF

    sudo systemctl enable fail2ban
    sudo systemctl restart fail2ban
    print_status "fail2ban configured"

    print_step "1.5 Configuring Automatic Security Updates"
    sudo tee /etc/apt/apt.conf.d/20auto-upgrades > /dev/null << 'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::Download-Upgradeable-Packages "1";
APT::Periodic::AutocleanInterval "7";
EOF

    sudo tee /etc/apt/apt.conf.d/50unattended-upgrades > /dev/null << 'EOF'
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}";
    "${distro_id}:${distro_codename}-security";
    "${distro_id}ESMApps:${distro_codename}-apps-security";
    "${distro_id}ESM:${distro_codename}-infra-security";
};
Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::MinimalSteps "true";
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
EOF

    sudo systemctl enable unattended-upgrades
    sudo systemctl start unattended-upgrades
    print_status "Automatic security updates configured"

    print_step "1.6 SSH Hardening"
    sudo tee /etc/ssh/sshd_config.d/hardening.conf > /dev/null << 'EOF'
# SSH Hardening Configuration
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
X11Forwarding no
AllowTcpForwarding no
AllowAgentForwarding no
PermitEmptyPasswords no
ChallengeResponseAuthentication no
UsePAM yes
EOF

    # Test SSH config before restarting
    if sudo sshd -t; then
        sudo systemctl restart sshd || sudo systemctl restart ssh
        print_status "SSH hardened"
    else
        print_error "SSH configuration error - not applying changes"
    fi

    print_step "1.7 Creating Security Monitoring Script"
    sudo tee /usr/local/bin/security-check.sh > /dev/null << 'EOFSCRIPT'
#!/bin/bash

echo "=== Security Check $(date) ==="

echo -e "\n--- Crontabs ---"
for user in $(cut -f1 -d: /etc/passwd); do
    crontab -u $user -l 2>/dev/null | grep -v "^#" | grep -v "^$" && echo "  ^ User: $user"
done

echo -e "\n--- Suspicious processes ---"
ps aux | grep -E "(javae|xmrig|mine|pnscan|cc.txt|kdevtmpfsi|immunify|/dev/shm/|/var/tmp/\.)" | grep -v grep || echo "None found"

echo -e "\n--- High CPU processes ---"
ps aux --sort=-%cpu | head -5

echo -e "\n--- Failed SSH attempts (last 24h) ---"
sudo grep "Failed password\|Invalid user" /var/log/auth.log 2>/dev/null | tail -10 || echo "None"

echo -e "\n--- fail2ban status ---"
sudo fail2ban-client status sshd 2>/dev/null || echo "fail2ban not running"

echo -e "\n--- Hidden directories in /tmp and /var/tmp ---"
find /tmp /var/tmp -name ".*" -type d 2>/dev/null | grep -v -E "^\.(X11|ICE|font|XIM)-unix$" || echo "None"

echo -e "\n--- Listening ports ---"
sudo ss -tlnp

echo -e "\n--- SSH authorized_keys ---"
cat ~/.ssh/authorized_keys 2>/dev/null | cut -d' ' -f3

echo -e "\n--- Shell config sizes (should be ~3-4KB) ---"
ls -la ~/.bashrc ~/.profile ~/.bash_profile 2>/dev/null || echo "Some files missing"

echo -e "\n--- Active network connections to external IPs ---"
sudo ss -tupn | grep -v "127.0.0.1" | grep -v ":22 " | head -10

echo -e "\n=== Check Complete ==="
EOFSCRIPT

    sudo chmod +x /usr/local/bin/security-check.sh
    
    # Schedule weekly security check
    (crontab -l 2>/dev/null | grep -v "security-check.sh"; echo "0 8 * * 1 /usr/local/bin/security-check.sh >> /var/log/security-check.log 2>&1") | crontab -
    print_status "Security monitoring configured"

    print_step "1.8 Configuring Temp Directory Cleanup"
    sudo tee /etc/tmpfiles.d/tmp-clean.conf > /dev/null << 'EOF'
# Clean temp directories
D /tmp 1777 root root 1d
D /var/tmp 1777 root root 7d
D /dev/shm 1777 root root 1d
EOF
    print_status "Temp directory cleanup configured"

    print_status "Security hardening complete!"
else
    print_warning "Skipping security hardening (--skip-security flag)"
fi

# =============================================================================
# PHASE 2: SYSTEM DEPENDENCIES
# =============================================================================

print_section "PHASE 2: SYSTEM DEPENDENCIES"

print_step "2.1 Installing Build Dependencies"
sudo apt install -y \
    python3-pip python3-venv python3-dev \
    nginx supervisor certbot python3-certbot-nginx \
    curl wget git build-essential \
    pkg-config libssl-dev \
    jq htop

print_status "Build dependencies installed"

print_step "2.2 Installing Rust"
if ! command -v cargo &> /dev/null; then
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
    print_status "Rust installed"
else
    print_status "Rust already installed"
fi
rustc --version
cargo --version

print_step "2.3 Installing Node.js 20.x"
if ! command -v node &> /dev/null || ! node --version | grep -q "v20"; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt install -y nodejs
fi
print_status "Node.js $(node --version) installed"

# =============================================================================
# PHASE 3: APPLICATION DEPLOYMENT
# =============================================================================

print_section "PHASE 3: APPLICATION DEPLOYMENT"

print_step "3.1 Cloning Repository"
if [ -d "$PROJECT_DIR" ]; then
    print_warning "Project directory exists, pulling latest changes..."
    cd "$PROJECT_DIR"
    git pull origin main
else
    sudo mkdir -p "$(dirname $PROJECT_DIR)"
    sudo chown "$USER:$USER" "$(dirname $PROJECT_DIR)"
    git clone "$GIT_REPO" "$PROJECT_DIR"
fi
sudo chown -R "$USER:$USER" "$PROJECT_DIR"
print_status "Repository ready"

print_step "3.2 Building Rust Backend"
cd "$BACKEND_DIR"
source "$HOME/.cargo/env"

print_status "Running Rust release build (this may take a while)..."
cargo build --release

# Find the binary
RUST_BINARY=""
for name in server african_lca_backend african-lca-backend; do
    if [ -f "$BACKEND_DIR/target/release/$name" ]; then
        RUST_BINARY="$BACKEND_DIR/target/release/$name"
        break
    fi
done

if [ -z "$RUST_BINARY" ]; then
    RUST_BINARY=$(find "$BACKEND_DIR/target/release/" -maxdepth 1 -type f -executable ! -name "*.so" ! -name "*.d" | head -1)
fi

if [ -z "$RUST_BINARY" ]; then
    print_error "Rust build failed - no executable found"
    exit 1
fi
print_status "Rust binary: $RUST_BINARY"

print_step "3.3 Setting up Python Virtual Environment"
cd "$API_DIR"

# Create fresh virtual environment
rm -rf "$VENV_DIR"
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Install dependencies
pip install --upgrade pip
if [ -f "$API_DIR/requirements.txt" ]; then
    pip install -r "$API_DIR/requirements.txt"
elif [ -f "$PROJECT_DIR/requirements.txt" ]; then
    pip install -r "$PROJECT_DIR/requirements.txt"
fi

# Verify FastAPI
python -c "import fastapi; print(f'FastAPI {fastapi.__version__} installed')"
print_status "Python environment ready"

print_step "3.4 Configuring API Environment"
cat > "$API_DIR/.env" << EOF
# Production Environment Configuration
API_HOST=127.0.0.1
API_PORT=8000
RUST_BACKEND_PATH=$RUST_BINARY
CORS_ORIGINS=https://greenmeansgo.ai,https://www.greenmeansgo.ai
ENVIRONMENT=production
LOG_LEVEL=info
# Add your API keys below:
# ANTHROPIC_API_KEY=your_key_here
EOF
print_status "API environment configured"
print_warning "Remember to add your ANTHROPIC_API_KEY to $API_DIR/.env"

print_step "3.5 Building Frontend"
cd "$FRONTEND_DIR"

# Clean previous builds
rm -rf .next node_modules/.cache 2>/dev/null || true

# Create production environment
cat > "$FRONTEND_DIR/.env.production.local" << EOF
NEXT_PUBLIC_API_URL=https://greenmeansgo.ai/api
NEXT_PUBLIC_SITE_URL=https://greenmeansgo.ai
NEXT_PUBLIC_DOMAIN=greenmeansgo.ai
EOF

# Install and build
npm ci
npm run build
print_status "Frontend built"

# =============================================================================
# PHASE 4: SERVER CONFIGURATION
# =============================================================================

print_section "PHASE 4: SERVER CONFIGURATION"

print_step "4.1 Configuring Nginx"

# Create nginx configuration
sudo tee /etc/nginx/sites-available/greenmeansgo.ai > /dev/null << 'EOF'
# Rate limiting zones
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=general_limit:10m rate=30r/s;
limit_conn_zone $binary_remote_addr zone=conn_limit:10m;

# Upstream definitions
upstream fastapi_backend {
    server 127.0.0.1:8000 fail_timeout=30s;
    keepalive 32;
}

upstream nextjs_frontend {
    server 127.0.0.1:3000 fail_timeout=30s;
    keepalive 32;
}

# Block direct IP access
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    return 444;
}

# Main server block
server {
    listen 80;
    listen [::]:80;
    server_name greenmeansgo.ai www.greenmeansgo.ai;

    # Let's Encrypt challenge
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # Security headers
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    client_max_body_size 20M;

    # Proxy settings
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_redirect off;
    proxy_read_timeout 300;
    proxy_connect_timeout 300;
    proxy_send_timeout 300;

    # API endpoints
    location /api/ {
        limit_req zone=api_limit burst=20 nodelay;
        limit_conn conn_limit 10;
        rewrite ^/api/(.*)$ /$1 break;
        proxy_pass http://fastapi_backend;
    }

    location /api {
        limit_req zone=api_limit burst=20 nodelay;
        rewrite ^/api$ / break;
        proxy_pass http://fastapi_backend;
    }

    location = /assess {
        limit_req zone=api_limit burst=5 nodelay;
        proxy_pass http://fastapi_backend;
    }

    location ~ ^/assess/(.*)$ {
        limit_req zone=api_limit burst=5 nodelay;
        proxy_pass http://fastapi_backend;
    }

    location /assessments {
        limit_req zone=api_limit burst=10 nodelay;
        proxy_pass http://fastapi_backend;
    }

    location /health {
        proxy_pass http://fastapi_backend;
    }

    location /reports {
        limit_req zone=api_limit burst=5 nodelay;
        proxy_pass http://fastapi_backend;
    }

    location /reports/ {
        limit_req zone=api_limit burst=5 nodelay;
        proxy_pass http://fastapi_backend;
    }

    # Next.js static files
    location /_next/static/ {
        proxy_pass http://nextjs_frontend;
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    # Frontend
    location / {
        limit_req zone=general_limit burst=50 nodelay;
        proxy_pass http://nextjs_frontend;
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

# Enable site
sudo ln -sf /etc/nginx/sites-available/greenmeansgo.ai /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test nginx
sudo nginx -t
print_status "Nginx configured"

# Create error page
sudo mkdir -p /var/www/html
sudo tee /var/www/html/50x.html > /dev/null << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>Green Means Go - Service Temporarily Unavailable</title>
    <style>
        body { 
            font-family: -apple-system, sans-serif; 
            text-align: center; 
            margin-top: 100px;
            background: linear-gradient(135deg, #059669, #10b981);
            color: white;
            padding: 20px;
        }
        .container {
            background: rgba(255,255,255,0.1);
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
    </div>
</body>
</html>
EOF

print_step "4.2 Configuring Supervisor"

# API configuration
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
stopsignal=KILL
stopasgroup=true
killasgroup=true
EOF

# Frontend configuration
NPM_PATH=$(which npm)
sudo tee /etc/supervisor/conf.d/greenmeansgo-frontend.conf > /dev/null << EOF
[program:greenmeansgo-frontend]
command=$NPM_PATH start
directory=$FRONTEND_DIR
user=$USER
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/greenmeansgo-frontend.log
stderr_logfile=/var/log/greenmeansgo-frontend-error.log
environment=NODE_ENV="production",PORT="3000"
stopwaitsecs=60
stopsignal=KILL
stopasgroup=true
killasgroup=true
EOF

print_status "Supervisor configured"

# Create log files
sudo touch /var/log/greenmeansgo-{api,api-error,frontend,frontend-error}.log
sudo chown "$USER:$USER" /var/log/greenmeansgo-*.log

# =============================================================================
# PHASE 5: SSL AND STARTUP
# =============================================================================

print_section "PHASE 5: SSL AND STARTUP"

print_step "5.1 Starting Services"
sudo systemctl enable nginx supervisor
sudo supervisorctl reread
sudo supervisorctl update
sudo systemctl start nginx
sudo supervisorctl start all

# Wait for services
print_status "Waiting for services to start..."
sleep 10
sudo supervisorctl status

print_step "5.2 SSL Certificate"
if [[ "$SKIP_SSL" == false ]]; then
    # Download certbot files if needed
    sudo mkdir -p /etc/letsencrypt
    if [ ! -f "/etc/letsencrypt/options-ssl-nginx.conf" ]; then
        sudo curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf -o /etc/letsencrypt/options-ssl-nginx.conf
        sudo curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem -o /etc/letsencrypt/ssl-dhparams.pem
    fi

    print_warning "Requesting SSL certificate..."
    print_warning "Make sure DNS is configured: $DOMAIN → $(curl -s ifconfig.me)"
    
    if sudo certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" --non-interactive --agree-tos --email "$SSL_EMAIL" --redirect; then
        print_status "SSL certificate installed"
        sudo nginx -t && sudo systemctl reload nginx
    else
        print_error "SSL certificate failed - configure manually later"
    fi

    # Setup auto-renewal
    (sudo crontab -l 2>/dev/null | grep -v "certbot renew"; echo "0 12 * * * /usr/bin/certbot renew --quiet && systemctl reload nginx") | sudo crontab -
else
    print_warning "Skipping SSL (--skip-ssl flag)"
fi

# =============================================================================
# PHASE 6: HEALTH CHECKS AND COMPLETION
# =============================================================================

print_section "PHASE 6: HEALTH CHECKS"

print_step "6.1 Testing Services"
sleep 5

if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    print_status "API is responding"
else
    print_warning "API not responding - check logs: sudo tail -f /var/log/greenmeansgo-api.log"
fi

if curl -sf http://localhost:3000 > /dev/null 2>&1; then
    print_status "Frontend is responding"
else
    print_warning "Frontend not responding - check logs: sudo tail -f /var/log/greenmeansgo-frontend.log"
fi

print_step "6.2 Security Check"
/usr/local/bin/security-check.sh 2>/dev/null || true

# =============================================================================
# CREATE UTILITY SCRIPTS
# =============================================================================

print_section "CREATING UTILITY SCRIPTS"

# Update script
sudo tee /usr/local/bin/greenmeansgo-update.sh > /dev/null << 'EOFUPDATE'
#!/bin/bash
set -e
echo "🔄 Updating Green Means Go..."

cd /var/www/green_means_go
git pull origin main

# Rebuild Rust
cd african_lca_backend
source $HOME/.cargo/env
cargo build --release

# Update Python
cd ../app
source venv/bin/activate
pip install -r requirements.txt

# Rebuild frontend
cd ../african-lca-frontend
npm ci
npm run build

# Restart services
sudo supervisorctl restart all
sudo systemctl reload nginx

echo "✅ Update complete!"
EOFUPDATE
sudo chmod +x /usr/local/bin/greenmeansgo-update.sh

# Quick status script
sudo tee /usr/local/bin/greenmeansgo-status.sh > /dev/null << 'EOFSTATUS'
#!/bin/bash
echo "=== Green Means Go Status ==="
echo ""
echo "Services:"
sudo supervisorctl status
echo ""
echo "Firewall:"
sudo ufw status | head -15
echo ""
echo "fail2ban:"
sudo fail2ban-client status sshd 2>/dev/null | grep -E "(Currently|Total)" || echo "Not running"
echo ""
echo "Disk:"
df -h / | tail -1
echo ""
echo "Memory:"
free -h | grep Mem
echo ""
echo "CPU Usage (top 3):"
ps aux --sort=-%cpu | head -4
EOFSTATUS
sudo chmod +x /usr/local/bin/greenmeansgo-status.sh

# =============================================================================
# COMPLETION
# =============================================================================

print_banner

echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                    🎉 DEPLOYMENT COMPLETE! 🎉                    ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo "
🌍 Your application is running at:
   • https://$DOMAIN (HTTPS)
   • http://$(curl -s ifconfig.me) (Direct IP)

🔒 Security measures active:
   • SSH restricted to: $ALLOWED_SSH_IP
   • fail2ban: Blocking after 3 failed attempts
   • Firewall: Mining ports blocked
   • Auto-updates: Security patches enabled

📁 Important paths:
   • Project: $PROJECT_DIR
   • API logs: /var/log/greenmeansgo-api.log
   • Frontend logs: /var/log/greenmeansgo-frontend.log
   • Security logs: /var/log/security-check.log

🛠 Utility commands:
   • Status: greenmeansgo-status.sh
   • Update: sudo /usr/local/bin/greenmeansgo-update.sh
   • Security: sudo /usr/local/bin/security-check.sh
   • Restart: sudo supervisorctl restart all

⚠️  Remember to:
   1. Add ANTHROPIC_API_KEY to $API_DIR/.env
   2. Verify DNS: dig $DOMAIN
   3. Test: curl https://$DOMAIN/health
"