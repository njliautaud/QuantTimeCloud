# QuantTime Poetry Setup Guide

This guide covers the Poetry-based environment management system for QuantTime, ensuring consistent and reproducible environments across all nodes (laptop and servers).

## 🎯 Overview

QuantTime uses **Poetry** as the primary dependency manager to ensure:
- **Exact version control** for all dependencies
- **Reproducible environments** across all nodes
- **Consistent deployment** on laptop and servers
- **Conflict prevention** through proper .gitignore configuration

## 📋 Prerequisites

- Python 3.9+ installed
- Git installed
- Access to the QuantTime repository

## 🚀 Quick Start

### 1. Automated Setup (Recommended)

Run the automated setup script:

```bash
python setup_poetry.py
```

This script will:
- Install Poetry if not present
- Configure Poetry settings
- Install all dependencies
- Create necessary directories
- Generate poetry.lock file
- Create .env file
- Run validation tests

### 2. Manual Setup

If you prefer manual setup:

```bash
# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Configure Poetry
poetry config virtualenvs.in-project true
poetry config virtualenvs.prefer-active-python true

# Install dependencies
poetry install

# Generate lock file
poetry lock
```

## 📁 Project Structure

```
QuantTime/
├── pyproject.toml          # Poetry configuration
├── poetry.lock            # Locked dependency versions
├── requirements.txt       # Compatible requirements (kept for compatibility)
├── setup_poetry.py       # Automated setup script
├── .env                  # Environment configuration
├── .gitignore           # Comprehensive git ignore
├── quanttime/           # Main application
├── server/              # Server infrastructure
├── logs/                # Application logs
├── data/                # Data files
├── models/              # Model files
├── cache/               # Cache files
└── temp/                # Temporary files
```

## 🔧 Poetry Configuration

### Key Settings

The `pyproject.toml` file includes:

- **Exact version pinning** for all dependencies
- **Development dependencies** separated from production
- **Script definitions** for easy execution
- **Tool configurations** for code quality

### Virtual Environment

Poetry is configured to:
- Create virtual environments in the project directory (`.venv/`)
- Use the active Python version
- Automatically activate when running commands

## 🌐 Multi-Node Deployment

### Laptop (Development Node)

```bash
# Development setup
poetry install  # Includes dev dependencies

# Run dashboard
poetry run streamlit run quanttime/dashboard/app.py

# Run tests
poetry run pytest

# Code formatting
poetry run black .
poetry run isort .
```

### Server Deployment

Use the automated server setup script:

```bash
# On Ubuntu 22.04 server
chmod +x server/setup/poetry_server_setup.sh
./server/setup/poetry_server_setup.sh "server-name" "laptop" "tailscale-auth-key"
```

The server setup includes:
- Poetry installation and configuration
- System dependencies
- Syncthing for file synchronization
- Ray for distributed computing
- Redis and PostgreSQL
- Systemd services
- Firewall configuration

### Post-Server-Setup

After server setup, complete the environment:

```bash
# On the server
sudo -u quanttime /opt/quanttime/setup_complete.sh
```

## 🔄 Syncthing Integration

### Configuration

Syncthing is configured to:
- Sync the entire project directory
- Maintain version consistency across nodes
- Prevent conflicts through proper .gitignore

### Setup

1. **Laptop**: Syncthing runs as a service
2. **Servers**: Syncthing runs as systemd service
3. **Web Interface**: Access at `http://server-ip:8384`

### Folder Configuration

The main sync folder is configured as:
- **Folder Path**: `/opt/quanttime` (servers) or project root (laptop)
- **Folder Type**: Send & Receive
- **Versioning**: Simple File Versioning
- **Ignore Patterns**: Based on .gitignore

## ⚡ Ray Integration

### Cluster Configuration

Ray is configured for distributed computing:
- **Head Node**: Laptop (development)
- **Worker Nodes**: R630XL, R810 servers
- **Dashboard**: Access at `http://server-ip:8265`

### Job Management

Jobs are managed through the dashboard:
- **Sync Dependency**: Jobs wait for sync completion
- **Resource Allocation**: CPU and memory requirements
- **Priority Queue**: Critical, High, Normal, Low priorities

## 📝 Environment Variables

### Configuration Files

- **`.env`**: Default configuration (template)
- **`.env.local`**: Local overrides (not synced)
- **`.env.production`**: Production settings

### Key Variables

```bash
# Application
QUANTTIME_ENV=development
QUANTTIME_DEBUG=true
QUANTTIME_LOG_LEVEL=INFO

# Database
DATABASE_URL=sqlite:///quanttime.db

# Databento
DATABENTO_KEY=your_key_here

# Server
SERVER_HOST=0.0.0.0
SERVER_PORT=5000

# Ray
RAY_DASHBOARD_HOST=0.0.0.0
RAY_DASHBOARD_PORT=8265

# Syncthing
SYNCTHING_API_KEY=your_key_here
SYNCTHING_HOST=localhost
SYNCTHING_PORT=8384
```

## 🔒 Version Control

### .gitignore Strategy

The comprehensive .gitignore prevents:
- **Environment conflicts**: Virtual environments, .env files
- **Data conflicts**: Large files, databases, models
- **Cache conflicts**: Python cache, temporary files
- **Node-specific conflicts**: Local configurations

### Lock File Management

- **`poetry.lock`**: Committed to ensure reproducible builds
- **`requirements.txt`**: Kept for compatibility
- **Version consistency**: All nodes use identical versions

## 🧪 Testing

### Environment Validation

```bash
# Run setup validation
python setup_poetry.py

# Test imports
poetry run python -c "
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
import torch
import lightgbm as lgb
print('✅ All dependencies imported successfully')
"
```

### Health Checks

```bash
# Laptop health check
poetry run python -c "import quanttime; print('✅ QuantTime imports work')"

# Server health check
/opt/quanttime/health_check.sh
```

## 🚨 Troubleshooting

### Common Issues

1. **Poetry not found**
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   export PATH="$HOME/.local/bin:$PATH"
   ```

2. **Virtual environment issues**
   ```bash
   poetry env remove python
   poetry install
   ```

3. **Dependency conflicts**
   ```bash
   poetry lock --no-update
   poetry install
   ```

4. **Sync conflicts**
   ```bash
   # Check sync status
   poetry run python -c "from server.core.syncthing_manager import get_syncthing_manager; print(get_syncthing_manager().get_sync_status())"
   ```

### Logs

- **Application logs**: `logs/quanttime.log`
- **Poetry logs**: `poetry.log`
- **System logs**: `journalctl -u quanttime`

## 📊 Monitoring

### Dashboard Integration

The QuantTime dashboard includes:
- **Sync Status**: Real-time Syncthing status
- **Ray Cluster**: Node and job monitoring
- **Centralized Logging**: All-node log aggregation
- **Health Checks**: System status monitoring

### Metrics

- **Sync Progress**: File synchronization status
- **Job Queue**: Ray job management
- **Resource Usage**: CPU, memory, disk
- **Error Tracking**: Centralized error logging

## 🔄 Updates

### Dependency Updates

```bash
# Update dependencies
poetry update

# Update specific package
poetry update package-name

# Regenerate lock file
poetry lock
```

### Environment Updates

```bash
# Reinstall environment
poetry env remove python
poetry install

# Update Poetry itself
poetry self update
```

## 📚 Additional Resources

- [Poetry Documentation](https://python-poetry.org/docs/)
- [Syncthing Documentation](https://docs.syncthing.net/)
- [Ray Documentation](https://docs.ray.io/)
- [QuantTime Documentation](docs/)

## 🤝 Contributing

When contributing to QuantTime:

1. **Use Poetry**: Always use Poetry for dependency management
2. **Update pyproject.toml**: Add new dependencies with exact versions
3. **Regenerate lock**: Run `poetry lock` after dependency changes
4. **Test locally**: Ensure everything works in Poetry environment
5. **Update requirements.txt**: Keep it in sync with pyproject.toml

## 📞 Support

For issues with Poetry setup:
1. Check the troubleshooting section
2. Run health checks
3. Review logs
4. Create an issue with detailed error information

---

**Note**: This Poetry setup ensures that all QuantTime deployments are consistent and reproducible across all nodes in your distributed computing environment.
