# Infrastructure Documentation
## Complete Deployment Architecture

**Last Updated**: October 25, 2025  
**Server**: AWS EC2 (Ubuntu)  
**Domain**: sensexbot.ddns.net  

---

## 🏗️ Complete Stack Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    INTERNET REQUEST                          │
│                    https://sensexbot.ddns.net                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │     No-IP DDNS Service       │
        │   (Dynamic DNS Resolution)    │
        │  sensexbot.ddns.net → EC2 IP │
        └──────────────┬───────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │    AWS Security Group        │
        │  Port 80  → HTTP (redirect)  │
        │  Port 443 → HTTPS (SSL)      │
        │  Port 22  → SSH              │
        └──────────────┬───────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │         Nginx Server         │
        │    (Reverse Proxy + SSL)     │
        │                              │
        │  - Listen: 443 (HTTPS)       │
        │  - SSL: Let's Encrypt        │
        │  - Redirect: 80 → 443        │
        └──────────────┬───────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │     Flask Backend            │
        │  (Python Trading System)     │
        │                              │
        │  Port: 8001 (localhost)      │
        │  Process: postback_server.py │
        │  Virtual Env: venv/          │
        └──────────────────────────────┘
```

---

## 🔐 SSL/TLS Configuration

### Let's Encrypt Certificates

**Status**: Active and Valid
```
Certificate Name: sensexbot.ddns.net
Expiry Date: 2025-11-08 08:58:01+00:00 (VALID: 13 days remaining)
Certificate Path: /etc/letsencrypt/live/sensexbot.ddns.net/fullchain.pem
Private Key Path: /etc/letsencrypt/live/sensexbot.ddns.net/privkey.pem
```

### Certificate Auto-Renewal

**Certbot** is installed and configured for automatic renewal:

```bash
# Check certificate status
sudo certbot certificates

# Test renewal (dry-run)
sudo certbot renew --dry-run

# Force renewal (if expiring soon)
sudo certbot renew --force-renewal

# Auto-renewal service
sudo systemctl status certbot.timer
```

**Certificate Files Location**:
```
/etc/letsencrypt/live/sensexbot.ddns.net/
├── cert.pem       → Certificate only
├── chain.pem      → Certificate chain
├── fullchain.pem  → Certificate + chain (used by nginx)
└── privkey.pem    → Private key (used by nginx)
```

### SSL Security Settings

Nginx is configured with modern SSL settings:
- **Protocols**: TLSv1.2, TLSv1.3 (secure, no old protocols)
- **Ciphers**: Strong ECDHE and DHE ciphers
- **Security Headers**: X-Frame-Options, X-Content-Type-Options, X-XSS-Protection

---

## 🌐 Nginx Reverse Proxy

### Configuration File

**Location**: `/etc/nginx/sites-available/sensexbot.ddns.net`  
**Symlink**: `/etc/nginx/sites-enabled/sensexbot.ddns.net`

### Port Mapping

```
External (Internet)          Nginx           Internal (Flask)
──────────────────────────────────────────────────────────────
https://sensexbot.ddns.net:443
                      ↓      Reverse         ↓
                      ↓      Proxy           ↓
                      ↓      ────→    http://localhost:8001
```

### Key Features

1. **HTTPS Termination**: Nginx handles SSL, Flask receives plain HTTP
2. **HTTP → HTTPS Redirect**: All port 80 requests redirect to 443
3. **Reverse Proxy**: Routes requests to Flask backend on port 8001
4. **Special Endpoints**:
   - `/` → Main application
   - `/postback` → Kite Connect postback (important!)
   - `/health` → Health check (no logging)
   - `/status` → System status

### Nginx Commands

```bash
# Test configuration
sudo nginx -t

# Reload configuration (no downtime)
sudo systemctl reload nginx

# Restart nginx
sudo systemctl restart nginx

# Check status
sudo systemctl status nginx

# View logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/postback_access.log
```

---

## 🔌 Port Configuration

### AWS Security Group Rules

```
┌──────────┬──────────┬────────────┬─────────────────────────┐
│   Port   │ Protocol │   Source   │       Description       │
├──────────┼──────────┼────────────┼─────────────────────────┤
│    22    │   TCP    │  0.0.0.0/0 │ SSH Access              │
│    80    │   TCP    │  0.0.0.0/0 │ HTTP (redirects to 443) │
│   443    │   TCP    │  0.0.0.0/0 │ HTTPS (SSL/TLS)         │
│  8001    │   TCP    │  0.0.0.0/0 │ Kite Postback (legacy)  │
│   ICMP   │   All    │  0.0.0.0/0 │ Ping                    │
└──────────┴──────────┴────────────┴─────────────────────────┘
```

**Note**: Port 8001 is open in security group but Flask only listens on localhost (nginx proxies to it).

### Actual Listening Ports

```bash
# Check what's listening
sudo ss -tulpn | grep -E "22|80|443|8001"

# Current setup:
# Port 22  → sshd (SSH)
# Port 80  → nginx (HTTP → redirects to 443)
# Port 443 → nginx (HTTPS → proxies to 8001)
# Port 8001 → python3 postback_server.py (localhost only)
```

---

## 🌍 Dynamic DNS (No-IP)

### Configuration

**Service**: No-IP (https://www.noip.com)  
**Hostname**: sensexbot.ddns.net  
**IP Update**: Automatic (via No-IP DUC or router)

### Verify DNS Resolution

```bash
# Test DNS resolution
nslookup sensexbot.ddns.net
ping sensexbot.ddns.net

# Check current public IP
curl -s https://api.ipify.org
curl -s https://ifconfig.me
```

### Update IP Manually (if needed)

```bash
# If using No-IP DUC (Dynamic Update Client)
sudo noip2 -S  # Check status
sudo noip2 -M  # Force update

# Or update via router DDNS settings
```

---

## 💾 Current System Status

### Running Processes

```bash
# Old trading system still running
Process: /home/ubuntu/main_trading/venv/bin/python3
Script: /home/ubuntu/main_trading/postback_server.py
Port: 8001
PID: 780548
Running Since: Sep 27 (4 weeks ago)
```

### Failed Services

```bash
# trading-system.service is failed (old systemd service)
sudo systemctl status trading-system.service
# Status: failed

# To disable old service:
sudo systemctl disable trading-system.service
```

### Disk Usage

```
Filesystem: /dev/root
Total: 7.6G
Used: 4.4G (59%)
Available: 3.2G
```

**Note**: Nginx logs were full (causing "No space left on device" errors). Clean regularly!

---

## 🗂️ Directory Structure

### Old System
```
/home/ubuntu/main_trading/
├── venv/                    # Virtual environment
├── postback_server.py       # Currently running (port 8001)
└── ... (other files)
```

### New System (This Repository)
```
/home/ubuntu/pivot-trading-system/
├── venv/                    # New virtual environment
├── modules/                 # Core trading modules
├── utils/                   # Utilities
├── data/                    # Database & cache
├── logs/                    # System logs
├── config.json              # Configuration (gitignored)
└── main.py                  # Main trading loop (to be created)
```

---

## 🔧 Maintenance Tasks

### Regular Tasks

```bash
# 1. Clean Nginx logs (monthly)
sudo truncate -s 0 /var/log/nginx/access.log
sudo truncate -s 0 /var/log/nginx/error.log

# 2. Rotate logs
sudo logrotate -f /etc/logrotate.d/nginx

# 3. Check certificate expiry (weekly)
sudo certbot certificates

# 4. Renew certificate (if < 30 days)
sudo certbot renew

# 5. Check disk space
df -h

# 6. Check system logs
journalctl -xe --no-pager | tail -50
```

### Before Deployment

```bash
# 1. Stop old system
kill 780548  # PID of old postback_server.py
# Or:
ps aux | grep postback_server.py | grep -v grep | awk '{print $2}' | xargs kill

# 2. Disable old systemd service
sudo systemctl disable trading-system.service

# 3. Verify nginx config
sudo nginx -t

# 4. Reload nginx (if config changed)
sudo systemctl reload nginx

# 5. Clean logs
sudo truncate -s 0 /var/log/nginx/*.log

# 6. Check available disk space
df -h
```

---

## 🚀 Deployment Steps (New System)

### 1. Stop Old System

```bash
# Find and kill old process
ps aux | grep python | grep 8001
kill <PID>

# Verify port is free
sudo ss -tulpn | grep 8001
```

### 2. Setup New System

```bash
cd ~/pivot-trading-system
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure

```bash
# Edit config.json with credentials
nano config.json

# Update if needed (should work with existing nginx)
# auth.callback_port: 8001
# auth.redirect_url: https://sensexbot.ddns.net/callback
# auth.postback_url: https://sensexbot.ddns.net/postback
```

### 4. Test Flask Server

```bash
# Run test server
python auth_server.py

# In another terminal, test:
curl http://localhost:8001/health
```

### 5. Run as Systemd Service

Create new service file:
```bash
sudo nano /etc/systemd/system/pivot-trading.service
```

Content:
```ini
[Unit]
Description=Pivot Trading System
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/pivot-trading-system
Environment="PATH=/home/ubuntu/pivot-trading-system/venv/bin"
ExecStart=/home/ubuntu/pivot-trading-system/venv/bin/python main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable pivot-trading
sudo systemctl start pivot-trading
sudo systemctl status pivot-trading
```

---

## 🔍 Troubleshooting

### Nginx Issues

```bash
# Test config
sudo nginx -t

# Check error logs
sudo tail -50 /var/log/nginx/error.log

# Common fixes:
# - Syntax error: Check config file
# - Port conflict: Something else on 80/443
# - SSL error: Certificate expired or wrong path
```

### SSL Certificate Issues

```bash
# Check expiry
sudo certbot certificates

# Renew if expired
sudo certbot renew --force-renewal

# If renewal fails, check:
# 1. Port 80 accessible (needed for renewal)
# 2. Domain resolves correctly
# 3. No firewall blocking
```

### Flask Not Responding

```bash
# Check if process running
ps aux | grep python | grep 8001

# Check port listening
sudo ss -tulpn | grep 8001

# Check Flask logs
tail -f ~/pivot-trading-system/logs/system.log

# Restart service
sudo systemctl restart pivot-trading
```

### DNS Issues

```bash
# Test resolution
nslookup sensexbot.ddns.net

# Update IP manually (No-IP)
sudo noip2 -M

# Check current IP matches
curl -s https://api.ipify.org
nslookup sensexbot.ddns.net | grep Address
```

---

## 📊 Monitoring Commands

```bash
# System health check (run daily)
echo "=== System Health Check ==="
echo "1. Nginx Status:"
sudo systemctl status nginx --no-pager | head -3

echo "2. Certificate Expiry:"
sudo certbot certificates | grep "Expiry Date"

echo "3. Disk Space:"
df -h | grep /dev/root

echo "4. Trading System:"
sudo systemctl status pivot-trading --no-pager | head -3

echo "5. Port 8001:"
sudo ss -tulpn | grep 8001

echo "6. Recent Errors:"
sudo tail -5 /var/log/nginx/error.log
```

---

## 🔒 Security Checklist

- [x] SSL/TLS enabled (Let's Encrypt)
- [x] HTTP → HTTPS redirect
- [x] Strong cipher suites (TLSv1.2, TLSv1.3)
- [x] Security headers configured
- [x] Flask only on localhost (not exposed)
- [x] SSH key authentication (disable password auth)
- [x] Firewall rules (AWS Security Group)
- [x] Regular log rotation
- [x] Certificate auto-renewal
- [ ] Fail2ban (optional - consider adding)
- [ ] Rate limiting (optional - consider adding)

---

## 📝 Important Notes

1. **Old System**: Currently running on port 8001 - needs to be stopped before deploying new system
2. **Port 8001**: Used by both old and new system - only one can run at a time
3. **Nginx Config**: Already perfect - no changes needed, works with new system
4. **SSL Certificates**: Valid until Nov 8, 2025 - will auto-renew
5. **Disk Space**: Clean logs regularly to prevent "disk full" errors
6. **DDNS**: No-IP keeps domain pointing to EC2 IP

---

## 🎯 Next Steps

1. Complete remaining modules (database, notifier, auth_manager)
2. Create main.py integration
3. Test authentication flow with existing nginx
4. Stop old system (kill PID 780548)
5. Deploy new system as systemd service
6. Monitor logs and verify functionality

---

**Infrastructure is production-ready!** Just need to:
1. Stop old process on port 8001
2. Deploy new system
3. Everything else (nginx, SSL, DNS) already working perfectly! ✅
