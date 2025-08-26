#!/bin/bash
# QuantTime Tailscale Setup Script
# Run this once to set up Tailscale on your Ubuntu server

echo "🚀 Setting up Tailscale for QuantTime..."

# Update system
echo "📦 Updating system packages..."
sudo apt update

# Install curl if not present
if ! command -v curl &> /dev/null; then
    echo "📥 Installing curl..."
    sudo apt install curl -y
fi

# Install Tailscale
echo "📥 Installing Tailscale..."
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/jammy.noarmor.gpg | sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/jammy.tailscale-keyring.list | sudo tee /etc/apt/sources.list.d/tailscale.list
sudo apt update
sudo apt install tailscale -y

# Start and enable Tailscale daemon
echo "🔄 Starting Tailscale daemon..."
sudo systemctl start tailscaled
sudo systemctl enable tailscaled

# Start Tailscale
echo "🔗 Starting Tailscale..."
echo "You will be prompted to authenticate via web browser..."
sudo tailscale up

# Get the IP address
echo "📋 Getting Tailscale IP..."
TAILSCALE_IP=$(tailscale ip -4)
echo "✅ Tailscale IP: $TAILSCALE_IP"

# Show status
echo "📊 Tailscale Status:"
tailscale status

echo ""
echo "🎉 Tailscale setup complete!"
echo "Your Tailscale IP is: $TAILSCALE_IP"
echo ""
echo "Next steps:"
echo "1. Update server/config/servers.json with IP: $TAILSCALE_IP"
echo "2. Test connectivity: ping $TAILSCALE_IP"
echo "3. Deploy QuantTime: python scripts/deploy_to_servers.py deploy r630xl"
echo ""
echo "To manage Tailscale, visit: https://login.tailscale.com/admin/machines"
