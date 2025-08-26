#!/bin/bash
# Tailscale Troubleshooting Script

echo "🔧 Diagnosing Tailscale connection issues..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run with sudo"
    exit 1
fi

echo "📊 Checking system status..."

# Check daemon status
echo "1. Checking Tailscale daemon..."
if systemctl is-active --quiet tailscaled; then
    echo "✅ Daemon is running"
else
    echo "❌ Daemon is not running"
    echo "🔄 Starting daemon..."
    systemctl start tailscaled
    systemctl enable tailscaled
    sleep 2
fi

# Check daemon logs
echo "2. Checking daemon logs..."
RECENT_LOGS=$(journalctl -u tailscaled --no-pager -n 10)
if echo "$RECENT_LOGS" | grep -q "error\|failed\|Error\|Failed"; then
    echo "❌ Found errors in logs:"
    echo "$RECENT_LOGS"
else
    echo "✅ No obvious errors in logs"
fi

# Check network
echo "3. Checking network..."
if ping -c 1 8.8.8.8 >/dev/null 2>&1; then
    echo "✅ Internet connectivity OK"
else
    echo "❌ No internet connectivity"
fi

# Check DNS
echo "4. Checking DNS..."
if nslookup login.tailscale.com >/dev/null 2>&1; then
    echo "✅ DNS resolution OK"
else
    echo "❌ DNS resolution failed"
fi

# Check port availability
echo "5. Checking port availability..."
if netstat -tlnp 2>/dev/null | grep -q ":41641"; then
    echo "❌ Port 41641 is in use"
    netstat -tlnp | grep ":41641"
else
    echo "✅ Port 41641 is available"
fi

# Check firewall
echo "6. Checking firewall..."
if command -v ufw >/dev/null 2>&1; then
    UFW_STATUS=$(ufw status)
    if echo "$UFW_STATUS" | grep -q "active"; then
        echo "⚠️  Firewall is active - may block Tailscale"
    else
        echo "✅ Firewall is inactive"
    fi
else
    echo "✅ No UFW firewall detected"
fi

# Check disk space
echo "7. Checking disk space..."
DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 90 ]; then
    echo "❌ Low disk space: ${DISK_USAGE}% used"
else
    echo "✅ Disk space OK: ${DISK_USAGE}% used"
fi

echo ""
echo "🔧 Attempting fixes..."

# Restart daemon
echo "🔄 Restarting Tailscale daemon..."
systemctl restart tailscaled
sleep 3

# Try to start Tailscale
echo "🔗 Attempting to start Tailscale..."
if tailscale up; then
    echo "✅ Tailscale started successfully!"
    echo "📋 Your Tailscale IP: $(tailscale ip -4)"
else
    echo "❌ Failed to start Tailscale"
    echo ""
    echo "🔍 Additional troubleshooting steps:"
    echo "1. Check logs: sudo journalctl -u tailscaled -f"
    echo "2. Try manual start: sudo tailscaled &"
    echo "3. Check network: sudo netstat -tlnp | grep 41641"
    echo "4. Reinstall: sudo apt remove tailscale && sudo apt install tailscale"
fi

echo ""
echo "📊 Final status:"
tailscale status
