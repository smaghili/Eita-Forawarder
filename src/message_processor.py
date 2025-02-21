import os
import json
import time

class MessageProcessor:
    def __init__(self, config, telegram_handler, info_logger=None, error_logger=None):
        self.config = config
        self.telegram_handler = telegram_handler
        self.info_logger = info_logger
        self.error_logger = error_logger
        self.current_message_text = None
        
        # ساخت مسیر کامل برای last_message.json در پوشه config
        base_dir = os.path.dirname(os.path.dirname(__file__))
        self.last_message_file = os.path.join(base_dir, 'config', self.config['paths']['last_message_file'])

    def process_message(self, message):
        """Process a single message"""
        try:
            msg_id = message.get_attribute('data-mid')
            text = self._extract_text(message)
            
            # Get message text first
            if text:
                self.current_message_text = self._format_message(text)
            
            # Then process media if exists
            media_container = message.query_selector('div.media-container')
            if media_container:
                try:
                    media_container.click()
                    print(f"Opening image in message: {msg_id}")
                    
                    download_button = message.page.wait_for_selector('.btn-icon.tgico-download', timeout=5000)
                    if download_button:
                        print(f"Found download button for message: {msg_id}")
                        download_button.click()
                        time.sleep(1)  # Wait for download
                    
                    message.page.keyboard.press('Escape')
                    time.sleep(0.5)
                    
                except Exception as img_error:
                    print(f"Error with image in message {msg_id}: {str(img_error)}")
                    try:
                        message.page.keyboard.press('Escape')
                    except:
                        pass
                    # اگر عکس با خطا مواجه شد، فقط متن را ارسال می‌کنیم
                    if self.current_message_text:
                        self.telegram_handler.queue_message(self.current_message_text)
            else:
                # اگر پیام عکس ندارد، فقط متن را ارسال می‌کنیم
                if self.current_message_text:
                    self.telegram_handler.queue_message(self.current_message_text)
            
            return msg_id, text
            
        except Exception as e:
            print(f"Error processing message: {e}")
            return None, None

    def _extract_text(self, message):
        """Extract text from message"""
        text_element = message.query_selector('div.message')
        if not text_element:
            return None

        full_text = text_element.inner_text()
        lines = [line.strip() for line in full_text.splitlines() if line.strip()]
        
        # Extract components
        sender = ""
        time_sent = ""
        views_count = None
        content_lines = []

        for line in reversed(lines):
            if not time_sent and ("بعدازظهر" in line or "قبل‌ازظهر" in line):
                time_sent = line
            elif not sender and line and not any(x in line for x in ["بعدازظهر", "قبل‌ازظهر"]):
                sender = line.rstrip(',')

        for line in lines:
            if line != sender and line != time_sent:
                if line.strip().isdigit() and not views_count:
                    views_count = line
                elif not line.strip().endswith(','):
                    content_lines.append(line)

        return {
            'sender': sender,
            'time': time_sent,
            'views': views_count,
            'content': '\n'.join(content_lines)
        }

    def _process_media(self, message):
        """Process media in message"""
        media_container = message.query_selector('div.media-container')
        if not media_container:
            return None

        try:
            # Get page from message
            page = message.page
            
            # Add download event listener
            file_path = [None]  # برای ذخیره مسیر فایل
            
            def handle_download(download):
                path = os.path.join('channel_images', download.suggested_filename)
                print(f"Starting download: {download.suggested_filename}")
                download.save_as(path)
                file_path[0] = path
                print(f"File downloaded to: {path}")
                
            # اضافه کردن event listener به page اصلی
            page.context.pages[0].on("download", handle_download)
            
            try:
                media_container.click()
                download_button = page.wait_for_selector('.btn-icon.tgico-download', timeout=5000)
                if download_button:
                    download_button.click()
                    time.sleep(2)  # Wait for download
                    
                    if file_path[0] and os.path.exists(file_path[0]):
                        return file_path[0]
                
                page.keyboard.press('Escape')
                
            except Exception as e:
                print(f"Error in media download: {e}")
                try:
                    page.keyboard.press('Escape')
                except:
                    pass
                
            finally:
                # Remove the event listener
                page.context.pages[0].remove_listener("download", handle_download)
                
            return None
            
        except Exception as e:
            print(f"Error processing media: {e}")
            try:
                message.page.keyboard.press('Escape')
            except:
                pass
            return None

    def _format_message(self, text_data):
        """Format message for sending"""
        if not text_data:
            return None

        message = "Message from Eitaa:\n\n"
        if text_data['sender']:
            message += f"Sender: {text_data['sender']}\n"
        if text_data['time']:
            message += f"Time: {text_data['time']}\n"
        if text_data['content']:
            message += f"Text:\n{text_data['content']}"
        if text_data['views']:
            message += f"\nViews: {text_data['views']}"
        
        return message

    def save_last_message_id(self, channel_id, message_id):
        """Save last message ID"""
        try:
            data = {}
            os.makedirs(os.path.dirname(self.last_message_file), exist_ok=True)
            
            if os.path.exists(self.last_message_file):
                try:
                    with open(self.last_message_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except json.JSONDecodeError:
                    self.error_logger.warning("Invalid JSON file, creating new one...")
                    data = {}
            
            data[channel_id] = message_id
            
            with open(self.last_message_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            
        except Exception as e:
            self.error_logger.error(f"Error saving last message ID: {e}")

    def load_last_message_id(self, channel_id):
        """Load last message ID"""
        try:
            os.makedirs(os.path.dirname(self.last_message_file), exist_ok=True)
            
            if os.path.exists(self.last_message_file):
                try:
                    with open(self.last_message_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        return data.get(channel_id)
                except json.JSONDecodeError:
                    self.error_logger.warning("Invalid JSON file, creating new one...")
                    with open(self.last_message_file, 'w', encoding='utf-8') as f:
                        json.dump({}, f, indent=4)
            else:
                self.info_logger.info("Creating new last_message.json file...")
                with open(self.last_message_file, 'w', encoding='utf-8') as f:
                    json.dump({}, f, indent=4)
                
        except Exception as e:
            self.error_logger.error(f"Error loading last message ID: {e}")
        return None 