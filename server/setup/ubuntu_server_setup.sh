#!/bin/bash

# QuantTime Ubuntu 22.04 Server Setup Script
# Complete server setup for R630XL and R810 servers
# Includes static IP, Tailscale VPN, and all dependencies

set -e  # Exit on any error

echo "🚀 Starting QuantTime Ubuntu Server Setup..."

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

# Configuration variables
SERVER_NAME=""
STATIC_IP=""
GATEWAY=""
TAILSCALE_AUTH_KEY=""
GITHUB_TOKEN=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --server-name)
            SERVER_NAME="$2"
            shift 2
            ;;
        --static-ip)
            STATIC_IP="$2"
            shift 2
            ;;
        --gateway)
            GATEWAY="$2"
            shift 2
            ;;
        --tailscale-key)
            TAILSCALE_AUTH_KEY="$2"
            shift 2
            ;;
        --github-token)
            GITHUB_TOKEN="$2"
            shift 2
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate required parameters
if [[ -z "$SERVER_NAME" || -z "$STATIC_IP" || -z "$GATEWAY" || -z "$TAILSCALE_AUTH_KEY" ]]; then
    print_error "Usage: $0 --server-name <name> --static-ip <ip> --gateway <gateway> --tailscale-key <key> [--github-token <token>]"
    print_error "Example: $0 --server-name r630xl --static-ip jupiter --gateway 192.168.2.1 --tailscale-key tskey-xxx"
    exit 1
fi

print_status "Server Name: $SERVER_NAME"
print_status "Static IP: $STATIC_IP"
print_status "Gateway: $GATEWAY"

# Update system
print_status "Updating system packages..."
apt-get update
apt-get upgrade -y

# Install essential packages
print_status "Installing essential packages..."
apt-get install -y \
    curl \
    wget \
    git \
    vim \
    htop \
    iotop \
    nethogs \
    rsync \
    openssh-server \
    openssh-client \
    fail2ban \
    ufw \
    logrotate \
    postgresql \
    postgresql-contrib \
    redis-server \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    libpq-dev \
    libssl-dev \
    libffi-dev \
    pkg-config

# Configure static IP
print_status "Configuring static IP..."
INTERFACE=$(ip route | grep default | awk '{print $5}')
NETMASK="255.255.255.0"

# Backup original network config
cp /etc/netplan/00-installer-config.yaml /etc/netplan/00-installer-config.yaml.backup

# Create new network config
cat > /etc/netplan/00-installer-config.yaml << EOF
network:
  version: 2
  renderer: networkd
  ethernets:
    $INTERFACE:
      dhcp4: false
      addresses:
        - $STATIC_IP/$NETMASK
      gateway4: $GATEWAY
      nameservers:
        addresses: [8.8.8.8, 8.8.4.4]
EOF

# Apply network config
netplan apply

# Set hostname
print_status "Setting hostname..."
hostnamectl set-hostname $SERVER_NAME
echo "127.0.1.1 $SERVER_NAME" >> /etc/hosts

# Create quanttime user
print_status "Creating quanttime user..."
if ! id "quanttime" &>/dev/null; then
    useradd -m -s /bin/bash quanttime
    usermod -aG sudo quanttime
    echo "quanttime:${QUANTTIME_USER_PASSWORD:?export QUANTTIME_USER_PASSWORD before running this script}" | chpasswd
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
mkdir -p /opt/quanttime/scripts
mkdir -p /opt/quanttime/services

# Set ownership
chown -R quanttime:quanttime /opt/quanttime

# Install Tailscale
print_status "Installing Tailscale..."
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/jammy.noarmor.gpg | tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/jammy.tailscale-keyring.list | tee /etc/apt/sources.list.d/tailscale.list
apt-get update
apt-get install -y tailscale

# Start Tailscale
print_status "Starting Tailscale..."
tailscale up --authkey=$TAILSCALE_AUTH_KEY --hostname=$SERVER_NAME

# Configure firewall
print_status "Configuring firewall..."
ufw --force enable
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 22
ufw allow 80
ufw allow 443
ufw allow 8000
ufw allow 8501
ufw allow 5432
ufw allow 6379
ufw allow 5672
ufw allow 15672

# Configure fail2ban
print_status "Configuring fail2ban..."
systemctl enable fail2ban
systemctl start fail2ban

# Configure PostgreSQL
print_status "Configuring PostgreSQL..."
sudo -u postgres createuser --interactive quanttime
sudo -u postgres createdb quanttime
sudo -u postgres psql -c "ALTER USER quanttime PASSWORD '${POSTGRES_PASSWORD:?export POSTGRES_PASSWORD before running this script}';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE quanttime TO quanttime;"

# Configure Redis
print_status "Configuring Redis..."
systemctl enable redis-server
systemctl start redis-server

# Install Python dependencies
print_status "Installing Python dependencies..."
pip3 install --upgrade pip
pip3 install \
    fastapi \
    uvicorn \
    celery \
    redis \
    paramiko \
    psutil \
    requests \
    PyJWT \
    python-multipart \
    pandas \
    numpy \
    pyarrow \
    sqlalchemy \
    psycopg2-binary \
    pydantic \
    python-dotenv \
    pyzmq \
    streamlit \
    scikit-learn \
    lightgbm \
    torch \
    optuna \
    pyyaml \
    tabulate \
    typer \
    plotly \
    protobuf \
    grpcio-tools \
    zstandard \
    databento \
    pytz

# Create systemd services
print_status "Creating systemd services..."

# QuantTime API Server
cat > /etc/systemd/system/quanttime-api-server.service << EOF
[Unit]
Description=QuantTime API Server
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=quanttime
WorkingDirectory=/opt/quanttime
Environment=PATH=/usr/bin:/usr/local/bin
ExecStart=/usr/bin/python3 -m uvicorn server.core.server_api:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# QuantTime Data Collector
cat > /etc/systemd/system/quanttime-data-collector.service << EOF
[Unit]
Description=QuantTime Data Collector
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=quanttime
WorkingDirectory=/opt/quanttime
Environment=PATH=/usr/bin:/usr/local/bin
ExecStart=/usr/bin/python3 /opt/quanttime/scripts/data_collector.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# QuantTime Celery Worker
cat > /etc/systemd/system/quanttime-celery-worker.service << EOF
[Unit]
Description=QuantTime Celery Worker
After=network.target redis-server.service

[Service]
Type=simple
User=quanttime
WorkingDirectory=/opt/quanttime
Environment=PATH=/usr/bin:/usr/local/bin
ExecStart=/usr/bin/celery -A server.scripts.celery_app worker --loglevel=info --concurrency=4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# QuantTime Monitoring
cat > /etc/systemd/system/quanttime-monitoring.service << EOF
[Unit]
Description=QuantTime Monitoring
After=network.target

[Service]
Type=simple
User=quanttime
WorkingDirectory=/opt/quanttime
Environment=PATH=/usr/bin:/usr/local/bin
ExecStart=/usr/bin/python3 /opt/quanttime/scripts/monitoring.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable services
systemctl daemon-reload
systemctl enable quanttime-api-server
systemctl enable quanttime-data-collector
systemctl enable quanttime-celery-worker
systemctl enable quanttime-monitoring

# Create startup script
cat > /opt/quanttime/scripts/start_all_services.sh << 'EOF'
#!/bin/bash
# Start all QuantTime services

echo "Starting QuantTime services..."

# Start systemd services
systemctl start quanttime-api-server
systemctl start quanttime-data-collector
systemctl start quanttime-celery-worker
systemctl start quanttime-monitoring

echo "All services started!"
EOF

chmod +x /opt/quanttime/scripts/start_all_services.sh

# Create health check script
cat > /opt/quanttime/scripts/health_check.sh << 'EOF'
#!/bin/bash
# Health check script for QuantTime services

echo "=== QuantTime Health Check ==="
echo "Date: $(date)"
echo ""

# Check system resources
echo "System Resources:"
echo "CPU Usage: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)%"
echo "Memory Usage: $(free | grep Mem | awk '{printf("%.2f%%", $3/$2 * 100.0)}')"
echo "Disk Usage: $(df / | tail -1 | awk '{print $5}')"
echo ""

# Check services
echo "Service Status:"
systemctl is-active quanttime-api-server
systemctl is-active quanttime-data-collector
systemctl is-active quanttime-celery-worker
systemctl is-active quanttime-monitoring
echo ""

# Check network
echo "Network Status:"
echo "Tailscale IP: $(tailscale ip -4)"
echo "Local IP: $(hostname -I | awk '{print $1}')"
echo ""

# Check PostgreSQL
echo "PostgreSQL Status:"
systemctl is-active postgresql
echo ""

# Check Redis
echo "Redis Status:"
systemctl is-active redis-server
echo ""
EOF

chmod +x /opt/quanttime/scripts/health_check.sh

# Create crontab for regular health checks
(crontab -l 2>/dev/null; echo "*/5 * * * * /opt/quanttime/scripts/health_check.sh >> /opt/quanttime/logs/health_check.log 2>&1") | crontab -

# Set up log rotation
cat > /etc/logrotate.d/quanttime << EOF
/opt/quanttime/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 quanttime quanttime
    postrotate
        systemctl reload quanttime-api-server
    endscript
}
EOF

# Create environment file
cat > /opt/quanttime/.env << EOF
# QuantTime Server Environment
SERVER_NAME=$SERVER_NAME
DATABASE_URL=postgresql://quanttime:${POSTGRES_PASSWORD}@localhost:5432/quanttime
REDIS_URL=redis://localhost:6379/0
LOG_LEVEL=INFO
ENVIRONMENT=production
EOF

chown quanttime:quanttime /opt/quanttime/.env

# Final setup
print_status "Finalizing setup..."

# Set proper permissions
chown -R quanttime:quanttime /opt/quanttime

# Create symbolic links
ln -sf /opt/quanttime/scripts/start_all_services.sh /usr/local/bin/quanttime-start
ln -sf /opt/quanttime/scripts/health_check.sh /usr/local/bin/quanttime-health

# Print completion message
print_success "=== QuantTime Server Setup Complete ==="
print_success "Server Name: $SERVER_NAME"
print_success "Static IP: $STATIC_IP"
print_success "Tailscale IP: $(tailscale ip -4)"
print_success ""
print_success "Next steps:"
print_success "1. Clone the QuantTime repository:"
print_success "   sudo -u quanttime git clone https://github.com/your-repo/QuantTime.git /opt/quanttime/repo"
print_success ""
print_success "2. Start all services:"
print_success "   quanttime-start"
print_success ""
print_success "3. Check health status:"
print_success "   quanttime-health"
print_success ""
print_success "4. Access the API:"
print_success "   http://$(tailscale ip -4):8000"
print_success ""
print_success "Server is ready for QuantTime deployment!"

print_success "Configuring rsync for data transmission..."
# Create rsync configuration
cat > /etc/rsyncd.conf << 'EOF'
# QuantTime rsync configuration
[quanttime]
    path = /opt/quanttime
    comment = QuantTime data directory
    read only = no
    write only = no
    list = yes
    uid = quanttime
    gid = quanttime
    auth users = quanttime
    secrets file = /etc/rsyncd.secrets
    hosts allow = 192.168.2.0/24 100.64.0.0/10
    hosts deny = *
EOF

# Create rsync secrets file
echo "quanttime:${QUANTTIME_USER_PASSWORD}" > /etc/rsyncd.secrets
chmod 600 /etc/rsyncd.secrets

# Enable and start rsync service
systemctl enable rsync
systemctl start rsync
