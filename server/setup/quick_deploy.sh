#!/bin/bash

# QuantTime Quick Deployment Script
# Quickly deploy and configure the distributed computing cluster

set -e

echo "🚀 QuantTime Quick Deployment Script"
echo "===================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check if running from project root
if [ ! -f "quanttime/__init__.py" ]; then
    print_error "Please run this script from the QuantTime project root directory"
    exit 1
fi

# Check dependencies
print_status "Checking dependencies..."

if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is required but not installed"
    exit 1
fi

if ! command -v ssh &> /dev/null; then
    print_error "SSH is required but not installed"
    exit 1
fi

if ! command -v rsync &> /dev/null; then
    print_error "rsync is required but not installed"
    exit 1
fi

print_success "Dependencies check passed"

# Create necessary directories
print_status "Creating directory structure..."
mkdir -p logs
mkdir -p data/server
mkdir -p models/server
mkdir -p results/server
mkdir -p temp/server
mkdir -p backups

print_success "Directory structure created"

# Install Python dependencies
print_status "Installing Python dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    print_success "Python dependencies installed"
else
    print_warning "requirements.txt not found, skipping Python dependencies"
fi

# Generate server configuration
print_status "Generating server configuration..."
python3 server/setup/configure_servers.py networking

# Set up environment variables
print_status "Setting up environment variables..."
if [ ! -f ".env" ]; then
    cat > .env << EOF
# QuantTime Environment Configuration
QUANTTIME_DEPLOYMENT=laptop
QUANTTIME_NODE_TYPE=control
QUANTTIME_SERVER_HOST=0.0.0.0
QUANTTIME_SERVER_PORT=8000
QUANTTIME_SERVER_WORKERS=1

# Database
DATABASE_URL=sqlite:///quanttime.db

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# API Keys (set these manually)
# DATABENTO_API_KEY=your_databento_api_key_here

# Monitoring
QUANTTIME_MONITORING_ENABLED=true
QUANTTIME_METRICS_INTERVAL=60

# Performance
QUANTTIME_MAX_WORKERS=8
QUANTTIME_BATCH_SIZE=1000
QUANTTIME_CACHE_SIZE=1GB
EOF
    print_success "Environment file created (.env)"
else
    print_warning "Environment file already exists (.env)"
fi

# Server deployment options
echo ""
echo "🖥️ Server Deployment Options:"
echo "1. Local only (laptop control center)"
echo "2. Deploy to all servers (full cluster)"
echo "3. Configure servers only (no deployment)"
echo "4. Check server status"

read -p "Select option (1-4): " option

case $option in
    1)
        print_status "Setting up local control center only..."
        
        # Start local services
        print_status "Starting local services..."
        
        # Check if Redis is running
        if ! pgrep -x "redis-server" > /dev/null; then
            print_warning "Redis not running. Please start Redis manually:"
            print_warning "  sudo systemctl start redis"
            print_warning "  or: redis-server"
        fi
        
        print_success "Local setup completed!"
        print_status "You can now run:"
        print_status "  streamlit run quanttime/dashboard/app.py"
        ;;
        
    2)
        print_status "Deploying to all servers..."
        
        # Full server deployment
        python3 server/setup/configure_servers.py setup
        
        print_success "Full cluster deployment completed!"
        ;;
        
    3)
        print_status "Configuring servers..."
        
        # Configure servers without deployment
        python3 server/setup/configure_servers.py ssh-keys
        python3 server/setup/configure_servers.py networking
        
        print_success "Server configuration completed!"
        ;;
        
    4)
        print_status "Checking server status..."
        
        # Check server status
        python3 server/setup/configure_servers.py status
        ;;
        
    *)
        print_error "Invalid option selected"
        exit 1
        ;;
esac

# Final instructions
echo ""
print_success "QuantTime deployment completed!"
echo ""
print_status "Next steps:"
print_status "1. Set your API keys in the .env file"
print_status "2. Configure server IP addresses in server/config/servers.json"
print_status "3. Run the dashboard: streamlit run quanttime/dashboard/app.py"
print_status "4. Access the server control center in the 'Servers' tab"
echo ""
print_status "For more information, see:"
print_status "  - docs/SERVER_SETUP.md"
print_status "  - server/docs/README.md"
echo ""
