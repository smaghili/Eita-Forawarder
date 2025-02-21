import os
import json
import sys
import time
import subprocess
from dotenv import load_dotenv
from src.telegram_handler import TelegramHandler
from src.eitaa_login import EitaaLogin
from src.message_processor import MessageProcessor
from src.logger import setup_logger

def parse_arguments():
    """Parse command line arguments"""
    args = {
        'no_send': "-nosend" in sys.argv,
        'show_browser': "-page" in sys.argv,
        'clear_session': "-clear" in sys.argv,
        'one_time': "-once" in sys.argv,
        'telegram_targets': None
    }

    # Parse -send argument
    for i, arg in enumerate(sys.argv):
        if arg == "-send":
            try:
                if i + 1 < len(sys.argv):
                    targets_str = sys.argv[i + 1]
                    if ',' in targets_str:
                        args['telegram_targets'] = [int(t.strip()) for t in targets_str.split(',')]
                    else:
                        args['telegram_targets'] = [int(targets_str)]
                    print(f"Will send messages to: {args['telegram_targets']}")
                else:
                    print("Error: No target ID provided after -send")
                    sys.exit(1)
            except Exception as e:
                print(f"Error parsing telegram targets: {e}")
                print("Use format: -send id1,id2,id3")
                sys.exit(1)

    return args

def run_scraper(config, args, info_logger, error_logger, base_dir):
    """Run the scraper"""
    telegram_handler = None
    eitaa_login = None
    
    try:
        telegram_handler = TelegramHandler(config, args['telegram_targets'], info_logger, error_logger)
        eitaa_login = EitaaLogin(config, args['show_browser'], info_logger, error_logger)
        message_processor = MessageProcessor(config, telegram_handler, info_logger, error_logger)

        # Initialize components
        info_logger.info("Initializing components...")
        eitaa_login.initialize()
        telegram_handler.connect()

        # Login to Eitaa
        if not eitaa_login.login():
            error_logger.error("Failed to login to Eitaa")
            return False

        channels = config['eitaa']['channels']  # لیست کانال‌ها از کانفیگ
        last_check_time = time.time()
        channel_last_messages = {}  # ذخیره آخرین پیام هر کانال
        
        # بارگذاری آخرین پیام‌های ذخیره شده برای هر کانال
        for channel in channels:
            channel_id = channel['id']
            last_message_id = message_processor.load_last_message_id(channel_id)
            channel_last_messages[channel_id] = last_message_id
            if last_message_id:
                info_logger.info(f"Channel {channel_id}: Resuming from message ID: {last_message_id}")
            else:
                info_logger.info(f"Channel {channel_id}: Starting fresh")

        # Main processing loop
        while True:
            try:
                # چک کردن لاگین بر اساس زمان تنظیم شده در کانفیگ
                current_time = time.time()
                login_check_interval = config['eitaa'].get('login_check_interval', 300)  # پیش‌فرض 300 ثانیه (5 دقیقه)
                if current_time - last_check_time > login_check_interval:
                    if not eitaa_login.is_logged_in():
                        info_logger.warning("Session expired, trying to login again...")
                        if not eitaa_login.login():
                            raise Exception("Failed to re-login")
                    last_check_time = current_time

                # پردازش همه کانال‌ها
                for channel in channels:
                    channel_id = channel['id']
                    channel_name = channel.get('name', str(channel_id))
                    channel_status = channel.get('status', 'active')
                    
                    if channel_status != 'active':
                        info_logger.info(f"Skipping channel {channel_name} (status: {channel_status})")
                        continue
                    
                    info_logger.info(f"Checking channel: {channel_name}")
                    
                    try:
                        telegram_targets = channel.get('telegram_targets', config['telegram']['default_targets'])
                        current_id = eitaa_login.process_messages(
                            message_processor,
                            channel_id,
                            channel_last_messages[channel_id],
                            telegram_targets
                        )
                        
                        if current_id != channel_last_messages[channel_id]:
                            info_logger.info(f"Channel {channel_name}: Updated last message ID: {current_id}")
                            message_processor.save_last_message_id(channel_id, current_id)
                            channel_last_messages[channel_id] = current_id
                            
                    except Exception as e:
                        error_logger.error(f"Error processing channel {channel_name}: {e}")
                        # اطلاع‌رسانی به ادمین
                        error_msg = f"⚠️ خطا در کانال {channel_name}:\n{str(e)}\n\nکانال غیرفعال شد."
                        message_processor.telegram_handler.queue_message(error_msg)
                        # تغییر وضعیت کانال به error
                        channel['status'] = 'error'
                        # ذخیره تغییرات در فایل کانفیگ
                        save_config(config, config_path)

                # منتظر خالی شدن صف پیام‌ها
                while not telegram_handler.message_queue.empty():
                    info_logger.info("Waiting for messages to be sent...")
                    time.sleep(0.5)

                if args['one_time']:
                    info_logger.info("One-time check completed")
                    return True
                    
                # تاخیر بین چک‌ها
                check_interval = config['eitaa'].get('check_interval', 60)  # پیش‌فرض 60 ثانیه (1 دقیقه)
                time.sleep(check_interval)

            except KeyboardInterrupt:
                info_logger.info("Received keyboard interrupt, cleaning up...")
                return True
            except Exception as e:
                error_logger.error(f"Error in main loop: {e}")
                time.sleep(60)  # در صورت خطا، یک دقیقه صبر می‌کند

    except Exception as e:
        error_logger.error(f"Scraper error: {e}")
        return False
    finally:
        info_logger.info("Cleanup started...")
        if telegram_handler:
            telegram_handler._running = False
        if eitaa_login:
            eitaa_login.close()

def initialize_json_file(file_path, default_content=None):
    """Initialize JSON file with default content if empty or invalid"""
    if default_content is None:
        default_content = {}
        
    try:
        if not os.path.exists(file_path):
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(default_content, f, indent=4)
            return True
            
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:  # فایل خالی است
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(default_content, f, indent=4)
                return True
            json.loads(content)  # تست اعتبار JSON
            return True
    except json.JSONDecodeError:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(default_content, f, indent=4)
        return True
    except Exception as e:
        print(f"Error initializing {file_path}: {e}")
        return False

def check_required_files(base_dir, is_page_mode=False):
    """Check if all required JSON files exist and are valid"""
    required_files = {
        'config/config.json': "Config file is not valid",
        'config/auth.json': "Session is not valid. Please run with -page flag to login",
        'config/last_message.json': "Last message file is not valid"
    }

    for file_path, error_msg in required_files.items():
        full_path = os.path.join(base_dir, file_path)
        
        # در حالت page- فایل auth.json را چک نمی‌کنیم
        if 'auth.json' in file_path and is_page_mode:
            initialize_json_file(full_path)
            continue
            
        # اگر فایل کانفیگ است و مشکل دارد، خطا بدهد
        if 'config.json' in file_path:
            if not os.path.exists(full_path):
                print(f"Error: {error_msg}")
                sys.exit(1)
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    json.load(f)
            except:
                print(f"Error: {error_msg}")
                sys.exit(1)
        else:
            # برای بقیه فایل‌ها، اگر مشکل دارند initialize کن
            initialize_json_file(full_path)

def write_pid():
    """Write PID file"""
    pid_dir = "/run/eitaa-forwarder"
    if not os.path.exists(pid_dir):
        os.makedirs(pid_dir, exist_ok=True)
    with open(os.path.join(pid_dir, "service.pid"), "w") as f:
        f.write(str(os.getpid()))

def main():
    """Main entry point"""
    try:
        write_pid()  # اضافه کردن این خط
        base_dir = os.path.dirname(os.path.abspath(__file__))
        args = parse_arguments()
        
        # چک کردن فایل‌ها با توجه به حالت اجرا
        check_required_files(base_dir, args['show_browser'])
        
        config_path = os.path.join(base_dir, 'config', 'config.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # Setup loggers
        info_logger, error_logger = setup_logger(base_dir)
        
        info_logger.info("Starting scraper...")
        success = run_scraper(config, args, info_logger, error_logger, base_dir)
        
        if success:
            info_logger.info("Scraper finished successfully")
            sys.exit(0)
        else:
            info_logger.error("Scraper failed")
            sys.exit(1)

    except KeyboardInterrupt:
        if error_logger:
            error_logger.warning("Scraper stopped by user")
        sys.exit(0)
    except Exception as e:
        if error_logger:
            error_logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 
