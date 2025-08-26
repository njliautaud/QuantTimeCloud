# QuantTime Initial Syncthing Deployment (PowerShell)
# This script handles the initial setup where we need to:
# 1. Install Syncthing on servers first
# 2. Configure basic folders
# 3. Sync the project over
# 4. Then configure the full QuantTime setup

param(
    [string]$Step = "",
    [switch]$Help
)

# Configuration
$ConfigFile = "server/config/servers.json"
$Servers = @("r630xl", "r810")
$ProjectName = "quanttime"

# Colors for output
$Red = "Red"
$Green = "Green"
$Yellow = "Yellow"
$Blue = "Blue"

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor $Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor $Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor $Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor $Red
}

# Function to get server details from config
function Get-ServerDetails {
    param([string]$ServerName)
    
    $config = Get-Content $ConfigFile | ConvertFrom-Json
    $server = $config.$ServerName
    
    return @{
        IP = $server.tailscale_ip
        Username = $server.username
    }
}

# Step 1: Install Syncthing on servers
function Install-SyncthingOnServers {
    Write-Info "Step 1: Installing Syncthing on servers..."
    
    foreach ($server in $Servers) {
        $details = Get-ServerDetails $server
        $ip = $details.IP
        $username = $details.Username
        
        Write-Info "Installing Syncthing on $server ($ip)..."
        
        $installScript = @"
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
"@
        
        # Execute SSH command
        $result = ssh "${username}@${ip}" $installScript
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "✅ Syncthing installation completed on $server"
        } else {
            Write-Error "❌ Syncthing installation failed on $server"
            return $false
        }
    }
    
    return $true
}

# Step 2: Setup local Syncthing
function Setup-LocalSyncthing {
    Write-Info "Step 2: Setting up local Syncthing..."
    
    # Check if Syncthing is installed
    try {
        $null = Get-Command syncthing -ErrorAction Stop
        Write-Info "Syncthing is already installed"
    } catch {
        Write-Info "Installing Syncthing locally..."
        
        # For Windows, we'll use Chocolatey or direct download
        if (Get-Command choco -ErrorAction SilentlyContinue) {
            choco install syncthing -y
        } else {
            Write-Warning "Chocolatey not found. Please install Syncthing manually from https://syncthing.net/"
            return $false
        }
    }
    
    # Create project directory (Windows equivalent)
    $projectDir = "C:\opt\quanttime"
    if (!(Test-Path $projectDir)) {
        New-Item -ItemType Directory -Path $projectDir -Force
    }
    
    # Start Syncthing
    Start-Process syncthing -WindowStyle Hidden
    Start-Sleep -Seconds 10
    
    Write-Success "✅ Local Syncthing setup complete"
    return $true
}

# Step 3: Get device IDs
function Get-DeviceIds {
    Write-Info "Step 3: Collecting device IDs..."
    
    $deviceIds = @{}
    
    # Get local device ID (Windows path)
    $localConfigPath = "$env:APPDATA\Syncthing\config.xml"
    if (Test-Path $localConfigPath) {
        $configContent = Get-Content $localConfigPath -Raw
        if ($configContent -match 'device id="([^"]*)"') {
            $localDeviceId = $matches[1]
            $deviceIds["laptop"] = $localDeviceId
            Write-Info "Local device ID: $localDeviceId"
        }
    }
    
    # Get server device IDs
    foreach ($server in $Servers) {
        $details = Get-ServerDetails $server
        $ip = $details.IP
        $username = $details.Username
        
        $serverDeviceId = ssh "${username}@${ip}" "cat /home/quanttime/.config/syncthing/config.xml | grep -o 'device id=\"[^\"]*\"' | head -1 | cut -d'\"' -f2"
        $deviceIds[$server] = $serverDeviceId
        Write-Info "$server device ID: $serverDeviceId"
    }
    
    # Save device IDs to file
    $deviceIds.GetEnumerator() | ForEach-Object {
        "$($_.Key):$($_.Value)" | Out-File -FilePath "$env:TEMP\syncthing_device_ids.txt" -Append
    }
    
    Write-Success "✅ Device IDs collected and saved"
    return $true
}

# Step 4: Create initial folder configuration
function Create-InitialFolderConfig {
    Write-Info "Step 4: Creating initial folder configuration..."
    
    # Read device IDs
    $deviceIds = @{}
    Get-Content "$env:TEMP\syncthing_device_ids.txt" | ForEach-Object {
        $parts = $_ -split ":"
        $deviceIds[$parts[0]] = $parts[1]
    }
    
    # Create initial folder config
    $config = @{
        folders = @(
            @{
                id = "quanttime-project"
                label = "QuantTime Project"
                path = "C:\opt\quanttime"
                type = "sendreceive"
                devices = @()
            }
        )
    }
    
    # Add devices
    foreach ($device in $deviceIds.GetEnumerator()) {
        $config.folders[0].devices += @{
            deviceID = $device.Value
            introducedBy = ""
            encryptionPassword = ""
            skipIntroductionRemovals = $false
            introducer = $false
            compression = "metadata"
            certName = ""
            paused = $false
            allowedNetworks = @()
            autoAcceptFolders = $false
            maxSendKbps = 0
            maxRecvKbps = 0
            ignoredFolders = @()
            pendingFolders = @()
            maxRequestKiB = 0
        }
    }
    
    # Save config
    $config | ConvertTo-Json -Depth 10 | Out-File -FilePath "$env:TEMP\initial_syncthing_config.json"
    
    Write-Success "✅ Initial folder configuration created"
    return $true
}

# Step 5: Deploy initial configuration to servers
function Deploy-InitialConfig {
    Write-Info "Step 5: Deploying initial configuration to servers..."
    
    foreach ($server in $Servers) {
        $details = Get-ServerDetails $server
        $ip = $details.IP
        $username = $details.Username
        
        Write-Info "Deploying config to $server..."
        
        # Upload config file
        scp "$env:TEMP\initial_syncthing_config.json" "${username}@${ip}:/tmp/"
        
        # Apply configuration
        $applyScript = @"
# Wait for Syncthing to be ready
sleep 10

# Apply folder configuration via API
curl -X POST http://localhost:8384/rest/config/folders \
    -H "Content-Type: application/json" \
    -d @/tmp/initial_syncthing_config.json

# Restart Syncthing to apply changes
sudo systemctl restart syncthing@quanttime
"@
        
        $result = ssh "${username}@${ip}" $applyScript
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "✅ Configuration deployed to $server"
        } else {
            Write-Error "❌ Configuration deployment failed on $server"
        }
    }
    
    return $true
}

# Step 6: Apply configuration locally
function Apply-LocalConfig {
    Write-Info "Step 6: Applying configuration locally..."
    
    # Apply folder configuration via API
    $configContent = Get-Content "$env:TEMP\initial_syncthing_config.json" -Raw
    $response = Invoke-RestMethod -Uri "http://localhost:8384/rest/config/folders" -Method POST -Body $configContent -ContentType "application/json"
    
    Write-Success "✅ Local configuration applied"
    return $true
}

# Step 7: Copy project to local Syncthing folder
function Copy-ProjectToSync {
    Write-Info "Step 7: Copying project to Syncthing folder..."
    
    # Copy current project to C:\opt\quanttime
    $sourceDir = Get-Location
    $targetDir = "C:\opt\quanttime"
    
    # Create target directory if it doesn't exist
    if (!(Test-Path $targetDir)) {
        New-Item -ItemType Directory -Path $targetDir -Force
    }
    
    # Copy files (excluding .git, __pycache__, etc.)
    Get-ChildItem -Path $sourceDir -Exclude @(".git", "__pycache__", "*.pyc", ".venv") | Copy-Item -Destination $targetDir -Recurse -Force
    
    Write-Success "✅ Project copied to Syncthing folder"
    return $true
}

# Step 8: Wait for initial sync
function Wait-ForInitialSync {
    Write-Info "Step 8: Waiting for initial sync to complete..."
    
    Write-Info "Waiting 60 seconds for initial sync..."
    Start-Sleep -Seconds 60
    
    # Check sync status on servers
    foreach ($server in $Servers) {
        $details = Get-ServerDetails $server
        $ip = $details.IP
        $username = $details.Username
        
        Write-Info "Checking sync status on $server..."
        
        # Check if project files exist
        $result = ssh "${username}@${ip}" "ls -la /opt/quanttime/"
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Files not yet synced to $server"
        }
    }
    
    Write-Success "✅ Initial sync phase completed"
    return $true
}

# Step 9: Deploy full QuantTime setup
function Deploy-FullSetup {
    Write-Info "Step 9: Deploying full QuantTime setup..."
    
    foreach ($server in $Servers) {
        $details = Get-ServerDetails $server
        $ip = $details.IP
        $username = $details.Username
        
        Write-Info "Running full setup on $server..."
        
        $setupScript = @"
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
"@
        
        $result = ssh "${username}@${ip}" $setupScript
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "✅ Full setup completed on $server"
        } else {
            Write-Error "❌ Full setup failed on $server"
        }
    }
    
    return $true
}

# Main deployment function
function Main {
    Write-Info "🚀 Starting initial Syncthing deployment..."
    
    # Check prerequisites
    if (!(Test-Path $ConfigFile)) {
        Write-Error "Configuration file not found: $ConfigFile"
        exit 1
    }
    
    # Execute deployment steps
    if (!(Install-SyncthingOnServers)) { exit 1 }
    if (!(Setup-LocalSyncthing)) { exit 1 }
    if (!(Get-DeviceIds)) { exit 1 }
    if (!(Create-InitialFolderConfig)) { exit 1 }
    if (!(Deploy-InitialConfig)) { exit 1 }
    if (!(Apply-LocalConfig)) { exit 1 }
    if (!(Copy-ProjectToSync)) { exit 1 }
    if (!(Wait-ForInitialSync)) { exit 1 }
    if (!(Deploy-FullSetup)) { exit 1 }
    
    Write-Success "🎉 Initial Syncthing deployment completed successfully!"
    
    # Display next steps
    Write-Host ""
    Write-Info "Next steps:"
    Write-Host "1. Access Syncthing web interfaces:"
    foreach ($server in $Servers) {
        $details = Get-ServerDetails $server
        Write-Host "   - $server`: http://$($details.IP):8384"
    }
    Write-Host "   - Local: http://localhost:8384"
    Write-Host ""
    Write-Host "2. Run the full QuantTime setup:"
    Write-Host "   python scripts/setup_syncthing.py --action full"
    Write-Host ""
    Write-Host "3. Monitor sync status:"
    Write-Host "   python scripts/setup_syncthing.py --action test"
}

# Show usage
function Show-Usage {
    Write-Host "Usage: $($MyInvocation.MyCommand.Name) [OPTIONS]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -Step <number>    Run specific step (1-9)"
    Write-Host "  -Help            Show this help message"
    Write-Host ""
    Write-Host "Steps:"
    Write-Host "  1. Install Syncthing on servers"
    Write-Host "  2. Setup local Syncthing"
    Write-Host "  3. Get device IDs"
    Write-Host "  4. Create initial folder config"
    Write-Host "  5. Deploy initial config to servers"
    Write-Host "  6. Apply local config"
    Write-Host "  7. Copy project to sync folder"
    Write-Host "  8. Wait for initial sync"
    Write-Host "  9. Deploy full setup"
}

# Parse command line arguments
if ($Help) {
    Show-Usage
    exit 0
}

# Execute specific step or full deployment
if ($Step) {
    switch ($Step) {
        "1" { Install-SyncthingOnServers }
        "2" { Setup-LocalSyncthing }
        "3" { Get-DeviceIds }
        "4" { Create-InitialFolderConfig }
        "5" { Deploy-InitialConfig }
        "6" { Apply-LocalConfig }
        "7" { Copy-ProjectToSync }
        "8" { Wait-ForInitialSync }
        "9" { Deploy-FullSetup }
        default {
            Write-Error "Invalid step: $Step. Valid steps: 1-9"
            exit 1
        }
    }
} else {
    Main
}
