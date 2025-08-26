# 🔧 QuantTime Development Workflow & Troubleshooting Guide

This guide explains how to maintain development velocity while working with distributed servers and how to troubleshoot issues effectively.

## 🎯 **Development Philosophy**

### **Local-First Development**
- ✅ **All development** happens on your laptop first
- ✅ **Local testing** before server deployment
- ✅ **Cursor integration** for immediate feedback
- ✅ **Fast iteration** cycles

### **Distributed Deployment**
- 🚀 **Automated sync** to servers
- 🚀 **Remote debugging** capabilities
- 🚀 **Continuous deployment** pipeline
- 🚀 **Real-time monitoring**

---

## 🚀 **Quick Deployment Commands**

### **Deploy to Single Server**
```bash
# Deploy to R630XL
python scripts/deploy_to_servers.py deploy r630xl

# Deploy to R810 (when available)
python scripts/deploy_to_servers.py deploy r810
```

### **Deploy to All Servers**
```bash
# Deploy to all configured servers
python scripts/deploy_to_servers.py deploy-all
```

### **Check Server Status**
```bash
# Check R630XL status
python scripts/deploy_to_servers.py status r630xl

# Check all servers
python scripts/deploy_to_servers.py status
```

### **View Server Logs**
```bash
# View all logs from R630XL
python scripts/deploy_to_servers.py logs r630xl

# View specific service logs
python scripts/deploy_to_servers.py logs r630xl celery_worker
```

### **Quick Fixes**
```bash
# Restart all services
python scripts/deploy_to_servers.py fix r630xl services_down

# Fix permissions
python scripts/deploy_to_servers.py fix r630xl permissions

# Restart Redis
python scripts/deploy_to_servers.py fix r630xl redis

# Restart PostgreSQL
python scripts/deploy_to_servers.py fix r630xl postgres
```

---

## 📊 **Dashboard Development Tools**

### **Access Dev Tools**
1. **Launch dashboard**: `streamlit run quanttime/dashboard/app.py`
2. **Go to "Dev Tools" tab**
3. **Select target server** from dropdown
4. **Use quick action buttons** for common tasks

### **Available Actions**
- **🚀 Deploy**: Sync code and restart services
- **📊 Status**: Check server health and metrics
- **📋 Logs**: View real-time server logs
- **🔄 Restart**: Restart all services
- **📈 Start Monitoring**: Real-time monitoring for 60 seconds

### **Quick Fixes (Dashboard)**
- **Fix Services**: Restart all QuantTime services
- **Fix Permissions**: Fix file ownership and permissions
- **Fix Redis**: Restart Redis server
- **Fix PostgreSQL**: Restart PostgreSQL database

---

## 🔄 **Development Workflow**

### **1. Local Development**
```bash
# 1. Make changes locally
# 2. Test locally
streamlit run quanttime/dashboard/app.py

# 3. Run tests
python -m pytest tests/

# 4. Debug locally
python debug_script.py
```

### **2. Deploy to Server**
```bash
# Option A: Command line
python scripts/deploy_to_servers.py deploy r630xl

# Option B: Dashboard
# Go to Dev Tools tab → Select server → Click "Deploy"
```

### **3. Test on Server**
```bash
# Check server status
python scripts/deploy_to_servers.py status r630xl

# View logs
python scripts/deploy_to_servers.py logs r630xl

# Test API endpoints
curl http://jupiter:8000/api/v1/server/health
```

### **4. Iterate**
- **If issues found**: Use quick fixes or debug locally
- **If working**: Continue development
- **If major changes**: Full redeployment

---

## 🚨 **Troubleshooting Common Issues**

### **Issue 1: Server Not Responding**

**Symptoms:**
- Dashboard shows server offline
- SSH connection fails
- API endpoints not responding

**Diagnosis:**
```bash
# Check SSH connectivity
ssh quanttime@jupiter

# Check if server is reachable
ping jupiter

# Check service status
python scripts/deploy_to_servers.py status r630xl
```

**Solutions:**
```bash
# Quick fix: Restart services
python scripts/deploy_to_servers.py fix r630xl services_down

# Manual fix: SSH to server and restart
ssh quanttime@jupiter
sudo systemctl restart quanttime-*
```

### **Issue 2: Code Not Syncing**

**Symptoms:**
- Changes not appearing on server
- Old code still running
- File sync errors

**Diagnosis:**
```bash
# Check sync status
python scripts/deploy_to_servers.py logs r630xl

# Check file timestamps
ssh quanttime@jupiter "ls -la /opt/quanttime/quanttime/dashboard/app.py"
```

**Solutions:**
```bash
# Force redeploy
python scripts/deploy_to_servers.py deploy r630xl

# Manual sync
rsync -avz --exclude=.git --exclude=__pycache__ ./ quanttime@jupiter:/opt/quanttime/
```

### **Issue 3: Services Not Starting**

**Symptoms:**
- Services show as failed
- Port conflicts
- Permission errors

**Diagnosis:**
```bash
# Check service logs
python scripts/deploy_to_servers.py logs r630xl

# Check system logs
ssh quanttime@jupiter "journalctl -u quanttime-* --no-pager"
```

**Solutions:**
```bash
# Fix permissions
python scripts/deploy_to_servers.py fix r630xl permissions

# Restart services
python scripts/deploy_to_servers.py fix r630xl services_down

# Check port conflicts
ssh quanttime@jupiter "sudo netstat -tlnp | grep :8000"
```

### **Issue 4: Database Connection Issues**

**Symptoms:**
- Database connection errors
- Data not persisting
- PostgreSQL service down

**Diagnosis:**
```bash
# Check PostgreSQL status
ssh quanttime@jupiter "sudo systemctl status postgresql"

# Check database connectivity
ssh quanttime@jupiter "sudo -u postgres psql -c 'SELECT version();'"
```

**Solutions:**
```bash
# Restart PostgreSQL
python scripts/deploy_to_servers.py fix r630xl postgres

# Check database configuration
ssh quanttime@jupiter "sudo -u postgres psql -c '\\l'"
```

### **Issue 5: Redis Connection Issues**

**Symptoms:**
- Task queue not working
- Celery workers not processing
- Redis connection errors

**Diagnosis:**
```bash
# Check Redis status
ssh quanttime@jupiter "sudo systemctl status redis-server"

# Test Redis connection
ssh quanttime@jupiter "redis-cli ping"
```

**Solutions:**
```bash
# Restart Redis
python scripts/deploy_to_servers.py fix r630xl redis

# Check Redis configuration
ssh quanttime@jupiter "redis-cli info"
```

---

## 🔧 **Advanced Troubleshooting**

### **Real-Time Monitoring**
```bash
# Start monitoring for 60 seconds
# In dashboard: Dev Tools → Start Monitoring

# Or command line monitoring
watch -n 1 'python scripts/deploy_to_servers.py status r630xl'
```

### **Debug Mode**
```bash
# Enable debug logging on server
ssh quanttime@jupiter << 'EOF'
cd /opt/quanttime
export QUANTTIME_LOG_LEVEL=DEBUG
bash server/scripts/start_all_services.sh
EOF
```

### **Service-Specific Logs**
```bash
# Celery worker logs
python scripts/deploy_to_servers.py logs r630xl celery_worker

# API server logs
python scripts/deploy_to_servers.py logs r630xl api_server

# Monitoring logs
python scripts/deploy_to_servers.py logs r630xl monitoring
```

### **Network Diagnostics**
```bash
# Check network connectivity
ssh quanttime@jupiter "ping -c 4 8.8.8.8"

# Check firewall rules
ssh quanttime@jupiter "sudo ufw status"

# Check port availability
ssh quanttime@jupiter "sudo netstat -tlnp | grep :8000"
```

---

## 📈 **Performance Monitoring**

### **Resource Usage**
```bash
# Check CPU and memory
ssh quanttime@jupiter "htop"

# Check disk usage
ssh quanttime@jupiter "df -h"

# Check network usage
ssh quanttime@jupiter "nethogs"
```

### **Service Performance**
```bash
# Check Celery worker performance
ssh quanttime@jupiter "celery -A server.scripts.celery_app inspect stats"

# Check API response times
curl -w "@-" -o /dev/null -s "http://jupiter:8000/api/v1/server/health" << 'EOF'
     time_namelookup:  %{time_namelookup}\n
        time_connect:  %{time_connect}\n
     time_appconnect:  %{time_appconnect}\n
    time_pretransfer:  %{time_pretransfer}\n
       time_redirect:  %{time_redirect}\n
  time_starttransfer:  %{time_starttransfer}\n
                     ----------\n
          time_total:  %{time_total}\n
EOF
```

---

## 🎯 **Best Practices**

### **Development Workflow**
1. **Always develop locally first**
2. **Test thoroughly before deployment**
3. **Use version control** for all changes
4. **Deploy incrementally** to catch issues early
5. **Monitor after deployment**

### **Troubleshooting Approach**
1. **Check the obvious first** (SSH, services, logs)
2. **Use quick fixes** for common issues
3. **Check logs** for specific error messages
4. **Test connectivity** step by step
5. **Document solutions** for future reference

### **Deployment Strategy**
1. **Deploy to one server first**
2. **Test thoroughly** before deploying to others
3. **Use rolling deployments** for zero downtime
4. **Keep backups** before major changes
5. **Monitor performance** after deployment

---

## 🚀 **Quick Reference**

### **Essential Commands**
```bash
# Deploy
python scripts/deploy_to_servers.py deploy r630xl

# Status
python scripts/deploy_to_servers.py status r630xl

# Logs
python scripts/deploy_to_servers.py logs r630xl

# Quick fix
python scripts/deploy_to_servers.py fix r630xl services_down
```

### **Dashboard Access**
- **URL**: `http://localhost:8501`
- **Dev Tools**: Last tab in dashboard
- **Server Control**: Left sidebar

### **Emergency Procedures**
```bash
# Emergency restart
ssh quanttime@jupiter "sudo reboot"

# Emergency service restart
ssh quanttime@jupiter "sudo systemctl restart quanttime-*"

# Emergency log check
ssh quanttime@jupiter "journalctl -u quanttime-* --no-pager -n 100"
```

---

## 🎉 **Success Indicators**

**Your development workflow is working when:**
- ✅ **Local development** is fast and responsive
- ✅ **Deployments** complete in under 2 minutes
- ✅ **Servers** respond immediately after deployment
- ✅ **Logs** show successful service starts
- ✅ **Dashboard** shows all servers online
- ✅ **Jobs** execute successfully on servers

**You can troubleshoot effectively when:**
- ✅ **Quick fixes** resolve 80% of issues
- ✅ **Logs** provide clear error messages
- ✅ **Monitoring** shows real-time status
- ✅ **Deployment** is automated and reliable
- ✅ **Recovery** takes under 5 minutes

---

This workflow ensures you maintain development velocity while having robust troubleshooting capabilities for your distributed QuantTime cluster! 🚀
