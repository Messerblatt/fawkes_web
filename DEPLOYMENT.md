# Fawkes Web Application - Production Deployment Guide

This guide covers deploying the Fawkes Web Application to a production server using Gunicorn and Nginx.

## Prerequisites

- Ubuntu 20.04+ or similar Linux distribution
- Python 3.7+
- Nginx
- Git
- sudo access

## Installation Steps

### 1. System Dependencies

\`\`\`bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies
sudo apt install -y python3 python3-pip python3-venv nginx git

# Install system libraries for TensorFlow and OpenCV
sudo apt install -y libsm6 libxext6 libxrender-dev libgomp1
\`\`\`

### 2. Create Application User

\`\`\`bash
# Create dedicated user for the application
sudo useradd -m -s /bin/bash fawkes
sudo usermod -aG www-data fawkes
\`\`\`

### 3. Clone and Setup Application

\`\`\`bash
# Clone repository
sudo mkdir -p /var/www
sudo chown fawkes:fawkes /var/www
cd /var/www

# As fawkes user
sudo -u fawkes git clone <your-repo-url> fawkes-web
cd fawkes-web

# Create virtual environment
sudo -u fawkes python3 -m venv venv
sudo -u fawkes venv/bin/pip install --upgrade pip

# Install Python dependencies
sudo -u fawkes venv/bin/pip install -r requirements.txt
\`\`\`

### 4. Setup Fawkes

\`\`\`bash
# Clone Fawkes repository
cd /var/www/fawkes-web
sudo -u fawkes git clone https://github.com/Shawn-Shan/fawkes.git
cd fawkes
sudo -u fawkes ../venv/bin/pip install -e .
\`\`\`

### 5. Create Required Directories

\`\`\`bash
cd /var/www/fawkes-web
sudo -u fawkes mkdir -p images logs
\`\`\`

### 6. Configure Environment

\`\`\`bash
# Generate secret key
SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')

# Create environment file
sudo -u fawkes tee .env << EOF
SECRET_KEY=$SECRET_KEY
FLASK_ENV=production
EOF
\`\`\`

### 7. Setup Systemd Service

\`\`\`bash
# Copy service file
sudo cp fawkes-web.service /etc/systemd/system/

# Edit the service file
sudo nano /etc/systemd/system/fawkes-web.service
# Update WorkingDirectory and User/Group if needed

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable fawkes-web
\`\`\`

### 8. Configure Nginx

\`\`\`bash
# Copy nginx configuration
sudo cp nginx.conf /etc/nginx/sites-available/fawkes-web

# Edit configuration
sudo nano /etc/nginx/sites-available/fawkes-web
# Update server_name with your domain

# Enable site
sudo ln -s /etc/nginx/sites-available/fawkes-web /etc/nginx/sites-enabled/

# Test nginx configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
\`\`\`

### 9. Start Application

\`\`\`bash
# Start the service
sudo systemctl start fawkes-web

# Check status
sudo systemctl status fawkes-web

# View logs
sudo journalctl -u fawkes-web -f
\`\`\`

## SSL/HTTPS Setup (Recommended)

### Using Let's Encrypt (Certbot)

\`\`\`bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d your-domain.com

# Certbot will automatically configure Nginx for HTTPS
# Test automatic renewal
sudo certbot renew --dry-run
\`\`\`

## Testing Deployment

\`\`\`bash
# Test health endpoint
curl http://localhost:5000/health

# Check from outside
curl http://your-domain.com/health
\`\`\`

## Monitoring and Maintenance

### View Logs

\`\`\`bash
# Application logs
sudo journalctl -u fawkes-web -f

# Nginx access logs
sudo tail -f /var/log/nginx/access.log

# Nginx error logs
sudo tail -f /var/log/nginx/error.log
\`\`\`

### Restart Service

\`\`\`bash
# Restart application
sudo systemctl restart fawkes-web

# Reload application (graceful)
sudo systemctl reload fawkes-web

# Restart Nginx
sudo systemctl restart nginx
\`\`\`

### Update Application

\`\`\`bash
# Pull latest changes
cd /var/www/fawkes-web
sudo -u fawkes git pull

# Update dependencies if needed
sudo -u fawkes venv/bin/pip install -r requirements.txt

# Restart service
sudo systemctl restart fawkes-web
\`\`\`

## Performance Tuning

### For CPU-Only Servers

The default configuration is optimized for CPU processing. No changes needed.

### For GPU Servers

Install CUDA and GPU-enabled TensorFlow:

\`\`\`bash
# Install CUDA (version depends on your GPU)
# Follow Nvidia's official guide

# Install GPU TensorFlow
sudo -u fawkes venv/bin/pip install tensorflow-gpu==2.13.0
\`\`\`

### Adjust Worker Configuration

Edit `gunicorn_config.py` if needed:

\`\`\`python
# For more CPU cores (CPU-intensive workloads)
# Keep workers=1 for SocketIO
workers = 1
worker_connections = 1000

# Adjust timeout for longer processing
timeout = 300  # 5 minutes
\`\`\`

## Troubleshooting

### Application Won't Start

\`\`\`bash
# Check service status
sudo systemctl status fawkes-web

# Check logs
sudo journalctl -u fawkes-web -n 100

# Test application manually
cd /var/www/fawkes-web
sudo -u fawkes venv/bin/gunicorn --config gunicorn_config.py wsgi:app
\`\`\`

### Permission Issues

\`\`\`bash
# Fix ownership
sudo chown -R fawkes:fawkes /var/www/fawkes-web

# Fix permissions
sudo chmod -R 755 /var/www/fawkes-web
sudo chmod 600 /var/www/fawkes-web/.env
\`\`\`

### Port Already in Use

\`\`\`bash
# Check what's using port 5000
sudo lsof -i :5000

# Kill process if needed
sudo kill <PID>
\`\`\`

### Nginx 502 Bad Gateway

\`\`\`bash
# Check if application is running
sudo systemctl status fawkes-web

# Check Nginx error logs
sudo tail -f /var/log/nginx/error.log

# Verify upstream configuration
curl http://127.0.0.1:5000/health
\`\`\`

## Security Hardening

### Firewall Configuration

\`\`\`bash
# Enable UFW
sudo ufw enable

# Allow SSH
sudo ufw allow ssh

# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Deny direct access to application port
sudo ufw deny 5000/tcp
\`\`\`

### File Permissions

\`\`\`bash
# Secure sensitive files
sudo chmod 600 /var/www/fawkes-web/.env
sudo chmod 600 /etc/systemd/system/fawkes-web.service
\`\`\`

### Regular Updates

\`\`\`bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Update Python dependencies
cd /var/www/fawkes-web
sudo -u fawkes venv/bin/pip install --upgrade pip
sudo -u fawkes venv/bin/pip list --outdated
\`\`\`

## Backup Strategy

### Backup Script

\`\`\`bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/var/backups/fawkes-web"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup application files
tar -czf $BACKUP_DIR/fawkes-web-$DATE.tar.gz \
    -C /var/www fawkes-web \
    --exclude='fawkes-web/venv' \
    --exclude='fawkes-web/images/*' \
    --exclude='fawkes-web/__pycache__'

# Keep only last 7 backups
ls -t $BACKUP_DIR/fawkes-web-*.tar.gz | tail -n +8 | xargs rm -f

echo "Backup completed: $BACKUP_DIR/fawkes-web-$DATE.tar.gz"
\`\`\`

## Monitoring

### Setup Basic Monitoring

\`\`\`bash
# Install monitoring tools
sudo apt install -y htop iotop

# Monitor resources
htop

# Check disk usage
df -h

# Check application resource usage
ps aux | grep gunicorn
\`\`\`

## Support

For issues:
- Check application logs: `sudo journalctl -u fawkes-web`
- Check Nginx logs: `/var/log/nginx/`
- Review this deployment guide
- Consult the main README.md

## Quick Reference

\`\`\`bash
# Start service
sudo systemctl start fawkes-web

# Stop service
sudo systemctl stop fawkes-web

# Restart service
sudo systemctl restart fawkes-web

# View logs
sudo journalctl -u fawkes-web -f

# Update application
cd /var/www/fawkes-web && sudo -u fawkes git pull && sudo systemctl restart fawkes-web
