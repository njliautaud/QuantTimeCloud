# QuantTime Syncthing Quick Setup
# One-command setup for Windows users

param(
    [switch]$Help,
    [switch]$TestOnly
)

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Show-Usage {
    Write-Host "QuantTime Syncthing Quick Setup"
    Write-Host ""
    Write-Host "Usage:"
    Write-Host "  .\scripts\quick_setup_syncthing.ps1          # Full setup"
    Write-Host "  .\scripts\quick_setup_syncthing.ps1 -TestOnly # Test connections only"
    Write-Host "  .\scripts\quick_setup_syncthing.ps1 -Help     # Show this help"
    Write-Host ""
    Write-Host "This script will:"
    Write-Host "  1. Check prerequisites"
    Write-Host "  2. Install Syncthing on all servers"
    Write-Host "  3. Setup local Syncthing"
    Write-Host "  4. Configure folders and sync"
    Write-Host "  5. Deploy QuantTime project"
    Write-Host ""
}

if ($Help) {
    Show-Usage
    exit 0
}

# Main setup function
function Main {
    Write-Host "🚀 QuantTime Syncthing Quick Setup" -ForegroundColor Cyan
    Write-Host "=====================================" -ForegroundColor Cyan
    Write-Host ""
    
    # Check prerequisites
    Write-Info "Checking prerequisites..."
    
    # Check if config file exists
    if (!(Test-Path "server/config/servers.json")) {
        Write-Error "Configuration file not found: server/config/servers.json"
        Write-Info "Please ensure your server configuration is set up correctly."
        exit 1
    }
    
    # Check if jq is installed
    try {
        $null = Get-Command jq -ErrorAction Stop
        Write-Success "✅ jq is installed"
    } catch {
        Write-Error "❌ jq is not installed"
        Write-Info "Installing jq via Chocolatey..."
        if (Get-Command choco -ErrorAction SilentlyContinue) {
            choco install jq -y
        } else {
            Write-Error "Chocolatey not found. Please install jq manually:"
            Write-Info "  choco install jq"
            exit 1
        }
    }
    
    # Check SSH access
    Write-Info "Testing SSH access to servers..."
    $config = Get-Content "server/config/servers.json" | ConvertFrom-Json
    
    foreach ($server in @("r630xl", "r810")) {
        $serverConfig = $config.$server
        $ip = $serverConfig.tailscale_ip
        $username = $serverConfig.username
        
        Write-Info "Testing connection to $server ($ip)..."
        $result = ssh "${username}@${ip}" "echo 'SSH connection successful'" 2>$null
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "✅ SSH connection to $server successful"
        } else {
            Write-Error "❌ SSH connection to $server failed"
            Write-Info "Please ensure:"
            Write-Info "  1. Tailscale is running"
            Write-Info "  2. SSH keys are configured"
            Write-Info "  3. Server is accessible at $ip"
            exit 1
        }
    }
    
    if ($TestOnly) {
        Write-Success "✅ All prerequisites check passed!"
        Write-Info "Run without -TestOnly to perform full setup"
        exit 0
    }
    
    # Run the full deployment
    Write-Info "Starting full Syncthing deployment..."
    Write-Host ""
    
    # Run the deployment script
    $deploymentScript = ".\scripts\deploy_syncthing_initial.ps1"
    
    if (Test-Path $deploymentScript) {
        Write-Info "Running deployment script..."
        & $deploymentScript
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "🎉 Syncthing deployment completed successfully!"
            Write-Host ""
            Write-Info "Next steps:"
            Write-Host "1. Access Syncthing web interfaces:"
            foreach ($server in @("r630xl", "r810")) {
                $serverConfig = $config.$server
                Write-Host "   - $server`: http://$($serverConfig.tailscale_ip):8384"
            }
            Write-Host "   - Local: http://localhost:8384"
            Write-Host ""
            Write-Host "2. Run the full QuantTime setup:"
            Write-Host "   python scripts/setup_syncthing.py --action full"
            Write-Host ""
            Write-Host "3. Monitor sync status:"
            Write-Host "   python scripts/setup_syncthing.py --action test"
            Write-Host ""
            Write-Host "4. Start your QuantTime dashboard:"
            Write-Host "   python run.py"
        } else {
            Write-Error "❌ Deployment failed with exit code $LASTEXITCODE"
            Write-Info "Check the logs above for details"
            exit 1
        }
    } else {
        Write-Error "Deployment script not found: $deploymentScript"
        Write-Info "Please ensure all scripts are in place"
        exit 1
    }
}

# Run main function
Main
