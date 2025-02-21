import os
import json
import time
from playwright.sync_api import sync_playwright

class EitaaLogin:
    def __init__(self, config, show_browser=False, info_logger=None, error_logger=None):
        self.config = config
        self.show_browser = show_browser
        self.info_logger = info_logger
        self.error_logger = error_logger
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.error_count = 0
        self.error_count_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            'config', 
            'error_count.json'
        )
        self._load_error_count()

    def initialize(self):
        """Initialize browser"""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=not self.show_browser,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu'
            ]
        )
        
        # چک کردن وجود فایل auth
        base_dir = os.path.dirname(os.path.dirname(__file__))
        session_file = os.path.join(base_dir, 'config', self.config['paths']['session_file'])
        
        # ساخت context با storage_state اگر وجود داشت
        if os.path.exists(session_file):
            self.context = self.browser.new_context(
                storage_state=session_file,
                viewport={'width': 1920, 'height': 1080}
            )
        else:
            self.context = self.browser.new_context(
                viewport={'width': 1920, 'height': 1080}
            )
        
        self.page = self.context.new_page()
        self.page.goto('https://web.eitaa.com/')
        
        # تنظیم localStorage برای افزایش مدت سشن
        self.page.evaluate("""() => {
            localStorage.setItem('sessionDuration', '31536000000');  // یک سال
            localStorage.setItem('keepLoggedIn', 'true');
            localStorage.setItem('rememberMe', 'true');
            localStorage.setItem('persistSession', 'true');
            sessionStorage.setItem('sessionPersist', 'true');
        }""")

    def login(self):
        """Handle login process"""
        try:
            base_dir = os.path.dirname(os.path.dirname(__file__))
            session_file = os.path.join(base_dir, 'config', self.config['paths']['session_file'])
            
            if os.path.exists(session_file) and os.path.getsize(session_file) > 0:
                self.info_logger.info(f"Found existing auth file at: {session_file}")
                result = self._load_session(session_file)
                if result:
                    return True
                else:
                    self.error_logger.warning("Existing session is invalid, need to login again")
            
            return self._new_login(session_file)
            
        except Exception as e:
            self.error_logger.error(f"Login error: {e}")
            return False

    def _load_session(self, session_file):
        """Load existing session"""
        try:
            self.info_logger.info("Loading saved session...")
            self.context.storage_state(path=session_file)
            self.page.goto('https://web.eitaa.com/')
            time.sleep(2)
            
            if self.is_logged_in():
                return True
            return False
            
        except Exception as e:
            self.error_logger.error(f"Error loading session: {e}")
            return False

    def _new_login(self, session_file):
        """Handle new login"""
        self.info_logger.info("Starting new login process...")
        
        if self.show_browser:
            self.info_logger.info("Please login manually...")
            input("After login, press Enter to continue...")
            self.context.storage_state(path=session_file)
            return self.is_logged_in()
        else:
            return self._handle_headless_login(session_file)

    def _handle_headless_login(self, session_file):
        """Handle headless login process"""
        try:
            # استفاده از صفحه موجود
            self.page.goto('https://web.eitaa.com/')
            time.sleep(2)

            # Wait for phone input field
            phone_input_selector = '.input-field-input[data-left-pattern=" ‒‒‒ ‒‒‒ ‒‒‒‒"]'
            self.page.wait_for_selector(phone_input_selector, timeout=10000)
            
            # Get phone number
            while True:
                phone = input("\nEnter phone number (+98xxxxxxxxxx): ")
                if phone.startswith('+') and len(phone) >= 12:
                    break
                print("Invalid format. Include country code (+98)")

            # Enter phone number
            self.page.fill(phone_input_selector, phone.strip())
            self.page.click('button.btn-primary span.i18n')
            
            # Get verification code
            code_input = 'input[type="tel"].input-field-input'
            self.page.wait_for_selector(code_input, timeout=10000)
            
            while True:
                code = input("\nEnter verification code: ")
                if code.isdigit() and len(code) >= 4:
                    break
                print("Invalid code format")

            # Enter verification code
            self.page.fill(code_input, code)
            time.sleep(5)

            # Handle password if needed
            try:
                pwd_input = 'input[type="password"].input-field-input'
                pwd_field = self.page.wait_for_selector(pwd_input, timeout=5000)
                if pwd_field:
                    pwd = input("\nEnter Eitaa password: ")
                    self.page.fill(pwd_input, pwd)
                    self.page.click('button.btn-primary')
                    time.sleep(5)
            except:
                pass

            if self.is_logged_in():
                self.context.storage_state(path=session_file)
                return True
            return False

        except Exception as e:
            self.error_logger.error(f"Headless login error: {e}")
            return False

    def is_logged_in(self):
        """Check login status"""
        try:
            self.info_logger.info("Checking login status...")
            
            # چک کردن صفحه لاگین
            login_page = self.page.query_selector('.tabs-tab.page-sign.active')
            if login_page:
                self.error_logger.warning("❌ Login page detected - Not logged in")
                return False
            
            # چک کردن وجود sidebar
            sidebar = self.page.query_selector(
                '.tabs-tab.chatlist-container.sidebar.sidebar-left.main-column'
            )
            
            if sidebar:
                self.info_logger.info("[OK] Successfully logged in - Main sidebar detected")
                return True
            
            # اگر هیچکدام از حالت‌های بالا نبود
            self.info_logger.warning("⚠️ Could not determine login status")
            
            # اضافه کردن اطلاعات بیشتر برای دیباگ
            current_url = self.page.url
            self.info_logger.info(f"Current URL: {current_url}")
            
            # گرفتن اسکرین‌شات برای دیباگ
            self.page.screenshot(path='debug_screenshot.png')
            self.info_logger.info("Debug screenshot saved as 'debug_screenshot.png'")
            
            return False
            
        except Exception as e:
            self.error_logger.error(f"❌ Error checking login status: {e}")
            return False

    def close(self):
        """Close browser and cleanup"""
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            self.error_logger.error(f"Error during cleanup: {e}")

    def _load_error_count(self):
        """Load error count from file"""
        try:
            if os.path.exists(self.error_count_file):
                with open(self.error_count_file, 'r') as f:
                    data = json.load(f)
                    self.error_count = data.get('error_count', 0)
        except Exception as e:
            self.error_logger.error(f"Error loading error count: {e}")

    def _save_error_count(self):
        """Save error count to file"""
        try:
            with open(self.error_count_file, 'w') as f:
                json.dump({'error_count': self.error_count}, f)
        except Exception as e:
            self.error_logger.error(f"Error saving error count: {e}")

    def process_messages(self, message_processor, channel_id, last_message_id=None, telegram_targets=None):
        """Process messages from channel"""
        try:
            # تغییر مسیر ذخیره عکس‌ها به پوشه config
            base_dir = os.path.dirname(os.path.dirname(__file__))
            images_dir = os.path.join(base_dir, 'config', self.config['paths']['images_dir'])
            if not os.path.exists(images_dir):
                os.makedirs(images_dir)
            
            # Add download event listener
            current_message_text = None
            
            def handle_download(download):
                file_path = os.path.join(images_dir, download.suggested_filename)
                self.info_logger.info(f"Starting download of file: {download.suggested_filename}")
                self.info_logger.info(f"Saving to path: {file_path}")
                download.save_as(file_path)
                self.info_logger.info(f"File downloaded successfully to: {file_path}")
                
                # ارسال فوری به تلگرام با تارگت‌های مشخص شده
                if current_message_text:
                    message_processor.telegram_handler.queue_message(current_message_text, file_path, telegram_targets)
                    self.info_logger.info(f"Message and image queued for Telegram: {file_path}")
            
            self.page.on("download", handle_download)

            # صبر برای لود شدن کامل صفحه
            self.page.wait_for_load_state('networkidle')
            self.page.wait_for_selector('.chatlist-container', timeout=30000)  # 30 ثانیه صبر برای لود لیست چت‌ها
            time.sleep(5)  # افزایش از 2 به 5 ثانیه برای اطمینان از لود کامل

            # Click on the channel
            channel_selector = f'li.chatlist-chat[data-peer-id="{channel_id}"]'
            channel = self.page.query_selector(channel_selector)
            
            if not channel:
                # بلافاصله چک می‌کنیم آیا لاگ‌اوت شده
                if self.page.query_selector('.tabs-tab.page-sign.active'):
                    error_msg = (
                        "⚠️ خطای دسترسی به ایتا\n\n"
                        "❌ سشن معتبر نیست\n"
                        "🔑 نیاز به لاگین مجدد"
                    )
                    message_processor.telegram_handler.queue_message(error_msg)
                    # پاک کردن فایل auth.json
                    session_file = os.path.join(base_dir, 'config', self.config['paths']['session_file'])
                    if os.path.exists(session_file):
                        os.remove(session_file)
                        self.info_logger.info("Removed expired auth file")
                    # برنامه باید بسته شود
                    raise Exception("Session expired, login required")
                else:
                    # کانال پیدا نشده ولی لاگ‌اوت نیستیم
                    error_msg = f"⚠️ کانال {channel_id} پیدا نشد\n\nکانال غیرفعال شد."
                    message_processor.telegram_handler.queue_message(error_msg)
                    # تغییر وضعیت کانال به disabled
                    for ch in self.config['eitaa']['channels']:
                        if ch['id'] == channel_id:
                            ch['status'] = 'disabled'
                            break
                    # ذخیره تغییرات در کانفیگ
                    config_path = os.path.join(base_dir, 'config', 'config.json')
                    with open(config_path, 'w', encoding='utf-8') as f:
                        json.dump(self.config, f, indent=4, ensure_ascii=False)
                    return None
            
            else:
                channel.click()
                
            time.sleep(5)  # افزایش از 2 به 5 ثانیه برای لود کامل پیام‌ها
            
            # Get messages
            messages = self.page.query_selector_all('div.bubble')
            if not messages:
                return last_message_id
            
            # Get the newest message ID
            newest_id = None
            valid_messages = []
            
            for message in messages:
                try:
                    msg_id = message.get_attribute('data-mid')
                    if msg_id:  # Check if msg_id is not None
                        msg_id = int(msg_id)
                        if newest_id is None or msg_id > newest_id:
                            newest_id = msg_id
                        valid_messages.append(message)
                except:
                    continue
            
            if newest_id is None:
                return last_message_id
            
            # If we have a last message ID, only process newer messages
            if last_message_id and last_message_id.isdigit():
                last_id = int(last_message_id)
                messages = []
                for m in valid_messages:
                    try:
                        current_id = int(m.get_attribute('data-mid'))
                        if current_id > last_id:
                            messages.append(m)
                            self.info_logger.info(f"Found new message with ID: {current_id}")
                    except:
                        continue
            else:
                messages = valid_messages
                self.info_logger.info("Processing all messages (no last message ID found)")
            
            if not messages:
                self.info_logger.info(f"No new messages found (all message IDs are <= {last_message_id})")
                return str(newest_id)
            
            self.info_logger.info(f"Processing {len(messages)} new messages")
            
            for message in messages:
                try:
                    msg_id = message.get_attribute('data-mid')
                    
                    # Get message text
                    text_element = message.query_selector('div.message')
                    if text_element:
                        full_text = text_element.inner_text()
                        lines = full_text.splitlines()
                        lines = [line for line in lines if line.strip()]
                        
                        # جدا کردن sender و time قبل از پردازش متن
                        sender = ""
                        time_sent = ""
                        
                        for line in reversed(lines):
                            line = line.strip()
                            if not time_sent and ("بعدازظهر" in line or "قبل‌ازظهر" in line):
                                time_sent = line
                            elif not sender and line and not any(x in line for x in ["بعدازظهر", "قبل‌ازظهر"]):
                                sender = line.rstrip(',').strip()
                        
                        # جدا کردن عدد ویو از آخر متن
                        views_count = None
                        remaining_lines = []
                        for line in lines:
                            if line != sender and line != time_sent:
                                if line.strip().isdigit() and not views_count:
                                    views_count = line.strip()
                                elif not line.strip().endswith(','):
                                    remaining_lines.append(line)
                        
                        # ساخت متن اصلی پیام
                        message_text = '\n'.join(remaining_lines)
                        
                        # Format message
                        current_message_text = f"Message from Eitaa:\n\n"
                        current_message_text += f"Sender: {sender}\n"
                        current_message_text += f"Time: {time_sent}\n"
                        current_message_text += f"Text:\n{message_text}"
                        if views_count:
                            current_message_text += f"\nViews: {views_count}"
                    
                    # Process image if exists
                    media_container = message.query_selector('div.media-container')
                    if media_container:
                        try:
                            media_container.click()
                            self.info_logger.info(f"Opening image in message: {msg_id}")
                            
                            download_button = self.page.wait_for_selector('.btn-icon.tgico-download', timeout=5000)
                            if download_button:
                                self.info_logger.info(f"Found download button for message: {msg_id}")
                                download_button.click()
                                time.sleep(1)  # Wait for download
                            
                            self.page.keyboard.press('Escape')
                            time.sleep(0.5)
                            
                        except Exception as img_error:
                            self.error_logger.error(f"Error with image in message {msg_id}: {str(img_error)}")
                            try:
                                self.page.keyboard.press('Escape')
                            except:
                                pass
                            # اگر عکس با خطا مواجه شد، فقط متن را ارسال می‌کنیم
                            if current_message_text:
                                message_processor.telegram_handler.queue_message(current_message_text)
                    else:
                        # اگر پیام عکس ندارد، فقط متن را ارسال می‌کنیم
                        if current_message_text:
                            message_processor.telegram_handler.queue_message(current_message_text)
                    
                except Exception as e:
                    self.error_logger.error(f"Error processing message: {str(e)}")
                    continue
            
            # اگر موفق بود، شمارنده صفر میشه
            self.error_count = 0
            self._save_error_count()
            
            return str(newest_id)
            
        except Exception as e:
            error_str = str(e)
            self.error_count += 1
            self._save_error_count()
            
            max_errors = self.config['eitaa']['error_handling']['max_errors']
            
            # فقط اگر به حداکثر خطا رسید پیام ارسال کند
            if self.error_count >= max_errors:
                error_msg = (
                    "⛔️ خطای سیستمی ایتا\n\n"
                    f"❌ {error_str}\n\n"
                    f"🔢 تعداد خطا به حداکثر رسید: {max_errors} بار\n\n"
                    "🔍 جزئیات خطا:\n"
                    "🔹 قطع ارتباط با سرور ایتا\n"
                    "🔸 مشکل در دسترسی به کانال\n"
                    "🔹 خطای احراز هویت\n\n"
                    "⚠️ کرونجاب غیرفعال شد\n"
                    "📋 برای راه‌اندازی مجدد با پشتیبانی تماس بگیرید"
                )
                
                message_processor.telegram_handler.queue_message(error_msg)
                self.error_logger.error(f"Max errors reached ({max_errors}). Last error: {e}")
                
                time.sleep(5)  # صبر برای ارسال پیام
                return last_message_id
                
            else:
                # فقط لاگ خطا، بدون ارسال پیام
                self.error_logger.error(f"Error {self.error_count} of {max_errors}: {e}")
            
            return last_message_id

    def _save_cookies(self):
        """Save cookies after successful login"""
        cookies = self.context.cookies()
        base_dir = os.path.dirname(os.path.dirname(__file__))
        cookies_file = os.path.join(base_dir, 'config', 'cookies.json')
        with open(cookies_file, 'w') as f:
            json.dump(cookies, f)

    def _load_cookies(self):
        """Load saved cookies"""
        base_dir = os.path.dirname(os.path.dirname(__file__))
        cookies_file = os.path.join(base_dir, 'config', 'cookies.json')
        if os.path.exists(cookies_file):
            with open(cookies_file, 'r') as f:
                cookies = json.load(f)
            self.context.add_cookies(cookies) 