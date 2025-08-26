#!/bin/bash
# QuantTime Server Setup with Poetry
# Automated setup script for Ubuntu 22.04 servers with Poetry environment management

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

# Configuration
SERVER_NAME="${1:-quanttime-server}"
SERVER_IP="${2:-laptop}"
TAILSCALE_AUTHKEY="${3:-}"
QUANTTIME_USER="quanttime"
QUANTTIME_HOME="/opt/quanttime"
POETRY_VERSION="1.7.1"

log "Starting QuantTime Server Setup with Poetry"
log "Server: $SERVER_NAME"
log "IP: $SERVER_IP"

# Update system
log "Updating system packages..."
apt-get update
apt-get upgrade -y

# Install essential packages
log "Installing essential packages..."
apt-get install -y \
    curl \
    wget \
    git \
    vim \
    htop \
    tmux \
    screen \
    unzip \
    zip \
    rsync \
    nginx \
    ufw \
    fail2ban \
    logrotate \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    libssl-dev \
    libffi-dev \
    libpq-dev \
    libxml2-dev \
    libxslt1-dev \
    libjpeg-dev \
    libpng-dev \
    libfreetype6-dev \
    libblas-dev \
    liblapack-dev \
    libatlas-base-dev \
    gfortran \
    pkg-config \
    cmake \
    redis-server \
    postgresql \
    postgresql-contrib

# Create quanttime user
log "Creating quanttime user..."
if ! id "$QUANTTIME_USER" &>/dev/null; then
    useradd -m -s /bin/bash -d "$QUANTTIME_HOME" "$QUANTTIME_USER"
    usermod -aG sudo "$QUANTTIME_USER"
    echo "$QUANTTIME_USER ALL=(ALL) NOPASSWD:ALL" | tee /etc/sudoers.d/quanttime
    log "User $QUANTTIME_USER created"
else
    log "User $QUANTTIME_USER already exists"
fi

# Install Poetry
log "Installing Poetry..."
if ! command -v poetry &> /dev/null; then
    curl -sSL https://install.python-poetry.org | python3 -
    
    # Add Poetry to PATH
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$QUANTTIME_HOME/.bashrc"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> /root/.bashrc
    
    # Configure Poetry
    su - "$QUANTTIME_USER" -c "poetry config virtualenvs.in-project true"
    su - "$QUANTTIME_USER" -c "poetry config virtualenvs.prefer-active-python true"
    su - "$QUANTTIME_USER" -c "poetry config virtualenvs.create true"
    
    log "Poetry installed and configured"
else
    log "Poetry already installed"
fi

# Install Node.js and npm (for Syncthing)
log "Installing Node.js..."
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt-get install -y nodejs

# Install Syncthing
log "Installing Syncthing..."
curl -s https://syncthing.net/release-key.txt | apt-key add -
echo "deb https://apt.syncthing.net/ syncthing stable" | tee /etc/apt/sources.list.d/syncthing.list
apt-get update
apt-get install -y syncthing

# Create Syncthing service
cat > /etc/systemd/system/syncthing@$QUANTTIME_USER.service << EOF
[Unit]
Description=Syncthing - Open Source Continuous File Synchronization for $QUANTTIME_USER
Documentation=man:syncthing(1)
After=network.target
Wants=syncthing-inotify@$QUANTTIME_USER.service

[Service]
Type=simple
User=$QUANTTIME_USER
ExecStart=/usr/bin/syncthing serve --no-browser --no-restart --logflags=0
Restart=on-failure
RestartSec=5
SuccessExitStatus=3 4
RestartForceExitStatus=3 4

# Hardening
ProtectSystem=strict
ReadWritePaths=$QUANTTIME_HOME
PrivateTmp=true
ProtectHome=true

[Install]
WantedBy=multi-user.target
EOF

# Enable and start Syncthing
systemctl daemon-reload
systemctl enable syncthing@$QUANTTIME_USER
systemctl start syncthing@$QUANTTIME_USER

# Install Tailscale
log "Installing Tailscale..."
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/jammy.noarmor.gpg | tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/jammy.tailscale-keyring.list | tee /etc/apt/sources.list.d/tailscale.list
apt-get update
apt-get install -y tailscale

# Configure Tailscale
if [ -n "$TAILSCALE_AUTHKEY" ]; then
    tailscale up --authkey="$TAILSCALE_AUTHKEY" --hostname="$SERVER_NAME"
else
    log "Tailscale auth key not provided. Please run: tailscale up"
fi

# Configure network
log "Configuring network..."
cat > /etc/netplan/01-netcfg.yaml << EOF
network:
  version: 2
  renderer: networkd
  ethernets:
    eth0:
      dhcp4: false
      addresses:
        - $SERVER_IP/24
      gateway4: 192.168.1.1
      nameservers:
          addresses: [8.8.8.8, 8.8.4.4]
EOF

netplan apply

# Configure firewall
log "Configuring firewall..."
ufw --force enable
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 8384/tcp  # Syncthing
ufw allow 22000/tcp  # Syncthing sync
ufw allow 21027/udp  # Syncthing discovery
ufw allow 5000/tcp   # QuantTime API
ufw allow 8501/tcp   # Streamlit
ufw allow 8265/tcp   # Ray dashboard
ufw allow 10000/tcp  # Ray
ufw allow 6379/tcp   # Redis
ufw allow 5432/tcp   # PostgreSQL

# Configure fail2ban
log "Configuring fail2ban..."
cat > /etc/fail2ban/jail.local << EOF
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3

[nginx-http-auth]
enabled = true
filter = nginx-http-auth
port = http,https
logpath = /var/log/nginx/error.log
EOF

systemctl restart fail2ban

# Configure logrotate
log "Configuring logrotate..."
cat > /etc/logrotate.d/quanttime << EOF
$QUANTTIME_HOME/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 $QUANTTIME_USER $QUANTTIME_USER
    postrotate
        systemctl reload quanttime
    endscript
}
EOF

# Create project directory structure
log "Creating project directory structure..."
mkdir -p "$QUANTTIME_HOME"
chown -R "$QUANTTIME_USER:$QUANTTIME_USER" "$QUANTTIME_HOME"

# Create necessary directories
su - "$QUANTTIME_USER" -c "mkdir -p $QUANTTIME_HOME/{logs,data,models,cache,temp,config,config/secrets,config/credentials}"

# Configure Redis
log "Configuring Redis..."
sed -i 's/bind 127.0.0.1/bind 0.0.0.0/' /etc/redis/redis.conf
sed -i 's/# maxmemory <bytes>/maxmemory 2gb/' /etc/redis/redis.conf
sed -i 's/# maxmemory-policy noeviction/maxmemory-policy allkeys-lru/' /etc/redis/redis.conf
systemctl restart redis-server

# Configure PostgreSQL
log "Configuring PostgreSQL..."
sudo -u postgres createuser --createdb --createrole --superuser "$QUANTTIME_USER" || true
sudo -u postgres createdb quanttime || true

# Create systemd service for QuantTime
log "Creating QuantTime systemd service..."
cat > /etc/systemd/system/quanttime.service << EOF
[Unit]
Description=QuantTime ML Trading Suite
After=network.target redis-server.service postgresql.service syncthing@$QUANTTIME_USER.service
Wants=redis-server.service postgresql.service syncthing@$QUANTTIME_USER.service

[Service]
Type=simple
User=$QUANTTIME_USER
Group=$QUANTTIME_USER
WorkingDirectory=$QUANTTIME_HOME
Environment=PATH=$QUANTTIME_HOME/.venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONPATH=$QUANTTIME_HOME
ExecStart=$QUANTTIME_HOME/.venv/bin/python -m streamlit run quanttime/dashboard/app.py --server.port 8501 --server.address 0.0.0.0
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=$QUANTTIME_HOME
ProtectHome=true

[Install]
WantedBy=multi-user.target
EOF

# Create Ray systemd service
cat > /etc/systemd/system/ray.service << EOF
[Unit]
Description=Ray Distributed Computing
After=network.target
Wants=network.target

[Service]
Type=simple
User=$QUANTTIME_USER
Group=$QUANTTIME_USER
WorkingDirectory=$QUANTTIME_HOME
Environment=PATH=$QUANTTIME_HOME/.venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONPATH=$QUANTTIME_HOME
ExecStart=$QUANTTIME_HOME/.venv/bin/ray start --head --port=6379 --dashboard-host=0.0.0.0 --dashboard-port=8265
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=$QUANTTIME_HOME
ProtectHome=true

[Install]
WantedBy=multi-user.target
EOF

# Create environment file
log "Creating environment configuration..."
cat > "$QUANTTIME_HOME/.env" << EOF
# QuantTime Server Environment Configuration
QUANTTIME_ENV=production
QUANTTIME_DEBUG=false
QUANTTIME_LOG_LEVEL=INFO

# Server settings
SERVER_HOST=0.0.0.0
SERVER_PORT=5000
SERVER_WORKERS=4

# Database settings
DATABASE_URL=postgresql://$QUANTTIME_USER@localhost/quanttime
DATABASE_ECHO=false

# Redis settings
REDIS_URL=redis://localhost:6379/0

# Ray settings
RAY_DASHBOARD_HOST=0.0.0.0
RAY_DASHBOARD_PORT=8265
RAY_HEAD_NODE_IP=$SERVER_IP

# Syncthing settings
SYNCTHING_API_KEY=your_syncthing_api_key_here
SYNCTHING_HOST=localhost
SYNCTHING_PORT=8384

# Logging settings
LOG_LEVEL=INFO
LOG_FILE=$QUANTTIME_HOME/logs/quanttime.log
LOG_FORMAT=%(asctime)s [%(levelname)s] [%(name)s] %(message)s

# Model settings
MODEL_CACHE_DIR=$QUANTTIME_HOME/models/cache
MODEL_CHECKPOINT_DIR=$QUANTTIME_HOME/models/checkpoints

# Data settings
DATA_DIR=$QUANTTIME_HOME/data
CACHE_DIR=$QUANTTIME_HOME/cache
TEMP_DIR=$QUANTTIME_HOME/temp

# Security settings
SECRET_KEY=your_secret_key_here_change_in_production
JWT_SECRET_KEY=your_jwt_secret_key_here_change_in_production

# Development settings
DEBUG=false
RELOAD=false
TESTING=false
EOF

chown "$QUANTTIME_USER:$QUANTTIME_USER" "$QUANTTIME_HOME/.env"

# Create setup completion script
log "Creating setup completion script..."
cat > "$QUANTTIME_HOME/setup_complete.sh" << 'EOF'
#!/bin/bash
# QuantTime Setup Completion Script
# Run this after syncing the project files

set -e

QUANTTIME_USER="quanttime"
QUANTTIME_HOME="/opt/quanttime"

echo "🚀 Completing QuantTime setup..."

# Switch to quanttime user
cd "$QUANTTIME_HOME"

# Install Poetry dependencies
echo "📦 Installing Poetry dependencies..."
poetry install --no-dev

# Create virtual environment
echo "🔧 Creating virtual environment..."
poetry env use python3

# Install dependencies
echo "📦 Installing project dependencies..."
poetry install

# Generate poetry.lock if not exists
if [ ! -f "poetry.lock" ]; then
    echo "🔒 Generating poetry.lock..."
    poetry lock
fi

# Test installation
echo "🧪 Testing installation..."
poetry run python -c "
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
import torch
import lightgbm as lgb
print('✅ All dependencies imported successfully')
"

# Enable services
echo "🔧 Enabling services..."
sudo systemctl enable quanttime.service
sudo systemctl enable ray.service

echo "🎉 Setup completed successfully!"
echo "📋 Next steps:"
echo "  1. Configure your .env file with proper settings"
echo "  2. Start services: sudo systemctl start quanttime ray"
echo "  3. Access dashboard at: http://$SERVER_IP:8501"
echo "  4. Access Ray dashboard at: http://$SERVER_IP:8265"
EOF

chmod +x "$QUANTTIME_HOME/setup_complete.sh"
chown "$QUANTTIME_USER:$QUANTTIME_USER" "$QUANTTIME_HOME/setup_complete.sh"

# Create health check script
log "Creating health check script..."
cat > "$QUANTTIME_HOME/health_check.sh" << 'EOF'
#!/bin/bash
# QuantTime Health Check Script

QUANTTIME_USER="quanttime"
QUANTTIME_HOME="/opt/quanttime"

echo "🏥 QuantTime Health Check"
echo "========================"

# Check services
echo "📊 Service Status:"
systemctl is-active --quiet quanttime && echo "✅ QuantTime: Active" || echo "❌ QuantTime: Inactive"
systemctl is-active --quiet ray && echo "✅ Ray: Active" || echo "❌ Ray: Inactive"
systemctl is-active --quiet syncthing@$QUANTTIME_USER && echo "✅ Syncthing: Active" || echo "❌ Syncthing: Inactive"
systemctl is-active --quiet redis-server && echo "✅ Redis: Active" || echo "❌ Redis: Inactive"
systemctl is-active --quiet postgresql && echo "✅ PostgreSQL: Active" || echo "❌ PostgreSQL: Inactive"

# Check ports
echo ""
echo "🌐 Port Status:"
netstat -tlnp | grep :8501 && echo "✅ Streamlit (8501): Listening" || echo "❌ Streamlit (8501): Not listening"
netstat -tlnp | grep :8265 && echo "✅ Ray Dashboard (8265): Listening" || echo "❌ Ray Dashboard (8265): Not listening"
netstat -tlnp | grep :8384 && echo "✅ Syncthing (8384): Listening" || echo "❌ Syncthing (8384): Not listening"
netstat -tlnp | grep :6379 && echo "✅ Redis (6379): Listening" || echo "❌ Redis (6379): Not listening"
netstat -tlnp | grep :5432 && echo "✅ PostgreSQL (5432): Listening" || echo "❌ PostgreSQL (5432): Not listening"

# Check disk space
echo ""
echo "💾 Disk Usage:"
df -h "$QUANTTIME_HOME"

# Check memory usage
echo ""
echo "🧠 Memory Usage:"
free -h

# Check Python environment
echo ""
echo "🐍 Python Environment:"
if [ -d "$QUANTTIME_HOME/.venv" ]; then
    echo "✅ Virtual environment exists"
    "$QUANTTIME_HOME/.venv/bin/python" --version
else
    echo "❌ Virtual environment not found"
fi
EOF

chmod +x "$QUANTTIME_HOME/health_check.sh"
chown "$QUANTTIME_USER:$QUANTTIME_USER" "$QUANTTIME_HOME/health_check.sh"

# Final setup
log "Finalizing setup..."

# Set proper permissions
chown -R "$QUANTTIME_USER:$QUANTTIME_USER" "$QUANTTIME_HOME"

# Create log files
touch "$QUANTTIME_HOME/logs/quanttime.log"
chown "$QUANTTIME_USER:$QUANTTIME_USER" "$QUANTTIME_HOME/logs/quanttime.log"

# Reload systemd
systemctl daemon-reload

log "🎉 Server setup completed successfully!"
log ""
log "📋 Next steps:"
log "  1. Sync your QuantTime project to $QUANTTIME_HOME"
log "  2. Run: sudo -u $QUANTTIME_USER $QUANTTIME_HOME/setup_complete.sh"
log "  3. Configure your .env file with proper settings"
log "  4. Start services: sudo systemctl start quanttime ray"
log "  5. Access dashboard at: http://$SERVER_IP:8501"
log "  6. Access Ray dashboard at: http://$SERVER_IP:8265"
log "  7. Run health check: $QUANTTIME_HOME/health_check.sh"
log ""
log "🔧 Services created:"
log "  - quanttime.service (Streamlit dashboard)"
log "  - ray.service (Ray distributed computing)"
log "  - syncthing@$QUANTTIME_USER.service (File synchronization)"
log ""
log "🌐 Ports configured:"
log "  - 8501: Streamlit dashboard"
log "  - 8265: Ray dashboard"
log "  - 8384: Syncthing web interface"
log "  - 22000: Syncthing sync"
log "  - 6379: Redis"
log "  - 5432: PostgreSQL"
