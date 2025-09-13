#!/bin/bash

# News Check App - Automated Deployment Script
# Usage: ./deploy.sh

set -e  # エラーが発生したら停止

echo "🚀 Starting News Check App Deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_DIR="/home/kanatsutsui/news_check_app/news_check_app"
BACKEND_DIR="$APP_DIR/backend"
FRONTEND_DIR="$APP_DIR/frontend"
DEPLOY_DIR="/var/www/news_check_app"
SERVICE_NAME="news-check-backend.service"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as non-root user
if [ "$EUID" -eq 0 ]; then
    log_error "Please run this script as non-root user (not with sudo)"
    exit 1
fi

# Step 1: Update code from Git
log_info "Step 1: Updating code from Git repository..."
cd $APP_DIR
git stash push -m "Auto-stash before deployment $(date)"
git pull origin main
log_success "Code updated from Git"

# Step 2: Update backend dependencies
log_info "Step 2: Updating backend dependencies..."
cd $BACKEND_DIR
source ../../.news_check_app/bin/activate
pip install -r requirements.txt
log_success "Backend dependencies updated"

# Step 3: Check environment files
log_info "Step 3: Checking environment files..."
if [ ! -f "$BACKEND_DIR/.env" ]; then
    log_warning "Backend .env file not found. Please create it manually."
else
    log_success "Backend .env file exists"
fi

if [ ! -f "$FRONTEND_DIR/.env" ]; then
    log_warning "Frontend .env file not found. Creating with default values..."
    cat > $FRONTEND_DIR/.env << EOF
VITE_API_BASE_URL=https://news-check-app.mofu-mofu-application.com/api
VITE_RSS_FILE_PATH=/home/kanatsutsui/news_check_app/news_check_app/backend/rss_feeds.txt
EOF
    log_success "Frontend .env file created"
else
    log_success "Frontend .env file exists"
fi

# Step 4: Build frontend
log_info "Step 4: Building frontend..."
cd $FRONTEND_DIR
npm install
rm -rf dist/
npm run build
log_success "Frontend built successfully"

# Step 5: Deploy frontend to nginx directory
log_info "Step 5: Deploying frontend files..."
sudo rm -rf $DEPLOY_DIR/*
sudo cp -r dist/* $DEPLOY_DIR/
sudo chown -R nginx:nginx $DEPLOY_DIR/
sudo chmod -R 755 $DEPLOY_DIR/
log_success "Frontend deployed to $DEPLOY_DIR"

# Step 6: Restart backend service
log_info "Step 6: Restarting backend service..."
sudo systemctl restart $SERVICE_NAME
sleep 3

# Step 7: Check service status
log_info "Step 7: Checking service status..."
if sudo systemctl is-active --quiet $SERVICE_NAME; then
    log_success "Backend service is running"
else
    log_error "Backend service failed to start"
    sudo systemctl status $SERVICE_NAME
    exit 1
fi

# Step 8: Reload nginx
log_info "Step 8: Reloading nginx..."
sudo nginx -t
if [ $? -eq 0 ]; then
    sudo systemctl reload nginx
    log_success "Nginx configuration is valid and reloaded"
else
    log_error "Nginx configuration test failed"
    exit 1
fi

# Step 9: Final health checks
log_info "Step 9: Performing health checks..."

# Check backend API
log_info "Checking backend API..."
if curl -s -f http://127.0.0.1:8000/api/docs > /dev/null; then
    log_success "Backend API is responding"
else
    log_warning "Backend API may not be responding properly"
fi

# Check frontend
log_info "Checking frontend..."
if curl -s -f https://news-check-app.mofu-mofu-application.com > /dev/null; then
    log_success "Frontend is responding"
else
    log_warning "Frontend may not be responding properly"
fi

# Step 10: Show service status
log_info "Step 10: Final service status..."
echo ""
log_info "PostgreSQL Status:"
sudo systemctl status postgresql --no-pager -l

echo ""
log_info "Redis Status:"
sudo systemctl status redis --no-pager -l

echo ""
log_info "Backend Service Status:"
sudo systemctl status $SERVICE_NAME --no-pager -l

echo ""
log_info "Nginx Status:"
sudo systemctl status nginx --no-pager -l

# Summary
echo ""
echo "=================================="
log_success "🎉 Deployment completed successfully!"
echo "=================================="
echo ""
log_info "Application URLs:"
echo "  Frontend: https://news-check-app.mofu-mofu-application.com"
echo "  Backend API Docs: https://news-check-app.mofu-mofu-application.com/api/docs"
echo ""
log_info "To view logs in real-time:"
echo "  Backend: sudo journalctl -u $SERVICE_NAME -f"
echo "  Nginx: sudo tail -f /var/log/nginx/news_check_app.error.log"
echo ""
log_info "Deployment completed at: $(date)"