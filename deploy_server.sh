#!/bin/bash
set -e

echo "=========================================================="
echo " Deploying AI Sales Platform to therealbonz.com/JsProject"
echo "=========================================================="

APP_DIR="/var/www/JsProject"
if [ "$EUID" -ne 0 ]; then
  SUDO="sudo"
else
  SUDO=""
fi

# 1. Install prerequisites if missing
$SUDO apt-get update -y
$SUDO apt-get install -y python3 python3-venv python3-pip git nginx

# 2. Setup project directory
$SUDO mkdir -p /var/www
if [ ! -d "$APP_DIR/.git" ]; then
    echo "Cloning repository..."
    $SUDO git clone https://github.com/therealbonz/JsProject.git "$APP_DIR"
else
    echo "Pulling latest code from GitHub..."
    cd "$APP_DIR"
    $SUDO git fetch origin main
    $SUDO git reset --hard origin/main
fi

$SUDO chown -R $USER:$USER "$APP_DIR" 2>/dev/null || true

# 3. Create virtual environment & install requirements
cd "$APP_DIR/backend"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# 4. Create Systemd Service
echo "Configuring systemd service..."
$SUDO bash -c "cat << 'EOF' > /etc/systemd/system/jsproject.service
[Unit]
Description=AI Sales Automation Platform (JsProject)
After=network.target

[Service]
Type=simple
User=bonz
WorkingDirectory=$APP_DIR/backend
ExecStart=$APP_DIR/backend/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5
Environment=PATH=$APP_DIR/backend/.venv/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
EOF"

$SUDO systemctl daemon-reload
$SUDO systemctl enable --now jsproject
$SUDO systemctl restart jsproject

# 5. Configure Nginx Subdirectory Location
echo "Configuring Nginx reverse proxy for /JsProject..."
NGINX_SNIPPET="/etc/nginx/conf.d/jsproject.conf"
if [ -d "/etc/nginx/conf.d" ]; then
    # Create or update location block in default site
    DEFAULT_SITE="/etc/nginx/sites-available/default"
    if [ -f "$DEFAULT_SITE" ]; then
        if ! grep -q "location /JsProject" "$DEFAULT_SITE"; then
            $SUDO sed -i '/server {/a \
    location /JsProject/ {\
        proxy_pass http://127.0.0.1:8000/JsProject/;\
        proxy_set_header Host $host;\
        proxy_set_header X-Real-IP $remote_addr;\
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\
        proxy_set_header X-Forwarded-Proto $scheme;\
    }\
    location = /JsProject {\
        return 301 /JsProject/;\
    }' "$DEFAULT_SITE"
        fi
    fi
fi

$SUDO nginx -t && $SUDO systemctl reload nginx

echo ""
echo "=========================================================="
echo " SUCCESS! Deployment completed."
echo " Open on your phone: http://therealbonz.com/JsProject"
echo "=========================================================="
