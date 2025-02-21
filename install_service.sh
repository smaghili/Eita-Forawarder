#!/bin/bash

# تنظیم رنگ‌ها برای خروجی
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# چک کردن دسترسی root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run as root (use sudo)${NC}"
    exit 1
fi

# مسیر فعلی پروژه
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# ایجاد فایل سرویس
cat > /etc/systemd/system/eitaa-forwarder.service << EOL
[Unit]
Description=Eitaa to Telegram Forwarder
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=${PROJECT_DIR}
ExecStart=/usr/bin/python3 ${PROJECT_DIR}/main.py
Restart=on-failure
RestartSec=60
LimitNPROC=50
LimitNOFILE=1024
MemoryMax=600M
TasksMax=100

[Install]
WantedBy=multi-user.target
EOL

# تنظیم دسترسی‌ها
chmod 644 /etc/systemd/system/eitaa-forwarder.service

# بارگذاری مجدد systemd
systemctl daemon-reload

# فعال‌سازی سرویس
systemctl enable eitaa-forwarder

# شروع سرویس
systemctl start eitaa-forwarder

# نمایش وضعیت
echo -e "\n${GREEN}Service installed and started!${NC}"
echo -e "\nYou can manage the service with these commands:"
echo -e "  ${GREEN}sudo systemctl status eitaa-forwarder${NC} - Check status"
echo -e "  ${GREEN}sudo systemctl stop eitaa-forwarder${NC}   - Stop service"
echo -e "  ${GREEN}sudo systemctl start eitaa-forwarder${NC}  - Start service"
echo -e "  ${GREEN}sudo systemctl restart eitaa-forwarder${NC} - Restart service"
echo -e "  ${GREEN}journalctl -u eitaa-forwarder${NC}        - View logs"