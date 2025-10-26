#!/bin/bash
echo "========================================"
echo "Nginx + SSL Configuration Check"
echo "========================================"
echo ""

echo "1. Nginx Status:"
sudo systemctl status nginx --no-pager | head -5
echo ""

echo "2. Let's Encrypt Certificates:"
sudo certbot certificates 2>/dev/null || echo "   Certbot not installed or no certificates"
echo ""

echo "3. Certificate files for sensexbot.ddns.net:"
sudo ls -la /etc/letsencrypt/live/sensexbot.ddns.net/ 2>/dev/null || echo "   Not found"
echo ""

echo "4. Nginx sites enabled:"
sudo ls -la /etc/nginx/sites-enabled/
echo ""

echo "5. Nginx default site config (first 50 lines):"
sudo head -50 /etc/nginx/sites-enabled/default 2>/dev/null || echo "   Not found"
echo ""

echo "6. Looking for port 8000/8001 in nginx configs:"
sudo grep -r "8000\|8001" /etc/nginx/ 2>/dev/null || echo "   Not found in nginx configs"
echo ""

echo "7. What's listening on ports 8000/8001:"
sudo ss -tulpn | grep -E "8000|8001" 2>/dev/null || sudo netstat -tulpn | grep -E "8000|8001" 2>/dev/null || echo "   Nothing listening"
echo ""

echo "8. Nginx error log (last 10 lines):"
sudo tail -10 /var/log/nginx/error.log 2>/dev/null || echo "   Log not found"
echo ""

echo "9. Checking for sensexbot-specific nginx config:"
sudo find /etc/nginx -type f -name "*sensexbot*" 2>/dev/null || echo "   No sensexbot-specific config found"
echo ""

echo "10. Test nginx configuration:"
sudo nginx -t
echo ""
