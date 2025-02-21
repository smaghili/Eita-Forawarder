#!/bin/bash

# تنظیم رنگ‌ها
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# چک کردن دسترسی root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run as root (use sudo)${NC}"
    exit 1
fi

echo -e "${BLUE}Starting installation...${NC}"

# آپدیت سیستم
echo -e "${GREEN}Updating system packages...${NC}"
apt update && apt upgrade -y

# نصب پیش‌نیازها
echo -e "${GREEN}Installing prerequisites...${NC}"
apt install -y python3 python3-pip wget curl git software-properties-common

# نصب pip اگر نصب نبود
if ! command -v pip3 &> /dev/null; then
    echo -e "${GREEN}Installing pip3...${NC}"
    apt install -y python3-pip
fi

# نصب پکیج‌های پایتون
echo -e "${GREEN}Installing Python packages...${NC}"
pip3 install --upgrade pip
pip3 install telethon python-dotenv playwright asyncio

# نصب Playwright و مرورگرها
echo -e "${GREEN}Installing Playwright and browsers...${NC}"
playwright install
playwright install-deps

# ساخت پوشه‌های مورد نیاز
echo -e "${GREEN}Creating required directories...${NC}"
mkdir -p config
mkdir -p logs
mkdir -p config/channel_images

# تنظیم دسترسی‌ها
echo -e "${GREEN}Setting up permissions...${NC}"
chmod +x install_service.sh
chmod +x main.py
chmod -R 755 .
chmod -R 700 config

# لاگین اولیه
echo -e "${BLUE}Starting initial login process...${NC}"
echo -e "${GREEN}Please complete Telegram and Eitaa login...${NC}"
python3 main.py -onlylogin

# چک کردن وجود فایل‌های auth
if [ ! -f "config/auth.json" ]; then
    echo -e "${RED}Login failed! Please run 'python3 main.py -onlylogin' manually and try again${NC}"
    exit 1
fi

# نصب سرویس
echo -e "${GREEN}Installing systemd service...${NC}"
./install_service.sh

echo -e "${BLUE}Installation completed!${NC}"
echo -e "\nYou can now:"
echo -e "1. Edit ${GREEN}config/config.json${NC} with your settings"
echo -e "2. Run ${GREEN}python3 main.py -onlylogin${NC} to setup initial login"
echo -e "3. Start the service with ${GREEN}sudo systemctl start eitaa-forwarder${NC}"
echo -e "\nTo check service status:"
echo -e "${GREEN}sudo systemctl status eitaa-forwarder${NC}" 