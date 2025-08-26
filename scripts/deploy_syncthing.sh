#!/bin/bash

# QuantTime Syncthing Deployment Script
# Deploys Syncthing to all servers in the cluster

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CONFIG_FILE="server/config/servers.json"
SERVERS=("r630xl" "r810")

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to get server details from config
get_server_details() {
    local server_name=$1
    local ip=$(jq -r ".$server_name.tailscale_ip" "$CONFIG_FILE")
    local username=$(jq -r ".$server_name.username" "$CONFIG_FILE")
    echo "$ip $username"
}

# Function to install Syncthing on a server
install_syncthing_on_server() {
    local server_name=$1
    local ip=$2
    local username=$3
    
    log_info "Installing Syncthing on $server_name ($ip)..."
    
    # SSH commands to install Syncthing
    ssh "$username@$ip" << 'EOF'
        # Add Syncthing repository
        curl -s https://syncthing.net/release-key.txt | sudo apt-key add -
        echo 'deb https://apt.syncthing.net/ syncthing stable' | sudo tee /etc/apt/sources.list.d/syncthing.list
        
        # Update package list
        sudo apt-get update
        
        # Install Syncthing
        sudo apt-get install -y syncthing
        
        # Create quanttime user if it doesn't exist
        if ! id "quanttime" &>/dev/null; then
            sudo useradd -m -s /bin/bash quanttime
            sudo usermod -aG sudo quanttime
        fi
        
        # Create project directories
        sudo mkdir -p /opt/quanttime
        sudo chown quanttime:quanttime /opt/quanttime
        
        # Create data directories
        sudo -u quanttime mkdir -p /opt/quanttime/data
        sudo -u quanttime mkdir -p /opt/quanttime/models
        sudo -u quanttime mkdir -p /opt/quanttime/logs
        sudo -u quanttime mkdir -p /opt/quanttime/config
        
        # Copy systemd service file
        sudo tee /etc/systemd/system/syncthing@quanttime.service > /dev/null << 'SERVICE_EOF'
[Unit]
Description=Syncthing - Continuous File Synchronization
Documentation=man:syncthing(1)
After=network.target
Wants=network.target

[Service]
Type=simple
User=quanttime
Group=quanttime
ExecStart=/usr/bin/syncthing serve --no-browser --no-restart --logflags=0
Restart=on-failure
RestartSec=5
SuccessExitStatus=3 4
RestartForceExitStatus=3 4

# Hardening
ProtectSystem=strict
ReadWritePaths=/opt/quanttime /home/quanttime/.config/syncthing
PrivateTmp=true
ProtectHome=true
NoNewPrivileges=true
PrivateDevices=true

# Resource limits
LimitNOFILE=65536
LimitNPROC=4096

[Install]
WantedBy=multi-user.target
SERVICE_EOF
        
        # Reload systemd and enable service
        sudo systemctl daemon-reload
        sudo systemctl enable syncthing@quanttime
        
        # Start Syncthing
        sudo systemctl start syncthing@quanttime
        
        # Wait for Syncthing to start
        sleep 10
        
        # Configure web interface to listen on all interfaces
        sudo -u quanttime sed -i 's/<address>127.0.0.1:8384<\/address>/<address>0.0.0.0:8384<\/address>/g' /home/quanttime/.config/syncthing/config.xml
        
        # Restart Syncthing to apply changes
        sudo systemctl restart syncthing@quanttime
        
        log_success "Syncthing installed and configured on $server_name"
EOF
    
    if [ $? -eq 0 ]; then
        log_success "Syncthing installation completed on $server_name"
        return 0
    else
        log_error "Syncthing installation failed on $server_name"
        return 1
    fi
}

# Function to test Syncthing connection
test_syncthing_connection() {
    local server_name=$1
    local ip=$2
    
    log_info "Testing Syncthing connection to $server_name ($ip)..."
    
    # Test web interface
    if curl -s -f "http://$ip:8384" > /dev/null; then
        log_success "Syncthing web interface accessible on $server_name"
        return 0
    else
        log_error "Syncthing web interface not accessible on $server_name"
        return 1
    fi
}

# Function to get device ID from server
get_device_id() {
    local server_name=$1
    local ip=$2
    local username=$3
    
    log_info "Getting device ID from $server_name..."
    
    local device_id=$(ssh "$username@$ip" "cat /home/quanttime/.config/syncthing/config.xml | grep -o 'device id=\"[^\"]*\"' | head -1 | cut -d'\"' -f2")
    
    if [ -n "$device_id" ]; then
        log_success "Device ID for $server_name: $device_id"
        echo "$device_id"
    else
        log_error "Could not get device ID from $server_name"
        echo ""
    fi
}

# Main deployment function
deploy_syncthing() {
    log_info "Starting Syncthing deployment..."
    
    # Check if config file exists
    if [ ! -f "$CONFIG_FILE" ]; then
        log_error "Configuration file not found: $CONFIG_FILE"
        exit 1
    fi
    
    # Check if jq is installed
    if ! command -v jq &> /dev/null; then
        log_error "jq is required but not installed. Please install jq first."
        exit 1
    fi
    
    # Deploy to each server
    for server in "${SERVERS[@]}"; do
        log_info "Processing server: $server"
        
        # Get server details
        read -r ip username <<< "$(get_server_details "$server")"
        
        if [ -z "$ip" ] || [ -z "$username" ]; then
            log_error "Could not get server details for $server"
            continue
        fi
        
        # Install Syncthing
        if install_syncthing_on_server "$server" "$ip" "$username"; then
            # Test connection
            if test_syncthing_connection "$server" "$ip"; then
                # Get device ID
                device_id=$(get_device_id "$server" "$ip" "$username")
                if [ -n "$device_id" ]; then
                    echo "$server:$device_id" >> /tmp/syncthing_device_ids.txt
                fi
            fi
        fi
        
        echo ""
    done
    
    log_success "Syncthing deployment completed!"
    
    # Display device IDs if collected
    if [ -f /tmp/syncthing_device_ids.txt ]; then
        log_info "Device IDs collected:"
        cat /tmp/syncthing_device_ids.txt
        rm /tmp/syncthing_device_ids.txt
    fi
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  -s, --server   Deploy to specific server (r630xl or r810)"
    echo "  -t, --test     Test connections only"
    echo ""
    echo "Examples:"
    echo "  $0                    # Deploy to all servers"
    echo "  $0 -s r630xl          # Deploy to R630XL only"
    echo "  $0 -t                 # Test connections only"
}

# Parse command line arguments
SERVER_ONLY=""
TEST_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_usage
            exit 0
            ;;
        -s|--server)
            SERVER_ONLY="$2"
            shift 2
            ;;
        -t|--test)
            TEST_ONLY=true
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Main execution
if [ "$TEST_ONLY" = true ]; then
    log_info "Testing Syncthing connections..."
    
    for server in "${SERVERS[@]}"; do
        read -r ip username <<< "$(get_server_details "$server")"
        test_syncthing_connection "$server" "$ip"
    done
    
elif [ -n "$SERVER_ONLY" ]; then
    if [[ " ${SERVERS[*]} " =~ " ${SERVER_ONLY} " ]]; then
        read -r ip username <<< "$(get_server_details "$SERVER_ONLY")"
        install_syncthing_on_server "$SERVER_ONLY" "$ip" "$username"
        test_syncthing_connection "$SERVER_ONLY" "$ip"
    else
        log_error "Invalid server: $SERVER_ONLY. Valid servers: ${SERVERS[*]}"
        exit 1
    fi
else
    deploy_syncthing
fi
