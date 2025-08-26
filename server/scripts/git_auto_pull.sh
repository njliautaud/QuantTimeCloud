#!/bin/bash

# QuantTime Git Auto-Pull Script
# Run this on servers to pull latest code from GitHub

set -e

echo "🔄 Pulling latest code from GitHub..."

# Change to QuantTime directory
cd /opt/quanttime

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    echo "❌ Not a git repository. Please clone the repository first."
    exit 1
fi

# Stash any local changes (optional)
git stash -u

# Pull latest changes
git pull origin main

# Pop stashed changes if any
git stash pop

# Install/update dependencies if requirements.txt changed
if git diff --name-only HEAD~1 HEAD | grep -q "requirements.txt"; then
    echo "📦 Requirements.txt changed, updating dependencies..."
    pip install -r requirements.txt
fi

echo "✅ Code updated successfully!"

# Restart services if needed
echo "🔄 Restarting services..."
systemctl restart quanttime-api-server
systemctl restart quanttime-celery-worker

echo "�� Update complete!"
