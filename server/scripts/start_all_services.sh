#!/bin/bash

# QuantTime Distributed Computing - Start All Services
# Comprehensive service startup script for the entire cluster

set -e

echo "🚀 Starting QuantTime Distributed Computing Cluster"
echo "=================================================="

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

# Function to check if service is running
check_service() {
    local service=$1
    if systemctl is-active --quiet $service; then
        print_success "$service is running"
        return 0
    else
        print_error "$service is not running"
        return 1
    fi
}

# Function to start service with retry
start_service() {
    local service=$1
    local max_attempts=3
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        print_status "Starting $service (attempt $attempt/$max_attempts)"
        
        if sudo systemctl start $service; then
            sleep 2
            if check_service $service; then
                print_success "$service started successfully"
                return 0
            fi
        fi
        
        attempt=$((attempt + 1))
        if [ $attempt -le $max_attempts ]; then
            print_warning "Retrying $service startup in 3 seconds..."
            sleep 3
        fi
    done
    
    print_error "Failed to start $service after $max_attempts attempts"
    return 1
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   print_error "This script must be run as root"
   exit 1
fi

# Navigate to project directory
cd /opt/quanttime || {
    print_error "QuantTime project directory not found at /opt/quanttime"
    exit 1
}

print_status "Checking project environment..."

# Check virtual environment
if [ ! -d ".venv" ]; then
    print_error "Python virtual environment not found"
    exit 1
fi

# Check configuration files
if [ ! -f "server/config/deployment.yaml" ]; then
    print_warning "Deployment config not found, using defaults"
fi

# Step 1: Start system dependencies
print_status "Step 1: Starting system dependencies..."

# Start Redis
print_status "Starting Redis..."
if ! systemctl is-active --quiet redis-server; then
    systemctl start redis-server
    sleep 2
fi
check_service redis-server

# Start PostgreSQL
print_status "Starting PostgreSQL..."
if ! systemctl is-active --quiet postgresql; then
    systemctl start postgresql
    sleep 3
fi
check_service postgresql

# Start Nginx
print_status "Starting Nginx..."
if ! systemctl is-active --quiet nginx; then
    systemctl start nginx
    sleep 2
fi
check_service nginx

print_success "System dependencies started"

# Step 2: Start QuantTime core services
print_status "Step 2: Starting QuantTime core services..."

# List of QuantTime services in startup order
services=(
    "quanttime-monitoring"
    "quanttime-data-collector"
    "quanttime-data-warehouse"
    "quanttime-celery-worker"
    "quanttime-celery-beat"
    "quanttime-model-deployer"
    "quanttime-flower"
)

# Start each service
for service in "${services[@]}"; do
    start_service $service
done

print_success "QuantTime core services started"

# Step 3: Health checks
print_status "Step 3: Performing health checks..."

# Wait for services to initialize
print_status "Waiting for services to initialize..."
sleep 10

# Check API endpoints
print_status "Checking API endpoints..."

if curl -f -s http://localhost:8000/api/v1/server/health > /dev/null; then
    print_success "Main API server is responding"
else
    print_warning "Main API server may still be starting up"
fi

# Check Redis connectivity
if redis-cli ping > /dev/null 2>&1; then
    print_success "Redis connectivity confirmed"
else
    print_error "Redis connectivity failed"
fi

# Check Celery workers
print_status "Checking Celery workers..."
worker_count=$(ps aux | grep -c '[c]elery.*worker' || true)
if [ $worker_count -gt 0 ]; then
    print_success "Celery workers are running ($worker_count processes)"
else
    print_warning "No Celery workers detected"
fi

# Step 4: Display service status
print_status "Step 4: Service status summary..."

echo ""
echo "🖥️  QuantTime Service Status:"
echo "================================"

for service in "${services[@]}" redis-server postgresql nginx; do
    if systemctl is-active --quiet $service; then
        echo -e "✅ $service: ${GREEN}RUNNING${NC}"
    else
        echo -e "❌ $service: ${RED}STOPPED${NC}"
    fi
done

# Step 5: Display access information
print_status "Step 5: Access information..."

echo ""
echo "🌐 Service Endpoints:"
echo "===================="
echo "• Main API Server: http://localhost:8000"
echo "• API Documentation: http://localhost:8000/docs"
echo "• Flower (Celery Monitor): http://localhost:5555"
echo "• Health Check: http://localhost:8000/api/v1/server/health"

echo ""
echo "📊 Monitoring Commands:"
echo "======================"
echo "• Check all services: systemctl status quanttime-*"
echo "• View logs: journalctl -u quanttime-* -f"
echo "• Check workers: celery -A server.scripts.celery_app inspect active"
echo "• Redis CLI: redis-cli"

echo ""
echo "🔧 Management Commands:"
echo "======================"
echo "• Stop all services: bash server/scripts/stop_server.sh"
echo "• Restart services: systemctl restart quanttime-*"
echo "• Check system resources: htop"

# Final status
failed_services=0
for service in "${services[@]}"; do
    if ! systemctl is-active --quiet $service; then
        failed_services=$((failed_services + 1))
    fi
done

if [ $failed_services -eq 0 ]; then
    print_success "🎉 QuantTime Distributed Computing Cluster started successfully!"
    echo ""
    echo "Your cluster is ready to handle quantitative trading workloads!"
    echo "All services are running and the system is operational."
else
    print_warning "⚠️  Cluster started with $failed_services service(s) having issues"
    echo ""
    echo "Check the logs for failed services:"
    echo "journalctl -u <service-name> -f"
fi

echo ""
print_status "Startup complete. Monitor the system via the dashboard or API endpoints."
