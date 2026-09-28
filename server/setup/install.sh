#!/bin/bash

# QuantTime Server Installation Script
# Sets up server environment for 24/7 data warehousing and automated operations

set -e  # Exit on any error

echo "🚀 Starting QuantTime Server Installation..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   print_error "This script must be run as root for server installation"
   exit 1
fi

# Check operating system
OS="$(uname -s)"
case "${OS}" in
    Linux*)     MACHINE=Linux;;
    Darwin*)    MACHINE=Mac;;
    CYGWIN*)    MACHINE=Cygwin;;
    MINGW*)     MACHINE=MinGw;;
    *)          MACHINE="UNKNOWN:${OS}"
esac

print_status "Detected OS: $MACHINE"

if [ "$MACHINE" != "Linux" ]; then
    print_error "Server installation is only supported on Linux"
    exit 1
fi

# Create quanttime user
print_status "Creating quanttime user..."
if ! id "quanttime" &>/dev/null; then
    useradd -m -s /bin/bash quanttime
    usermod -aG sudo quanttime
    print_success "Created quanttime user"
else
    print_success "quanttime user already exists"
fi

# Create necessary directories
print_status "Creating directory structure..."
mkdir -p /opt/quanttime
mkdir -p /opt/quanttime/data/server
mkdir -p /opt/quanttime/models/server
mkdir -p /opt/quanttime/cache/server
mkdir -p /opt/quanttime/temp/server
mkdir -p /opt/quanttime/logs
mkdir -p /opt/quanttime/backups
mkdir -p /opt/quanttime/config

# Set ownership
chown -R quanttime:quanttime /opt/quanttime

# Install system dependencies
print_status "Installing system dependencies..."

# Detect Linux distribution
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
    VER=$VERSION_ID
else
    print_error "Cannot detect Linux distribution"
    exit 1
fi

case $OS in
    "Ubuntu"|"Debian GNU/Linux")
        print_status "Installing dependencies for Ubuntu/Debian..."
        apt-get update
        apt-get install -y python3 python3-pip python3-venv git curl wget
        apt-get install -y build-essential libssl-dev libffi-dev
        apt-get install -y zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev
        apt-get install -y libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev
        apt-get install -y postgresql postgresql-contrib postgresql-client
        apt-get install -y nginx supervisor cron logrotate
        apt-get install -y htop iotop nethogs
        ;;
    "CentOS Linux"|"Red Hat Enterprise Linux")
        print_status "Installing dependencies for CentOS/RHEL..."
        yum update -y
        yum install -y python3 python3-pip python3-devel git curl wget
        yum install -y gcc gcc-c++ make openssl-devel libffi-devel
        yum install -y zlib-devel bzip2-devel readline-devel sqlite-devel
        yum install -y postgresql postgresql-server postgresql-contrib
        yum install -y nginx supervisor cronie logrotate
        yum install -y htop iotop nethogs
        ;;
    *)
        print_error "Unsupported Linux distribution: $OS"
        exit 1
        ;;
esac

# Switch to quanttime user for Python setup
print_status "Setting up Python environment..."
su - quanttime << 'EOF'

# Create virtual environment
cd /opt/quanttime
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install Python dependencies
pip install -r requirements.txt

# Install additional server-specific packages
pip install psutil  # System monitoring
pip install paramiko  # SSH connectivity
pip install watchdog  # File system monitoring
pip install schedule  # Job scheduling
pip install zstandard  # High-performance compression
pip install psycopg2-binary  # PostgreSQL adapter
pip install redis  # Redis for caching
pip install celery  # Task queue
pip install flower  # Celery monitoring
pip install prometheus-client  # Metrics collection
pip install grafana-api  # Grafana integration

# Install web framework for API
pip install fastapi uvicorn

# Install monitoring tools
pip install prometheus-client
pip install grafana-api

EOF

# Set up PostgreSQL
print_status "Setting up PostgreSQL..."
: "${POSTGRES_PASSWORD:?export POSTGRES_PASSWORD before running this script}"
if [ "$OS" = "Ubuntu" ] || [ "$OS" = "Debian GNU/Linux" ]; then
    systemctl start postgresql
    systemctl enable postgresql
    
    # Create database and user
    sudo -u postgres psql << EOF
CREATE DATABASE quanttime;
CREATE USER quanttime WITH PASSWORD '${POSTGRES_PASSWORD}';
GRANT ALL PRIVILEGES ON DATABASE quanttime TO quanttime;
ALTER USER quanttime CREATEDB;
EOF
elif [ "$OS" = "CentOS Linux" ] || [ "$OS" = "Red Hat Enterprise Linux" ]; then
    postgresql-setup initdb
    systemctl start postgresql
    systemctl enable postgresql
    
    # Create database and user
    sudo -u postgres psql << EOF
CREATE DATABASE quanttime;
CREATE USER quanttime WITH PASSWORD '${POSTGRES_PASSWORD}';
GRANT ALL PRIVILEGES ON DATABASE quanttime TO quanttime;
ALTER USER quanttime CREATEDB;
EOF
fi

# Set up SSH keys
print_status "Setting up SSH configuration..."
su - quanttime << 'EOF'
mkdir -p ~/.ssh
if [ ! -f ~/.ssh/id_rsa ]; then
    ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ""
fi

# Create SSH config
cat > ~/.ssh/config << 'SSHCONFIG'
# QuantTime SSH Configuration
Host laptop
    HostName your-laptop-ip
    User your-laptop-user
    Port 22
    IdentityFile ~/.ssh/id_rsa
    StrictHostKeyChecking no

Host desktop
    HostName your-desktop-ip
    User your-desktop-user
    Port 22
    IdentityFile ~/.ssh/id_rsa
    StrictHostKeyChecking no
SSHCONFIG

chmod 600 ~/.ssh/config
chmod 600 ~/.ssh/id_rsa
chmod 644 ~/.ssh/id_rsa.pub
EOF

# Set up environment variables
print_status "Setting up environment variables..."
cat > /opt/quanttime/.env << EOF
# QuantTime Server Environment Variables
QUANTTIME_DEPLOYMENT=server
QUANTTIME_NODE_TYPE=server
QUANTTIME_CONFIG_PATH=server/config/deployment.yaml
QUANTTIME_DATA_PATH=data/server
QUANTTIME_MODELS_PATH=models/server
QUANTTIME_CACHE_PATH=cache/server
QUANTTIME_TEMP_PATH=temp/server
QUANTTIME_LOGS_PATH=logs

# Database
DATABASE_URL=postgresql://quanttime:${POSTGRES_PASSWORD}@localhost/quanttime

# API Keys (set these manually)
# DATABENTO_API_KEY=your_databento_api_key_here

# Performance
QUANTTIME_MAX_WORKERS=16
QUANTTIME_BATCH_SIZE=1000
QUANTTIME_CACHE_SIZE=2GB

# Monitoring
QUANTTIME_MONITORING_ENABLED=true
QUANTTIME_METRICS_INTERVAL=60

# Redis
REDIS_URL=redis://localhost:6379/0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
EOF

chown quanttime:quanttime /opt/quanttime/.env

# Set up Redis
print_status "Setting up Redis..."
if [ "$OS" = "Ubuntu" ] || [ "$OS" = "Debian GNU/Linux" ]; then
    apt-get install -y redis-server
    systemctl start redis-server
    systemctl enable redis-server
elif [ "$OS" = "CentOS Linux" ] || [ "$OS" = "Red Hat Enterprise Linux" ]; then
    yum install -y redis
    systemctl start redis
    systemctl enable redis
fi

# Set up Nginx
print_status "Setting up Nginx..."
cat > /etc/nginx/sites-available/quanttime << 'EOF'
server {
    listen 80;
    server_name your-server-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /flower {
        proxy_pass http://127.0.0.1:5555;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /grafana {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

ln -sf /etc/nginx/sites-available/quanttime /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
systemctl restart nginx
systemctl enable nginx

# Set up systemd services
print_status "Setting up systemd services..."

# Data Collector Service
cat > /etc/systemd/system/quanttime-data-collector.service << 'EOF'
[Unit]
Description=QuantTime Data Collector
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=quanttime
Group=quanttime
WorkingDirectory=/opt/quanttime
Environment=PATH=/opt/quanttime/.venv/bin
ExecStart=/opt/quanttime/.venv/bin/python server/scripts/data_collector.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Data Warehouse Service
cat > /etc/systemd/system/quanttime-data-warehouse.service << 'EOF'
[Unit]
Description=QuantTime Data Warehouse
After=network.target postgresql.service

[Service]
Type=simple
User=quanttime
Group=quanttime
WorkingDirectory=/opt/quanttime
Environment=PATH=/opt/quanttime/.venv/bin
ExecStart=/opt/quanttime/.venv/bin/python server/scripts/data_warehouse.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Model Deployer Service
cat > /etc/systemd/system/quanttime-model-deployer.service << 'EOF'
[Unit]
Description=QuantTime Model Deployer
After=network.target postgresql.service

[Service]
Type=simple
User=quanttime
Group=quanttime
WorkingDirectory=/opt/quanttime
Environment=PATH=/opt/quanttime/.venv/bin
ExecStart=/opt/quanttime/.venv/bin/python server/scripts/model_deployer.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Monitoring Service
cat > /etc/systemd/system/quanttime-monitoring.service << 'EOF'
[Unit]
Description=QuantTime Monitoring
After=network.target

[Service]
Type=simple
User=quanttime
Group=quanttime
WorkingDirectory=/opt/quanttime
Environment=PATH=/opt/quanttime/.venv/bin
ExecStart=/opt/quanttime/.venv/bin/python server/scripts/monitoring.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Celery Worker Service
cat > /etc/systemd/system/quanttime-celery-worker.service << 'EOF'
[Unit]
Description=QuantTime Celery Worker
After=network.target redis.service

[Service]
Type=simple
User=quanttime
Group=quanttime
WorkingDirectory=/opt/quanttime
Environment=PATH=/opt/quanttime/.venv/bin
ExecStart=/opt/quanttime/.venv/bin/celery -A server.scripts.celery_app worker --loglevel=info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Celery Beat Service
cat > /etc/systemd/system/quanttime-celery-beat.service << 'EOF'
[Unit]
Description=QuantTime Celery Beat
After=network.target redis.service

[Service]
Type=simple
User=quanttime
Group=quanttime
WorkingDirectory=/opt/quanttime
Environment=PATH=/opt/quanttime/.venv/bin
ExecStart=/opt/quanttime/.venv/bin/celery -A server.scripts.celery_app beat --loglevel=info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Flower Service
cat > /etc/systemd/system/quanttime-flower.service << 'EOF'
[Unit]
Description=QuantTime Flower (Celery Monitoring)
After=network.target redis.service

[Service]
Type=simple
User=quanttime
Group=quanttime
WorkingDirectory=/opt/quanttime
Environment=PATH=/opt/quanttime/.venv/bin
ExecStart=/opt/quanttime/.venv/bin/celery -A server.scripts.celery_app flower --port=5555
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable services
systemctl daemon-reload
systemctl enable quanttime-data-collector
systemctl enable quanttime-data-warehouse
systemctl enable quanttime-model-deployer
systemctl enable quanttime-monitoring
systemctl enable quanttime-celery-worker
systemctl enable quanttime-celery-beat
systemctl enable quanttime-flower

# Set up cron jobs
print_status "Setting up cron jobs..."
su - quanttime << 'EOF'
# Daily backup at 2 AM
(crontab -l 2>/dev/null; echo "0 2 * * * cd /opt/quanttime && .venv/bin/python server/scripts/backup.py") | crontab -

# Health check every 5 minutes
(crontab -l 2>/dev/null; echo "*/5 * * * * cd /opt/quanttime && .venv/bin/python server/scripts/health_check.py") | crontab -

# Data cleanup every day at 3 AM
(crontab -l 2>/dev/null; echo "0 3 * * * cd /opt/quanttime && .venv/bin/python server/scripts/data_cleanup.py") | crontab -

# Log rotation every day at 4 AM
(crontab -l 2>/dev/null; echo "0 4 * * * cd /opt/quanttime && .venv/bin/python server/scripts/log_rotation.py") | crontab -
EOF

# Set up log rotation
print_status "Setting up log rotation..."
cat > /etc/logrotate.d/quanttime-server << 'EOF'
/opt/quanttime/logs/*.log {
    daily
    missingok
    rotate 90
    compress
    delaycompress
    notifempty
    create 644 quanttime quanttime
    postrotate
        systemctl reload quanttime-data-collector
        systemctl reload quanttime-data-warehouse
        systemctl reload quanttime-model-deployer
        systemctl reload quanttime-monitoring
    endscript
}
EOF

# Set up firewall
print_status "Setting up firewall..."
if command -v ufw &> /dev/null; then
    ufw allow ssh
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw allow 8000/tcp
    ufw allow 5555/tcp
    ufw allow 3000/tcp
    ufw --force enable
elif command -v firewall-cmd &> /dev/null; then
    firewall-cmd --permanent --add-service=ssh
    firewall-cmd --permanent --add-service=http
    firewall-cmd --permanent --add-service=https
    firewall-cmd --permanent --add-port=8000/tcp
    firewall-cmd --permanent --add-port=5555/tcp
    firewall-cmd --permanent --add-port=3000/tcp
    firewall-cmd --reload
fi

# Create startup script
print_status "Creating startup script..."
cat > /opt/quanttime/server/scripts/start_server.sh << 'EOF'
#!/bin/bash

# QuantTime Server Startup Script

set -e

echo "Starting QuantTime Server services..."

# Activate virtual environment
source /opt/quanttime/.venv/bin/activate

# Set environment variables
export QUANTTIME_DEPLOYMENT=server
export QUANTTIME_NODE_TYPE=server

# Start all services
systemctl start quanttime-data-collector
systemctl start quanttime-data-warehouse
systemctl start quanttime-model-deployer
systemctl start quanttime-monitoring
systemctl start quanttime-celery-worker
systemctl start quanttime-celery-beat
systemctl start quanttime-flower

echo "QuantTime Server services started"
echo "Check status with: systemctl status quanttime-*"
EOF

chmod +x /opt/quanttime/server/scripts/start_server.sh

# Create stop script
cat > /opt/quanttime/server/scripts/stop_server.sh << 'EOF'
#!/bin/bash

# QuantTime Server Stop Script

echo "Stopping QuantTime Server services..."

# Stop all services
systemctl stop quanttime-flower
systemctl stop quanttime-celery-beat
systemctl stop quanttime-celery-worker
systemctl stop quanttime-monitoring
systemctl stop quanttime-model-deployer
systemctl stop quanttime-data-warehouse
systemctl stop quanttime-data-collector

echo "QuantTime Server services stopped"
EOF

chmod +x /opt/quanttime/server/scripts/stop_server.sh

# Set permissions
chown -R quanttime:quanttime /opt/quanttime
chmod 755 /opt/quanttime/server/scripts/
chmod 644 /opt/quanttime/server/config/*.yaml
chmod 644 /opt/quanttime/.env

# Final setup
print_status "Performing final setup..."

# Test installation
print_status "Testing installation..."
su - quanttime << 'EOF'
cd /opt/quanttime
source .venv/bin/activate
python -c "import psutil, paramiko, watchdog, schedule, zstandard, psycopg2, redis, celery; print('All packages imported successfully')"
EOF

print_success "QuantTime Server installation completed successfully!"
print_status ""
print_status "Next steps:"
print_status "1. Edit /opt/quanttime/.env file and set your API keys"
print_status "2. Configure SSH access from laptop and desktop"
print_status "3. Update Nginx configuration with your domain"
print_status "4. Run: /opt/quanttime/server/scripts/start_server.sh"
print_status "5. Monitor logs in /opt/quanttime/logs/ directory"
print_status ""
print_status "Services will be available at:"
print_status "- Main API: http://your-server-ip:8000"
print_status "- Flower (Celery): http://your-server-ip:5555"
print_status "- Nginx: http://your-server-ip"
print_status ""
print_status "For more information, see server/docs/README.md"
