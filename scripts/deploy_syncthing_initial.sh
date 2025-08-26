#!/bin/bash

# QuantTime Initial Syncthing Deployment
# This script handles the initial setup where we need to:
# 1. Install Syncthing on servers first
# 2. Configure basic folders
# 3. Sync the project over
# 4. Then configure the full QuantTime setup

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
PROJECT_NAME="quanttime"

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

# Step 1: Install Syncthing on servers
install_syncthing_on_servers() {
    log_info "Step 1: Installing Syncthing on servers..."
    
    for server in "${SERVERS[@]}"; do
        read -r ip username <<< "$(get_server_details "$server")"
        
        log_info "Installing Syncthing on $server ($ip)..."
        
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
            
            # Create initial project directory
            sudo mkdir -p /opt/quanttime
            sudo chown quanttime:quanttime /opt/quanttime
            
            # Create systemd service file
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
            
            # Wait for Syncthing to start and generate config
            sleep 15
            
            # Configure web interface to listen on all interfaces
            sudo -u quanttime sed -i 's/<address>127.0.0.1:8384<\/address>/<address>0.0.0.0:8384<\/address>/g' /home/quanttime/.config/syncthing/config.xml
            
            # Restart Syncthing to apply changes
            sudo systemctl restart syncthing@quanttime
            
            log_success "Syncthing installed and configured on $server"
EOF
        
        if [ $? -eq 0 ]; then
            log_success "✅ Syncthing installation completed on $server"
        else
            log_error "❌ Syncthing installation failed on $server"
            return 1
        fi
    done
}

# Step 2: Setup local Syncthing
setup_local_syncthing() {
    log_info "Step 2: Setting up local Syncthing..."
    
    # Check if Syncthing is installed
    if ! command -v syncthing &> /dev/null; then
        log_info "Installing Syncthing locally..."
        
        # Install Syncthing (Ubuntu/Debian)
        curl -s https://syncthing.net/release-key.txt | sudo apt-key add -
        echo 'deb https://apt.syncthing.net/ syncthing stable' | sudo tee /etc/apt/sources.list.d/syncthing.list
        sudo apt-get update
        sudo apt-get install -y syncthing
    fi
    
    # Create project directory
    sudo mkdir -p /opt/quanttime
    sudo chown $USER:$USER /opt/quanttime
    
    # Start Syncthing locally
    syncthing &
    sleep 10
    
    log_success "✅ Local Syncthing setup complete"
}

# Step 3: Get device IDs
get_device_ids() {
    log_info "Step 3: Collecting device IDs..."
    
    declare -A device_ids
    
    # Get local device ID
    local_device_id=$(cat ~/.config/syncthing/config.xml | grep -o 'device id="[^"]*"' | head -1 | cut -d'"' -f2)
    device_ids["laptop"]="$local_device_id"
    log_info "Local device ID: $local_device_id"
    
    # Get server device IDs
    for server in "${SERVERS[@]}"; do
        read -r ip username <<< "$(get_server_details "$server")"
        
        server_device_id=$(ssh "$username@$ip" "cat /home/quanttime/.config/syncthing/config.xml | grep -o 'device id=\"[^\"]*\"' | head -1 | cut -d'\"' -f2")
        device_ids["$server"]="$server_device_id"
        log_info "$server device ID: $server_device_id"
    done
    
    # Save device IDs to file
    for server in "${!device_ids[@]}"; do
        echo "$server:${device_ids[$server]}" >> /tmp/syncthing_device_ids.txt
    done
    
    log_success "✅ Device IDs collected and saved"
}

# Step 4: Create initial folder configuration
create_initial_folder_config() {
    log_info "Step 4: Creating initial folder configuration..."
    
    # Read device IDs
    declare -A device_ids
    while IFS=: read -r server device_id; do
        device_ids["$server"]="$device_id"
    done < /tmp/syncthing_device_ids.txt
    
    # Create initial folder config (just the project folder)
    cat > /tmp/initial_syncthing_config.json << EOF
{
  "folders": [
    {
      "id": "quanttime-project",
      "label": "QuantTime Project",
      "path": "/opt/quanttime",
      "type": "sendreceive",
      "devices": [
        {
          "deviceID": "${device_ids["laptop"]}",
          "introducedBy": "",
          "encryptionPassword": "",
          "skipIntroductionRemovals": false,
          "introducer": false,
          "compression": "metadata",
          "certName": "",
          "paused": false,
          "allowedNetworks": [],
          "autoAcceptFolders": false,
          "maxSendKbps": 0,
          "maxRecvKbps": 0,
          "ignoredFolders": [],
          "pendingFolders": [],
          "maxRequestKiB": 0
        }
EOF
    
    # Add server devices
    for server in "${SERVERS[@]}"; do
        cat >> /tmp/initial_syncthing_config.json << EOF
        ,
        {
          "deviceID": "${device_ids["$server"]}",
          "introducedBy": "",
          "encryptionPassword": "",
          "skipIntroductionRemovals": false,
          "introducer": false,
          "compression": "metadata",
          "certName": "",
          "paused": false,
          "allowedNetworks": [],
          "autoAcceptFolders": false,
          "maxSendKbps": 0,
          "maxRecvKbps": 0,
          "ignoredFolders": [],
          "pendingFolders": [],
          "maxRequestKiB": 0
        }
EOF
    done
    
    cat >> /tmp/initial_syncthing_config.json << EOF
      ],
      "rescanIntervalS": 3600,
      "fsWatcherEnabled": true,
      "fsWatcherDelayS": 10,
      "ignorePerms": false,
      "autoNormalize": true,
      "minDiskFree": {
        "unit": "GB",
        "value": 1
      },
      "versioning": {
        "type": "simple",
        "params": {
          "keep": "10"
        }
      },
      "copiers": 0,
      "pullerMaxPendingKiB": 0,
      "hashers": 0,
      "order": "random",
      "ignoreDelete": false,
      "scanProgressIntervalS": 0,
      "pullerPauseS": 0,
      "maxConflicts": 10,
      "disableSparseFiles": false,
      "disableTempIndexes": false,
      "paused": false,
      "weakHashThresholdPct": 25,
      "markerName": ".stfolder",
      "copyOwnershipFromParent": false,
      "modTimeWindowS": 0,
      "maxConcurrentWrites": 2,
      "disableFsync": false,
      "blockPullOrder": "standard",
      "copyRangeMethod": "standard",
      "caseSensitiveFS": false,
      "junctionsAsDirs": false,
      "syncOwnership": false,
      "sendOwnership": false,
      "syncXattrs": false,
      "sendXattrs": false,
      "xattrFilter": {
        "entries": null,
        "maxSingleEntrySize": 0,
        "maxTotalSize": 0
      }
    }
  ]
}
EOF
    
    log_success "✅ Initial folder configuration created"
}

# Step 5: Deploy initial configuration to servers
deploy_initial_config() {
    log_info "Step 5: Deploying initial configuration to servers..."
    
    for server in "${SERVERS[@]}"; do
        read -r ip username <<< "$(get_server_details "$server")"
        
        log_info "Deploying config to $server..."
        
        # Upload config file
        scp /tmp/initial_syncthing_config.json "$username@$ip:/tmp/"
        
        # Apply configuration
        ssh "$username@$ip" << 'EOF'
            # Wait for Syncthing to be ready
            sleep 10
            
            # Apply folder configuration via API
            curl -X POST http://localhost:8384/rest/config/folders \
                -H "Content-Type: application/json" \
                -d @/tmp/initial_syncthing_config.json
            
            # Restart Syncthing to apply changes
            sudo systemctl restart syncthing@quanttime
            
            log_success "Configuration applied to $server"
EOF
        
        if [ $? -eq 0 ]; then
            log_success "✅ Configuration deployed to $server"
        else
            log_error "❌ Configuration deployment failed on $server"
        fi
    done
}

# Step 6: Apply configuration locally
apply_local_config() {
    log_info "Step 6: Applying configuration locally..."
    
    # Apply folder configuration via API
    curl -X POST http://localhost:8384/rest/config/folders \
        -H "Content-Type: application/json" \
        -d @/tmp/initial_syncthing_config.json
    
    log_success "✅ Local configuration applied"
}

# Step 7: Copy project to local Syncthing folder
copy_project_to_sync() {
    log_info "Step 7: Copying project to Syncthing folder..."
    
    # Copy current project to /opt/quanttime
    rsync -av --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' \
        ./ /opt/quanttime/
    
    log_success "✅ Project copied to Syncthing folder"
}

# Step 8: Wait for initial sync
wait_for_initial_sync() {
    log_info "Step 8: Waiting for initial sync to complete..."
    
    log_info "Waiting 60 seconds for initial sync..."
    sleep 60
    
    # Check sync status on servers
    for server in "${SERVERS[@]}"; do
        read -r ip username <<< "$(get_server_details "$server")"
        
        log_info "Checking sync status on $server..."
        
        # Check if project files exist
        ssh "$username@$ip" "ls -la /opt/quanttime/" || log_warning "Files not yet synced to $server"
    done
    
    log_success "✅ Initial sync phase completed"
}

# Step 9: Deploy full QuantTime setup
deploy_full_setup() {
    log_info "Step 9: Deploying full QuantTime setup..."
    
    # Now that the project is synced, run the full setup
    for server in "${SERVERS[@]}"; do
        read -r ip username <<< "$(get_server_details "$server")"
        
        log_info "Running full setup on $server..."
        
        ssh "$username@$ip" << 'EOF'
            cd /opt/quanttime
            
            # Create additional directories
            mkdir -p data models logs config
            
            # Set up Python environment
            python3 -m venv venv
            source venv/bin/activate
            pip install --upgrade pip
            pip install -r requirements.txt
            
            # Set up systemd services
            sudo cp server/setup/syncthing.service /etc/systemd/system/
            sudo systemctl daemon-reload
            
            log_success "Full setup completed on $server"
EOF
        
        if [ $? -eq 0 ]; then
            log_success "✅ Full setup completed on $server"
        else
            log_error "❌ Full setup failed on $server"
        fi
    done
}

# Main deployment function
main() {
    log_info "🚀 Starting initial Syncthing deployment..."
    
    # Check prerequisites
    if [ ! -f "$CONFIG_FILE" ]; then
        log_error "Configuration file not found: $CONFIG_FILE"
        exit 1
    fi
    
    if ! command -v jq &> /dev/null; then
        log_error "jq is required but not installed. Please install jq first."
        exit 1
    fi
    
    # Execute deployment steps
    install_syncthing_on_servers || exit 1
    setup_local_syncthing || exit 1
    get_device_ids || exit 1
    create_initial_folder_config || exit 1
    deploy_initial_config || exit 1
    apply_local_config || exit 1
    copy_project_to_sync || exit 1
    wait_for_initial_sync || exit 1
    deploy_full_setup || exit 1
    
    log_success "🎉 Initial Syncthing deployment completed successfully!"
    
    # Display next steps
    echo ""
    log_info "Next steps:"
    echo "1. Access Syncthing web interfaces:"
    for server in "${SERVERS[@]}"; do
        read -r ip username <<< "$(get_server_details "$server")"
        echo "   - $server: http://$ip:8384"
    done
    echo "   - Local: http://localhost:8384"
    echo ""
    echo "2. Run the full QuantTime setup:"
    echo "   python scripts/setup_syncthing.py --action full"
    echo ""
    echo "3. Monitor sync status:"
    echo "   python scripts/setup_syncthing.py --action test"
}

# Show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  -s, --step     Run specific step (1-9)"
    echo ""
    echo "Steps:"
    echo "  1. Install Syncthing on servers"
    echo "  2. Setup local Syncthing"
    echo "  3. Get device IDs"
    echo "  4. Create initial folder config"
    echo "  5. Deploy initial config to servers"
    echo "  6. Apply local config"
    echo "  7. Copy project to sync folder"
    echo "  8. Wait for initial sync"
    echo "  9. Deploy full setup"
}

# Parse command line arguments
STEP=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_usage
            exit 0
            ;;
        -s|--step)
            STEP="$2"
            shift 2
            ;;
        *)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Execute specific step or full deployment
if [ -n "$STEP" ]; then
    case $STEP in
        1) install_syncthing_on_servers ;;
        2) setup_local_syncthing ;;
        3) get_device_ids ;;
        4) create_initial_folder_config ;;
        5) deploy_initial_config ;;
        6) apply_local_config ;;
        7) copy_project_to_sync ;;
        8) wait_for_initial_sync ;;
        9) deploy_full_setup ;;
        *)
            log_error "Invalid step: $STEP. Valid steps: 1-9"
            exit 1
            ;;
    esac
else
    main
fi
