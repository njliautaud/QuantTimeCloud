# QuantTime Windows Node Deployment Script
# Automated deployment for Windows machines with Tailscale

param(
    [string]$GitRepo = "https://github.com/njliautaud/QuantTimeCloud.git",
    [string]$NodeName = "",
    [string]$InstallPath = "C:\QuantTime",
    [switch]$Dev = $false
)

Write-Host "🚀 QuantTime Windows Node Deployment" -ForegroundColor Green
Write-Host "====================================="

# Check if running as Administrator
$currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "⚠️ This script requires Administrator privileges" -ForegroundColor Yellow
    Write-Host "Please run PowerShell as Administrator and try again"
    exit 1
}

# Step 1: Check Prerequisites
Write-Host "`n🔍 Checking prerequisites..." -ForegroundColor Cyan

# Check Python
try {
    $pythonVersion = python --version 2>&1
    if ($pythonVersion -match "Python 3\.1[1-9]") {
        Write-Host "✅ Python: $pythonVersion" -ForegroundColor Green
    } else {
        Write-Host "❌ Python 3.11+ required. Current: $pythonVersion" -ForegroundColor Red
        Write-Host "📥 Download from: https://www.python.org/downloads/"
        exit 1
    }
} catch {
    Write-Host "❌ Python not found" -ForegroundColor Red
    Write-Host "📥 Install Python 3.11+ from: https://www.python.org/downloads/"
    exit 1
}

# Check Git
try {
    $gitVersion = git --version 2>&1
    Write-Host "✅ Git: $gitVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Git not found" -ForegroundColor Red
    Write-Host "📥 Install Git from: https://git-scm.com/download/win"
    exit 1
}

# Check Tailscale
try {
    $tailscaleStatus = tailscale status 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Tailscale is running" -ForegroundColor Green
        
        # Extract Tailscale IP
        $tailscaleIP = ($tailscaleStatus | Select-String "100\.\d+\.\d+\.\d+").Matches.Value
        if ($tailscaleIP) {
            Write-Host "🔗 Tailscale IP: $tailscaleIP" -ForegroundColor Green
        }
    } else {
        Write-Host "⚠️ Tailscale not running" -ForegroundColor Yellow
        Write-Host "📥 Install Tailscale from: https://tailscale.com/download"
    }
} catch {
    Write-Host "⚠️ Tailscale not found" -ForegroundColor Yellow
    Write-Host "📥 Install Tailscale from: https://tailscale.com/download"
}

# Step 2: Clone Repository
Write-Host "`n📥 Cloning QuantTime repository..." -ForegroundColor Cyan

if (Test-Path $InstallPath) {
    Write-Host "⚠️ Directory $InstallPath already exists" -ForegroundColor Yellow
    $overwrite = Read-Host "Overwrite? (y/N)"
    if ($overwrite -eq "y" -or $overwrite -eq "Y") {
        Remove-Item -Path $InstallPath -Recurse -Force
    } else {
        Write-Host "🛑 Deployment cancelled" -ForegroundColor Red
        exit 1
    }
}

try {
    git clone $GitRepo $InstallPath
    Set-Location $InstallPath
    Write-Host "✅ Repository cloned successfully" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to clone repository: $_" -ForegroundColor Red
    exit 1
}

# Step 3: Run Setup Script
Write-Host "`n⚙️ Running QuantTime setup..." -ForegroundColor Cyan

try {
    if ($Dev) {
        python setup.py --dev
    } else {
        python setup.py --init
    }
    Write-Host "✅ Setup completed successfully" -ForegroundColor Green
} catch {
    Write-Host "❌ Setup failed: $_" -ForegroundColor Red
    exit 1
}

# Step 4: Generate SSH Key for Automation
Write-Host "`n🔑 Setting up SSH automation key..." -ForegroundColor Cyan

$sshDir = "$env:USERPROFILE\.ssh"
$sshKeyPath = "$sshDir\quanttime_automation"

if (-not (Test-Path $sshDir)) {
    New-Item -ItemType Directory -Path $sshDir -Force | Out-Null
}

if (-not (Test-Path $sshKeyPath)) {
    try {
        ssh-keygen -t ed25519 -C "quanttime-automation-$(hostname)" -f $sshKeyPath -N '""'
        Write-Host "✅ SSH automation key generated" -ForegroundColor Green
    } catch {
        Write-Host "❌ SSH key generation failed: $_" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "✅ SSH automation key already exists" -ForegroundColor Green
}

# Step 5: Configure Windows Firewall
Write-Host "`n🔥 Configuring Windows Firewall..." -ForegroundColor Cyan

try {
    # Allow Ray cluster port
    New-NetFirewallRule -DisplayName "QuantTime Ray Cluster" -Direction Inbound -Port 10001 -Protocol TCP -Action Allow -ErrorAction SilentlyContinue
    
    # Allow Ray dashboard port
    New-NetFirewallRule -DisplayName "QuantTime Ray Dashboard" -Direction Inbound -Port 8265 -Protocol TCP -Action Allow -ErrorAction SilentlyContinue
    
    # Allow peer discovery port
    New-NetFirewallRule -DisplayName "QuantTime Peer Discovery" -Direction Inbound -Port 10002 -Protocol UDP -Action Allow -ErrorAction SilentlyContinue
    
    # Allow SSH port
    New-NetFirewallRule -DisplayName "QuantTime SSH" -Direction Inbound -Port 22 -Protocol TCP -Action Allow -ErrorAction SilentlyContinue
    
    Write-Host "✅ Firewall rules configured" -ForegroundColor Green
} catch {
    Write-Host "⚠️ Firewall configuration failed: $_" -ForegroundColor Yellow
    Write-Host "You may need to configure firewall manually"
}

# Step 6: Create Desktop Shortcut
Write-Host "`n🖥️ Creating desktop shortcut..." -ForegroundColor Cyan

try {
    $desktopPath = [Environment]::GetFolderPath("Desktop")
    $shortcutPath = "$desktopPath\QuantTime.lnk"
    
    $WshShell = New-Object -comObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut($shortcutPath)
    $Shortcut.TargetPath = "python"
    $Shortcut.Arguments = "run.py"
    $Shortcut.WorkingDirectory = $InstallPath
    $Shortcut.Description = "QuantTime ML Trading Suite"
    $Shortcut.Save()
    
    Write-Host "✅ Desktop shortcut created" -ForegroundColor Green
} catch {
    Write-Host "⚠️ Desktop shortcut creation failed: $_" -ForegroundColor Yellow
}

# Step 7: Display SSH Public Key for Manual Exchange
Write-Host "`n🔑 SSH Key Exchange Required" -ForegroundColor Yellow
Write-Host "========================================="

if (Test-Path "$sshKeyPath.pub") {
    $publicKey = Get-Content "$sshKeyPath.pub"
    Write-Host "Your public key:" -ForegroundColor Cyan
    Write-Host $publicKey -ForegroundColor White
    
    Write-Host "`nTo connect to other nodes, add this key to their ~/.ssh/authorized_keys" -ForegroundColor Yellow
    Write-Host "Example commands for each peer:" -ForegroundColor Cyan
    Write-Host 'ssh user@peer-ip "echo ''$publicKey'' >> ~/.ssh/authorized_keys"' -ForegroundColor White
}

# Step 8: Display Connection Information
Write-Host "`n🌐 Node Information" -ForegroundColor Green
Write-Host "==================="
Write-Host "Node Name: $(hostname)" -ForegroundColor White
Write-Host "Install Path: $InstallPath" -ForegroundColor White
Write-Host "Tailscale IP: $tailscaleIP" -ForegroundColor White

# Get local IP
try {
    $localIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notmatch "Loopback"}).IPAddress | Select-Object -First 1
    Write-Host "Local IP: $localIP" -ForegroundColor White
} catch {
    Write-Host "Local IP: Unable to detect" -ForegroundColor Yellow
}

Write-Host "`n🚀 Next Steps:" -ForegroundColor Green
Write-Host "1. Add SSH key to other nodes (see above)" -ForegroundColor White
Write-Host "2. Update settings.txt with your Databento API key" -ForegroundColor White
Write-Host "3. Run: python run.py" -ForegroundColor White
Write-Host "4. Node will auto-discover other QuantTime nodes" -ForegroundColor White

Write-Host "`n✅ Windows node deployment complete!" -ForegroundColor Green
Write-Host "📍 Installation location: $InstallPath" -ForegroundColor Cyan

# Offer to start immediately
$startNow = Read-Host "`nStart QuantTime now? (y/N)"
if ($startNow -eq "y" -or $startNow -eq "Y") {
    Write-Host "`n🚀 Starting QuantTime..." -ForegroundColor Green
    python run.py
}
